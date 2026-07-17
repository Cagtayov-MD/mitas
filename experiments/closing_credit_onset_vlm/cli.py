from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .models import DetectionConfig, DetectionStatus
from .window_detector import (
    WINDOW_PROTOCOL,
    WindowClosingCreditOnsetDetector,
    WindowProtocolConfig,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "TEST ONLY: locate the first true terminal closing-credit frame "
            "with aggregate VLM window evidence and corroborating exact views."
        )
    )
    parser.add_argument(
        "--frames", type=Path, required=True,
        help="ordered 1.5 fps frames/cikis directory (read-only)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "new run directory inside E:/MITAS/outputs/closing_credit_onset_vlm; "
            "must not already exist"
        ),
    )
    parser.add_argument("--fps", type=float, default=1.5)
    parser.add_argument("--model", default="qwen3-vl:30b")
    parser.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--max-wall-seconds",
        type=float,
        default=120.0,
        help="film-level wall budget; insufficient remaining time fails closed",
    )
    parser.add_argument("--keep-alive", default="10m")
    parser.add_argument("--max-cv-proposals", type=int, default=16)
    parser.add_argument("--proposal-min-distance-seconds", type=float, default=10.0)
    parser.add_argument("--cv-width", type=int, default=320)
    parser.add_argument("--num-ctx", type=int, default=4096)
    parser.add_argument("--num-predict", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=2)

    window = parser.add_argument_group("window-boundary-v1")
    window.add_argument("--coarse-window-seconds", type=float, default=120.0)
    window.add_argument("--coarse-anchors", type=int, default=9)
    window.add_argument("--coarse-max-cells", type=int, default=24)
    window.add_argument("--fine-pre-seconds", type=float, default=3.0)
    window.add_argument("--fine-post-seconds", type=float, default=15.0)
    window.add_argument("--fine-anchors", type=int, default=9)
    window.add_argument("--coarse-tile-width", type=int, default=384)
    window.add_argument("--fine-tile-width", type=int, default=512)
    window.add_argument("--verify-tile-width", type=int, default=640)
    window.add_argument("--panel-jpeg-quality", type=int, default=95)
    window.add_argument("--min-support-seconds", type=float, default=8.0)
    window.add_argument("--min-call-budget-seconds", type=float, default=10.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        config = DetectionConfig(
            fps=args.fps,
            model=args.model,
            ollama_host=args.ollama_host,
            timeout_seconds=args.timeout,
            max_wall_seconds=args.max_wall_seconds,
            keep_alive=args.keep_alive,
            image_width=args.coarse_tile_width,
            mosaic_columns=3,
            jpeg_quality=args.panel_jpeg_quality,
            batch_size=max(9, args.coarse_anchors),
            fine_overlap=0,
            max_cv_proposals=args.max_cv_proposals,
            proposal_min_distance_seconds=args.proposal_min_distance_seconds,
            cv_width=args.cv_width,
            num_ctx=args.num_ctx,
            num_predict=args.num_predict,
            seed=args.seed,
            temperature=args.temperature,
            retry_count=args.retries,
        )
        protocol = WindowProtocolConfig(
            coarse_window_seconds=args.coarse_window_seconds,
            coarse_anchor_count=args.coarse_anchors,
            coarse_max_cells=args.coarse_max_cells,
            fine_pre_seconds=args.fine_pre_seconds,
            fine_post_seconds=args.fine_post_seconds,
            fine_anchor_count=args.fine_anchors,
            coarse_tile_width=args.coarse_tile_width,
            fine_tile_width=args.fine_tile_width,
            verify_tile_width=args.verify_tile_width,
            jpeg_quality=args.panel_jpeg_quality,
            min_support_seconds=args.min_support_seconds,
            min_call_budget_seconds=args.min_call_budget_seconds,
        )
        detector = WindowClosingCreditOnsetDetector(config, protocol=protocol)
        result = detector.run(args.frames, args.out)
    except Exception as exc:  # noqa: BLE001
        print(f"HATA: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 10

    print(json.dumps({
        "semantic_protocol": WINDOW_PROTOCOL,
        "status": result.status,
        "start_pos": result.start_pos,
        "start_frame_no": result.start_frame_no,
        "start_file": result.start_file,
        "start_time_seconds": result.start_time_seconds,
        "onset_kind": result.onset_kind,
        "confidence": result.confidence,
        "reason": result.reason,
        "output_dir": result.output_dir,
        "result_json": result.artifacts.get("result"),
        "publishable": result.publishable,
        "pool_may_be_replaced": result.pool_may_be_replaced,
    }, ensure_ascii=False, indent=2))

    return {
        DetectionStatus.FOUND.value: 0,
        DetectionStatus.REVIEW.value: 3,
        DetectionStatus.LEFT_CENSORED.value: 3,
        DetectionStatus.NOT_FOUND.value: 4,
        DetectionStatus.MODEL_ERROR.value: 5,
    }.get(result.status, 9)


if __name__ == "__main__":
    raise SystemExit(main())
