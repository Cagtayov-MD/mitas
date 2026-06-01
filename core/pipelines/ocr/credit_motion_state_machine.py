"""Motion-state credit composer.

This sidecar turns existing unified credit artifacts into a canonical block
sequence. It is deliberately read-only against the OCR pipeline: cards,
scroll composites, and events are consumed as evidence, then a new PNG and
JSON report are emitted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class MotionComposerConfig:
    target_width: int = 600
    gap_px: int = 18
    section_gap_px: int = 54
    label_height_px: int = 24
    crop_pad_px: int = 5
    visual_crop_pad_px: int = 10
    card_text_only: bool = False
    card_text_pad_px: int = 18
    card_text_search_backward_frames: int = 0
    card_text_search_forward_frames: int = 0
    card_text_search_after_sec: dict[str, float] = field(default_factory=dict)
    card_text_search_max_chars: int = 0
    card_text_search_max_bbox_width_px: int = 0
    cut_gap_sec: float = 2.0
    min_card_red_ratio: float | None = None
    min_scroll_red_ratio: float | None = None
    min_text_chars: int = 3
    reject_short_numeric_cards: bool = True
    draw_labels: bool = True
    scroll_override_paths: dict[str, str] = field(default_factory=dict)
    scroll_override_sequences: dict[str, list[str]] = field(default_factory=dict)
    expand_red_band_when_visual_context: bool = True
    force_red_band_after_sec: dict[str, float] = field(default_factory=dict)
    red_band_row_threshold: float = 0.45
    visual_context_min_ratio: float = 0.03


@dataclass
class MotionBlock:
    block_id: str
    segment: str
    state: str
    source_type: str
    source_id: str
    start_sec: float | None
    end_sec: float | None
    transition: str
    text_preview: str
    image: Image.Image | None = field(repr=False, default=None)
    metrics: dict[str, Any] = field(default_factory=dict)
    skip_reason: str | None = None
    canvas_y: int | None = None
    canvas_h: int | None = None

    def to_report_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("image", None)
        return data


def compose_item_motion_blocks(
    item_dir: str | Path,
    out_dir: str | Path,
    *,
    config: MotionComposerConfig | None = None,
) -> dict[str, Any]:
    """Build motion blocks and render a PNG for one unified item directory."""

    item_path = Path(item_dir)
    out_path = Path(out_dir)
    cfg = config or MotionComposerConfig()
    out_path.mkdir(parents=True, exist_ok=True)

    kept: list[MotionBlock] = []
    skipped: list[MotionBlock] = []

    for segment in ("opening", "closing"):
        segment_blocks = _build_segment_blocks(item_path, segment, cfg)
        kept.extend([b for b in segment_blocks if b.skip_reason is None])
        skipped.extend([b for b in segment_blocks if b.skip_reason is not None])

    image_path = out_path / "credits_motion_state_machine.png"
    render_report = _render_blocks(kept, image_path, cfg)

    report = {
        "item_dir": str(item_path),
        "output_png": str(image_path),
        "config": asdict(cfg),
        "kept_count": len(kept),
        "skipped_count": len(skipped),
        "by_segment": {
            segment: {
                "kept": sum(1 for b in kept if b.segment == segment),
                "skipped": sum(1 for b in skipped if b.segment == segment),
            }
            for segment in ("opening", "closing")
        },
        "render": render_report,
        "blocks": [b.to_report_dict() for b in kept],
        "skipped_blocks": [b.to_report_dict() for b in skipped],
    }
    report_path = out_path / "motion_blocks.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def _build_segment_blocks(item_dir: Path, segment: str, cfg: MotionComposerConfig) -> list[MotionBlock]:
    unified = item_dir / "unified" / segment
    frames_dir = item_dir / "frames" / segment
    events = _load_json(unified / "events.json").get("events", [])
    cards = _load_cards(unified / "cards")

    blocks: list[MotionBlock] = []
    block_index = 1
    last_kept_end: float | None = None

    card_events = [ev for ev in events if ev.get("type") == "card"]
    card_events.sort(key=lambda ev: (float(ev.get("start_sec") or 0.0), str(ev.get("event_id") or "")))

    for ev in card_events:
        event_id = str(ev.get("event_id") or "")
        card = _card_for_event(event_id, cards)
        if not card:
            continue
        image = _crop_card(card, frames_dir, cfg, segment=segment)
        if image is None:
            continue
        metrics = _image_metrics(image)
        text_preview = _text_preview(card.get("text_lines") or [], fallback=ev.get("text", ""))
        skip_reason = _card_skip_reason(card, text_preview, metrics, cfg)
        start_sec = _float_or_none(ev.get("start_sec"))
        end_sec = _float_or_none(ev.get("end_sec"))
        transition = _transition(last_kept_end, start_sec, state="STATIC", cfg=cfg)
        block = MotionBlock(
            block_id=f"{segment}_{block_index:03d}",
            segment=segment,
            state="STATIC",
            source_type="card",
            source_id=event_id,
            start_sec=start_sec,
            end_sec=end_sec,
            transition=transition,
            text_preview=text_preview,
            image=image,
            metrics=metrics,
            skip_reason=skip_reason,
        )
        blocks.append(block)
        block_index += 1
        if skip_reason is None:
            last_kept_end = end_sec if end_sec is not None else start_sec

    scroll_events = [ev for ev in events if ev.get("type") == "scroll_credit"]
    if scroll_events:
        override_sequence = cfg.scroll_override_sequences.get(segment) or []
        if override_sequence:
            for part_index, override_path in enumerate(override_sequence, start=1):
                scroll = _load_scroll_block(
                    unified,
                    segment,
                    scroll_events[0],
                    block_index,
                    last_kept_end,
                    cfg,
                    override_path=override_path,
                    source_suffix=f"_part{part_index}",
                )
                if scroll is None:
                    continue
                if part_index > 1:
                    scroll.transition = "SCROLL_CONTINUE_APPEND_BELOW"
                scroll.metrics["part_index"] = part_index
                scroll.metrics["part_count"] = len(override_sequence)
                blocks.append(scroll)
                block_index += 1
                if scroll.skip_reason is None:
                    last_kept_end = scroll.end_sec if scroll.end_sec is not None else scroll.start_sec
        else:
            scroll = _load_scroll_block(unified, segment, scroll_events[0], block_index, last_kept_end, cfg)
            if scroll is not None:
                blocks.append(scroll)

    return blocks


def _load_scroll_block(
    unified: Path,
    segment: str,
    event: dict[str, Any],
    block_index: int,
    last_kept_end: float | None,
    cfg: MotionComposerConfig,
    *,
    override_path: str | None = None,
    source_suffix: str = "",
) -> MotionBlock | None:
    scroll_dir = unified / "scroll"
    effective_override = override_path or cfg.scroll_override_paths.get(segment)
    composite_path = Path(effective_override) if effective_override else scroll_dir / "row_composite.png"
    if not composite_path.exists():
        return None
    try:
        image = Image.open(composite_path).convert("RGB")
    except OSError:
        return None

    metrics = _image_metrics(image)
    scroll_lines = _load_json(scroll_dir / "scroll_text_lines.json").get("lines", [])
    override_lines = composite_path.parent / "lines.json"
    if effective_override and override_lines.exists():
        scroll_lines = _load_json(override_lines).get("lines", scroll_lines)
    text_preview = _text_preview(scroll_lines, fallback=event.get("text", ""))
    skip_reason = _scroll_skip_reason(text_preview, metrics, cfg)
    event_start = _float_or_none(event.get("start_sec"))
    event_end = _float_or_none(event.get("end_sec"))
    start_sec = event_start if event_start and event_start > 0 else _next_time_after(last_kept_end)
    end_sec = event_end if event_end and event_end > 0 else start_sec
    transition = _transition(last_kept_end, start_sec, state="SCROLL", cfg=cfg)

    return MotionBlock(
        block_id=f"{segment}_{block_index:03d}",
        segment=segment,
        state="SCROLL",
        source_type="scroll_run",
        source_id=f"{event.get('event_id') or 'scroll'}{source_suffix}",
        start_sec=start_sec,
        end_sec=end_sec,
        transition=transition,
        text_preview=text_preview,
        image=image,
        metrics={
            **metrics,
            "line_count": len(scroll_lines),
            "composite_path": str(composite_path),
        },
        skip_reason=skip_reason,
    )


def _render_blocks(blocks: list[MotionBlock], output_path: Path, cfg: MotionComposerConfig) -> dict[str, Any]:
    if not blocks:
        canvas = Image.new("RGB", (cfg.target_width, cfg.label_height_px), (0, 0, 0))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(str(output_path))
        return {"width": cfg.target_width, "height": cfg.label_height_px, "file_size_kb": 0.0}

    font = _load_font(14)
    pieces: list[tuple[MotionBlock, Image.Image]] = []
    total_h = 0
    current_segment: str | None = None
    for block in blocks:
        if block.segment != current_segment:
            total_h += cfg.label_height_px
            if current_segment is not None:
                total_h += cfg.section_gap_px
            current_segment = block.segment
        img = _resize_to_width(block.image, cfg.target_width) if block.image is not None else None
        if img is None:
            continue
        pieces.append((block, img))
        total_h += img.height + cfg.gap_px
        if cfg.draw_labels:
            total_h += cfg.label_height_px

    canvas = Image.new("RGB", (cfg.target_width, max(1, total_h)), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    y = 0
    current_segment = None
    for block, img in pieces:
        if block.segment != current_segment:
            if current_segment is not None:
                y += cfg.section_gap_px
            _draw_band(draw, y, cfg.target_width, cfg.label_height_px, f"{block.segment.upper()} CREDITS", (34, 34, 70), font)
            y += cfg.label_height_px
            current_segment = block.segment

        if cfg.draw_labels:
            label = _block_label(block)
            color = (34, 58, 34) if block.state == "STATIC" else (70, 44, 18)
            _draw_band(draw, y, cfg.target_width, cfg.label_height_px, label, color, font)
            y += cfg.label_height_px

        block.canvas_y = y
        block.canvas_h = img.height
        canvas.paste(img, (0, y))
        y += img.height + cfg.gap_px

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas = canvas.crop((0, 0, cfg.target_width, max(1, y)))
    canvas.save(str(output_path))
    return {
        "width": canvas.width,
        "height": canvas.height,
        "file_size_kb": round(output_path.stat().st_size / 1024, 1),
    }


def _draw_band(draw: ImageDraw.ImageDraw, y: int, width: int, height: int, label: str, fill: tuple[int, int, int], font: ImageFont.ImageFont) -> None:
    draw.rectangle([(0, y), (width, y + height)], fill=fill)
    draw.text((8, y + 5), label[:120], fill=(225, 225, 225), font=font)


def _block_label(block: MotionBlock) -> str:
    time = ""
    if block.start_sec is not None:
        time = f" t={block.start_sec:.1f}s"
    return f"{block.state} {block.source_id}{time}  {block.transition}"


def _transition(last_end: float | None, start: float | None, *, state: str, cfg: MotionComposerConfig) -> str:
    if last_end is None:
        return f"NO_TEXT->{state}"
    if start is None:
        return f"UNKNOWN->{state}"
    gap = start - last_end
    if state == "SCROLL":
        return "STATIC->SCROLL_APPEND_BELOW" if gap <= cfg.cut_gap_sec else "GAP->SCROLL_APPEND_BELOW"
    if gap > cfg.cut_gap_sec:
        return "CUT_OR_DISSOLVE->STATIC_APPEND_BELOW"
    return "STATIC_SWAP->STATIC_APPEND_BELOW"


def _next_time_after(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value + 0.5, 3)


def _card_skip_reason(card: dict[str, Any], text: str, metrics: dict[str, Any], cfg: MotionComposerConfig) -> str | None:
    norm = _norm(text)
    if len(norm) < cfg.min_text_chars:
        return "too_few_text_chars"
    if cfg.reject_short_numeric_cards and re.fullmatch(r"[0-9 ]{1,4}", norm):
        return "short_numeric_text"
    if cfg.min_card_red_ratio is not None and metrics["red_ratio"] < cfg.min_card_red_ratio:
        return f"red_ratio_below_{cfg.min_card_red_ratio:.2f}"
    return None


def _scroll_skip_reason(text: str, metrics: dict[str, Any], cfg: MotionComposerConfig) -> str | None:
    norm = _norm(text)
    if len(norm) < cfg.min_text_chars:
        return "too_few_text_chars"
    if cfg.min_scroll_red_ratio is not None and metrics["red_ratio"] < cfg.min_scroll_red_ratio:
        return f"red_ratio_below_{cfg.min_scroll_red_ratio:.2f}"
    return None


def _crop_card(card: dict[str, Any], frames_dir: Path, cfg: MotionComposerConfig, *, segment: str) -> Image.Image | None:
    best = str(card.get("best_frame_path") or "")
    frame_path = _resolve_path(best)
    if not frame_path.exists() and best:
        frame_path = frames_dir / Path(best).name
    if not frame_path.exists():
        return None
    try:
        frame = Image.open(frame_path).convert("RGB")
    except OSError:
        return None
    width, height = frame.size
    y_range = card.get("y_range") or [0, height]
    try:
        y0_raw = float(y_range[0])
        y1_raw = float(y_range[1])
    except (TypeError, ValueError, IndexError):
        y0_raw, y1_raw = 0.0, float(height)
    x0_raw = float(width)
    x1_raw = 0.0
    has_text_bbox = False

    for line in card.get("text_lines") or []:
        bbox = line.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            continue
        try:
            line_x0 = float(bbox[0])
            line_x1 = float(bbox[0]) + float(bbox[2])
            line_y0 = float(bbox[1])
            line_y1 = float(bbox[1]) + float(bbox[3])
        except (TypeError, ValueError):
            continue
        x0_raw = min(x0_raw, line_x0)
        x1_raw = max(x1_raw, line_x1)
        y0_raw = min(y0_raw, line_y0)
        y1_raw = max(y1_raw, line_y1)
        has_text_bbox = True

    text_y0 = max(0, int(y0_raw) - cfg.crop_pad_px)
    text_y1 = min(height, int(y1_raw) + cfg.crop_pad_px)
    text_x0 = max(0, int(x0_raw) - cfg.crop_pad_px) if has_text_bbox else 0
    text_x1 = min(width, int(x1_raw) + cfg.crop_pad_px) if has_text_bbox else width
    text_bbox = (text_x0, text_y0, text_x1, text_y1)

    if cfg.card_text_only:
        searched = _search_card_text_crop(card, frame_path, frames_dir, text_bbox, cfg, segment=segment)
        if searched is not None:
            return searched
        if cfg.min_card_red_ratio is not None and _region_red_ratio(frame, text_bbox, cfg.card_text_pad_px) < cfg.min_card_red_ratio:
            return None
        return _card_text_canvas(frame, text_bbox, cfg)

    y0, y1 = text_y0, text_y1

    if cfg.expand_red_band_when_visual_context:
        red_run = _red_row_run_around(frame, (text_y0 + text_y1) / 2.0, cfg)
        force_after = cfg.force_red_band_after_sec.get(segment)
        first_ts = _float_or_none(card.get("first_timestamp"))
        force_red_band = force_after is not None and first_ts is not None and first_ts >= force_after
        if red_run is not None and (
            force_red_band
            or _has_visual_context_outside_text(frame, red_run, (text_y0, text_y1), cfg)
        ):
            y0 = max(0, red_run[0] - cfg.visual_crop_pad_px)
            y1 = min(height, red_run[1] + cfg.visual_crop_pad_px)

    if y1 <= y0:
        y0, y1 = 0, height
    return frame.crop((0, y0, width, y1))


def _search_card_text_crop(
    card: dict[str, Any],
    frame_path: Path,
    frames_dir: Path,
    text_bbox: tuple[int, int, int, int],
    cfg: MotionComposerConfig,
    *,
    segment: str,
) -> Image.Image | None:
    after = cfg.card_text_search_after_sec.get(segment)
    first_ts = _float_or_none(card.get("first_timestamp"))
    if after is None or first_ts is None or first_ts < after:
        return None
    text = _text_preview(card.get("text_lines") or [])
    if cfg.card_text_search_max_chars > 0 and len(_norm(text)) > cfg.card_text_search_max_chars:
        return None
    if cfg.card_text_search_max_bbox_width_px > 0 and _max_text_bbox_width(card) > cfg.card_text_search_max_bbox_width_px:
        return None
    frame_no = _frame_number(frame_path)
    if frame_no is None:
        return None

    best: tuple[float, Image.Image, tuple[int, int, int, int]] | None = None
    start = frame_no - max(0, cfg.card_text_search_backward_frames)
    end = frame_no + max(0, cfg.card_text_search_forward_frames)
    for candidate_no in range(start, end + 1):
        candidate_path = frames_dir / f"frame_{candidate_no:05d}.png"
        if not candidate_path.exists():
            continue
        try:
            candidate = Image.open(candidate_path).convert("RGB")
        except OSError:
            continue
        detected = _detect_text_bbox(candidate, _search_region(candidate.size, text_bbox))
        if detected is None:
            continue
        bbox, pixel_count = detected
        if cfg.min_card_red_ratio is not None and _region_red_ratio(candidate, bbox, cfg.card_text_pad_px) < cfg.min_card_red_ratio:
            continue
        bbox_w = max(0, bbox[2] - bbox[0])
        bbox_h = max(0, bbox[3] - bbox[1])
        score = float(pixel_count + bbox_w * 18 + bbox_h * 3)
        if best is None or score > best[0]:
            best = (score, candidate, bbox)

    if best is None:
        return None
    return _card_text_canvas(best[1], best[2], cfg)


def _region_red_ratio(image: Image.Image, bbox: tuple[int, int, int, int], pad: int) -> float:
    width, height = image.size
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(width, x1 + pad)
    y1 = min(height, y1 + pad)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    pix = image.load()
    red = 0
    total = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = pix[x, y]
            total += 1
            if _is_red_credit_bg(r, g, b):
                red += 1
    return red / max(1, total)


def _max_text_bbox_width(card: dict[str, Any]) -> float:
    widths: list[float] = []
    for line in card.get("text_lines") or []:
        bbox = line.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 3:
            try:
                widths.append(float(bbox[2]))
            except (TypeError, ValueError):
                continue
    return max(widths) if widths else 0.0


def _search_region(size: tuple[int, int], text_bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    width, height = size
    x0, y0, x1, y1 = text_bbox
    return (
        max(0, x0 - 130),
        max(0, y0 - 70),
        min(width, max(x1 + 170, int(width * 0.98))),
        min(height, y1 + 70),
    )


def _detect_text_bbox(
    image: Image.Image,
    region: tuple[int, int, int, int],
) -> tuple[tuple[int, int, int, int], int] | None:
    rx0, ry0, rx1, ry1 = region
    if rx1 <= rx0 or ry1 <= ry0:
        return None
    pix = image.load()
    min_x, min_y = rx1, ry1
    max_x, max_y = rx0, ry0
    pixel_count = 0
    for y in range(ry0, ry1):
        for x in range(rx0, rx1):
            r, g, b = pix[x, y]
            if _is_credit_text_pixel(r, g, b):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                pixel_count += 1
    if pixel_count < 20:
        return None
    if max_x - min_x < 8 or max_y - min_y < 6:
        return None
    return (min_x, min_y, max_x + 1, max_y + 1), pixel_count


def _card_text_canvas(
    frame: Image.Image,
    text_bbox: tuple[int, int, int, int],
    cfg: MotionComposerConfig,
) -> Image.Image:
    width, height = frame.size
    x0, y0, x1, y1 = text_bbox
    pad = cfg.card_text_pad_px
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(width, x1 + pad)
    y1 = min(height, y1 + pad)
    if x1 <= x0 or y1 <= y0:
        return frame
    patch = frame.crop((x0, y0, x1, y1))
    bg = (145, 8, 8)
    canvas = Image.new("RGB", (width, patch.height), bg)
    canvas.paste(patch, ((width - patch.width) // 2, 0))
    return canvas


def _sample_red_background(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    pix = image.load()
    samples: list[tuple[int, int, int]] = []
    for y in range(0, height, max(1, height // 16)):
        for x in range(0, width, max(1, width // 16)):
            r, g, b = pix[x, y]
            if _is_red_credit_bg(r, g, b):
                samples.append((r, g, b))
    if not samples:
        return (140, 8, 8)
    samples.sort(key=lambda rgb: rgb[0] + rgb[1] + rgb[2])
    return samples[len(samples) // 2]


def _red_row_run_around(image: Image.Image, center_y: float, cfg: MotionComposerConfig) -> tuple[int, int] | None:
    width, height = image.size
    pix = image.load()
    row_scores: list[float] = []
    for y in range(height):
        red = 0
        for x in range(width):
            r, g, b = pix[x, y]
            if _is_red_credit_bg(r, g, b):
                red += 1
        row_scores.append(red / max(1, width))

    center = max(0, min(height - 1, int(round(center_y))))
    if row_scores[center] <= cfg.red_band_row_threshold:
        candidates = [
            idx for idx, value in enumerate(row_scores)
            if value > cfg.red_band_row_threshold
        ]
        if not candidates:
            return None
        center = min(candidates, key=lambda idx: abs(idx - center))

    y0 = center
    while y0 > 0 and row_scores[y0 - 1] > cfg.red_band_row_threshold:
        y0 -= 1
    y1 = center + 1
    while y1 < height and row_scores[y1] > cfg.red_band_row_threshold:
        y1 += 1
    if y1 - y0 < 8:
        return None
    return y0, y1


def _has_visual_context_outside_text(
    image: Image.Image,
    red_run: tuple[int, int],
    text_band: tuple[int, int],
    cfg: MotionComposerConfig,
) -> bool:
    width, _height = image.size
    pix = image.load()
    y0, y1 = red_run
    text_y0, text_y1 = text_band
    margin = 12
    text_y0 = max(y0, text_y0 - margin)
    text_y1 = min(y1, text_y1 + margin)

    total = 0
    visual = 0
    for y in range(y0, y1):
        if text_y0 <= y <= text_y1:
            continue
        for x in range(width):
            r, g, b = pix[x, y]
            total += 1
            if _is_visual_context_pixel(r, g, b):
                visual += 1
    if total == 0:
        return False
    return (visual / total) >= cfg.visual_context_min_ratio


def _is_red_credit_bg(r: int, g: int, b: int) -> bool:
    return r > 70 and r > g * 1.35 and r > b * 1.35


def _is_visual_context_pixel(r: int, g: int, b: int) -> bool:
    if _is_red_credit_bg(r, g, b):
        return False
    if r + g + b < 80:
        return False
    if max(r, g, b) - min(r, g, b) < 18 and r > 180:
        return False
    return True


def _is_credit_text_pixel(r: int, g: int, b: int) -> bool:
    total = r + g + b
    return r > 170 and g > 140 and b > 100 and total > 440


def _frame_number(path: Path) -> int | None:
    match = re.search(r"frame_(\d+)", path.stem)
    if not match:
        return None
    return int(match.group(1))


def _resize_to_width(image: Image.Image | None, width: int) -> Image.Image | None:
    if image is None:
        return None
    if image.width == width:
        return image
    new_h = max(1, int(round(image.height * width / image.width)))
    return image.resize((width, new_h), Image.LANCZOS)


def _image_metrics(image: Image.Image) -> dict[str, Any]:
    sample_w = max(1, min(160, image.width))
    sample_h = max(1, int(round(image.height * sample_w / max(1, image.width))))
    sample = image.resize((sample_w, sample_h))
    red = 0
    dark = 0
    total = sample_w * sample_h
    for r, g, b in sample.getdata():
        if _is_red_credit_bg(r, g, b):
            red += 1
        if r + g + b < 90:
            dark += 1
    return {
        "width": image.width,
        "height": image.height,
        "red_ratio": round(red / total, 4) if total else 0.0,
        "dark_ratio": round(dark / total, 4) if total else 0.0,
    }


def _load_cards(cards_dir: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    if not cards_dir.exists():
        return cards
    for path in sorted(cards_dir.glob("card_*.json")):
        data = _load_json(path)
        card_id = data.get("card_id")
        if card_id:
            cards[str(card_id)] = data
    return cards


def _card_for_event(event_id: str, cards: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    try:
        number = int(event_id.split("_")[1])
    except (IndexError, ValueError):
        return None
    return cards.get(f"card_{number:03d}")


def _text_preview(lines: list[dict[str, Any]], *, fallback: Any = "") -> str:
    texts = [str(line.get("text") or "").strip() for line in lines if str(line.get("text") or "").strip()]
    if not texts and fallback:
        texts = [str(fallback).strip()]
    return " | ".join(texts[:8])


def _norm(text: str) -> str:
    return re.sub(r"[^0-9A-Z]+", "", text.upper())


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _resolve_path(value: str) -> Path:
    path = Path(str(value).replace("\\", "/"))
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()
