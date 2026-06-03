# -*- coding: utf-8 -*-
"""MITAS — kunye satirlari -> {oyuncular, yapimci, yonetmen} ayirici (GLOBAL python).

Kurallar (bicim + rol sozlugu) + isim-DB dogrulamasi (IMDB names + Turkce isim CSV).
FIDELITY: ham OCR satiri TEK gercek. DB sadece SINIFLANDIRIR (kisi mi? meslegi?),
icerik EKLEMEZ/DEGISTIRMEZ/UYDURMAZ. DB yoksa kural-only calisir (graceful).

Cikti JSON: {oyuncular:[...], yapimci:[...], yonetmen:[...], needs_review, notes, db_used}
"""
from __future__ import annotations
import sys, re, json, argparse, unicodedata, time
from pathlib import Path

IMDB_DB = r"Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb"
TR_GIVEN = r"Y:\DIGER\Mitas_Files\MitaData\06_name_databases\turkish\turkish_given_names.csv"
TR_SUR = r"Y:\DIGER\Mitas_Files\MitaData\06_name_databases\turkish\turkish_surnames.csv"

sys.stdout.reconfigure(encoding="utf-8")

# rol/is sozcukleri (normalize edilmis) — bunlar oyuncu adi DEGIL
ROLE_TOKENS = {
    "YAPIMCI", "YAPIM", "PRODUCER", "PRODUCED", "PRODUCTION", "EXECUTIVE", "COPRODUCER",
    "YONETMEN", "YONETEN", "DIRECTOR", "DIRECTED", "DIRECTION",
    "SENARYO", "SCREENPLAY", "WRITER", "WRITTEN", "STORY", "YAZAN",
    "GORUNTU", "PHOTOGRAPHY", "CINEMATOGRAPHER", "DOP", "KAMERA", "CAMERA", "OPERATOR",
    "KURGU", "EDITOR", "EDITED", "EDITING", "MONTAJ",
    "MUZIK", "MUSIC", "COMPOSER", "SCORE", "SONG", "SOUND", "SES",
    "SANAT", "DESIGN", "DESIGNER", "DEKOR", "ART", "KOSTUM", "COSTUME", "WARDROBE",
    "MAKYAJ", "MAKEUP", "HAIR", "CUTTER", "FITTER", "FITTERS", "AGER", "DYER", "DYERS",
    "ASSISTANT", "YARDIMCI", "ASSOCIATE", "COORDINATOR", "KOORDINATOR", "SUPERVISOR",
    "AMIRI", "GRIP", "GAFFER", "ELECTRIC", "BEST", "BOY", "DRIVER", "TRANSPORT",
    "TRAINEE", "INTERN", "AIDE", "OFFICIAL", "RUNNER", "STUNT", "STUNTS", "STUNTMAN",
    "DECORATOR", "PROPS", "PROP", "SET", "STANDBY", "TABLE", "PERSON", "CASTING",
    "MANAGER", "PRODUKSIYON", "UNIT", "FOLEY", "MIXER", "RECORDIST", "BOOM",
}
HEAD_DIR = ("YONETMEN", "DIRECTED BY", "DIRECTOR", "YONETEN")
HEAD_PROD = ("YAPIMCI", "PRODUCED BY", "PRODUCER", "YAPIM", "EXECUTIVE PRODUCER")
HEAD_CAST = ("OYUNCULAR", "OYUNCU", "CAST", "STARRING", "OYNAYANLAR", "ROL DAGILIMI")
DIR_NOT = ("YARDIMCI", "ASSISTANT", "ASSOCIATE")
CORP_TOKENS = {"FILM", "FILMS", "PRODUCTION", "PRODUCTIONS", "PICTURES", "STUDIO", "STUDIOS",
               "ENTERTAINMENT", "MEDIA", "INC", "LLC", "LTD", "COMPANY", "DISNEY", "TV",
               "INTERNATIONAL", "GROUP", "CORP", "CORPORATION", "ASSOCIATES"}


def norm(s: str) -> str:
    s = (s or "").replace("ı", "i").replace("İ", "i")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_role_label(n: str) -> bool:
    return any(t in ROLE_TOKENS for t in n.split())


def is_company(n: str) -> bool:
    return any(t in CORP_TOKENS for t in n.split())


def is_all_caps(orig: str) -> bool:
    letters = [c for c in orig if c.isalpha()]
    return bool(letters) and all((not c.islower()) for c in letters)


def looks_like_name(n: str) -> bool:
    toks = n.split()
    return bool(n) and 1 <= len(toks) <= 4 and not is_role_label(n) and not is_company(n)


def load_turkish():
    given, sur = set(), set()
    try:
        import pandas as pd
        g = pd.read_csv(TR_GIVEN, usecols=["ascii_key"])
        given = set(str(x).upper() for x in g["ascii_key"].dropna())
        s = pd.read_csv(TR_SUR, usecols=["ascii_key"])
        sur = set(str(x).upper() for x in s["ascii_key"].dropna())
    except Exception:  # noqa: BLE001
        pass
    return given, sur


def imdb_professions(cands: list[str]) -> dict:
    """{normalize_edilmis_isim: set(meslekler)} — IMDB names tablosundan tek sorgu."""
    out: dict = {}
    uniq = sorted({c for c in cands if c})
    if not uniq:
        return out
    try:
        import duckdb
        con = duckdb.connect(IMDB_DB, read_only=True)
        con.execute("CREATE TEMP TABLE _c(k VARCHAR)")
        con.executemany("INSERT INTO _c VALUES (?)", [(c,) for c in uniq])
        rows = con.execute(
            "SELECT UPPER(strip_accents(primaryName)) k, primaryProfession p "
            "FROM names WHERE UPPER(strip_accents(primaryName)) IN (SELECT k FROM _c)"
        ).fetchall()
        for k, p in rows:
            out.setdefault(k, set()).update(x.strip() for x in (p or "").split(",") if x.strip())
        con.close()
    except Exception as exc:  # noqa: BLE001
        out["__error__"] = f"{type(exc).__name__}: {exc}"
    return out


