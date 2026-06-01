"""Test runner for the hybrid router credit mosaic engine.

Usage examples:

  # Run closing segment of a film:
  python -m core.pipelines.ocr.credit_mosaic_methods.hybrid_router.run_test \
      --item E:\MITAS\outputs\ocr_50films_aaaa_v21_paddle_20260525\items\1980_son_metro_end_credits \
      --segment closing \
      --out E:\MITAS\outputs\_mosaic_methods_compare_20260530\_benchmark_hybrid\son_metro_closing

  # Default (son_metro closing) if no args supplied:
  python -m core.pipelines.ocr.credit_mosaic_methods.hybrid_router.run_test
"""

import argparse
import sys
from pathlib import Path

# Allow running as a module from any cwd
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from core.pipelines.ocr.credit_mosaic_methods.hybrid_router import engine

DEFAULT_ITEM = (
    r"E:\MITAS\outputs\ocr_50films_aaaa_v21_paddle_20260525\items\1980_son_metro_end_credits"
)
DEFAULT_SEGMENT = "closing"
DEFAULT_OUT_BASE = r"E:\MITAS\outputs\_mosaic_methods_compare_20260530\_benchmark_hybrid"


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid router credit mosaic test runner")
    parser.add_argument(
        "--item", default=DEFAULT_ITEM,
        help="Item directory (contains frames/<segment>/ and unified/)",
    )
    parser.add_argument(
        "--segment", default=DEFAULT_SEGMENT,
        choices=["opening", "closing"],
        help="Segment to process (default: closing)",
    )
    parser.add_argument(
        "--out", default=None,
        help="Output directory. Default: auto under DEFAULT_OUT_BASE/<item_name>_<segment>.",
    )
    args = parser.parse_args()

    item_dir = Path(args.item)
    segment = args.segment

    if args.out:
        out_dir = Path(args.out)
    else:
        out_dir = Path(DEFAULT_OUT_BASE) / f"{item_dir.name}_{segment}"

    print(f"[hybrid_router run_test] item_dir = {item_dir}")
    print(f"[hybrid_router run_test] segment  = {segment}")
    print(f"[hybrid_router run_test] out_dir  = {out_dir}")
    print()

    result = engine.run(item_dir, out_dir, segment=segment)

    print()
    print("=" * 60)
    print(f"  master.png  : {result['master_path']}")
    print(f"  size        : {result['master_size'][0]} x {result['master_size'][1]} px")
    print(f"  style       : {result['style']}")
    print(f"  engine_used : {result['engine_used']}")
    print(f"  runtime_sec : {result['runtime_sec']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
