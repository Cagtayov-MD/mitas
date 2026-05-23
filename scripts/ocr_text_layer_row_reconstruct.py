"""CLI for OCR text-layer row reconstruction."""

from __future__ import annotations

import argparse
import json

from core.pipelines.ocr.text_layer_row_reconstruct import run_text_layer_row_reconstruct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build row crops from a vertically scrolling OCR item")
    parser.add_argument("--item-dir", default=None, help="Experiment item directory containing frames/ or frame_ocr.json")
    parser.add_argument("--frames", default=None, help="Comma-separated frame paths. Used when --item-dir is omitted")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--max-frames", type=int, default=180)
    parser.add_argument("--scale-for-rows", type=int, default=2)
    args = parser.parse_args(argv)

    frame_paths = [part.strip() for part in args.frames.split(",") if part.strip()] if args.frames else None
    result = run_text_layer_row_reconstruct(
        args.item_dir,
        frame_paths=frame_paths,
        output_dir=args.output_dir,
        max_frames=args.max_frames,
        scale_for_rows=args.scale_for_rows,
    )
    print(
        json.dumps(
            {
                "summary_path": str(result.summary_path),
                "report_path": str(result.report_path),
                "composite_path": str(result.composite_path),
                "sharpened_path": str(result.sharpened_path),
                "auto_split_path": str(result.auto_split_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
