#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
credit_validate.py — KÜNYE DOĞRULAMA katmanı (35B çıktısı → doğrula → QC1).

KONUM: OneOCR → 35B(qwen, SÜZER+anti-halüsinasyon) → [BU MODÜL] → QC1

KAYNAK: TEK birleşik yerel DB `mitas.duckdb` → IMDb (imdb.* şeması) + Wikidata
(works_master/people_master) + kişi-meta (ülke/meslek). İKİ BAĞIMSIZ otorite (IMDb crew
ve Wikidata P57), imdb_id ile çapraz-bağlı, AYRI AYRI oy verir (biri-yoksa-öteki).

DEMİR KURALLAR (Çağatay 2026-06-15):
  1. OCR = TEK veri kaynağı. IMDb/Wikidata/XML = yalnız DOĞRULAYICI.
  2. DOLDURMA YOK. OCR okumadıysa → "okunamadı" (kaynaklardan doldurma yok).
  3. SESSİZ EZME YOK. Çelişki → BAYRAK. Yalnız EXACT-eşleşmede yazım-kanonikle;
     YAKIN(close) eşleşme FARKLI kişi olabilir → ezme YOK, OCR korunur, not + QC1.
  4. YIL/SÜRE KULLANMA. Film-eşleştirme yalnız İÇERİKLE (başlık + OCR-yönetmen + OCR-cast).
  5. SESSİZLİK ≠ HATA. Kaynak veri-yoksa bayrak AÇMA.
  6. Çok-kaynak oy; tek kirli-dissent OCR GÜÇLÜ-kilitli + bağımsız-teyitliyse YUTULUR; aksi BAYRAK.
  7. Modül FLAG'ler; karar (re-read/insan) QC1'in.

