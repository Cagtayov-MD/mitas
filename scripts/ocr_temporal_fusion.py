"""CLI for OCR temporal fusion (K-3 median, K-4 variance masking)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.pipelines.ocr.temporal_fusion import (
    run_temporal_median_fusion,
    run_temporal_variance_masking,
)


def _collect_frames(frames_arg: str | None, frames_dir_arg: str | None) -> list[Path]:
    if frames_arg:
        return [Path(p.strip()) for p in frames_arg.split(",") if p.strip()]
    if frames_dir_arg:
        directory = Path(frames_dir_arg)
        paths = sorted(directory.glob("*.png")) + sorted(directory.glob("*.jpg"))
        return paths
    raise SystemExit("Either --frames or --frames-dir is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run temporal fusion (K-3 median or K-4 variance masking) on a frame set",
    )
    parser.add_argument(
        "--strategy",
        choices=("median", "variance", "auto"),
        default="auto",
        help="median=K-3 (static BG), variance=K-4 (moving BG), auto=run both",
    )
    parser.add_argument("--frames", default=None, help="Comma-separated frame paths")
    parser.add_argument("--frames-dir", default=None, help="Directory of *.png/*.jpg frames (sorted)")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument(
        "--low-var-quantile",
        type=float,
        default=0.30,
        help="K-4 only: pixels with variance ≤ this quantile are kept as static text",
    )
    args = parser.parse_args(argv)

    frames = _collect_frames(args.frames, args.frames_dir)
    output_dir = Path(args.output_dir)

    results: dict[str, dict[str, str]] = {}

    if args.strategy in ("median", "auto"):
        median_result = run_temporal_median_fusion(
            frame_paths=frames,
            output_dir=output_dir / "median" if args.strategy == "auto" else output_dir,
            max_frames=args.max_frames,
        )
        results["median"] = {
            "strategy": median_result.strategy,
            "output_path": str(median_result.output_path),
            "summary_path": str(median_result.summary_path),
        }

    if args.strategy in ("variance", "auto"):
        variance_result = run_temporal_variance_masking(
            frame_paths=frames,
            output_dir=output_dir / "variance" if args.strategy == "auto" else output_dir,
            max_frames=args.max_frames,
            low_var_quantile=args.low_var_quantile,
        )
        results["variance"] = {
            "strategy": variance_result.strategy,
            "output_path": str(variance_result.output_path),
            "summary_path": str(variance_result.summary_path),
        }

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
