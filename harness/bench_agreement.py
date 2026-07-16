# -*- coding: utf-8 -*-
"""bench_agreement.py — GT'siz VL bench çekirdek metriği: model-vs-model uzlaşı.

Her film için her modelin dilim_vl__<model>.json transkript satırlarını normalize edip
küme yapar; model çiftleri arası Jaccard + model başına:
  - agreement: diğer modellerle ort Jaccard (yüksek = tutarlı okuma)
  - coverage: tüm-model birleşimindeki satırların ne kadarını yakaladı (recall proxy)
  - consensus_precision: kendi satırlarının ≥1 başka modelce doğrulanan oranı (halüsinasyon-tersi)
Çıktı: reports/bench_agreement.json
"""
import glob, json, os, re, unicodedata
from itertools import combinations
from pathlib import Path

RUN = Path(os.environ.get("MITAS_RUN_ROOT", "/opt/mitas/candidate_runs/kunye51_20260714"))
REP = RUN / "reports"; REP.mkdir(parents=True, exist_ok=True)
SKIP = {"[okunamadı]", "[yazı yok]", "[okunamadi]"}


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().replace("İ", "I").replace("I", "I")
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return " ".join(s.split())


def lineset(transcript):
    """Transkript satırlarını normalize et; isim/kredi-benzeri (>=2 harf-grubu, >=4 krktr) tut."""
    out = set()
    for l in transcript:
        if not isinstance(l, str) or l.strip() in SKIP:
            continue
        n = norm(l)
        if len(n) >= 4 and len(n.split()) >= 1 and re.search(r"[A-Z]", n):
            out.add(n)
    return out


def jacc(a, b):
    if not a and not b:
        return None
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main():
    # her film -> {model: lineset}
    films = {}
    model_names = set()
    for sd in sorted(glob.glob(str(RUN / "Database" / "*"))):
        md = Path(sd) / "master_dilim"
        if not md.is_dir():
            continue
        fid = Path(sd).name
        per = {}
        for vj in md.glob("dilim_vl__*.json"):
            model = vj.name[len("dilim_vl__"):-5]
            try:
                d = json.loads(vj.read_text(encoding="utf-8"))
            except Exception:
                continue
            ls = set()
            for part in d.get("parts", []):
                ls |= lineset(part.get("transcript", []))
            per[model] = ls
            model_names.add(model)
        if per:
            films[fid] = per
    models = sorted(model_names)

    # per-model agregasyon
    agg = {m: {"films": 0, "lines": 0, "agree_sum": 0.0, "agree_n": 0,
               "cover_sum": 0.0, "cover_n": 0, "prec_sum": 0.0, "prec_n": 0} for m in models}
    pair_j = {f"{a}|{b}": [] for a, b in combinations(models, 2)}
    per_film = {}

    for fid, per in films.items():
        present = [m for m in per if per[m]]
        union = set().union(*[per[m] for m in present]) if present else set()
        row = {}
        for m in present:
            ls = per[m]
            agg[m]["films"] += 1
            agg[m]["lines"] += len(ls)
            # coverage
            if union:
                agg[m]["cover_sum"] += len(ls & union) / len(union); agg[m]["cover_n"] += 1
            # consensus precision: bu modelin satırı, başka >=1 modelde de var mı
            others = set().union(*[per[o] for o in present if o != m]) if len(present) > 1 else set()
            if ls:
                agg[m]["prec_sum"] += len(ls & others) / len(ls); agg[m]["prec_n"] += 1
            # agreement: diğer modellerle ort jaccard
            js = [jacc(ls, per[o]) for o in present if o != m]
            js = [x for x in js if x is not None]
            if js:
                agg[m]["agree_sum"] += sum(js)/len(js); agg[m]["agree_n"] += 1
            row[m] = {"lines": len(ls)}
        for a, b in combinations(present, 2):
            j = jacc(per[a], per[b])
            if j is not None:
                pair_j[f"{a}|{b}"].append(j) if f"{a}|{b}" in pair_j else pair_j.setdefault(f"{b}|{a}", []).append(j)
        per_film[fid] = row

    def avg(s, n): return round(s/n, 3) if n else None
    leaderboard = []
    for m in models:
        a = agg[m]
        leaderboard.append({
            "model": m, "films": a["films"], "total_lines": a["lines"],
            "agreement": avg(a["agree_sum"], a["agree_n"]),
            "coverage": avg(a["cover_sum"], a["cover_n"]),
            "consensus_precision": avg(a["prec_sum"], a["prec_n"]),
        })
    leaderboard.sort(key=lambda x: (-(x["consensus_precision"] or 0), -(x["coverage"] or 0)))
    pairs = {k: round(sum(v)/len(v), 3) for k, v in pair_j.items() if v}
    out = {"models": models, "n_films": len(films), "leaderboard": leaderboard,
           "pairwise_agreement": pairs}
    (REP / "bench_agreement.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"models": len(models), "films": len(films),
                      "leaderboard": [(l["model"], l["consensus_precision"], l["coverage"]) for l in leaderboard]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
