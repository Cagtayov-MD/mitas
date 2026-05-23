"""CLI for the MITAS OCR credit/KJ experiment runner."""

from __future__ import annotations

import argparse
import json

from core.pipelines.ocr.credit_experiment import DEFAULT_ENGINES, run_credit_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MITAS OCR credit/KJ experiments")
    parser.add_argument("--manifest", required=True, help="JSON manifest with video segments to process")
    parser.add_argument("--output-dir", required=True, help="Directory where experiment outputs will be written")
    parser.add_argument(
        "--engines",
        default=",".join(DEFAULT_ENGINES),
        help="Comma-separated OCR engines. Default: paddle,oneocr,tesseract",
    )
    parser.add_argument("--fps", type=float, default=None, help="Override frame sampling rate for every segment")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional cap for extracted frames per item")
    parser.add_argument(
        "--preprocess-mode",
        choices=["auto", "off", "always"],
        default="auto",
        help="Control 2x/inverted preprocessing. Default: auto",
    )
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Allow OCR engines to download first-run model files for this experiment",
    )
    args = parser.parse_args(argv)

    engines = [part.strip() for part in args.engines.split(",") if part.strip()]
    result = run_credit_experiment(
        args.manifest,
        output_dir=args.output_dir,
        engines=engines,
        fps=args.fps,
        max_frames=args.max_frames,
        preprocess_mode=args.preprocess_mode,
        allow_model_download=args.allow_model_download,
    )
    print(json.dumps({"summary_path": str(result.summary_path), "report_path": str(result.report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
