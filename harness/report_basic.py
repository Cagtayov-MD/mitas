# -*- coding: utf-8 -*-
"""report_basic.py — state/*.json'dan LLM'siz deterministik raporlar (garanti çıktı).
Zengin Sonnet-5 analizinden BAĞIMSIZ; her koşulda temel raporlar üretilir.
"""
import glob, json, os, sys
from pathlib import Path

RUN = Path(os.environ.get("MITAS_RUN_ROOT", "/opt/mitas/candidate_runs/kunye51_20260714"))
REP = RUN / "reports"; REP.mkdir(parents=True, exist_ok=True)


def load():
    out = []
    for p in sorted(glob.glob(str(RUN / "state" / "*.json"))):
        try:
            out.append(json.load(open(p, encoding="utf-8")))
        except Exception as e:
            out.append({"film_id": Path(p).stem, "_load_err": str(e)})
    return out


def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
        if d is None:
            return default
    return d


def short(fid): return fid[-40:]


def stage1(states):
    rows, npass, nfail, open_empty, early = [], 0, 0, 0, 0
    for s in states:
        s1 = s.get("stage1") or {}
        st = s1.get("status", "-")
        cp = g(s1, "cikis_pool", "pool_frames", default=0) or 0
        gp = g(s1, "giris_pool", "pool_frames", default=0) or 0
        rows.append((st, short(s["film_id"]),
                     round((g(s1, "probe", "duration_s", default=0) or 0)/60),
                     s1.get("giris_frames", "-"), s1.get("cikis_frames", "-"),
                     g(s1, "cikis_pool", "status", default="-"),
                     g(s1, "cikis_pool", "start_pos", default="-"),
                     cp, gp, st, s1.get("root_cause") or ""))
        if st == "pass": npass += 1
        elif st == "fail": nfail += 1
        if gp == 0: open_empty += 1
        if cp >= 880: early += 1
    rows.sort(key=lambda r: (r[0] != "fail", r[7]))  # fail üstte, sonra çıkış havuz artan
    md = [f"# Aşama-1 (Nezih Havuz) Raporu — Temel\n",
          f"**{len(states)} film · {npass} temiz geçti (kapanış havuzu doldu), {nfail} başarısız.** "
          f"Giriş havuzu boş (opening_paddle_empty): {open_empty}. Kapanış havuz≥880 (erken-tespit şüphesi): {early}.\n",
          "| film | süre(dk) | giriş kare | çıkış kare | detection | start_pos | çıkış havuz | giriş havuz | S1 | root_cause |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} | {r[8]} | {r[9]} | {r[10]} |")
    (REP / "stage1_basic.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return npass, nfail


def stage2(states):
    rows, npass, no_c, no_g = [], 0, 0, 0
    for s in states:
        s2 = s.get("stage2") or {}
        if not s2:
            continue
        st = s2.get("status", "-")
        ch = g(s2, "segments", "cikis", "reading", "h", default=0) or 0
        gh = g(s2, "segments", "giris", "reading", "h", default=0) or 0
        flags = g(s2, "manifest", default={}) or {}
        fl = flags.get("flags") if isinstance(flags, dict) else None
        rows.append((st, short(s["film_id"]), gh, ch, str(fl or ""), st, s2.get("root_cause") or ""))
        if st == "pass": npass += 1
        if not ch: no_c += 1
        if not gh: no_g += 1
    rows.sort(key=lambda r: (r[0] != "fail", r[3]))
    md = [f"# Aşama-2 (Master PNG) Raporu — Temel\n",
          f"**{len(rows)} film işlendi · {npass} pass.** Çıkış master yok: {no_c}. Giriş master yok: {no_g}.\n",
          "| film | giriş master h | çıkış master h | flags | S2 | root_cause |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |")
    (REP / "stage2_basic.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return npass


def stage3(states):
    # model bazında agregasyon + film×model matris
    models = {}
    matrix = []
    for s in states:
        mm = g(s, "stage3", "models", default={}) or {}
        row = {"film": short(s["film_id"])}
        for name, v in mm.items():
            row[name] = v
            d = models.setdefault(name, {"lines": 0, "unread": 0, "n": 0, "secs": 0.0, "readable": 0, "err": 0})
            if v.get("status") == "ok":
                d["lines"] += v.get("lines_total", 0) or 0
                ur = v.get("unreadable_rate")
                if ur is not None:
                    d["unread"] += ur; d["n"] += 1
                d["secs"] += v.get("secs", 0) or 0
                if (v.get("lines_total", 0) or 0) > 0: d["readable"] += 1
            else:
                d["err"] += 1
        matrix.append(row)
    md = [f"# Aşama-3 (VL Okuma) Bench Raporu — Temel (GT'siz)\n",
          f"**{len(models)} model × {len(states)} film.**\n",
          "## Model Liderlik Tablosu",
          "| model | Σ satır | ort [okunamadı]% | ort süre/film(s) | ≥1 okunabilir film | hata |",
          "|---|---|---|---|---|---|"]
    lead = []
    for name, d in models.items():
        avg_ur = round(100*d["unread"]/d["n"], 1) if d["n"] else None
        avg_s = round(d["secs"]/max(1, d["readable"] + d["err"]), 1)
        lead.append((d["lines"], name, avg_ur, avg_s, d["readable"], d["err"]))
        md.append(f"| {name} | {d['lines']} | {avg_ur} | {avg_s} | {d['readable']} | {d['err']} |")
    md.append("\n## Film × Model matris ([okunamadı]% / Σsatır)\n")
    mnames = list(models.keys())
    md.append("| film | " + " | ".join(mnames) + " |")
    md.append("|---|" + "|".join(["---"]*len(mnames)) + "|")
    for row in matrix:
        cells = []
        for n in mnames:
            v = row.get(n)
            if isinstance(v, dict) and v.get("status") == "ok":
                cells.append(f"{round((v.get('unreadable_rate') or 0)*100)}% / {v.get('lines_total','-')}")
            else:
                cells.append("-")
        md.append(f"| {row['film']} | " + " | ".join(cells) + " |")
    (REP / "stage3_bench_basic.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return list(models.keys())


def main():
    states = load()
    p1, f1 = stage1(states)
    p2 = stage2(states)
    m3 = stage3(states)
    summary = {"films": len(states), "stage1_pass": p1, "stage1_fail": f1,
               "stage2_pass": p2, "stage3_models": m3}
    (REP / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
