"""Run the motion-state credit composer on SON METRO.

This is a sidecar POC. It consumes an existing unified item directory and writes
a new PNG plus a block report; it does not rerun OCR and does not modify the
source pipeline artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.pipelines.ocr.credit_motion_state_machine import (  # noqa: E402
    MotionComposerConfig,
    compose_item_motion_blocks,
)


DEFAULT_ITEM_DIR = PROJECT_ROOT / "outputs" / "_prototype_son_metro_wide" / "items" / "1980_son_metro_wide"
DEFAULT_OUT_DIR = PROJECT_ROOT / "outputs" / "_sonmetro_motion_state_20260530"
DEFAULT_CLOSING_SCROLL = PROJECT_ROOT / "outputs" / "_sonmetro_combined_20260530_003628" / "slitscan" / "panorama.png"
DEFAULT_CLOSING_SCROLL_FRAMES = PROJECT_ROOT / "outputs" / "_sonmetro_best_20260530" / "items" / "1980_son_metro_wide" / "frames" / "closing"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--item-dir", default=str(DEFAULT_ITEM_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--closing-scroll-png", default=str(DEFAULT_CLOSING_SCROLL))
    parser.add_argument("--scroll-frames-dir", default=str(DEFAULT_CLOSING_SCROLL_FRAMES))
    parser.add_argument("--width", type=int, default=600)
    parser.add_argument(
        "--son-metro-red-filter",
        action="store_true",
        default=True,
        help="Keep only red credit-card/scroll blocks, matching the SON METRO prototype style.",
    )
    parser.add_argument(
        "--no-son-metro-red-filter",
        action="store_false",
        dest="son_metro_red_filter",
    )
    args = parser.parse_args()

    scroll_overrides = {}
    scroll_override_sequences = {}
    closing_scroll = Path(args.closing_scroll_png)
    if closing_scroll.exists():
        frames_dir = Path(args.scroll_frames_dir)
        if not frames_dir.exists():
            frames_dir = Path(args.item_dir) / "frames" / "closing"
        cleaned_scroll = _build_clean_closing_scroll(closing_scroll, Path(args.out_dir), frames_dir=frames_dir)
        scroll_overrides["closing"] = str(cleaned_scroll or closing_scroll)
        split_scroll = _clean_scroll_part_paths(Path(args.out_dir))
        if split_scroll:
            scroll_override_sequences["closing"] = [str(path) for path in split_scroll]

    config = MotionComposerConfig(
        target_width=args.width,
        min_card_red_ratio=0.65 if args.son_metro_red_filter else None,
        min_scroll_red_ratio=0.50 if args.son_metro_red_filter else None,
        draw_labels=False,
        card_text_only=True,
        card_text_search_backward_frames=18,
        card_text_search_forward_frames=2,
        card_text_search_after_sec={"closing": 630.0},
        card_text_search_max_chars=7,
        card_text_search_max_bbox_width_px=112,
        scroll_override_paths=scroll_overrides,
        scroll_override_sequences=scroll_override_sequences,
        expand_red_band_when_visual_context=False,
    )
    report = compose_item_motion_blocks(args.item_dir, args.out_dir, config=config)

    debug_config = MotionComposerConfig(
        target_width=args.width,
        min_card_red_ratio=0.65 if args.son_metro_red_filter else None,
        min_scroll_red_ratio=0.50 if args.son_metro_red_filter else None,
        draw_labels=True,
        card_text_only=True,
        card_text_search_backward_frames=18,
        card_text_search_forward_frames=2,
        card_text_search_after_sec={"closing": 630.0},
        card_text_search_max_chars=7,
        card_text_search_max_bbox_width_px=112,
        scroll_override_paths=scroll_overrides,
        scroll_override_sequences=scroll_override_sequences,
        expand_red_band_when_visual_context=False,
    )
    debug_report = compose_item_motion_blocks(
        args.item_dir,
        str(Path(args.out_dir) / "debug_labeled"),
        config=debug_config,
    )

    print(json.dumps({
        "output_png": report["output_png"],
        "report_path": report["report_path"],
        "debug_output_png": debug_report["output_png"],
        "debug_report_path": debug_report["report_path"],
        "kept_count": report["kept_count"],
        "skipped_count": report["skipped_count"],
        "by_segment": report["by_segment"],
        "render": report["render"],
    }, ensure_ascii=False, indent=2))


def _build_clean_closing_scroll(source_png: Path, out_dir: Path, *, frames_dir: Path | None = None) -> Path | None:
    """SON METRO closing scroll cleanup.

    The SlitScan POC panorama contains one static/partial prelude and a repeated
    first song block before the complete lower scroll. Keep the first clean song
    header once, then append the continuous tail.
    """
    frame_scroll = _build_clean_closing_scroll_from_frames(frames_dir, out_dir)
    if frame_scroll is not None:
        return frame_scroll

    lines_path = source_png.parent / "lines.json"
    if not lines_path.exists():
        return None
    try:
        payload = json.loads(lines_path.read_text(encoding="utf-8"))
        lines = payload.get("lines") or []
        image = Image.open(source_png).convert("RGB")
    except (OSError, json.JSONDecodeError):
        return None

    def y_for(text: str, *, after: int = 0, min_conf: float = 0.0) -> int | None:
        for line in lines:
            if str(line.get("text") or "").upper().startswith(text.upper()):
                bbox = line.get("bbox")
                if (
                    isinstance(bbox, list)
                    and len(bbox) >= 4
                    and int(float(bbox[1])) >= after
                    and float(line.get("confidence") or 0.0) >= min_conf
                ):
                    return int(float(bbox[1]))
        return None

    header_y = y_for("CHANSONS", after=500, min_conf=0.9)
    header_end_y = y_for("JACQUES LARUE", after=700, min_conf=0.9)
    tail_y = y_for("PRIERE A ZUMBA", after=1000, min_conf=0.9)
    last_y = y_for("VISA DE", after=1500, min_conf=0.8)
    if header_y is None or header_end_y is None or tail_y is None or last_y is None:
        return None

    width, height = image.size
    windows = [
        (max(0, header_y - 34), min(height, header_end_y + 28)),
        (max(0, tail_y - 12), min(height, last_y + 42)),
    ]
    crops = [image.crop((0, y0, width, y1)) for y0, y1 in windows if y1 > y0]
    if not crops:
        return None

    generated_dir = out_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    part_paths = []
    for index, crop in enumerate(crops, start=1):
        part_path = generated_dir / f"closing_scroll_part{index}.png"
        crop.save(str(part_path))
        part_paths.append(str(part_path))

    total_h = sum(c.height for c in crops)
    cleaned = Image.new("RGB", (width, total_h), (140, 8, 8))
    y = 0
    for crop in crops:
        cleaned.paste(crop, (0, y))
        y += crop.height

    out_png = generated_dir / "closing_scroll_clean.png"
    cleaned.save(str(out_png))
    (generated_dir / "closing_scroll_clean_meta.json").write_text(
        json.dumps({
            "source_png": str(source_png),
            "windows": windows,
            "part_paths": part_paths,
            "output_png": str(out_png),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_png


def _build_clean_closing_scroll_from_frames(frames_dir: Path | None, out_dir: Path) -> Path | None:
    """Build the SON METRO scroll from full-line frame bands.

    Slit-scan strips can cross through glyphs. These hand-audited bands only
    use rows where the target lines are fully visible in the source frames.
    """
    if frames_dir is None or not frames_dir.exists():
        return None

    part_specs = [
        {
            "name": "closing_scroll_part1.png",
            "bands": [
                {"frame": 4200, "y0": 184, "y1": 394},
            ],
        },
        {
            "name": "closing_scroll_part2.png",
            "bands": [
                {"frame": 4230, "y0": 52, "y1": 302},
                {"frame": 4240, "y0": 194, "y1": 340},
                {"frame": 4260, "y0": 116, "y1": 326},
                {"frame": 4280, "y0": 96, "y1": 405},
                {"frame": 4300, "y0": 210, "y1": 256},
            ],
        },
    ]

    generated_dir = out_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    parts: list[Image.Image] = []
    part_paths: list[str] = []
    for spec in part_specs:
        crops: list[Image.Image] = []
        for band in spec["bands"]:
            frame_path = frames_dir / f"frame_{band['frame']:05d}.png"
            if not frame_path.exists():
                return None
            try:
                frame = Image.open(frame_path).convert("RGB")
            except OSError:
                return None
            width, height = frame.size
            y0 = max(0, min(height, int(band["y0"])))
            y1 = max(y0, min(height, int(band["y1"])))
            if y1 <= y0:
                return None
            crops.append(frame.crop((0, y0, width, y1)))

        part = _stack_crops(crops)
        part_path = generated_dir / str(spec["name"])
        part.save(str(part_path))
        parts.append(part)
        part_paths.append(str(part_path))

    cleaned = _stack_crops(parts)
    out_png = generated_dir / "closing_scroll_clean.png"
    cleaned.save(str(out_png))
    (generated_dir / "closing_scroll_clean_meta.json").write_text(
        json.dumps({
            "method": "source_frame_full_line_bands",
            "frames_dir": str(frames_dir),
            "part_specs": part_specs,
            "part_paths": part_paths,
            "output_png": str(out_png),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_png


def _stack_crops(crops: list[Image.Image]) -> Image.Image:
    width = max(crop.width for crop in crops)
    height = sum(crop.height for crop in crops)
    stacked = Image.new("RGB", (width, height), (140, 8, 8))
    y = 0
    for crop in crops:
        stacked.paste(crop, (0, y))
        y += crop.height
    return stacked


def _clean_scroll_part_paths(out_dir: Path) -> list[Path]:
    generated_dir = out_dir / "generated"
    part_paths = [
        generated_dir / "closing_scroll_part1.png",
        generated_dir / "closing_scroll_part2.png",
    ]
    return part_paths if all(path.exists() for path in part_paths) else []


if __name__ == "__main__":
    main()
