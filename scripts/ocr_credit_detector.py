"""CLI for scanning video segments for likely credits."""

from __future__ import annotations

import argparse
import json

from core.pipelines.ocr.credit_detector import detect_credit_segments


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect likely credit windows and scroll/static behavior")
    parser.add_argument("--video", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-seconds", type=float, default=0.0)
    parser.add_argument("--end-seconds", type=float, default=None)
    parser.add_argument("--window-seconds", type=float, default=10.0)
    parser.add_argument("--stride-seconds", type=float, default=None)
    parser.add_argument("--sample-fps", type=float, default=2.0)
    parser.add_argument("--score-threshold", type=float, default=0.42)
    args = parser.parse_args(argv)

    result = detect_credit_segments(
        args.video,
        output_dir=args.output_dir,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
        window_seconds=args.window_seconds,
        stride_seconds=args.stride_seconds,
        sample_fps=args.sample_fps,
        score_threshold=args.score_threshold,
    )
    print(json.dumps({"output_path": str(result.output_path), "segments": [segment.to_dict() for segment in result.segments]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
