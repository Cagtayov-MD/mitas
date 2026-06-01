"""Scan all scroll row_reconstruct_summary.json -> dark_ratio + quality.
Low dark_ratio = bright/textured bg = moving-footage candidate (type 3).
High dark_ratio (~0.9+) = black bg scroll (type 1, slit-scan territory)."""
import json, glob
from pathlib import Path

base = r"E:/MITAS/outputs/ocr_50films_aaaa_v21_paddle_20260525/items"
bench = ["1980_son_metro", "2000_x_men", "1997_jurassic_park_2", "1953_kizgin_silah",
         "1964_zengin_olsaydin", "1968_anjelik_ve_sultan", "1999_cennet", "2003_franny",
         "2017_pororoca", "2025_robinson_crusoe"]

rows = []
for f in glob.glob(base + r"/*/unified/*/scroll/row_reconstruct_summary.json"):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    p = Path(f)
    item = p.parents[3].name
    seg = p.parents[1].name
    ff = d.get("frame_filter", {})
    dr = ff.get("median_dark_ratio")
    q = d.get("quality", {})
    mo = d.get("motion", {})
    sz = d.get("composite_size")
    bm = any(b in item for b in bench)
    rows.append((dr, item, seg, q.get("score"), q.get("ghost_penalty"),
                 q.get("text_density"), mo.get("median_dy_per_frame"), d.get("row_count"), sz, bm))

rows.sort(key=lambda r: (r[0] is None, r[0] if r[0] is not None else 9))
print("dark  |bench| film / seg                              | qscore ghost  tdens | dy      rows size")
print("-" * 115)
for dr, item, seg, sc, gh, td, dy, rc, sz, bm in rows:
    tag = "BNCH" if bm else "    "
    drs = f"{dr:.3f}" if dr is not None else "None "
    print(f"{drs} |{tag} | {item[:38]:38} {seg:7} | {sc}  {gh}  {td} | {dy} {rc} {sz}")
