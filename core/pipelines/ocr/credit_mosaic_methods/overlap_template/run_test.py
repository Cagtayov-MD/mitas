"""
run_test.py — CLI test runner for the overlap-template mosaic engine.

Usage:
    python run_test.py --frames-dir /path/to/frames --out-dir /path/to/out
    python run_test.py --frames-dir /path/to/frames --out-dir /path/to/out --stride 2
    python run_test.py --frames-dir /path/to/frames --out-dir /path/to/out --stride 1

Globs frame_*.png (or *.png) sorted numerically.
"""

import argparse
import glob
import os
import sys
import re

# Allow running from anywhere in the repo
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from core.pipelines.ocr.credit_mosaic_methods.overlap_template import engine


def _sort_key(path: str) -> int:
    """Extract leading integer from filename for numeric sort."""
    m = re.search(r"(\d+)", os.path.basename(path))
    return int(m.group(1)) if m else 0


def main():
    parser = argparse.ArgumentParser(
        description="Overlap-template credit mosaic engine test runner"
    )
    parser.add_argument(
        "--frames-dir", required=True,
        help="Directory containing frame_*.png files"
    )
    parser.add_argument(
        "--out-dir", required=True,
        help="Output directory for master.png and debug.json"
    )
    parser.add_argument(
        "--stride", type=int, default=1,
        help="Process every N-th frame (default=1, all frames)"
    )
    args = parser.parse_args()

    frames_dir = args.frames_dir
    out_dir = args.out_dir
    stride = args.stride

    # Glob frames
    pattern1 = os.path.join(frames_dir, "frame_*.png")
    pattern2 = os.path.join(frames_dir, "*.png")

    frames = sorted(glob.glob(pattern1), key=_sort_key)
    if not frames:
        frames = sorted(glob.glob(pattern2), key=_sort_key)

    if not frames:
        print(f"ERROR: No PNG frames found in {frames_dir}")
        sys.exit(1)

    print(f"Found {len(frames)} frames in {frames_dir}")
    print(f"Output -> {out_dir}")
    print(f"Stride = {stride}")
    print()

    result = engine.run(frames=frames, out_dir=out_dir, stride=stride, verbose=True)

    print()
    print("=" * 60)
    print("RESULT SUMMARY")
    print("=" * 60)
    print(f"Master PNG : {result.master_path}")
    print(f"Dimensions : {result.width} x {result.height} px")
    print(f"Sections   : {len(result.sections)}")
    print(f"Runtime    : {result.runtime_s:.1f}s")
    print(f"Debug JSON : {result.debug_path}")
    print()
    print("Sections:")
    for i, s in enumerate(result.sections):
        span = s['canvas_y_end'] - s['canvas_y_start']
        print(f"  [{i:2d}] frames {s['start_frame']:5d}-{s['end_frame']:5d} "
              f"canvas y={s['canvas_y_start']:6d}-{s['canvas_y_end']:6d} "
              f"({span}px) [{s['event']}]")


if __name__ == "__main__":
    main()
