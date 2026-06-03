"""Generic motion-state credit composer CLI.

This runner has no film-specific paths, frame numbers, or title-specific
cleanup. It consumes an existing MITAS unified item directory:

  item/
    frames/opening|closing/
    unified/opening|closing/events.json
    unified/opening|closing/cards/
    unified/opening|closing/scroll/
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.pipelines.ocr.credit_motion_state_machine import (  # noqa: E402
    MotionComposerConfig,
    compose_item_motion_blocks,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--item-dir", required=True, help="Unified item directory containing frames/ and unified/.")
    parser.add_argument("--out-dir", required=True, help="Output directory for PNG and motion_blocks.json.")
    parser.add_argument("--config-json", default=None, help="Optional JSON with MotionComposerConfig fields.")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--draw-labels", action="store_true")
    parser.add_argument("--debug-labeled", action="store_true")

    parser.add_argument("--card-text-only", action="store_true")
    parser.add_argument("--card-text-pad", type=int, default=None)
    parser.add_argument("--card-text-search-backward", type=int, default=None)
    parser.add_argument("--card-text-search-forward", type=int, default=None)
    parser.add_argument("--card-text-search-after", action="append", default=[], help="segment=sec, repeatable.")
    parser.add_argument("--card-text-search-max-chars", type=int, default=None)
    parser.add_argument("--card-text-search-max-bbox-width", type=int, default=None)

    parser.add_argument("--min-card-red-ratio", type=float, default=None)
    parser.add_argument("--min-scroll-red-ratio", type=float, default=None)
    parser.add_argument("--min-text-chars", type=int, default=None)
    parser.add_argument("--no-expand-red-band", action="store_true")
    parser.add_argument("--force-red-band-after", action="append", default=[], help="segment=sec, repeatable.")

    parser.add_argument("--scroll-override", action="append", default=[], help="segment=png_path, repeatable.")
    parser.add_argument(
        "--scroll-sequence",
        action="append",
        default=[],
        help="segment=png1;png2;png3, repeatable. Used when one scroll must render as separate blocks.",
    )
    args = parser.parse_args()

    cfg_data = _load_config_json(args.config_json)
    _set_if_not_none(cfg_data, "target_width", args.width)
    _set_if_not_none(cfg_data, "card_text_pad_px", args.card_text_pad)
    _set_if_not_none(cfg_data, "card_text_search_backward_frames", args.card_text_search_backward)
    _set_if_not_none(cfg_data, "card_text_search_forward_frames", args.card_text_search_forward)
    _set_if_not_none(cfg_data, "card_text_search_max_chars", args.card_text_search_max_chars)
    _set_if_not_none(cfg_data, "card_text_search_max_bbox_width_px", args.card_text_search_max_bbox_width)
    _set_if_not_none(cfg_data, "min_card_red_ratio", args.min_card_red_ratio)
    _set_if_not_none(cfg_data, "min_scroll_red_ratio", args.min_scroll_red_ratio)
    _set_if_not_none(cfg_data, "min_text_chars", args.min_text_chars)

    if args.draw_labels:
        cfg_data["draw_labels"] = True
    elif "draw_labels" not in cfg_data:
        cfg_data["draw_labels"] = False
    if args.card_text_only:
        cfg_data["card_text_only"] = True
    if args.no_expand_red_band:
        cfg_data["expand_red_band_when_visual_context"] = False

    cfg_data.setdefault("scroll_override_paths", {})
    cfg_data["scroll_override_paths"].update(_parse_key_path_args(args.scroll_override))

    cfg_data.setdefault("scroll_override_sequences", {})
    cfg_data["scroll_override_sequences"].update(_parse_key_path_list_args(args.scroll_sequence))

    cfg_data.setdefault("card_text_search_after_sec", {})
    cfg_data["card_text_search_after_sec"].update(_parse_key_float_args(args.card_text_search_after))

    cfg_data.setdefault("force_red_band_after_sec", {})
    cfg_data["force_red_band_after_sec"].update(_parse_key_float_args(args.force_red_band_after))

    config = MotionComposerConfig(**_filter_config_fields(cfg_data))
    report = compose_item_motion_blocks(args.item_dir, args.out_dir, config=config)

    debug_report = None
    if args.debug_labeled:
        debug_data = {**_filter_config_fields(cfg_data), "draw_labels": True}
        debug_report = compose_item_motion_blocks(
            args.item_dir,
            str(Path(args.out_dir) / "debug_labeled"),
            config=MotionComposerConfig(**debug_data),
        )

    payload = {
        "output_png": report["output_png"],
        "report_path": report["report_path"],
        "kept_count": report["kept_count"],
        "skipped_count": report["skipped_count"],
        "by_segment": report["by_segment"],
        "render": report["render"],
    }
    if debug_report:
        payload["debug_output_png"] = debug_report["output_png"]
        payload["debug_report_path"] = debug_report["report_path"]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _load_config_json(path_value: str | None) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"config okunamadı: {path} ({exc})") from exc
    if not isinstance(payload, dict):
        raise SystemExit("config-json kök değeri object olmalı")
    return payload


def _filter_config_fields(data: dict[str, Any]) -> dict[str, Any]:
    allowed = {field.name for field in fields(MotionComposerConfig)}
    return {key: value for key, value in data.items() if key in allowed}


def _set_if_not_none(data: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        data[key] = value


def _parse_key_path_args(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        key, raw_path = _split_key_value(value)
        parsed[key] = str(Path(raw_path))
    return parsed


def _parse_key_path_list_args(values: list[str]) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for value in values:
        key, raw_paths = _split_key_value(value)
        paths = [str(Path(part)) for part in raw_paths.split(";") if part.strip()]
        if paths:
            parsed[key] = paths
    return parsed


def _parse_key_float_args(values: list[str]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for value in values:
        key, raw_number = _split_key_value(value)
        try:
            parsed[key] = float(raw_number)
        except ValueError as exc:
            raise SystemExit(f"geçersiz sayı: {value}") from exc
    return parsed


def _split_key_value(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise SystemExit(f"key=value bekleniyor: {value}")
    key, raw = value.split("=", 1)
    key = key.strip()
    raw = raw.strip()
    if not key or not raw:
        raise SystemExit(f"key=value eksik: {value}")
    return key, raw


if __name__ == "__main__":
    main()