Anti-circular: bir kaynağın teyidi YALNIZ o kaynak filmi CAST-çapraz-kontrolle bulduysa (GÜÇLÜ)
bağımsız sayılır; yalnız-yönetmenle bulduysa (ZAYIF) totolojik → bağımsız sayılmaz.
Dub-tespiti: yabancı film (country≠Q43) + XML-yönetmeninde TR-vatandaşı isim → seslendirme → düş.
"""
from __future__ import annotations
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MITAS_KB_DUCKDB = os.environ.get("MITAS_KB_DUCKDB", r"Y:\DIGER\Mitas_Files\MitaData\mitas.duckdb")
_TR_QID = "Q43"
_FILM_P31 = ("Q11424", "Q506240", "Q24856", "Q5398426", "Q1261214", "Q202866", "Q93204", "Q1259759")

sys.path.insert(0, HERE)
try:
    import credit_crosscheck as _cc
    _nm, _nc = _cc.name_match, _cc.name_close
except Exception:            # noqa: BLE001
    def _nm(a, b):
        return bool(_fold(a)) and _fold(a) == _fold(b)
    def _nc(a, b):
        fa, fb = set(_fold(a).split()), set(_fold(b).split())
        return len(fa & fb) >= 2

import unicodedata as _ud
def _fold(s):
    s = (s or "").casefold()
    for a, b in (("ı","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),("İ","i")):
        s = s.replace(a, b)
    # "İ".casefold()='i'+U+0307 (combining dot) → NFKD+combining-strip yoksa regex kelimeyi BÖLER
    # ('nİyaz'→'ni yaz') → token-sayısı bozulur → transliterasyon/eşleşme kaçar.
    s = "".join(c for c in _ud.normalize("NFKD", s) if not _ud.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()

# Kuvvetle-Türkçe + OCR-STABİL karakterler (ğ/ş/ı): DB'de olmayan TR seslendirme adlarını
# yabancı-filmde dub tespiti için sezgi. İ DIŞARIDA — OCR yabancı 'I'yı sık 'İ' okur (PATRİCK)
# → İ false-pozitif yapar. ç/ö/ü pan-Avrupa (François/Müller) → dışarıda. İ-only TR adları DB'ye kalır.
_TR_CHARS = set("ğĞşŞı")
def _has_tr_chars(name):
    return any(c in _TR_CHARS for c in (name or ""))

def _lev(a, b):
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def _translit_match(a, b):
    """AYNI kişi, transliterasyon farkı (SADYK SHER-NIYAZ≈SADIK ŞER-NİYAZ, MOUSTAPHA≈MUSTAFA Akkad).
    YÜKSEK-İSABET: aynı token sayısı + SON token (soyad) TAM eşit (transliterasyonda korunur) +
    diğer tokenlar yakın (lev≤3, uzunluk-yakın). Soyad-tam-eşit şartı 'Ahmet Yılmaz≠Mehmet Yılmaz'
    riskini AZALTIR ama tam yok etmez → bu yüzden bu eşleşme CONFIRM değil, 'yakın' (çelişki-değil) sayılır."""
    ta, tb = _fold(a).split(), _fold(b).split()
    if len(ta) != len(tb) or len(ta) < 2 or ta[-1] != tb[-1]:
        return False
    # transliterasyon BAŞ-HARFİ korur (Moustapha/Mustafa=m, Sadyk/Sadik=s); Ahmet/Mehmet=a≠m REDDEDİLİR
    return all(x and y and x[0] == y[0] and _lev(x, y) <= 3 and abs(len(x) - len(y)) <= 3
               for x, y in zip(ta[:-1], tb[:-1]))

def _exact_in(name, pool):
    for p in (pool or []):
        if _nm(name, p):
            return p
    return None

def _close_in(name, pool):
    """EXACT-değil ama YAKIN (name_close VEYA transliterasyon) → ad. Çelişki-bastırma + 'şüphe' notu için
    (ezme/confirm DEĞİL — farklı kişi olabilir)."""
    for p in (pool or []):
        if not _nm(name, p) and (_nc(name, p) or _translit_match(name, p)):
            return p
    return None


# ───────────────────── KAYNAK: mitas.duckdb (IMDb + Wikidata + kişi-meta) ─────────────────────
class _KB:
    """TEK yerel DB: IMDb (imdb.*) + Wikidata (works_master/people_master). Yoksa graceful (her sorgu boş)."""
    def __init__(self, path=MITAS_KB_DUCKDB):
        self.con = None
        try:
            import duckdb
            if os.path.exists(path):
                self.con = duckdb.connect(path, read_only=True)
        except Exception:  # noqa: BLE001
            self.con = None

    def _q(self, sql, args):
        try:
            return self.con.execute(sql, args).fetchall()
        except Exception:  # noqa: BLE001
            return []

    # ---------- IMDb tarafı ----------
    def imdb_candidates(self, title, limit=8):
        if not (self.con and title):
            return []
        return [r[0] for r in self._q(
            "SELECT t.tconst FROM imdb.titles t LEFT JOIN imdb.ratings r ON r.tconst=t.tconst "
            "WHERE t.titleType IN ('movie','tvMovie') AND "
            "(strip_accents(lower(t.primaryTitle))=strip_accents(lower(?)) "
            " OR strip_accents(lower(t.originalTitle))=strip_accents(lower(?))) "
            "ORDER BY r.numVotes DESC NULLS LAST LIMIT ?", [title, title, limit])]

    def imdb_directors(self, tconst):
        if not (self.con and tconst):
            return []
        c = self._q("SELECT directors FROM imdb.crew WHERE tconst=?", [tconst])
        if not c or not c[0][0]:
            return []
        ncons = [x.strip() for x in str(c[0][0]).split(",") if x.strip()]
        return self._names_imdb(ncons)

    def imdb_cast(self, tconst):
        if not (self.con and tconst):
            return []
        return [r[0] for r in self._q(
            "SELECT n.primaryName FROM imdb.principals p JOIN imdb.names n ON p.nconst=n.nconst "
            "WHERE p.tconst=? AND p.category IN ('actor','actress')", [tconst])]

    def imdb_category(self, tconst, name):
        if not (self.con and tconst):
            return []
        return [r[0] for r in self._q(
            "SELECT p.category FROM imdb.principals p JOIN imdb.names n ON p.nconst=n.nconst "
            "WHERE p.tconst=? AND UPPER(strip_accents(n.primaryName))=UPPER(strip_accents(?))",
            [tconst, name])]

    def _names_imdb(self, ncons):
        if not ncons:
            return []
        ph = ",".join("?" * len(ncons))
        return [r[0] for r in self._q(f"SELECT primaryName FROM imdb.names WHERE nconst IN ({ph})", ncons)]

    # ---------- Wikidata tarafı (works_master) ----------
    def wiki_candidates(self, title, limit=8):
        """başlık → film qid adayları (p31=film). Döner [(qid, director_qids, cast_qids, country, imdb_id)]."""
        if not (self.con and title):
            return []
        ph = ",".join("?" * len(_FILM_P31))
        rows = self._q(
            "SELECT qid, director, cast_member, country_of_origin, imdb_id, sitelink_count "
            "FROM works_master WHERE p31 IN (" + ph + ") AND "
            "(strip_accents(lower(name))=strip_accents(lower(?)) "
            " OR strip_accents(lower(ascii_name))=strip_accents(lower(?)) "
            " OR strip_accents(lower(label_en))=strip_accents(lower(?))) "
            "ORDER BY sitelink_count DESC NULLS LAST LIMIT ?",
            list(_FILM_P31) + [title, title, title, limit])
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]

    def _names_wiki(self, qids_str):
        qids = [x.strip() for x in str(qids_str or "").split("|") if x.strip()]
        if not qids:
            return []
        ph = ",".join("?" * len(qids))
        d = {r[0]: r[1] for r in self._q(f"SELECT qid, name FROM people_master WHERE qid IN ({ph})", qids)}
        return [d[q] for q in qids if q in d]   # sıra korunur

    # ---------- kişi-meta (dub-tespiti) ----------
    def person_country(self, name):
        """isim → ülke QID'leri (mitas_people_index). TR=Q43 → yabancı filmde dub şüphesi."""
        if not (self.con and name):
            return None
        r = self._q("SELECT countries FROM mitas_people_index "
                    "WHERE UPPER(strip_accents(name))=UPPER(strip_accents(?)) LIMIT 1", [name])
        return r[0][0] if r else None

    def is_turkish_person(self, name):
        c = self.person_country(name)
        return bool(c) and _TR_QID in str(c)


