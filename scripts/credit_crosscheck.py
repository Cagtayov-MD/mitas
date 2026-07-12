#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
credit_crosscheck.py — Idea 2: okunan künyeyi BİRİNCİ-SINIF iki otoriteyle çapraz-doğrula.

KAYNAKLAR (ikisi de kalıcı/direkt — "arada kaynamasın"):
  • WIKIDATA  : X:\DIGER\Mitas_Files\MitaData\mitas.duckdb  (works_master: label_tr/director/cast_member/imdb_id; qid_labels)
  • IMDb      : Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb     (titles/akas/crew/principals/names)

İLKELER:
  • Kimlik = Türkçe başlık (label_tr / akas) ÖNCE; sonra orijinal-ad+yıl; çoklu adayda CAST örtüşmesiyle kesinleştir.
    KATALOG NUMARASI/yıl BAZ DEĞİL (2014-9073=ekleme yılı tuzağı).
  • Otoriter yönetmen/cast'i çek, OKUNANLA karşılaştır → TEYİT / ÇELİŞKİ / KAYNAK_YOK.
  • ASLA DÜZELTME YOK — sadece raporlar (Wikidata/IMDb ~%90; içerik nihai hakem).

CLI:  python scripts/credit_crosscheck.py --baslik "AHLAT AĞACI" --yonetmen "Nuri Bilge Ceylan" --yil 2018
"""
import argparse, os, re, sys, unicodedata
from name_fold import latin_ascii

WIKIDATA_DB = os.environ.get("MITAS_WIKIDATA_DUCKDB", r"X:\DIGER\Mitas_Files\MitaData\mitas.duckdb")
IMDB_DB = os.environ.get("MITAS_IMDB_DUCKDB", r"Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb")

def fold(s):
    s = (s or "")
    for a, b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
                 ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s = s.replace(a, b)
    s = latin_ascii(s)
    return re.sub(r"[^a-z0-9 ]", " ", s).strip()

_TR = (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
       ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c"))
def _tfold(s):
    """Türkçe-duyarlı katlama (ı→i, ğ→g…) — strip_accents'in ı tuzağını çözer."""
    s = (s or "")
    for a, b in _TR:
        s = s.replace(a, b)
    return s.lower().strip()
def _sqlfold(col):
    """col için SQL Türkçe-fold ifadesi (REPLACE zinciri + lower) — _tfold ile eşleşir."""
    e = col
    for a, b in _TR:
        e = f"replace({e},'{a}','{b}')"
    return f"lower({e})"

