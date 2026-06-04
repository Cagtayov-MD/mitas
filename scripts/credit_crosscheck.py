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

WIKIDATA_DB = os.environ.get("MITAS_WIKIDATA_DUCKDB", r"X:\DIGER\Mitas_Files\MitaData\mitas.duckdb")
IMDB_DB = os.environ.get("MITAS_IMDB_DUCKDB", r"Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb")

def fold(s):
    s = (s or "")
    for a, b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
                 ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
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

def name_match(a, b):
    """iki isim aynı kişi mi (soyad + tokenların çoğu)."""
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return False
    ta = [t for t in fa.split() if len(t) > 2]
    if not ta:
        return False
    hit = sum(1 for t in ta if t in fb)
    return hit >= max(1, len(ta) - 1)

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
            q = ("SELECT qid,name,label_tr,publication_year,director,cast_member,imdb_id FROM works_master "
                 "WHERE (" + " OR ".join(clauses) + ") AND director IS NOT NULL LIMIT 60")
            try:
                rows = self.wd.execute(q, params).fetchall()
            except Exception:
                rows = []
            for qid, nm, ltr, yr, dr, cast, imdb in rows:
                if qid not in cands:
                    cands[qid] = {"src": "wikidata", "id": qid, "name": nm, "tr": ltr, "year": yr,
                                  "imdb_id": imdb, "director": self._wd_resolve(dr), "cast": self._wd_resolve(cast)}
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
        try:
            # PASS 1: TAM-eşleşme öncelik
            if title_tr:
                for (tc,) in self.imdb.execute("SELECT DISTINCT tconst FROM akas WHERE title ILIKE ? LIMIT 20",
                                               [title_tr]).fetchall():
                    tconsts.setdefault(tc, 1)
            if original:
                for (tc,) in self.imdb.execute(
                        "SELECT tconst FROM titles WHERE (originalTitle ILIKE ? OR primaryTitle ILIKE ?) "
                        "AND titleType IN ('movie','tvMovie','tvSeries','tvMiniSeries') LIMIT 20",
                        [original, original]).fetchall():
                    tconsts.setdefault(tc, 1)
            # PASS 2: substring fallback
            if title_tr:
                for (tc,) in self.imdb.execute("SELECT DISTINCT tconst FROM akas WHERE title ILIKE ? LIMIT 20",
                                               [f"%{title_tr}%"]).fetchall():
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

    # ---------- birleşik çapraz-kontrol ----------
    def crosscheck(self, read_director, read_cast=None, *, title_tr=None, original=None, year=None):
        read_cast = read_cast or []
        cands = self.wd_find(title_tr, original, year) + self.imdb_find(title_tr, original, year)
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
        auth_dir = best.get("director") or []
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
                "otoriter_yonetmen": auth_dir, "otoriter_cast": (best.get("cast") or [])[:8], "okunan_yonetmen": read_director}

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