# ───────────────────── FİLM-KİLİT (kaynak başına, içerikle) ─────────────────────
def _resolve_source(kind, kb, title, ocr_dir, ocr_cast):
    """Bir kaynakta (imdb|wiki) filmi İÇERİKLE bul → {director, cast, strength, key, country}.
    GÜÇLÜ: yön+cast(≥1) veya cast≥2 (bağımsız doğrulama). ZAYIF: yalnız yön (totolojik).
    EN İYİ adayı seçer, EXACT eşleşme. Bulunmazsa strength=None (sessiz)."""
    best = None
    if kind == "imdb":
        for tconst in kb.imdb_candidates(title):
            dl, cl = kb.imdb_directors(tconst), kb.imdb_cast(tconst)
            best = _score(best, dl, cl, ocr_dir, ocr_cast, key=tconst, country=None)
    else:  # wiki
        for (qid, dq, cq, country, imdb_id) in kb.wiki_candidates(title):
            dl, cl = kb._names_wiki(dq), kb._names_wiki(cq)
            best = _score(best, dl, cl, ocr_dir, ocr_cast, key=qid, country=country)
    if not best:
        return {"director": [], "cast": [], "strength": None, "key": None, "country": None}
    _, dl, cl, key, country, strength = best
    return {"director": dl, "cast": cl, "strength": strength, "key": key, "country": country}

def _score(best, dl, cl, ocr_dir, ocr_cast, key, country):
    dirm = any(_exact_in(d, dl) for d in (ocr_dir or []))
    ov = sum(1 for c in (ocr_cast or []) if _exact_in(c, cl))
    if dirm and ov >= 1:
        strength = "GUCLU"
    elif ov >= 2:
        strength = "GUCLU"
    elif dirm:
        strength = "ZAYIF"
    else:
        return best
    sc = ((2 if strength == "GUCLU" else 1), (1 if dirm else 0) + ov)
    if best is None or sc > best[0]:
        return (sc, dl, cl, key, country, strength)
    return best