def _castfold(s):
    """isim eşleştirme: aksan-sız + küçük + alnum-tek-boşluk.
    SQL `trim(regexp_replace(lower(strip_accents(primaryName)),'[^a-z0-9]+',' ','g'))` ile EŞLEŞİR."""
    s = unicodedata.normalize("NFKD", (s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def name_match(a, b):
    """iki isim aynı kişi mi — SIKI token eşitliği (substring DEĞİL).

    KÖK SEBEP düzeltmesi: eski gevşek `t in fb` (substring) "Scott Paulin"~"Pauline Chan"
    ve "Kavi Raz"~"Micaella Raz" gibi YANLIŞ eşleşmeler üretiyordu (paulin⊂pauline,
    raz⊂micaella değil ama tek-token kesişimi yetiyordu). Artık:
      • karşılaştırma token-EŞİTLİĞİ üzerinden (substring yok),
      • 2+ kelimelik adlarda İLK ve SON anlamlı token DA eşit olmalı (tam ad güvencesi),
      • tek anlamlı tokenlı adlarda o token birebir eşit olmalı.
    """
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return False
    ta = [t for t in fa.split() if len(t) > 2]
    tb = [t for t in fb.split() if len(t) > 2]
    if not ta or not tb:
        return False
    sb = set(tb)
    # tek anlamlı token: birebir eşitlik (substring değil)
    if len(ta) == 1:
        return ta[0] in sb
    # 2+ token: İLK + SON anlamlı token eşitlik ŞART (ad+soyad çapası)
    if ta[0] not in sb or ta[-1] not in sb:
        return False
    # ek güvence: tokenların çoğu (n-1) birebir eşleşsin
    hit = sum(1 for t in ta if t in sb)
    return hit >= max(2, len(ta) - 1)

def _lev(a, b, cap=3):
    """küçük Levenshtein (cap'lı) — OCR tek-harf misread'i ölçer."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > cap:
        return cap + 1
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (0 if a[i - 1] == b[j - 1] else 1))
        prev = cur
    return prev[lb]

def _name_tokens_strict(s):
    toks = [t for t in fold(s).split() if t]
    if len(toks) < 2:
        return []
    if not any(len(t) >= 3 for t in toks):
        return []
    return toks

def strict_name_close(a, b, max_edits=1):
    """Global kişi kapısı için dar fuzzy: tek kelime yok, token sırası aynı, toplam 1 harf."""
    ta, tb = _name_tokens_strict(a), _name_tokens_strict(b)
    if not ta or not tb or len(ta) != len(tb):
        return False
    total = 0
    for x, y in zip(ta, tb):
        if not x or not y or x[0] != y[0]:
            return False
        if len(x) == 1 or len(y) == 1:
            if x != y:
                return False
            continue
        d = _lev(x, y, max_edits)
        if d > 1:
            return False
        total += d
        if total > max_edits:
            return False
    return True

def strict_name_distance(a, b, max_edits=1):
    if not strict_name_close(a, b, max_edits=max_edits):
        return max_edits + 1
    return sum(_lev(x, y, max_edits) for x, y in zip(_name_tokens_strict(a), _name_tokens_strict(b)))

def _one_edit_name_folds(name, max_variants=2500):
    """Aynı token sayısını koruyarak 0/1 harf varyantları üret; global DB taramasını IN sorgusuna indir."""
    toks = _name_tokens_strict(name)
    if not toks:
        return []
    alpha = "abcdefghijklmnopqrstuvwxyz"
    out = {" ".join(toks)}
    for i, tok in enumerate(toks):
        variants = {tok}
        if len(tok) > 1:
            for pos in range(1, len(tok)):  # ilk harf sabit: yanlış global snap'i azaltır
                variants.add(tok[:pos] + tok[pos + 1:])
                for ch in alpha:
                    if ch != tok[pos]:
                        variants.add(tok[:pos] + ch + tok[pos + 1:])
            for pos in range(1, len(tok) + 1):
                for ch in alpha:
                    variants.add(tok[:pos] + ch + tok[pos:])
        for v in variants:
            if not v:
                continue
            nt = list(toks)
            nt[i] = v
            out.add(" ".join(nt))
            if len(out) >= max_variants:
                return sorted(out)
    return sorted(out)

def name_close(a, b):
    """AYNI kişinin OCR-misread varyantı mı — YAZIM düzeltme için (gating DEĞİL).

    KESIN İLKE 2: web/KB okunan ismin YAZIMINI düzeltir (Ahmet Cimcir→Cemcir). name_match
    (gating) bunun için fazla SIKI (son token cimcir≠cemcir). Burada: aynı sayıda anlamlı
    token, tokenların TÜMÜ ya birebir eşit ya da küçük edit-mesafeli (≤2, uzunluk≥4 token'da);
    en fazla BİR token misread olabilir. Böylece "Murat Cimcir"~"Murat Cemcir" eşleşir ama
    "Scott Paulin"~"Pauline Chan" (token sayısı/ilk-token farkı) EŞLEŞMEZ."""
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return False
    ta = [t for t in fa.split() if len(t) > 2]
    tb = [t for t in fb.split() if len(t) > 2]
    if not ta or not tb or len(ta) != len(tb):
        return False
    fuzzy_used = 0
    for x, y in zip(ta, tb):
        if x == y:
            continue
        # token misread: yalnız uzun token'da (≥4) ve küçük edit-mesafesinde; en fazla 1 token
        if min(len(x), len(y)) >= 4 and _lev(x, y, 2) <= 2:
            fuzzy_used += 1
            if fuzzy_used > 1:
                return False
        else:
            return False
    return True

def name_close_window(ocr_line, db_name, thr=0.80):
    """GÖMÜLÜ-isim fuzzy (flag-kapılı kullan): OCR cast satırında karakter-adı/rol-etiketi
    karışmışsa (ör. 'VAHAP EFE NARAMAN', 'BAKKAL / THE GROCER ZÜLTİKAR GÜRLEK') db_name'i
    kayan-pencere SequenceMatcher ile ara. name_close token-sayısı-eşit ister → fazladan
    token olunca çöker; bu onu yakalar. YÜKSEK eşik (0.80) → yanlış-snap düşük."""
    import difflib, unicodedata
    _TRW = {'İ':'i','I':'i','ı':'i','Ş':'s','ş':'s','Ğ':'g','ğ':'g','Ü':'u','ü':'u','Ö':'o','ö':'o','Ç':'c','ç':'c'}
    def _f(s):
        s = ''.join(_TRW.get(c, c) for c in (s or ''))
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
        return ''.join(c for c in s if c.isalnum())
    a = _f(db_name); b = _f(ocr_line)
    if len(a) < 5 or not b:
        return False
    best = difflib.SequenceMatcher(None, a, b).ratio()
    if len(b) > len(a):
        for i in range(0, len(b) - len(a) + 1):
            r = difflib.SequenceMatcher(None, a, b[i:i + len(a)]).ratio()
            if r > best:
                best = r
                if best >= thr:
                    break
    return best >= thr

def cast_overlap_fuzzy(read_cast, auth_cast, thr=0.80):
    """auth_cast'tan kaç isim read_cast satırlarında gömülü-pencere ile bulunuyor (gate için)."""
    if not read_cast or not auth_cast:
        return 0
    return sum(1 for a in auth_cast if any(name_close_window(r, a, thr) for r in read_cast))

def cast_overlap(read_cast, auth_cast):
    if not read_cast or not auth_cast:
        return 0
    return sum(1 for r in read_cast if any(name_match(r, a) for a in auth_cast))

class CreditKB:
    def __init__(self):
        import duckdb
        self.wd = self.imdb = None
        try:
            if os.path.exists(WIKIDATA_DB):
                self.wd = duckdb.connect(WIKIDATA_DB, read_only=True)
        except Exception as e:
            sys.stderr.write(f"[uyari] wikidata acilamadi: {e}\n")
        try:
            if os.path.exists(IMDB_DB):
                self.imdb = duckdb.connect(IMDB_DB, read_only=True)
        except Exception as e:
            sys.stderr.write(f"[uyari] imdb acilamadi: {e}\n")

    # ---------- Wikidata ----------
    def _wd_resolve(self, qids):
        out = []
        for q in re.split(r"[|,;]\s*", str(qids or "")):
            q = q.strip()
            if not q.startswith("Q"):
                continue
            try:
                r = self.wd.execute("SELECT label_tr, label_en FROM qid_labels WHERE qid=?", [q]).fetchone()
                out.append((r[0] or r[1]) if r and (r[0] or r[1]) else q)
            except Exception:
                out.append(q)
        return out

    def wd_find(self, title_tr=None, original=None, year=None):
        if not self.wd:
            return []
        cands = {}
        def run(clauses, params):
            if not clauses:
                return
            q = ("SELECT qid,name,label_tr,publication_year,director,cast_member,imdb_id,tmdb_movie_id FROM works_master "
                 "WHERE (" + " OR ".join(clauses) + ") AND director IS NOT NULL LIMIT 60")
            try:
                rows = self.wd.execute(q, params).fetchall()
            except Exception:
                rows = []
            for qid, nm, ltr, yr, dr, cast, imdb, tmdb in rows:
                if qid not in cands:
                    cands[qid] = {"src": "wikidata", "id": qid, "name": nm, "tr": ltr, "year": yr,
                                  "imdb_id": imdb, "tmdb_movie_id": tmdb,
                                  "director": self._wd_resolve(dr), "cast": self._wd_resolve(cast)}
        sf_tr, sf_en, sf_nm = _sqlfold("label_tr"), _sqlfold("label_en"), _sqlfold("name")
        ft = _tfold(title_tr) if title_tr else None
        fo = _tfold(original) if original else None
        # PASS 1: TAM-eşleşme (Türkçe-fold) — kısa/yaygın başlıkta exact öncelik
        c1, p1 = [], []
        if ft: c1.append(f"{sf_tr}=?"); p1.append(ft)
        if fo: c1 += [f"{sf_en}=?", f"{sf_nm}=?"]; p1 += [fo, fo]
        run(c1, p1)
        # PASS 2: substring (Türkçe-fold) fallback
        c2, p2 = [], []
        if ft: c2.append(f"{sf_tr} LIKE ?"); p2.append(f"%{ft}%")
        if fo: c2 += [f"{sf_en} LIKE ?", f"{sf_nm} LIKE ?"]; p2 += [f"%{fo}%", f"%{fo}%"]
        run(c2, p2)
        return list(cands.values())

    # ---------- IMDb ----------
    def _imdb_names(self, nconsts):
        out = []
        for nc in [x for x in (nconsts or []) if x]:
            try:
                r = self.imdb.execute("SELECT primaryName FROM names WHERE nconst=?", [nc]).fetchone()
                if r:
                    out.append(r[0])
            except Exception:
                pass
        return out

    def _imdb_people_by_folds(self, folds):
        if not self.imdb or not folds:
            return []
        out = []
        exprs = (
            "trim(regexp_replace(lower(strip_accents(primaryName)),'[^a-z0-9]+',' ','g'))",
            "trim(regexp_replace(lower(primaryName),'[^a-z0-9]+',' ','g'))",
        )
        for expr in exprs:
            try:
                for i in range(0, len(folds), 400):
                    chunk = list(folds[i:i + 400])
                    ph = ",".join(["?"] * len(chunk))
                    rows = self.imdb.execute(
                        f"SELECT nconst, primaryName, primaryProfession FROM names WHERE {expr} IN ({ph}) LIMIT 200",
                        chunk,
                    ).fetchall()
                    out.extend(rows)
                break
            except Exception:
                out = []
                continue
        seen, dedup = set(), []
        for nc, nm, prof in out:
            if nc in seen:
                continue
            seen.add(nc)
            dedup.append((nc, nm, prof or ""))
        return dedup

    def _imdb_role_ok(self, nconst, role, professions=""):
        profs = {p.strip().lower() for p in str(professions or "").split(",") if p.strip()}
        if role == "cast":
            if profs & {"actor", "actress"}:
                return True
            try:
                r = self.imdb.execute(
                    "SELECT 1 FROM principals WHERE nconst=? AND category IN ('actor','actress') LIMIT 1",
                    [nconst],
                ).fetchone()
                return bool(r)
            except Exception:
                return False
        if role == "producer":
            if "producer" in profs:
                return True
            try:
                r = self.imdb.execute(
                    "SELECT 1 FROM principals WHERE nconst=? AND category='producer' LIMIT 1",
                    [nconst],
                ).fetchone()
                return bool(r)
            except Exception:
                return False
        if role == "director":
            if "director" in profs:
                return True
            try:
                r = self.imdb.execute("SELECT 1 FROM crew WHERE directors LIKE ? LIMIT 1", [f"%{nconst}%"]).fetchone()
                return bool(r)
            except Exception:
                return False
        return False

    def _wd_people_by_folds(self, folds):
        if not self.wd or not folds:
            return []
        out = []
        exprs = (
            ("trim(regexp_replace(lower(strip_accents(label_tr)),'[^a-z0-9]+',' ','g'))",
             "trim(regexp_replace(lower(strip_accents(label_en)),'[^a-z0-9]+',' ','g'))"),
            ("trim(regexp_replace(lower(label_tr),'[^a-z0-9]+',' ','g'))",
             "trim(regexp_replace(lower(label_en),'[^a-z0-9]+',' ','g'))"),
        )
        for expr_tr, expr_en in exprs:
            try:
                for i in range(0, len(folds), 400):
                    chunk = list(folds[i:i + 400])
                    ph = ",".join(["?"] * len(chunk))
                    rows = self.wd.execute(
                        f"SELECT qid, coalesce(label_tr, label_en) FROM qid_labels "
                        f"WHERE {expr_tr} IN ({ph}) OR {expr_en} IN ({ph}) LIMIT 200",
                        chunk + chunk,
                    ).fetchall()
                    out.extend(rows)
                break
            except Exception:
                out = []
                continue
        seen, dedup = set(), []
        for qid, nm in out:
            if qid in seen:
                continue
            seen.add(qid)
            dedup.append((qid, nm))
        return dedup

    def _wd_role_ok(self, qid, role):
        if not self.wd or not qid:
            return False
        if role == "cast":
            fields = ("cast_member",)
        elif role == "director":
            fields = ("director",)
        elif role == "producer":
            fields = ("producer", "produced_by")
        else:
            return False
        for field in fields:
            try:
                r = self.wd.execute(
                    f"SELECT 1 FROM works_master WHERE {field} LIKE ? LIMIT 1",
                    [f"%{qid}%"],
                ).fetchone()
                if r:
                    return True
            except Exception:
                continue
        return False

    def global_person_match(self, name, role="cast", max_edits=1):
        """Filmden bağımsız kişi kapısı: global IMDb/Wiki içinde role uygun, 0/1 harf eşleşme."""
        role = {"actor": "cast", "actress": "cast", "oyuncu": "cast",
                "yonetmen": "director", "yönetmen": "director",
                "yapimci": "producer", "yapımcı": "producer"}.get(str(role).lower(), role)
        folds = _one_edit_name_folds(name)
        if not folds:
            return None
        matches = []
        for nc, nm, prof in self._imdb_people_by_folds(folds):
            if strict_name_close(name, nm, max_edits=max_edits) and self._imdb_role_ok(nc, role, prof):
                matches.append({"source": "imdb-global", "id": nc, "name": nm,
                                "distance": strict_name_distance(name, nm, max_edits=max_edits)})
        for qid, nm in self._wd_people_by_folds(folds):
            if strict_name_close(name, nm, max_edits=max_edits) and self._wd_role_ok(qid, role):
                matches.append({"source": "wikidata-global", "id": qid, "name": nm,
                                "distance": strict_name_distance(name, nm, max_edits=max_edits)})
        if not matches:
            return None
        matches.sort(key=lambda m: (m["distance"], 0 if m["source"] == "wikidata-global" else 1, m["name"]))
        return matches[0]

    def imdb_credits(self, tconst):
        director, cast = [], []
        try:
            r = self.imdb.execute("SELECT directors FROM crew WHERE tconst=?", [tconst]).fetchone()
            if r and r[0]:
                director = self._imdb_names(re.split(r"[,\s]+", r[0]))
        except Exception:
            pass
        try:
            rows = self.imdb.execute(
                "SELECT nconst FROM principals WHERE tconst=? AND category IN ('actor','actress') ORDER BY ordering LIMIT 10",
                [tconst]).fetchall()
            cast = self._imdb_names([x[0] for x in rows])
        except Exception:
            pass
        return director, cast

    def imdb_find(self, title_tr=None, original=None, year=None):
        if not self.imdb:
            return []
        tconsts = {}
        sf = _sqlfold("title")                       # akas.title Türkçe-fold (ı/İ tuzağı — wd_find ile aynı)
        ft = _tfold(title_tr) if title_tr else None
        try:
            # PASS 1: Türkçe başlık TAM-eşleşme (TÜRKÇE-FOLD) — yabancı filmin TR release adı akas'ta
            # (ör. "BARBARLARI BEKLERKEN" → "Barbarları Beklerken" = tt6149154; düz ILIKE ı/İ yüzünden kaçırıyordu)
            if ft:
                for (tc,) in self.imdb.execute(
                        f"SELECT DISTINCT tconst FROM akas WHERE {sf}=? LIMIT 20", [ft]).fetchall():
                    tconsts.setdefault(tc, 1)
            if original:
                for (tc,) in self.imdb.execute(
                        "SELECT tconst FROM titles WHERE (originalTitle ILIKE ? OR primaryTitle ILIKE ?) "
                        "AND titleType IN ('movie','tvMovie','tvSeries','tvMiniSeries') LIMIT 20",
                        [original, original]).fetchall():
                    tconsts.setdefault(tc, 1)
            # PASS 2: substring fallback (Türkçe-fold TR başlık + orijinal)
            if ft:
                for (tc,) in self.imdb.execute(
                        f"SELECT DISTINCT tconst FROM akas WHERE {sf} LIKE ? LIMIT 20", [f"%{ft}%"]).fetchall():
                    tconsts.setdefault(tc, 1)
            if original:
                for (tc,) in self.imdb.execute(
                        "SELECT tconst FROM titles WHERE (originalTitle ILIKE ? OR primaryTitle ILIKE ?) "
                        "AND titleType IN ('movie','tvMovie','tvSeries','tvMiniSeries') LIMIT 20",
                        [f"%{original}%", f"%{original}%"]).fetchall():
                    tconsts.setdefault(tc, 1)
        except Exception:
            return []
        cands = []
        for tc in list(tconsts)[:25]:
            try:
                r = self.imdb.execute("SELECT primaryTitle,originalTitle,startYear FROM titles WHERE tconst=?", [tc]).fetchone()
            except Exception:
                r = None
            d, c = self.imdb_credits(tc)
            cands.append({"src": "imdb", "id": tc, "name": (r and r[0]), "tr": None,
                          "year": (r and r[2]), "imdb_id": tc, "director": d, "cast": c})
        return cands

    def cast_find(self, read_cast, year=None):
        """KADEME 1 — okunan CAST'tan kimlik: oyuncuları IMDb'de bul → en çok örtüşen film.
        Başlık DB'de olmasa da çalışır. Rastlantı önleme: ≥2 tanınan oyuncu + filmde ≥2 örtüşme."""
        if not self.imdb or not read_cast:
            return []
        folded = sorted({f for f in (_castfold(n) for n in read_cast) if len(f) >= 5})  # kısa/tek-kelime ele
        if len(folded) < 2:
            return []
        ph = ",".join(["?"] * len(folded))
        expr = "trim(regexp_replace(lower(strip_accents(primaryName)),'[^a-z0-9]+',' ','g'))"
        rows = None
        for e in (expr, "trim(regexp_replace(lower(primaryName),'[^a-z0-9]+',' ','g'))"):  # strip_accents yoksa yedek
            try:
                rows = self.imdb.execute(f"SELECT nconst FROM names WHERE {e} IN ({ph})", folded).fetchall()
                break
            except Exception:
                continue
        if not rows:
            return []
        nconsts = list({r[0] for r in rows})
        if len(nconsts) < 2:
            return []
        ph2 = ",".join(["?"] * len(nconsts))
        try:
            trows = self.imdb.execute(
                f"SELECT tconst, count(DISTINCT nconst) c FROM principals WHERE nconst IN ({ph2}) "
                f"GROUP BY tconst HAVING count(DISTINCT nconst) >= 2 ORDER BY c DESC LIMIT 8", nconsts).fetchall()
        except Exception:
            return []
        cands = []
        for tc, ov in trows:
            try:
                r = self.imdb.execute(
                    "SELECT primaryTitle,originalTitle,startYear,titleType FROM titles WHERE tconst=?", [tc]).fetchone()
            except Exception:
                r = None
            if not r or r[3] not in ("movie", "tvMovie", "tvSeries", "tvMiniSeries"):
                continue
            d, c = self.imdb_credits(tc)
            cands.append({"src": "imdb-cast", "id": tc, "name": r[0], "tr": None, "year": r[2],
                          "imdb_id": tc, "director": d, "cast": c})
        return cands

    # ---------- birleşik çapraz-kontrol ----------
    def crosscheck(self, read_director, read_cast=None, *, title_tr=None, original=None, year=None):
        read_cast = read_cast or []
        cands = self.wd_find(title_tr, original, year) + self.imdb_find(title_tr, original, year)
        # KADEME 1: başlık adaylarının cast-örtüşmesi GÜÇLÜ değilse (>=4 yoksa) CAST'tan da
        # kimlik kur (başlık DB'de olmasa/yanlış-başlık çakışsa da gerçek film havuza girsin).
        # Eski eşik (best_ov<2) "Uyarı İşareti"→"Warning Sign" gibi yanlış title-only çakışmada
        # cast_find'i hiç çalıştırmıyordu (best_ov=3 ama o 3 SAHTE name_match'ti); artık SIKI
        # name_match ile gerçek örtüşme düşük → cast_find devreye girer ve doğru filmi getirir.
        best_ov = max((cast_overlap(read_cast, c.get("cast")) for c in cands), default=0)
        if read_cast and best_ov < 4:
            cands += self.cast_find(read_cast, year)
        if not cands:
            return {"verdict": "KAYNAK_YOK", "kaynak": None, "otoriter_yonetmen": [], "neden": "film bulunamadı"}
        # en iyi aday: cast örtüşmesi (birincil) -> yıl yakınlığı -> director dolu
        def score(c):
            ov = cast_overlap(read_cast, c.get("cast"))
            yp = 0
            if year and c.get("year"):
                try: yp = 2 if abs(int(c["year"]) - int(year)) <= 1 else (1 if abs(int(c["year"]) - int(year)) <= 3 else 0)
                except Exception: yp = 0
            return (ov, yp, 1 if c.get("director") else 0)
        cands.sort(key=score, reverse=True)
        best = cands[0]
        # KİMLİK KAPISI (TÜM kaynaklara): bir filmi "tanındı" saymadan önce GERÇEK cast_overlap
        # (yeni SIKI name_match ile) >=2 olmalı. Aksi halde KAYNAK_YOK.
        # KÖK SEBEP: klip XML'siz → orijinal-ad yok → title-only "UYARI İŞARETİ" Filipinli
        # "Red Flag"in resmi TR adıyla çakıştı; eski kapı yalnız src=="imdb-cast"'e bakıyordu,
        # başlık-tabanlı yanlış adayı (cast_ov SAHTE 3) geçiriyordu. Artık başlık-tabanlı dahil
        # her kaynak gerçek cast örtüşmesiyle kapıdan geçer (yanlış kimlik > okunamadı).
        # İstisna: read_cast HİÇ verilmediyse (cast'sız sorgu) eski başlık-teyidi davranışı korunur.
        # KİLİT ≥3 (Çağatay 2026-06-15): same-title yanlış-kilit riskini düşür. D2 İSTİSNASI (onaylı):
        # ≥2 cast + yönetmen-eşleşmesi → yine kilitle (yön + 2 cast aynı anda yanlış-filme düşemez).
        _ov = cast_overlap(read_cast, best.get("cast"))
        auth_dir = best.get("director") or []
        _dir_ok = bool(read_director) and any(name_match(read_director, a) for a in auth_dir)
        if read_cast and _ov < 3 and not (_ov >= 2 and _dir_ok):
            return {"verdict": "KAYNAK_YOK", "kaynak": None, "otoriter_yonetmen": [],
                    "neden": f"cast-eşleşmesi zayıf (kilit ≥3 ya da ≥2+yön; ov={_ov})"}
        if not read_director:
            verdict = "OKUNAN_YOK"
        elif any(name_match(read_director, a) for a in auth_dir):
            verdict = "TEYİT"
        elif auth_dir:
            verdict = "ÇELİŞKİ"
        else:
            verdict = "KAYNAK_YOK"
        return {"verdict": verdict, "kaynak": best["src"], "eslesen_film": best.get("name") or best.get("tr"),
                "eslesen_yil": best.get("year"), "cast_ortusme": cast_overlap(read_cast, best.get("cast")),
                "otoriter_yonetmen": auth_dir,
                "otoriter_cast": list(dict.fromkeys((best.get("cast") or [])[:8])),
                "okunan_yonetmen": read_director,
                "matched_imdb_id": best.get("imdb_id"),    # KADEME 1: cast_find dahil her kaynağın imdb_id'si
                "wikidata_imdb_id": best.get("imdb_id") if best.get("src") == "wikidata" else None,
                "wikidata_tmdb_id": best.get("tmdb_movie_id") if best.get("src") == "wikidata" else None}

    def close(self):
        for c in (self.wd, self.imdb):
            try:
                if c: c.close()
            except Exception:
                pass

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--baslik", required=True, help="Türkçe başlık")
    ap.add_argument("--orijinal", default=None)
    ap.add_argument("--yonetmen", default="", help="okunan yönetmen")
    ap.add_argument("--cast", default="", help="okunan cast, virgülle")
    ap.add_argument("--yil", default=None)
    a = ap.parse_args()
    kb = CreditKB()
    r = kb.crosscheck(a.yonetmen, [x.strip() for x in a.cast.split(",") if x.strip()],
                      title_tr=a.baslik, original=a.orijinal, year=a.yil)
    import json
    print(json.dumps(r, ensure_ascii=False, indent=2))
    kb.close()

if __name__ == "__main__":
    main()
