"""Profile the KJ golden dataset and derive first-pass scanner thresholds.

The real KJ fixtures are owned outside the repo until they are provided. This
script therefore accepts a deliberately tolerant manifest shape while producing
one stable output contract for the later KJ parser and event-detector stages.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SegmentEvent:
    segment_id: str
    video_path: Path | None
    segment_start_seconds: float
    segment_end_seconds: float | None
    event_index: int
    start_seconds: float
    end_seconds: float
    name: str | None
    role: str | None
    organization: str | None
    title: str | None
    lines: tuple[str, ...]
    bbox: tuple[float, float, float, float] | None
    frame_width: int | None
    frame_height: int | None
    has_panel: bool | None
    raw: dict[str, Any]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile KJ golden parser/event fixtures.")
    parser.add_argument("--golden", required=True, type=Path, help="Parser golden-set JSON path.")
    parser.add_argument("--segments", required=True, type=Path, help="KJ video segment manifest YAML/JSON path.")
    parser.add_argument("--output", required=True, type=Path, help="Output profile JSON path.")
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=None,
        help="Optional Markdown summary path. Defaults to sibling *_summary.md.",
    )
    parser.add_argument("--work-dir", type=Path, default=PROJECT_ROOT / "outputs" / "kj_dataset_profile_work")
    parser.add_argument("--fps", type=float, default=2.0, help="Frame sample rate for PaddleOCR profiling.")
    parser.add_argument("--max-frames-per-segment", type=int, default=None)
    parser.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg executable.")
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Allow PaddleOCR to download models on first run.",
    )
    parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Only use manifest/golden annotations; do not run PaddleOCR.",
    )
    args = parser.parse_args(argv)

    warnings: list[str] = []
    golden_payload = _read_structured(args.golden)
    manifest_payload = _read_structured(args.segments)
    parser_examples = _parser_examples(golden_payload)
    events = _segment_events(manifest_payload, args.segments.parent, warnings)

    if not events:
        raise ValueError("No KJ events found in segment manifest.")

    ocr_records_by_segment: dict[str, list[dict[str, Any]]] = {}
    ocr_status: dict[str, Any] = {"enabled": not args.skip_ocr, "segments": {}}
    if not args.skip_ocr:
        try:
            ocr_records_by_segment = _run_paddle_profile_ocr(
                events,
                work_dir=args.work_dir,
                fps=args.fps,
                max_frames_per_segment=args.max_frames_per_segment,
                ffmpeg=args.ffmpeg,
                allow_model_download=args.allow_model_download,
                status=ocr_status,
                warnings=warnings,
            )
        except Exception as exc:  # pragma: no cover - depends on local OCR/runtime.
            warnings.append(f"PaddleOCR profiling skipped after error: {exc}")
            ocr_status["error"] = str(exc)

    event_profiles = [
        _profile_event(event, ocr_records_by_segment.get(event.segment_id, []), warnings)
        for event in events
    ]

    metric_groups = _metric_groups(event_profiles)
    panel_groups = {
        "panel_true": [item for item in event_profiles if item.get("has_panel") is True],
        "panel_false": [item for item in event_profiles if item.get("has_panel") is False],
        "panel_unknown": [item for item in event_profiles if item.get("has_panel") is None],
    }
    distributions: dict[str, Any] = {
        "overall": _summarize_metrics(event_profiles, metric_groups),
        "by_panel": {
            group_name: _summarize_metrics(items, metric_groups)
            for group_name, items in panel_groups.items()
            if items
        },
        "parser_golden": _summarize_metrics(parser_examples, {"line_count": "line_count"}),
    }

    profile = {
        "schema_version": 1,
        "profile_version": "kj_dataset_profile_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "golden": str(args.golden),
            "segments": str(args.segments),
        },
        "sample_fps": args.fps,
        "event_count": len(event_profiles),
        "parser_example_count": len(parser_examples),
        "ocr_status": ocr_status,
        "warnings": warnings,
        "events": event_profiles,
        "distributions": distributions,
        "derived_thresholds": _derive_thresholds(distributions.get("overall", {})),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = args.summary_output or args.output.with_name(args.output.stem + "_summary.md")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(_build_summary(profile), encoding="utf-8")
    print(json.dumps({"profile": str(args.output), "summary": str(summary_path)}, ensure_ascii=False))
    return 0


def _read_structured(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("PyYAML is required for YAML manifests.") from exc
        return yaml.safe_load(text)
    return json.loads(text)


def _parser_examples(payload: Any) -> list[dict[str, Any]]:
    raw_items = _first_list(payload, ("items", "examples", "cases", "golden", "records"))
    if raw_items is None and isinstance(payload, list):
        raw_items = payload
    examples: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items or []):
        if not isinstance(item, dict):
            continue
        lines = _lines_from_any(
            item.get("raw_lines")
            or item.get("ocr_lines")
            or item.get("lines")
            or item.get("input")
            or item.get("text")
        )
        examples.append(
            {
                "index": index,
                "line_count": len(lines),
                "raw_lines": lines,
                "expected": item.get("expected") or item.get("expected_json") or item.get("target"),
            }
        )
    return examples


def _segment_events(payload: Any, manifest_dir: Path, warnings: list[str]) -> list[SegmentEvent]:
    raw_segments = _first_list(payload, ("segments", "items", "videos", "cases"))
    if raw_segments is None and isinstance(payload, list):
        raw_segments = payload
    events: list[SegmentEvent] = []
    for segment_index, raw_segment in enumerate(raw_segments or []):
        if not isinstance(raw_segment, dict):
            warnings.append(f"Manifest segment {segment_index} is not an object; skipped.")
            continue
        segment_id = str(raw_segment.get("id") or raw_segment.get("segment_id") or f"segment_{segment_index + 1:04d}")
        video_path = _resolve_video_path(raw_segment, manifest_dir)
        segment_start = _number(
            _first_present(raw_segment, ("start_seconds", "start", "segment_start", "tc_in")),
            default=0.0,
        )
        segment_end = _optional_number(_first_present(raw_segment, ("end_seconds", "end", "segment_end", "tc_out")))
        frame_width, frame_height = _frame_size(raw_segment)
        raw_events = (
            _first_list(raw_segment, ("expected_kj_events", "kj_events", "events", "expected_events"))
            or []
        )
        for event_index, raw_event in enumerate(raw_events):
            if not isinstance(raw_event, dict):
                warnings.append(f"{segment_id} event {event_index} is not an object; skipped.")
                continue
            start_raw = _first_present(raw_event, ("start_seconds", "start", "begin"))
            end_raw = _first_present(raw_event, ("end_seconds", "end", "finish"))
            if start_raw is None or end_raw is None:
                warnings.append(f"{segment_id} event {event_index} has no start/end; skipped.")
                continue
            start = _event_time(float(start_raw), segment_start)
            end = _event_time(float(end_raw), segment_start)
            if end <= start:
                warnings.append(f"{segment_id} event {event_index} has invalid duration; skipped.")
                continue
            event_frame_width, event_frame_height = _frame_size(raw_event)
            event = SegmentEvent(
                segment_id=segment_id,
                video_path=video_path,
                segment_start_seconds=segment_start,
                segment_end_seconds=segment_end,
                event_index=event_index,
                start_seconds=start,
                end_seconds=end,
                name=_optional_string(raw_event.get("name")),
                role=_optional_string(raw_event.get("role")),
                organization=_optional_string(raw_event.get("organization") or raw_event.get("org")),
                title=_optional_string(raw_event.get("title")),
                lines=tuple(_lines_from_any(raw_event.get("lines") or raw_event.get("raw_lines") or raw_event.get("text"))),
                bbox=_bbox_from_event(raw_event),
                frame_width=event_frame_width or frame_width,
                frame_height=event_frame_height or frame_height,
                has_panel=_optional_bool(
                    raw_event.get("has_panel")
                    if "has_panel" in raw_event
                    else raw_event.get("panel")
                    if "panel" in raw_event
                    else raw_event.get("panel_present")
                ),
                raw=raw_event,
            )
            events.append(event)
    return events


def _run_paddle_profile_ocr(
    events: list[SegmentEvent],
    *,
    work_dir: Path,
    fps: float,
    max_frames_per_segment: int | None,
    ffmpeg: str,
    allow_model_download: bool,
    status: dict[str, Any],
    warnings: list[str],
) -> dict[str, list[dict[str, Any]]]:
    import os

    from core.pipelines.ocr.credit_experiment import PaddleOcrEngine, _extract_segment_frames

    if allow_model_download:
        os.environ["MITAS_OCR_ALLOW_MODEL_DOWNLOAD"] = "1"

    engine = PaddleOcrEngine()
    records_by_segment: dict[str, list[dict[str, Any]]] = {}
    unique_segments: dict[str, list[SegmentEvent]] = {}
    for event in events:
        unique_segments.setdefault(event.segment_id, []).append(event)

    for segment_id, segment_events in unique_segments.items():
        first = segment_events[0]
        segment_status: dict[str, Any] = {"record_count": 0, "frame_count": 0}
        status["segments"][segment_id] = segment_status
        if first.video_path is None or not first.video_path.exists():
            warnings.append(f"{segment_id}: video path missing; OCR skipped.")
            segment_status["skipped"] = "missing_video"
            continue
        start = first.segment_start_seconds
        end_candidates = [event.end_seconds for event in segment_events]
        if first.segment_end_seconds is not None:
            end_candidates.append(first.segment_end_seconds)
        end = max(end_candidates)
        frames_dir = work_dir / segment_id / "frames"
        frames = _extract_segment_frames(
            first.video_path,
            frames_dir,
            start_seconds=start,
            end_seconds=end,
            fps=fps,
            max_frames=max_frames_per_segment,
            ffmpeg_executable=ffmpeg,
        )
        records: list[dict[str, Any]] = []
        for frame_index, frame in enumerate(frames):
            timestamp = start + (frame_index / max(fps, 0.001))
            records.extend(engine.recognize(frame, strategy="kj_profile_paddle", timestamp_seconds=timestamp))
        records_by_segment[segment_id] = records
        segment_status["frame_count"] = len(frames)
        segment_status["record_count"] = len(records)
    return records_by_segment


def _profile_event(event: SegmentEvent, records: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    matched_records = _match_event_records(event, records)
    bbox = event.bbox or _union_record_bbox(matched_records)
    frame_width = event.frame_width or _frame_width_from_records(matched_records)
    frame_height = event.frame_height or _frame_height_from_records(matched_records)

    metrics: dict[str, float | int | None] = {
        "duration_seconds": round(event.end_seconds - event.start_seconds, 6),
        "line_count": len(event.lines) if event.lines else _line_count_from_records(matched_records),
        "ocr_confidence": _mean([_optional_number(record.get("confidence")) for record in matched_records]),
        "frame_to_frame_motion_px_s": _motion_px_s(matched_records),
        "y_center_ratio": None,
        "y_top_ratio": None,
        "y_bottom_ratio": None,
        "width_ratio": None,
        "height_ratio": None,
    }
    if bbox and frame_width and frame_height and frame_width > 0 and frame_height > 0:
        x, y, width, height = bbox
        metrics.update(
            {
                "y_center_ratio": round((y + height / 2.0) / frame_height, 6),
                "y_top_ratio": round(y / frame_height, 6),
                "y_bottom_ratio": round((y + height) / frame_height, 6),
                "width_ratio": round(width / frame_width, 6),
                "height_ratio": round(height / frame_height, 6),
            }
        )
    elif not matched_records:
        warnings.append(f"{event.segment_id} event {event.event_index}: no manual bbox or matching OCR records.")

    return {
        "segment_id": event.segment_id,
        "event_index": event.event_index,
        "video_path": str(event.video_path) if event.video_path else None,
        "start_seconds": event.start_seconds,
        "end_seconds": event.end_seconds,
        "has_panel": event.has_panel,
        "name": event.name,
        "title": event.title,
        "role": event.role,
        "organization": event.organization,
        "bbox": [round(part, 3) for part in bbox] if bbox else None,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "matched_ocr_record_count": len(matched_records),
        "metrics": metrics,
    }


def _match_event_records(event: SegmentEvent, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []
    event_records = [
        record
        for record in records
        if event.start_seconds <= _number(record.get("timestamp_seconds"), default=-1.0) <= event.end_seconds
    ]
    if not event_records:
        return []

    needles = {
        _normalize_text(value)
        for value in [event.name, event.title, event.role, event.organization, *event.lines]
        if value
    }
    needles = {needle for needle in needles if needle}
    if not needles:
        return event_records

    matched = []
    for record in event_records:
        normalized = _normalize_text(str(record.get("normalized_text") or record.get("text") or ""))
        if normalized and any(_text_matches(normalized, needle) for needle in needles):
            matched.append(record)
    return matched or event_records


def _text_matches(haystack: str, needle: str) -> bool:
    if needle in haystack or haystack in needle:
        return True
    hay_tokens = set(haystack.split())
    needle_tokens = set(needle.split())
    if not needle_tokens:
        return False
    return len(hay_tokens & needle_tokens) / len(needle_tokens) >= 0.5


def _union_record_bbox(records: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    boxes = [_bbox_from_any(record.get("bbox")) for record in records]
    boxes = [box for box in boxes if box is not None]
    if not boxes:
        return None
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    return (left, top, max(0.0, right - left), max(0.0, bottom - top))


def _motion_px_s(records: list[dict[str, Any]]) -> float | None:
    samples: list[tuple[float, float, float]] = []
    for record in records:
        timestamp = _optional_number(record.get("timestamp_seconds"))
        bbox = _bbox_from_any(record.get("bbox"))
        if timestamp is None or bbox is None:
            continue
        x, y, width, height = bbox
        samples.append((timestamp, x + width / 2.0, y + height / 2.0))
    samples.sort()
    velocities: list[float] = []
    for left, right in zip(samples, samples[1:]):
        dt = right[0] - left[0]
        if dt <= 0:
            continue
        distance = math.hypot(right[1] - left[1], right[2] - left[2])
        velocities.append(distance / dt)
    return round(statistics.median(velocities), 6) if velocities else None


def _metric_groups(event_profiles: list[dict[str, Any]]) -> dict[str, str]:
    return {
        "y_center_ratio": "y_center_ratio",
        "y_top_ratio": "y_top_ratio",
        "y_bottom_ratio": "y_bottom_ratio",
        "width_ratio": "width_ratio",
        "height_ratio": "height_ratio",
        "duration_seconds": "duration_seconds",
        "line_count": "line_count",
        "ocr_confidence": "ocr_confidence",
        "frame_to_frame_motion_px_s": "frame_to_frame_motion_px_s",
    }


def _summarize_metrics(items: list[dict[str, Any]], metric_paths: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {"sample_count": len(items), "metrics": {}}
    for metric_name, metric_path in metric_paths.items():
        values = [_metric_value(item, metric_path) for item in items]
        values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
        result["metrics"][metric_name] = _stats(values)
    return result


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "p5": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p95": None,
            "max": None,
            "mean": None,
            "std": None,
        }
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": round(ordered[0], 6),
        "p5": round(_percentile(ordered, 5), 6),
        "p25": round(_percentile(ordered, 25), 6),
        "median": round(_percentile(ordered, 50), 6),
        "p75": round(_percentile(ordered, 75), 6),
        "p95": round(_percentile(ordered, 95), 6),
        "max": round(ordered[-1], 6),
        "mean": round(statistics.fmean(ordered), 6),
        "std": round(statistics.pstdev(ordered), 6) if len(ordered) > 1 else 0.0,
    }


def _percentile(ordered: list[float], percentile: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _derive_thresholds(overall_distribution: dict[str, Any]) -> dict[str, Any]:
    metrics = overall_distribution.get("metrics") or {}
    duration = metrics.get("duration_seconds") or {}
    motion = metrics.get("frame_to_frame_motion_px_s") or {}
    return {
        "min_duration_sec": duration.get("p5"),
        "max_duration_sec": round(duration["p95"] * 1.3, 6) if duration.get("p95") is not None else None,
        "motion_median_px_s": motion.get("median"),
        "notes": [
            "Review these values before copying them to config/kj_scanner.yaml.",
            "Panel weight still requires A/B evaluation in the event-detector grid search.",
        ],
    }


def _build_summary(profile: dict[str, Any]) -> str:
    lines = [
        "# KJ Dataset Profile Summary",
        "",
        f"- Created at: `{profile['created_at']}`",
        f"- Event count: `{profile['event_count']}`",
        f"- Parser example count: `{profile['parser_example_count']}`",
        f"- Sample FPS: `{profile['sample_fps']}`",
        "",
        "## Derived Threshold Candidates",
        "",
    ]
    for key, value in (profile.get("derived_thresholds") or {}).items():
        if key == "notes":
            continue
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Overall Metrics", ""])
    metrics = (((profile.get("distributions") or {}).get("overall") or {}).get("metrics") or {})
    lines.append("| metric | count | p5 | median | p95 | min | max | mean | std |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for metric, stats in metrics.items():
        lines.append(
            "| {metric} | {count} | {p5} | {median} | {p95} | {min} | {max} | {mean} | {std} |".format(
                metric=metric,
                count=stats.get("count"),
                p5=_md_value(stats.get("p5")),
                median=_md_value(stats.get("median")),
                p95=_md_value(stats.get("p95")),
                min=_md_value(stats.get("min")),
                max=_md_value(stats.get("max")),
                mean=_md_value(stats.get("mean")),
                std=_md_value(stats.get("std")),
            )
        )
    panel_groups = ((profile.get("distributions") or {}).get("by_panel") or {})
    if panel_groups:
        lines.extend(["", "## Panel Groups", ""])
        for group_name, group in panel_groups.items():
            lines.append(f"- `{group_name}`: `{group.get('sample_count')}` events")
    warnings = profile.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    return "\n".join(lines)


def _metric_value(item: dict[str, Any], path: str) -> Any:
    if path in item:
        return item.get(path)
    metrics = item.get("metrics")
    if isinstance(metrics, dict):
        return metrics.get(path)
    return None


def _first_list(payload: Any, keys: Iterable[str]) -> list[Any] | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return None


def _first_present(payload: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _resolve_video_path(raw: dict[str, Any], manifest_dir: Path) -> Path | None:
    value = raw.get("video_path") or raw.get("path") or raw.get("file") or raw.get("source")
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = manifest_dir / path
    return path


def _event_time(value: float, segment_start: float) -> float:
    if segment_start > 0 and value < segment_start:
        return segment_start + value
    return value


def _frame_size(raw: dict[str, Any]) -> tuple[int | None, int | None]:
    width = _optional_number(_first_present(raw, ("frame_width", "width")))
    height = _optional_number(_first_present(raw, ("frame_height", "height")))
    size = raw.get("frame_size") or raw.get("image_size")
    if isinstance(size, (list, tuple)) and len(size) >= 2:
        width = width or _optional_number(size[0])
        height = height or _optional_number(size[1])
    elif isinstance(size, dict):
        width = width or _optional_number(_first_present(size, ("width", "w")))
        height = height or _optional_number(_first_present(size, ("height", "h")))
    return (int(width) if width else None, int(height) if height else None)


def _bbox_from_event(raw: dict[str, Any]) -> tuple[float, float, float, float] | None:
    for key in ("bbox", "box", "expected_bbox"):
        bbox = _bbox_from_any(raw.get(key))
        if bbox:
            return bbox
    return None


def _bbox_from_any(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, dict):
        if all(key in value for key in ("x", "y", "width", "height")):
            return (
                float(value["x"]),
                float(value["y"]),
                float(value["width"]),
                float(value["height"]),
            )
        if all(key in value for key in ("left", "top", "right", "bottom")):
            left = float(value["left"])
            top = float(value["top"])
            return (
                left,
                top,
                max(0.0, float(value["right"]) - left),
                max(0.0, float(value["bottom"]) - top),
            )
        if all(key in value for key in ("x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4")):
            value = [
                [value["x1"], value["y1"]],
                [value["x2"], value["y2"]],
                [value["x3"], value["y3"]],
                [value["x4"], value["y4"]],
            ]
    if isinstance(value, (list, tuple)) and len(value) == 4 and all(_optional_number(part) is not None for part in value):
        x, y, width, height = [float(part) for part in value]
        return (x, y, max(0.0, width), max(0.0, height))
    points: list[tuple[float, float]] = []
    try:
        for point in value:
            if hasattr(point, "tolist"):
                point = point.tolist()
            if len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
    except (TypeError, ValueError):
        return None
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def _frame_width_from_records(records: list[dict[str, Any]]) -> int | None:
    return _image_dimension_from_records(records, 0)


def _frame_height_from_records(records: list[dict[str, Any]]) -> int | None:
    return _image_dimension_from_records(records, 1)


def _image_dimension_from_records(records: list[dict[str, Any]], index: int) -> int | None:
    for record in records:
        frame = record.get("frame")
        if not frame:
            continue
        try:
            from PIL import Image

            with Image.open(Path(str(frame))) as image:
                return int(image.size[index])
        except Exception:
            continue
    return None


def _line_count_from_records(records: list[dict[str, Any]]) -> int:
    texts = {str(record.get("text") or "").strip() for record in records if str(record.get("text") or "").strip()}
    return len(texts)


def _lines_from_any(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, (list, tuple)):
        lines: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text") or item.get("line") or item.get("value")
                if text:
                    lines.append(str(text).strip())
            elif item is not None:
                lines.append(str(item).strip())
        return [line for line in lines if line]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_text(text: str) -> str:
    folds = {
        "İ": "I",
        "İ": "I",
        "ı": "I",
        "i": "I",
        "Ş": "S",
        "ş": "S",
        "Ğ": "G",
        "ğ": "G",
        "Ü": "U",
        "ü": "U",
        "Ö": "O",
        "ö": "O",
        "Ç": "C",
        "ç": "C",
    }
    for old, new in folds.items():
        text = text.replace(old, new)
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text.upper()).split())


def _mean(values: Iterable[float | None]) -> float | None:
    numeric = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return round(statistics.fmean(numeric), 6) if numeric else None


def _number(value: Any, *, default: float) -> float:
    parsed = _optional_number(value)
    return default if parsed is None else parsed


def _optional_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "panel", "present"}:
        return True
    if text in {"0", "false", "no", "n", "none", "absent"}:
        return False
    return None


def _md_value(value: Any) -> str:
    return "" if value is None else str(value)


if __name__ == "__main__":  # pragma: no cover
    sys.path.insert(0, str(PROJECT_ROOT))
    raise SystemExit(main())