def _dub_clean(xdir, film_country, ocr_dir, kb):
    """Yabancı film + XML-yönetmeninde TR-vatandaşı = seslendirme/dublaj → DÜŞ.
    YABANCI sinyali: (a) country biliniyor & ≠TR  YA DA  (b) OCR-yönetmenlerinin HİÇBİRİ TR-vatandaşı
    değil (film yabancı; country bilinmese de). Yalnız BİLİNEN TR-vatandaşı düşer (bilinmeyen kalır)
    → sınırlı/güvenli. Döner (temiz_liste, düşen_liste)."""
    if not xdir:
        return [], []
    def _tr(n):  # TR-vatandaşı (DB) VEYA kuvvetle-Türkçe-karakterli (DB'de olmayan seslendirme adı)
        return kb.is_turkish_person(n) or _has_tr_chars(n)
    foreign = (film_country and _TR_QID not in str(film_country)) or \
              (bool(ocr_dir) and not any(_tr(o) for o in ocr_dir))
    if not foreign:
        return list(xdir), []
    keep, dropped = [], []
    for d in xdir:
        (dropped if _tr(d) else keep).append(d)
    return keep, dropped


# ───────────────────── YÖNETMEN DOĞRULAMA ─────────────────────
def validate_director(ocr_dir, xml_dir, imdb_res, wiki_res, kb):
    ocr_dir = [d for d in (ocr_dir or []) if d and str(d).strip()]
    if not ocr_dir:
        return {"value": [], "status": "OKUNAMADI", "confidence": "—",
                "sources_confirm": [], "conflict_candidates": [], "notes": ["OCR boş → doldurma yok"]}

    # film ülkesi: kaynaklardan (dub-temizleme için)
    film_country = wiki_res.get("country") or None
    xdir0 = [d for d in (xml_dir or []) if d and str(d).strip()]
    xdir, dub_dropped = _dub_clean(xdir0, film_country, ocr_dir, kb)

    # 3 BAĞIMSIZ kaynak (her biri kendi kilit-gücüne göre bağımsız):
    #   IMDb/Wiki teyidi YALNIZ o kaynak GÜÇLÜ-kilitli (cast-çapraz) ise bağımsız (anti-circular).
    SOURCES = [
        ("XML",  xdir,                  True),
        ("IMDb", imdb_res.get("director") or [], imdb_res.get("strength") == "GUCLU"),
        ("Wiki", wiki_res.get("director") or [], wiki_res.get("strength") == "GUCLU"),
    ]
    n_active = sum(1 for _, pool, _ in SOURCES if pool)

    dconf = {d: set() for d in ocr_dir}
    weak_confirm = set()
    canonical, conflicts, close_notes = {}, [], []
    for src, pool, indep in SOURCES:
        if not pool:
            continue
        matched = False
        for d in ocr_dir:
            cm = _exact_in(d, pool)
            if cm:
                matched = True
                canonical.setdefault(d, cm)
                if indep:
                    dconf[d].add(src)
                else:
                    weak_confirm.add(d)
        if not matched:
            cl = [(d, _close_in(d, pool)) for d in ocr_dir]
            cl = [(d, c) for d, c in cl if c]
            if cl:
                close_notes.append(f"{src} yakın(exact-değil): " + ", ".join(f"{d}~{c}" for d, c in cl))
            else:
                conflicts.append((src, pool))

    # overreach: OCR-yönetmeni GÜÇLÜ-kilitli IMDb filminde 'oyuncu' mu
    overreach = []
    if imdb_res.get("strength") == "GUCLU" and imdb_res.get("key"):
        for d in ocr_dir:
            cats = kb.imdb_category(imdb_res["key"], d) or []
            if cats and "director" not in cats and ("actor" in cats or "actress" in cats):
                overreach.append(d)

    val = [canonical.get(d, d) for d in ocr_dir]
    indep_sources = set().union(*dconf.values()) if dconf else set()
    all_confirmed = all(dconf[d] for d in ocr_dir)

    notes = list(close_notes)
    if dub_dropped:
        notes.append("XML dub-temizlendi (yabancı film, TR-vatandaşı): " + ", ".join(dub_dropped))
    if overreach:
        notes.append("overreach-şüphe (kilitli filmde oyuncu): " + ", ".join(overreach))
    cands = sorted({n for _, pool in conflicts for n in pool})

    if conflicts:
        # corroboration: ≥1 BAĞIMSIZ teyit + TEK clean-dissent → yutulur (kural 6); ≥2 dissent → bayrak
        absorb = bool(indep_sources) and len(conflicts) == 1
        if absorb:
            conf = "KESIN" if (len(indep_sources) >= 2 and all_confirmed) else "ORTA"
            notes.append("dissent yutuldu (bağımsız teyit var): "
                         + "; ".join(f"{s}={pool}" for s, pool in conflicts))
            if not all_confirmed:
                notes.append("kısmi teyit")
            return {"value": val, "status": "DOGRULANDI", "confidence": conf,
                    "sources_confirm": sorted(indep_sources), "conflict_candidates": cands, "notes": notes}
        notes.append("çelişki: " + "; ".join(f"{s}={pool}" for s, pool in conflicts))
        if indep_sources:
            notes.append("not: bazı kaynaklar destekledi (" + ",".join(sorted(indep_sources)) + ") ama ≥2 dissent")
        return {"value": ocr_dir, "status": "CELISKI", "confidence": "BAYRAK",
                "sources_confirm": sorted(indep_sources), "conflict_candidates": cands, "notes": notes}

    if indep_sources:
        conf = "KESIN" if (len(indep_sources) >= 2 and all_confirmed) else "ORTA"
        if not all_confirmed:
            notes.append("kısmi teyit")
        return {"value": val, "status": "DOGRULANDI", "confidence": conf,
                "sources_confirm": sorted(indep_sources), "conflict_candidates": [], "notes": notes}

    notes.append("yalnız zayıf-kilit/yakın-eşleşme (sessiz)" if weak_confirm else "kaynak veri yok (sessiz)")
    return {"value": ocr_dir, "status": "DOGRULANAMADI", "confidence": "DUSUK",
            "sources_confirm": [], "conflict_candidates": [], "notes": notes}


