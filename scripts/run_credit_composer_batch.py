"""10-film credit composer batch.

Reuses the existing, tested motion-state compositor
(core/pipelines/ocr/credit_motion_state_machine.compose_item_motion_blocks) which
stacks the pipeline's ready artifacts — unified/<segment>/cards/*.json (static cards)
and unified/<segment>/scroll/row_composite.png (scroll) — into ONE master PNG per film.

This replaces the ghosting pixel slit-scan engine for this deliverable. No new CV code.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from time import perf_counter

from PIL import Image

PROJECT_ROOT = Path(r"E:\MITAS")
sys.path.insert(0, str(PROJECT_ROOT))

from core.pipelines.ocr.credit_motion_state_machine import (  # noqa: E402
    MotionComposerConfig,
    compose_item_motion_blocks,
)

ITEMS = PROJECT_ROOT / "outputs" / "ocr_50films_aaaa_v21_paddle_20260525" / "items"
OUT_BASE = PROJECT_ROOT / "outputs" / "_credit_composer_10film_20260530"

# film_id -> item directory name under ITEMS
FILMS: list[tuple[str, str]] = [
    ("1980_son_metro",         "1980_son_metro_end_credits"),
    ("2000_x_men",             "2000_x_men_end_credits"),
    ("1997_jurassic_park2",    "1997_jurassic_park_2_kayip_dnya_end_credits"),
    ("1953_kizgin_silah",      "1953_kizgin_silah_end_credits"),
    ("1964_zengin_olsaydin",   "1964_zengin_olsaydin_end_credits"),
    ("1968_anjelik_ve_sultan", "1968_anjelik_ve_sultan_end_credits"),
    ("1999_cennetin_rengi",    "1999_cennetİn_rengİ_end_credits"),
    ("2003_franny",            "2003_franny_nİn_ayaklari_end_credits"),
    ("2017_pororoca",          "2017_pororoca_end_credits"),
    ("2025_robinson_crusoe",   "2025_robinson_crusoe_end_credits"),
]

PREVIEW_MAX_H = 2600  # vertical (never horizontal) downscale preview for quick viewing


def _vertical_preview(master_png: Path, dest: Path) -> tuple[int, int]:
    img = Image.open(master_png).convert("RGB")
    w, h = img.size
    if h > PREVIEW_MAX_H:
        scale = PREVIEW_MAX_H / h
        img = img.resize((max(1, int(w * scale)), PREVIEW_MAX_H), Image.LANCZOS)
    img.save(str(dest))
    return img.size


def main() -> None:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    summary = []
    for fid, item_name in FILMS:
        t0 = perf_counter()
        item_dir = ITEMS / item_name
        out_dir = OUT_BASE / fid
        rec: dict = {"film": fid, "status": "ok", "item_dir": str(item_dir)}
        try:
            if not (item_dir / "unified").exists():
                rec.update(status="no_unified")
                summary.append(rec)
                print(f"[{fid}] NO unified dir", flush=True)
                continue

            # (a) clean master
            clean = compose_item_motion_blocks(
                item_dir, out_dir,
                config=MotionComposerConfig(target_width=600, draw_labels=False),
            )
            # (b) labeled debug master
            compose_item_motion_blocks(
                item_dir, out_dir / "debug_labeled",
                config=MotionComposerConfig(target_width=600, draw_labels=True),
            )

            master = Path(clean["output_png"])
            pw, ph = _vertical_preview(master, out_dir / "master_preview_vertical.png")
            rec.update(
                master_png=str(master),
                preview=str(out_dir / "master_preview_vertical.png"),
                kept=clean["kept_count"],
                skipped=clean["skipped_count"],
                by_segment=clean["by_segment"],
                render=clean["render"],
                preview_size=[pw, ph],
                sec=round(perf_counter() - t0, 1),
            )
            r = clean["render"]
            bs = clean["by_segment"]
            print(f"[{fid}] master {r['width']}x{r['height']}  kept={clean['kept_count']} "
                  f"skip={clean['skipped_count']}  open={bs['opening']} close={bs['closing']} "
                  f"{rec['sec']}s", flush=True)
        except Exception as exc:
            rec.update(status="error", error=str(exc))
            print(f"[{fid}] ERROR {exc}", flush=True)
            traceback.print_exc()
        summary.append(rec)

    (OUT_BASE / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== DONE ===", flush=True)
    for r in summary:
        if r["status"] == "ok":
            rr = r["render"]
            print(f"  {r['film']:24s} {rr['width']}x{rr['height']:5d}  "
                  f"kept={r['kept']:3d} skip={r['skipped']:3d}", flush=True)
        else:
            print(f"  {r['film']:24s} {r['status']}", flush=True)
    print(f"\nÇıktı: {OUT_BASE}", flush=True)


if __name__ == "__main__":
    main()
