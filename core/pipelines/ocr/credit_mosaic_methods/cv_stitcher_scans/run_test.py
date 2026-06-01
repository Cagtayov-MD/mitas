"""
run_test.py — CLI test harness for cv_stitcher_scans/engine.py

Usage
-----
python run_test.py --frames-dir <path> --out-dir <path> [--stride N]
                   [--chunk-size N] [--reg-resol F] [--conf-thresh F]
                   [--diff-threshold F] [--min-stable-frames N]

Example
-------
python run_test.py \
    --frames-dir "E:/MITAS/outputs/_sonmetro_best_20260530/items/1980_son_metro_wide/frames/opening" \
    --out-dir "E:/MITAS/outputs/_mosaic_methods_compare_20260530/C_cv_stitcher_scans/son_metro_opening"
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script from any cwd
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))  # repo root

from core.pipelines.ocr.credit_mosaic_methods.cv_stitcher_scans.engine import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CV Stitcher SCANS credit mosaic baseline"
    )
    parser.add_argument(
        "--frames-dir", required=True, help="Directory of ordered PNG frames"
    )
    parser.add_argument(
        "--out-dir", required=True, help="Output directory for master.png + debug.json"
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=None,
        help="Frame stride for scroll mode (None = auto from motion estimate)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=15,
        help="Frames per chunk in fallback chunk-stitching mode (default: 15)",
    )
    parser.add_argument(
        "--reg-resol",
        type=float,
        default=0.6,
        help="Stitcher registration resolution (default: 0.6)",
    )
    parser.add_argument(
        "--conf-thresh",
        type=float,
        default=0.3,
        help="Stitcher panorama confidence threshold (default: 0.3)",
    )
    parser.add_argument(
        "--diff-threshold",
        type=float,
        default=3.0,
        help="Frame diff threshold for card boundary detection (default: 3.0)",
    )
    parser.add_argument(
        "--min-stable-frames",
        type=int,
        default=5,
        help="Min frames to count a run as a stable card (default: 5)",
    )
    args = parser.parse_args()

    print(f"[cv_stitcher_scans] frames-dir : {args.frames_dir}")
    print(f"[cv_stitcher_scans] out-dir    : {args.out_dir}")
    print(f"[cv_stitcher_scans] stride     : {args.stride}")

    result = run(
        frames_dir=args.frames_dir,
        out_dir=args.out_dir,
        stride=args.stride,
        chunk_size=args.chunk_size,
        registration_resol=args.reg_resol,
        confidence_thresh=args.conf_thresh,
        min_stable_frames=args.min_stable_frames,
        diff_threshold=args.diff_threshold,
    )

    print("\n--- Result ---")
    # ensure_ascii=True to avoid Windows cp1254 codec issues on arrows/special chars
    print(json.dumps(result, indent=2, ensure_ascii=True))

    if result.get("master_path"):
        print("\nmaster.png : " + str(result["master_path"]))
        dims = result.get("dims", {})
        print("dims       : {}x{} px".format(dims.get("width"), dims.get("height")))
    status = result.get("stitch_status", "")
    print("stitch_status : " + status.encode("ascii", "replace").decode("ascii"))
    print("mode          : " + str(result.get("mode")))
    print("runtime_s     : " + str(result.get("runtime_s")))


if __name__ == "__main__":
    main()
