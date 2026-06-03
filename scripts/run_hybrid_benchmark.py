"""
Run hybrid router on all 10 benchmark films x {opening, closing}.
Saves:
  - master.png  (full-res)
  - preview.png (downscaled vertical, max 800px wide, max 2400px tall)
  - crop_top.png + crop_mid.png  (full-res crops for tall masters)
  - router_debug.json
Prints a routing table at the end.
"""
import os
import sys
import time
import json

import cv2
import numpy as np

sys.path.insert(0, r"E:\MITAS")

from core.pipelines.ocr.credit_mosaic_methods.hybrid_router import engine as router

ITEMS_BASE = r"E:\MITAS\outputs\ocr_50films_aaaa_v21_paddle_20260525\items"
OUT_BASE   = r"E:\MITAS\outputs\_mosaic_methods_compare_20260530\_benchmark_hybrid"
PREVIEW_W  = 800
PREVIEW_MAX_H = 2400

FILMS = [
    "1980_son_metro_end_credits",
    "2000_x_men_end_credits",
    "1997_jurassic_park_2_kayip_dnya_end_credits",
    "1953_kizgin_silah_end_credits",
    "1964_zengin_olsaydin_end_credits",
    "1968_anjelik_ve_sultan_end_credits",
    "1999_cennetİn_rengİ_end_credits",
    "2003_franny_nİn_ayaklari_end_credits",
    "2017_pororoca_end_credits",
    "2025_robinson_crusoe_end_credits",
]
SEGMENTS = ["opening", "closing"]


def _imread(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _imwrite(path, img):
    ext = os.path.splitext(path)[1].lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(path)


def make_preview(master_path, out_dir):
    """Downscale master to preview. For tall images also save 2 full-res crops."""
    img = _imread(master_path)
    if img is None:
        return
    h, w = img.shape[:2]
    scale = min(PREVIEW_W / w, PREVIEW_MAX_H / h, 1.0)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    preview = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    _imwrite(os.path.join(out_dir, "preview.png"), preview)

    # Full-res crops if tall
    if h > 1000:
        crop_h = min(600, h // 3)
        top_crop = img[:crop_h, :]
        _imwrite(os.path.join(out_dir, "crop_top.png"), top_crop)
        mid_y = max(0, h // 2 - crop_h // 2)
        mid_crop = img[mid_y:mid_y + crop_h, :]
        _imwrite(os.path.join(out_dir, "crop_mid.png"), mid_crop)


rows = []
total_t0 = time.time()

for film in FILMS:
    for seg in SEGMENTS:
        item_dir = os.path.join(ITEMS_BASE, film)
        if not os.path.isdir(item_dir):
            print(f"[SKIP] missing: {item_dir}")
            rows.append({"film": film, "seg": seg, "status": "MISSING"})
            continue

        out_dir = os.path.join(OUT_BASE, f"{film}_{seg}")
        os.makedirs(out_dir, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  {film}  {seg}")
        print(f"{'='*60}")
        try:
            result = router.run(item_dir, out_dir, segment=seg)
            make_preview(result["master_path"], out_dir)
            sz = result["master_size"]
            rows.append({
                "film": film,
                "seg": seg,
                "style": result["style"],
                "engine": result["engine_used"],
                "w": sz[0], "h": sz[1],
                "runtime": result["runtime_sec"],
                "status": "OK",
            })
            print(f"  -> style={result['style']}  engine={result['engine_used']}  "
                  f"size={sz[0]}x{sz[1]}  t={result['runtime_sec']}s")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            rows.append({"film": film, "seg": seg, "status": f"ERROR: {exc}"})

total_t = time.time() - total_t0

# Save table
os.makedirs(OUT_BASE, exist_ok=True)
table_path = os.path.join(OUT_BASE, "routing_table.json")
with open(table_path, "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=2, ensure_ascii=False)

print("\n\n" + "=" * 80)
print("ROUTING TABLE")
print("=" * 80)
fmt = "{:<45} {:<10} {:<15} {:<20} {:<12} {:<6}"
print(fmt.format("FILM", "SEG", "STYLE", "ENGINE", "SIZE", "TIME"))
print("-" * 80)
for r in rows:
    if r.get("status") == "OK":
        print(fmt.format(
            r["film"][:44], r["seg"],
            r.get("style", "?"),
            r.get("engine", "?")[:19],
            f"{r.get('w',0)}x{r.get('h',0)}",
            f"{r.get('runtime',0):.1f}s",
        ))
    else:
        print(fmt.format(r["film"][:44], r["seg"], "", "", "", r.get("status","?")))
print(f"\nTotal time: {total_t:.1f}s")
print(f"Table saved: {table_path}")