def classify(lines: list[str], profile: str = "film") -> dict:
    given, sur = load_turkish()
    db_used = bool(given or sur)
    norms = [norm(l) for l in lines]

    cand_idx = [i for i, n in enumerate(norms) if looks_like_name(n)]
    prof = imdb_professions([norms[i] for i in cand_idx])
    imdb_err = prof.pop("__error__", None)
    imdb_used = bool(prof) or (imdb_err is None and len(cand_idx) > 0)

    def is_turkish_name(n):
        toks = n.split()
        return any(t in given for t in toks) and any(t in sur for t in toks) if len(toks) >= 2 else False

    def professions(n):
        return prof.get(n, set())

    # --- bolge: ilk crew-header'a kadar = kadro bolgesi ---
    crew_start = len(lines)
    for i, n in enumerate(norms):
        if any(h in n for h in HEAD_PROD) or (any(h in n for h in HEAD_DIR) and not any(d in n for d in DIR_NOT)) \
           or n in ("KURGU", "MUZIK", "GORUNTU YONETMENI", "SENARYO"):
            crew_start = i
            break

    # --- OYUNCULAR ---
    # Oyuncu = BUYUK-harf + >=2 token + (IMDB oyuncu VEYA Turkce isim VEYA kadro bolgesi),
    # sadece-crew meslegi olan ve Title-case karakter/tek-token gurultu HARIC.
    CREW_PROF = {"director", "producer", "writer", "composer", "cinematographer",
                 "editor", "production_designer", "casting_director"}
    oyuncular, seen = [], set()
    for i in cand_idx:
        n = norms[i]
        toks = n.split()
        if not is_all_caps(lines[i]) or len(toks) < 2:
            continue  # Title-case karakter / tek-token gurultu (2E, MAYFLOWER) -> oyuncu degil
        if is_role_label(n) or is_company(n):
            continue
        ps = professions(n)
        is_actor = ("actor" in ps or "actress" in ps)
        if ps and not is_actor and (ps & CREW_PROF):
            continue  # IMDB'de sadece crew -> oyuncu degil
        # Precision-first (fidelity: yanlis > eksik): DB-dogrulamasi sart.
        # IMDB oyuncu VEYA Turkce isim. (DB yoksa kadro-bolgesi forma duser.)
        if is_actor or is_turkish_name(n) or (not db_used and i < crew_start):
            if n not in seen:
                seen.add(n)
                oyuncular.append(lines[i].strip())

    # --- header-cipali yapimci/yonetmen (TAM-SATIR header; "ART DIRECTOR" gibi alt-rolleri yakalamaz) ---
    DIR_HEAD = {"DIRECTED BY", "YONETMEN", "YONETEN", "YONETMENI", "DIRECTOR", "FILM BY"}
    PROD_HEAD = {"PRODUCED BY", "YAPIMCI", "YAPIMCISI", "PRODUCER", "PRODUCERS", "YAPIM", "EXECUTIVE PRODUCER"}

    def names_after(head_set):
        res = []
        for i, n in enumerate(norms):
            if n in head_set:  # tam-satir header esitligi
                for j in range(i + 1, min(i + 4, len(lines))):
                    nj = norms[j]
                    if len(nj.split()) >= 2 and is_all_caps(lines[j]) and not is_role_label(nj) and not is_company(nj):
                        res.append(lines[j].strip())
                    if len(res) >= 3:
                        break
        return res

    yonetmen = names_after(DIR_HEAD)
    yapimci = names_after(PROD_HEAD)
    # Header bulunamazsa BOS birak + needs_review. Meslek-tabanli fallback cop uretiyordu
    # (2E / Jamie White) -> kaldirildi. Uydurmaktansa eksik birak (fidelity).

    def dd(xs):
        s, o = set(), []
        for x in xs:
            k = norm(x)
            if k and k not in s:
                s.add(k); o.append(x)
        return o
    oyuncular, yapimci, yonetmen = dd(oyuncular), dd(yapimci), dd(yonetmen)

    if profile.lower().startswith("film"):
        oyuncular_out = oyuncular[:8]
    else:
        oyuncular_out = oyuncular

    needs_review = []
    if len(oyuncular_out) < 3:
        needs_review.append("az oyuncu (<3)")
    if not yonetmen:
        needs_review.append("yonetmen bulunamadi")
    if len(lines) > 300:
        needs_review.append(f"cok satir ({len(lines)}) — scroll bloat")

    return {
        "oyuncular": oyuncular_out,
        "oyuncular_tum": len(oyuncular),
        "yapimci": yapimci[:3],
        "yonetmen": yonetmen[:3],
        "needs_review": needs_review,
        "db_used": {"turkish": db_used, "imdb": imdb_used, "imdb_error": imdb_err},
        "candidate_count": len(cand_idx),
        "crew_start_line": crew_start,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kunye", required=True)
    ap.add_argument("--profile", default="film")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    lines = [l.strip() for l in Path(args.kunye).read_text(encoding="utf-8", errors="ignore").splitlines()
             if l.strip() and not l.startswith("#")]
    res = classify(lines, args.profile)
    res["runtime_sec"] = round(time.perf_counter() - t0, 2)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