# ───────────────────── CAST DOĞRULAMA ─────────────────────
from collections import Counter

def _consensus_variant(name, ocr_text):
    toks = set(_fold(name).split())
    if not ocr_text or len(toks) < 2:
        return name
    variants = Counter()
    for line in ocr_text.splitlines():
        line = line.strip()
        w = line.split()
        if not (len(toks) <= len(w) <= len(toks) + 1):
            continue
        tf = set(_fold(line).split())
        if tf and len(tf & toks) == len(toks):
            variants[line] += 1
    return variants.most_common(1)[0][0] if variants else name


def validate_cast(ocr_cast, ref_cast, lock_strength, ocr_text):
    """EXACT→kanonik(yazım); YAKIN→OCR korunur+not; DB-yok→kare-içi konsensüs. ZAYIF-kilitte kanonik YOK."""
    ocr_cast = [c for c in (ocr_cast or []) if c and str(c).strip()]
    icast = ref_cast if (ref_cast and lock_strength == "GUCLU") else []
    out, notes = [], []
    for c in ocr_cast:
        cm = _exact_in(c, icast) if icast else None
        if cm:
            out.append(cm)
            if cm != c:
                notes.append(f"yazım-teyit: {c}→{cm}")
            continue
        cl = _close_in(c, icast) if icast else None
        if cl:
            out.append(c)
            notes.append(f"yakın-eşleşme (QC kontrol, ezilmedi): {c}~{cl}")
            continue
        v = _consensus_variant(c, ocr_text)
        out.append(v)
        if v != c:
            notes.append(f"kare-içi: {c}→{v}")
    seen, ded = set(), []
    for x in out:
        k = _fold(x)
        if k and k not in seen:
            seen.add(k); ded.append(x)
    return {"value": ded, "notes": notes}


