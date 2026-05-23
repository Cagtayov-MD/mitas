"""CLI for OCR text-layer de-scroll v2."""

from __future__ import annotations

import argparse
import json

from core.pipelines.ocr.text_layer_descroll import run_text_layer_descroll


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a text-layer de-scroll canvas from an OCR item directory")
    parser.add_argument("--item-dir", required=True, help="Experiment item directory containing frame_ocr.json and temporal_voting.json")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--engine", default="paddle")
    parser.add_argument("--fusion-engines", default=None, help="Comma-separated engines to use for agreement/fusion. Default: all available")
    parser.add_argument("--min-records", type=int, default=3)
    parser.add_argument("--min-confidence", type=float, default=0.65)
    parser.add_argument("--strict-min-records", type=int, default=8)
    parser.add_argument("--strict-min-confidence", type=float, default=0.90)
    parser.add_argument("--scale", type=int, default=2)
    args = parser.parse_args(argv)

    result = run_text_layer_descroll(
        args.item_dir,
        output_dir=args.output_dir,
        engine=args.engine,
        min_records=args.min_records,
        min_confidence=args.min_confidence,
        strict_min_records=args.strict_min_records,
        strict_min_confidence=args.strict_min_confidence,
        scale=args.scale,
        fusion_engines=[part.strip() for part in args.fusion_engines.split(",") if part.strip()] if args.fusion_engines else None,
    )
    print(
        json.dumps(
            {
                "summary_path": str(result.summary_path),
                "report_path": str(result.report_path),
                "strict_canvas_path": str(result.strict_canvas_path),
                "loose_canvas_path": str(result.loose_canvas_path),
                "ordered_text_path": str(result.ordered_text_path),
                "structured_json_path": str(result.structured_json_path),
                "review_pack_path": str(result.review_pack_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
