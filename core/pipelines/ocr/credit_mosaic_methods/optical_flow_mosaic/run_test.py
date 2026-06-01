"""Test runner for optical_flow_mosaic engine.

Usage:
    python run_test.py --frames-dir PATH --out-dir PATH [--fps N] [--max-frames N]

Example:
    python run_test.py \\
        --frames-dir "E:/MITAS/outputs/_sonmetro_best_20260530/items/1980_son_metro_wide/frames/opening" \\
        --out-dir    "E:/MITAS/outputs/_mosaic_methods_compare_20260530/B_optical_flow/son_metro_opening"
"""

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Optical-flow credit mosaic test runner")
    parser.add_argument("--frames-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--fps", type=float, default=6.0)
    parser.add_argument("--max-frames", type=int, default=0,
                        help="Process only first N frames (0 = all)")
    args = parser.parse_args()

    frames_dir: Path = args.frames_dir
    if not frames_dir.exists():
        print(f"ERROR: frames-dir does not exist: {frames_dir}", file=sys.stderr)
        sys.exit(1)

    frames = sorted(frames_dir.glob("*.png")) + sorted(frames_dir.glob("*.jpg"))
    frames = sorted(set(frames))
    if not frames:
        print(f"ERROR: no PNG/JPG frames found in {frames_dir}", file=sys.stderr)
        sys.exit(1)

    if args.max_frames > 0:
        frames = frames[: args.max_frames]

    print(f"[run_test] frames_dir : {frames_dir}")
    print(f"[run_test] out_dir    : {args.out_dir}")
    print(f"[run_test] n_frames   : {len(frames)}")

    # Import engine (handle running from any cwd)
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here.parent.parent.parent.parent.parent))  # up to E:\MITAS

    from core.pipelines.ocr.credit_mosaic_methods.optical_flow_mosaic.engine import run

    result = run(frames, args.out_dir, source_fps=args.fps, verbose=True)

    print(f"\n[run_test] DONE")
    print(f"  master  : {result.master_path}")
    print(f"  debug   : {result.debug_path}")
    print(f"  size    : {result.canvas_size[0]}x{result.canvas_size[1]} px")
    print(f"  static  : {result.n_static_blocks}")
    print(f"  scroll  : {result.n_scroll_sections}")
    print(f"  cuts    : {result.n_cut_events}")
    print(f"  runtime : {result.runtime_sec}s")


if __name__ == "__main__":
    main()