# ───────────────────── ANA GİRİŞ ─────────────────────
def _recover_raw(title, ocr_raw, kb):
    """STITCH-DROP kurtarma: 35B-yön boş AMA başlık-adayı bir filmin yönetmeni HAM OCR'da TAM var
    (stitch düşürmüş). Yalnız TÜM anlamlı token'ları (≥4 harf) raw'da geçen TEK aday → kurtar.
    Fragman (ör. 'Kore') eşleşmez (token-tam şartı). Pixel-kaynaklı (katalog 'neye bak'ı söyler)."""
    if not (title and ocr_raw and kb.con):
        return None
    rf = _fold(ocr_raw)
    cands = set()
    for tconst in kb.imdb_candidates(title):
        for d in kb.imdb_directors(tconst):
            cands.add(d)
    for (qid, dq, cq, country, imdb_id) in kb.wiki_candidates(title):
        for d in kb._names_wiki(dq):
            cands.add(d)
    hits = []
    for d in cands:
        toks = [t for t in _fold(d).split() if len(t) >= 4]
        if len(toks) >= 1 and all(t in rf for t in toks):   # her anlamlı token HAM OCR'da TAM
            hits.append(d)
    return hits[0] if len(hits) == 1 else None


def validate(extracted, *, xml_roles=None, title="", ocr_text=None, ocr_raw=None, kb=None):
    kb = kb or _KB()
    xml_roles = xml_roles or {}
    ocr_dir = [d for d in (extracted.get("yonetmen") or []) if d and str(d).strip()]
    # STITCH-DROP kurtarma: 35B boş ama yönetmen HAM OCR'da tam → pixel-teyitli kurtar (no-fill korunur)
    if not ocr_dir and ocr_raw:
        _rec = _recover_raw(title, ocr_raw, kb)
        if _rec:
            ocr_dir = [_rec]
            extracted = dict(extracted); extracted["_recovered_raw"] = _rec
    if "cast" in extracted:
        ocr_cast = extracted.get("cast") or []
    else:
        ocr_cast = extracted.get("oyuncular") or []
    ocr_cast = [c for c in ocr_cast if c and str(c).strip()]

    imdb_res = _resolve_source("imdb", kb, title, ocr_dir, ocr_cast)
    wiki_res = _resolve_source("wiki", kb, title, ocr_dir, ocr_cast)

    dirv = validate_director(ocr_dir, xml_roles.get("yonetmen"), imdb_res, wiki_res, kb)

    # cast referansı: GÜÇLÜ-kilitli kaynağın cast'i (IMDb öncelik, yoksa Wiki)
    if imdb_res.get("strength") == "GUCLU":
        ref_cast, lock_s = imdb_res.get("cast"), "GUCLU"
    elif wiki_res.get("strength") == "GUCLU":
        ref_cast, lock_s = wiki_res.get("cast"), "GUCLU"
    else:
        ref_cast, lock_s = [], None
    castv = validate_cast(ocr_cast, ref_cast, lock_s, ocr_text)

    needs_reread = dirv["status"] in ("CELISKI", "OKUNAMADI")
    flag_level = {"CELISKI": "YUKSEK", "OKUNAMADI": "YUKSEK",
                  "DOGRULANAMADI": "DUSUK", "DOGRULANDI": "—"}[dirv["status"]]
    return {
        "yonetmen": dirv,
        "cast": castv,
        "kaynaklar": {"imdb": {k: imdb_res[k] for k in ("director", "strength", "key")},
                      "wiki": {k: wiki_res[k] for k in ("director", "strength", "key", "country")}},
        "qc1": {"needs_reread": needs_reread, "flag_level": flag_level, "reason": dirv["status"]},
    }


if __name__ == "__main__":
    import argparse, json
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="credit_validate (standalone, mitas.duckdb)")
    ap.add_argument("--extracted", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--xml-roles", default="")
    ap.add_argument("--ocr-text-file", default="")
    a = ap.parse_args()
    ext = json.loads(a.extracted)
    xr = json.loads(a.xml_roles) if a.xml_roles else {}
    ot = open(a.ocr_text_file, encoding="utf-8", errors="replace").read() if (a.ocr_text_file and os.path.exists(a.ocr_text_file)) else None
    print(json.dumps(validate(ext, xml_roles=xr, title=a.title, ocr_text=ot), ensure_ascii=False, indent=2))
