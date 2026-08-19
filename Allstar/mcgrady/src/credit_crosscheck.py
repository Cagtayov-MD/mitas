#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
credit_crosscheck.py — okunan künyeyi BİRİNCİ-SINIF iki otoriteyle çapraz-doğrula.

McGrady KULE KOPYASI (2026-08-18, scripts/credit_crosscheck.py'den). KULE FARKLARI:
  1. KAPSAM KIRPIMI: yalnız QC2 akışının kullandığı API'ler taşındı (CreditKB:
     wd_find/imdb_find/cast_find/imdb_credits/crosscheck; name_match/name_close/
     name_close_window/cast_overlap*). global_person_match + strict_name_* ailesi
     QC2'de KULLANILMIYOR (isim-düzeyi teyit süzgecinin işi — pipeline'da kalır).
  2. DIŞSAL SQL: sabit sorgular src/sql/sorgular.sql'de "-- @ad:" etiketli bloklar
     halinde durur; bu modül onları yükler. Kullanıcı verisi daima ? parametresi
     (sorgu metniyle asla birleştirilmez); LIKE örüntüleri ("%...%") DEĞER olarak
     hazırlanır; IN listeleri list_contains(?, kolon) ile bağlanır.
  3. TÜRKÇE-FOLD MAKROSU: orijinalin sorgu-içi _sqlfold REPLACE zinciri, bağlantı
     kurulurken bir kez TEMP MACRO tr_fold(x) olarak tanımlanır (read-only DB'de
     temp şema bellek-içidir, DB'ye YAZMAZ; doğrulandı 2026-08-18). tr_fold,
     scripts/ _sqlfold ile KARAKTER-KARAKTER aynı üretimdir — anlam birebir.
  4. ÇOK-OR AYRIMI: orijinalin "label_tr=? OR label_en=? OR name=?" tek sorgusu,
     kulede üç TEK-koşullu sorguya bölünüp sonuçlar Python'da birleştirilir
     (aday KÜMESİ aynı; cands sözlüğü qid ile tekilleştirir; ekleme sırası
     tr→en→name). Orijinalde eşit-skorlu adayların satır sırası DB planına
     bağlıydı — küme değişmez.
  5. wd_find'DE director-filtRESI YOK: orijinaldeki "AND director IS NOT NULL"
     bu DB'de no-op'tur (2026-08-18 ölçüm: works_master'da director IS NULL = 0
     satır; 564.019 satır director='' ve ikisi de filtreden geçiyor). Filtre
     kaldırılmakla davranış BİREBİR korunur.
  6. DB yolları env'den (MITAS_WIKIDATA_DUCKDB / MITAS_IMDB_DUCKDB); kule
     main.py config.yaml'daki zemin yollarını env'e yazar, aşağıdaki Windows
     varsayılanları kulede ASLA devreye girmez.

KAYNAKLAR: WIKIDATA works_master/qid_labels; IMDb titles/akas/crew/principals/names.

İLKELER:
  • Kimlik = Türkçe başlık (label_tr / akas) ÖNCE; sonra orijinal-ad+yıl; çoklu
    adayda CAST örtüşmesiyle kesinleştir. KATALOG NUMARASI/yıl BAZ DEĞİL.
  • Otoriter yönetmen/cast → TEYİT/ÇELİŞKİ/KAYNAK_YOK. ASLA DÜZELTME YOK.

CLI: python src/credit_crosscheck.py --baslik "AHLAT AĞACI" --yil 2018
"""
import argparse, os, re, sys, unicodedata
from pathlib import Path

from name_fold import latin_ascii

WIKIDATA_DB = os.environ.get("MITAS_WIKIDATA_DUCKDB", r"X:\DIGER\Mitas_Files\MitaData\mitas.duckdb")
IMDB_DB = os.environ.get("MITAS_IMDB_DUCKDB", r"Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb")

_SQL_DOSYA = Path(__file__).resolve().parent / "sql" / "sorgular.sql"

# tr_fold makro gövdesi — scripts/credit_crosscheck._sqlfold ile aynı REPLACE zinciri.
# TEMP MACRO: read-only bağlantının bellek-içi temp şemasında kurulur (DB'ye yazmaz).
_TR_FOLD_DDL = (
    "CREATE OR REPLACE TEMP MACRO tr_fold(x) AS lower("
    "replace(replace(replace(replace(replace(replace(replace(replace(replace("
    "replace(replace(replace(replace(x,'İ','i'),'I','i'),'ı','i'),'Ş','s'),'ş','s'),"
    "'Ğ','g'),'ğ','g'),'Ü','u'),'ü','u'),'Ö','o'),'ö','o'),'Ç','c'),'ç','c'))")


def sorgular_yukle() -> dict:
    """sorgular.sql'i "-- @ad:" etiketli bloklara ayır → {ad: sorgu}.
    Yorum satırları atılır; sorgu metni olduğu gibi korunur (veri BirLEŞTİRİLMEZ)."""
    sozluk, ad, parcalar = {}, None, []
    for satir in _SQL_DOSYA.read_text(encoding="utf-8").splitlines():
        m = re.match(r"--\s*@([a-z0-9_]+):\s*$", satir.strip())
        if m:
            if ad is not None:
                sozluk[ad] = "\n".join(parcalar).strip()
            ad, parcalar = m.group(1), []
        elif ad is not None and not satir.lstrip().startswith("--"):
            parcalar.append(satir)
    if ad is not None:
        sozluk[ad] = "\n".join(parcalar).strip()
    return sozluk


_SORGU = sorgular_yukle()

_TR = (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
       ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c"))

def fold(s):
    s = (s or "")
    for a, b in _TR:
        s = s.replace(a, b)
    s = latin_ascii(s)
    return re.sub(r"[^a-z0-9 ]", " ", s).strip()

def _tfold(s):
    """Türkçe-duyarlı katlama (ı→i, ğ→g…) — strip_accents'in ı tuzağını çözer."""
    s = (s or "")
    for a, b in _TR:
        s = s.replace(a, b)
    return s.lower().strip()

def _castfold(s):
    """isim eşleştirme: aksan-sız + küçük + alnum-tek-boşluk (SQL fold ifadesiyle EŞLEŞİR)."""
    s = unicodedata.normalize("NFKD", (s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def _like(v):
    """SQL LIKE örüntü parametresi (DEĞER, sorgu DEĞİL): %v% — None ise None."""
    return ("%" + v + "%") if v else None

def name_match(a, b):
    """iki isim aynı kişi mi — SIKI token eşitliği (substring DEĞİL): 2+ tokenlu
    adlarda İLK+SON anlamlı token eşitliği şart; tek tokenlu adlarda birebir."""
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return False
    ta = [t for t in fa.split() if len(t) > 2]
    tb = [t for t in fb.split() if len(t) > 2]
    if not ta or not tb:
        return False
    sb = set(tb)
    if len(ta) == 1:
        return ta[0] in sb
    if ta[0] not in sb or ta[-1] not in sb:
        return False
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

def name_close(a, b):
    """AYNI kişinin OCR-misread varyantı mı — YAZIM düzeltme için (gating DEĞİL).
    En fazla BİR token misread (≤2 edit, ≥4 uzunluk). "Murat Cimcir"~"Murat
    Cemcir" eşleşir; "Scott Paulin"~"Pauline Chan" EŞLEŞMEZ."""
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
        if min(len(x), len(y)) >= 4 and _lev(x, y, 2) <= 2:
            fuzzy_used += 1
            if fuzzy_used > 1:
                return False
        else:
            return False
    return True

def name_close_window(ocr_line, db_name, thr=0.80):
    """GÖMÜLÜ-isim fuzzy: OCR satırında karakter-adı karışmışsa db_name'i kayan
    pencere SequenceMatcher ile ara. YÜKSEK eşik (0.80) → yanlış-snap düşük."""
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
    """auth_cast'tan kaç isim read_cast satırlarında gömülü-pencere ile bulunuyor."""
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
                self.wd.execute(_TR_FOLD_DDL)
        except Exception as e:
            sys.stderr.write("[uyari] wikidata acilamadi: " + str(e) + "\n")
        try:
            if os.path.exists(IMDB_DB):
                self.imdb = duckdb.connect(IMDB_DB, read_only=True)
                self.imdb.execute(_TR_FOLD_DDL)
        except Exception as e:
            sys.stderr.write("[uyari] imdb acilamadi: " + str(e) + "\n")

    def db_hazir(self) -> bool:
        """Kimlik çapraz-kontrolü için EN AZ bir DB bağlı olmalı (yoksa arıza sinyali)."""
        return bool(self.wd or self.imdb)

    # ---------- Wikidata ----------
    def _wd_resolve(self, qids):
        out = []
        for q in re.split(r"[|,;]\s*", str(qids or "")):
            q = q.strip()
            if not q.startswith("Q"):
                continue
            try:
                r = self.wd.execute(_SORGU["wd_qid_labels"], [q]).fetchone()
                out.append((r[0] or r[1]) if r and (r[0] or r[1]) else q)
            except Exception:
                out.append(q)
        return out

    def wd_find(self, title_tr=None, original=None, year=None):
        if not self.wd:
            return []
        cands = {}
        def ekle(rows):
            for qid, nm, ltr, yr, dr, cast, imdb, tmdb in rows:
                if qid not in cands:
                    cands[qid] = {"src": "wikidata", "id": qid, "name": nm, "tr": ltr, "year": yr,
                                  "imdb_id": imdb, "tmdb_movie_id": tmdb,
                                  "director": self._wd_resolve(dr), "cast": self._wd_resolve(cast)}
        ft = _tfold(title_tr) if title_tr else None
        fo = _tfold(original) if original else None
        ft_like, fo_like = _like(ft), _like(fo)
        # PASS 1: TAM-eşleşme (Türkçe-fold) — kısa/yaygın başlıkta exact öncelik.
        try:
            if ft:
                ekle(self.wd.execute(_SORGU["wd_exact_label_tr"], [ft]).fetchall())
            if fo:
                ekle(self.wd.execute(_SORGU["wd_exact_label_en"], [fo]).fetchall())
                ekle(self.wd.execute(_SORGU["wd_exact_name"], [fo]).fetchall())
        except Exception:
            pass
        # PASS 2: substring (Türkçe-fold) fallback — yalnız YENİ qid'leri ekler.
        try:
            if ft_like:
                ekle(self.wd.execute(_SORGU["wd_like_label_tr"], [ft_like]).fetchall())
            if fo_like:
                ekle(self.wd.execute(_SORGU["wd_like_label_en"], [fo_like]).fetchall())
                ekle(self.wd.execute(_SORGU["wd_like_name"], [fo_like]).fetchall())
        except Exception:
            pass
        return list(cands.values())

    # ---------- IMDb ----------
    def _imdb_names(self, nconsts):
        out = []
        for nc in [x for x in (nconsts or []) if x]:
            try:
                r = self.imdb.execute(_SORGU["imdb_names_primary"], [nc]).fetchone()
                if r:
                    out.append(r[0])
            except Exception:
                pass
        return out

    def imdb_credits(self, tconst):
        director, cast = [], []
        try:
            r = self.imdb.execute(_SORGU["imdb_crew_directors"], [tconst]).fetchone()
            if r and r[0]:
                director = self._imdb_names(re.split(r"[,\s]+", r[0]))
        except Exception:
            pass
        try:
            rows = self.imdb.execute(_SORGU["imdb_principals_cast"], [tconst]).fetchall()
            cast = self._imdb_names([x[0] for x in rows])
        except Exception:
            pass
        return director, cast

    def imdb_find(self, title_tr=None, original=None, year=None):
        if not self.imdb:
            return []
        tconsts = {}
        ft = _tfold(title_tr) if title_tr else None
        ft_like, fo_like = _like(ft), _like(original)
        try:
            # PASS 1: Türkçe başlık TAM-eşleşme (TÜRKÇE-FOLD) — yabancı filmin TR
            # release adı akas'ta (ör. "BARBARLARI BEKLERKEN" = tt6149154).
            if ft:
                for (tc,) in self.imdb.execute(_SORGU["imdb_akas_exact"], [ft]).fetchall():
                    tconsts.setdefault(tc, 1)
            if original:
                for (tc,) in self.imdb.execute(_SORGU["imdb_titles_orig"], [original, original]).fetchall():
                    tconsts.setdefault(tc, 1)
            # PASS 2: substring fallback (Türkçe-fold TR başlık + orijinal).
            if ft_like:
                for (tc,) in self.imdb.execute(_SORGU["imdb_akas_like"], [ft_like]).fetchall():
                    tconsts.setdefault(tc, 1)
            if fo_like:
                for (tc,) in self.imdb.execute(_SORGU["imdb_titles_orig"], [fo_like, fo_like]).fetchall():
                    tconsts.setdefault(tc, 1)
        except Exception:
            return []
        cands = []
        for tc in list(tconsts)[:25]:
            try:
                r = self.imdb.execute(_SORGU["imdb_titles_by_tconst"], [tc]).fetchone()
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
        rows = None
        # strip_accents'i olmayan şemalar için plain-fold yedeği ayrı denenir.
        try:
            rows = self.imdb.execute(_SORGU["imdb_names_in_strip"], [folded]).fetchall()
        except Exception:
            rows = None
        if not rows:
            try:
                rows = self.imdb.execute(_SORGU["imdb_names_in_plain"], [folded]).fetchall()
            except Exception:
                rows = None
        if not rows:
            return []
        nconsts = list({r[0] for r in rows})
        if len(nconsts) < 2:
            return []
        try:
            trows = self.imdb.execute(_SORGU["imdb_principals_overlap"], [nconsts]).fetchall()
        except Exception:
            return []
        cands = []
        for tc, ov in trows:
            try:
                r = self.imdb.execute(_SORGU["imdb_titles_full"], [tc]).fetchone()
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
        # KİMLİK KAPISI: tanınma için GERÇEK cast_overlap >=2; KİLİT ≥3
        # (same-title yanlış-kilit riski); D2 istisnası: ≥2 cast + yönetmen-eşleşmesi.
        _ov = cast_overlap(read_cast, best.get("cast"))
        auth_dir = best.get("director") or []
        _dir_ok = bool(read_director) and any(name_match(read_director, a) for a in auth_dir)
        if read_cast and _ov < 3 and not (_ov >= 2 and _dir_ok):
            return {"verdict": "KAYNAK_YOK", "kaynak": None, "otoriter_yonetmen": [],
                    "neden": "cast-eşleşmesi zayıf (kilit >=3 ya da >=2+yön; ov=" + str(_ov) + ")"}
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
                "matched_imdb_id": best.get("imdb_id"),
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
