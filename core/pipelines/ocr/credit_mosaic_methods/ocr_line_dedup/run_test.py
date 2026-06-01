"""Test runner for the OCR line-dedup credit mosaic engine.

Usage examples:

  # Run closing segment (default):
  python -m core.pipelines.ocr.credit_mosaic_methods.ocr_line_dedup.run_test

  # Explicit:
  python -m core.pipelines.ocr.credit_mosaic_methods.ocr_line_dedup.run_test \
      --item E:\MITAS\outputs\ocr_50films_aaaa_v21_paddle_20260525\items\1980_son_metro_end_credits \
      --segment closing \
      --out E:\MITAS\outputs\_mosaic_methods_compare_20260530\D_ocr_line_dedup\son_metro_closing

  # Also accepts an explicit frames directory (e.g. the higher-quality opening):
  python -m core.pipelines.ocr.credit_mosaic_methods.ocr_line_dedup.run_test \
      --item E:\MITAS\outputs\_sonmetro_best_20260530\items\1980_son_metro_wide \
      --segment opening \
      --out E:\MITAS\outputs\_mosaic_methods_compare_20260530\D_ocr_line_dedup\son_metro_opening
"""

import argparse
import sys
from pathlib import Path

# Allow running as a module from any cwd
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from core.pipelines.ocr.credit_mosaic_methods.ocr_line_dedup import engine


DEFAULT_ITEM = (
    r"E:\MITAS\outputs\ocr_50films_aaaa_v21_paddle_20260525\items\1980_son_metro_end_credits"
)
DEFAULT_OUT_BASE = r"E:\MITAS\outputs\_mosaic_methods_compare_20260530\D_ocr_line_dedup"


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR line-dedup credit mosaic test runner")
    parser.add_argument("--item", default=DEFAULT_ITEM, help="Item directory (contains unified/ + frames/)")
    parser.add_argument("--segment", default=None, choices=["opening", "closing"],
                        help="Segment to process. Default: auto-detect.")
    parser.add_argument("--out", default=None, help="Output directory. Default: auto under DEFAULT_OUT_BASE.")
    parser.add_argument("--stride", type=int, default=engine.FRAME_STRIDE,
                        help=f"OCR every Nth frame (default {engine.FRAME_STRIDE})")
    args = parser.parse_args()

    item_dir = Path(args.item)
    segment = args.segment

    # Auto-detect segment for output naming
    if args.out:
        out_dir = Path(args.out)
    else:
        seg_name = segment or "auto"
        out_dir = Path(DEFAULT_OUT_BASE) / f"son_metro_{seg_name}"

    print(f"[run_test] item_dir  = {item_dir}")
    print(f"[run_test] segment   = {segment or 'auto'}")
    print(f"[run_test] out_dir   = {out_dir}")
    print(f"[run_test] stride    = {args.stride}")
    print()

    result = engine.run(item_dir, out_dir, segment=segment, frame_stride=args.stride)

    print()
    print("=" * 60)
    print(f"  master.png : {result['master_path']}")
    print(f"  size       : {result['master_size'][0]} x {result['master_size'][1]} px")
    print(f"  unique lines: {result['unique_lines']}")
    print(f"  runtime    : {result['runtime_sec']} s")
    print(f"  debug.json : {result['debug_path']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
