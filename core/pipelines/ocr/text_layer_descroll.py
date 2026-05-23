"""Text-layer de-scroll from OCR bounding boxes.

This module is a second-pass experiment over an existing OCR item directory. It
does not align full video frames. Instead, it turns stable OCR tracks into a
readable text-only strip by cropping only the detected text boxes.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import csv
import json
import math
from pathlib import Path
import re
from statistics import median, pstdev
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from core.pipelines.ocr.credit_experiment import normalize_text


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEXT_CORRECTIONS_PATH = PROJECT_ROOT / "data" / "ocr_text_corrections.json"


@dataclass(frozen=True)
class TextLayerDescrollResult:
    output_dir: Path
    summary_path: Path
    report_path: Path
    strict_canvas_path: Path
    loose_canvas_path: Path
    ordered_text_path: Path
    structured_json_path: Path
    review_pack_path: Path


def run_text_layer_descroll(
    item_dir: str | Path,
    *,
    output_dir: str | Path | None = None,
    engine: str = "paddle",
    min_records: int = 3,
    min_confidence: float = 0.65,
    strict_min_records: int = 8,
    strict_min_confidence: float = 0.90,
    scale: int = 2,
    fusion_engines: list[str] | None = None,
) -> TextLayerDescrollResult:
    item_dir = Path(item_dir)
    output_dir = Path(output_dir) if output_dir else item_dir / "text_layer_descroll_v2"
    output_dir.mkdir(parents=True, exist_ok=True)

    temporal_path = item_dir / "temporal_voting.json"
    frame_ocr_path = item_dir / "frame_ocr.json"
    if not temporal_path.exists():
        raise FileNotFoundError(f"Missing temporal_voting.json: {temporal_path}")
    if not frame_ocr_path.exists():
        raise FileNotFoundError(f"Missing frame_ocr.json: {frame_ocr_path}")

    temporal = _read_json(temporal_path)
    frame_ocr = _read_json(frame_ocr_path)
    item_summary = _read_optional_json(item_dir / "item_summary.json")
    expected_language = str(item_summary.get("expected_language") or "").lower() or None
    available_engines = sorted({str(record.get("engine") or "") for record in temporal.get("records", []) if record.get("engine")})
    selected_engines = _normalize_fusion_engines(engine, fusion_engines, available_engines)
    tracks_by_engine: dict[str, list[dict[str, Any]]] = {}
    for engine_name in selected_engines:
        engine_records = [record for record in temporal.get("records", []) if str(record.get("engine") or "") == engine_name]
        engine_groups = {str(group.get("line_group_id")): group for group in temporal.get("groups", []) if str(group.get("engine") or "") == engine_name}
        tracks_by_engine[engine_name] = _build_tracks(engine_records, engine_groups, engine_name=engine_name, expected_language=expected_language)

    records = [record for record in temporal.get("records", []) if str(record.get("engine") or "") == engine]
    groups = {str(group.get("line_group_id")): group for group in temporal.get("groups", []) if str(group.get("engine") or "") == engine}
    tracks = tracks_by_engine.get(engine) or _build_tracks(records, groups, engine_name=engine, expected_language=expected_language)
    all_tracks = [track for values in tracks_by_engine.values() for track in values]
    loose_tracks = _select_tracks(tracks, min_records=min_records, min_confidence=min_confidence)
    strict_tracks = _select_tracks(tracks, min_records=strict_min_records, min_confidence=strict_min_confidence)
    loose_tracks = _score_and_fuse_tracks(loose_tracks, all_tracks, expected_language=expected_language)
    strict_tracks = _score_and_fuse_tracks(strict_tracks, all_tracks, expected_language=expected_language)

    frame_paths = [Path(path) for path in frame_ocr.get("frames", [])]
    frame_size = _frame_size(frame_paths)
    bbox_layout = _detect_bbox_layout(loose_tracks, strict_tracks, frame_size=frame_size)
    _assign_column_ids(loose_tracks, bbox_layout)
    _assign_column_ids(strict_tracks, bbox_layout)
    role_name_pairs = _build_role_name_pairs(strict_tracks, loose_tracks, frame_size=frame_size, expected_language=expected_language, bbox_layout=bbox_layout)
    review_items = _build_review_items(strict_tracks, role_name_pairs, output_dir=output_dir)
    loose_canvas_path = output_dir / "text_layer_canvas_loose.png"
    strict_canvas_path = output_dir / "text_layer_canvas_strict.png"
    render_path = output_dir / "ordered_text_render.png"
    role_name_render_path = output_dir / "role_name_render.png"

    loose_canvas = _build_text_layer_canvas(loose_tracks, loose_canvas_path, frame_size=frame_size, scale=scale)
    strict_canvas = _build_text_layer_canvas(strict_tracks, strict_canvas_path, frame_size=frame_size, scale=scale)
    _render_ordered_text(strict_tracks, render_path)
    _render_role_name_pairs(role_name_pairs, role_name_render_path)

    ordered_text_path = output_dir / "ordered_credits_candidates.txt"
    ordered_text_path.write_text("\n".join(str(track.get("corrected_text") or track["winner_text"]) for track in strict_tracks) + "\n", encoding="utf-8")
    structured_json_path = output_dir / "structured_credits.json"
    review_pack_path = output_dir / "review_pack.json"
    review_csv_path = output_dir / "review_pack.csv"
    structured_json_path.write_text(json.dumps({"credits": role_name_pairs}, ensure_ascii=False, indent=2), encoding="utf-8")
    review_pack_path.write_text(json.dumps({"items": review_items}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_review_csv(review_csv_path, review_items)

    summary = {
        "strategy": "text_layer_descroll_v2",
        "item_dir": str(item_dir),
        "engine": engine,
        "fusion_engines": selected_engines,
        "expected_language": expected_language,
        "input_records": len(records),
        "input_groups": len(groups),
        "loose_threshold": {"min_records": min_records, "min_confidence": min_confidence},
        "strict_threshold": {"min_records": strict_min_records, "min_confidence": strict_min_confidence},
        "loose_track_count": len(loose_tracks),
        "strict_track_count": len(strict_tracks),
        "role_name_pair_count": len(role_name_pairs),
        "review_item_count": len(review_items),
        "needs_review_count": sum(1 for item in review_items if item.get("needs_review")),
        "frame_size": list(frame_size) if frame_size else None,
        "bbox_layout": bbox_layout,
        "estimated_scroll": _estimate_scroll(tracks),
        "outputs": {
            "loose_canvas": str(loose_canvas_path),
            "strict_canvas": str(strict_canvas_path),
            "ordered_text_render": str(render_path),
            "role_name_render": str(role_name_render_path),
            "ordered_text": str(ordered_text_path),
            "structured_json": str(structured_json_path),
            "review_pack": str(review_pack_path),
            "review_csv": str(review_csv_path),
        },
        "canvas": {"loose": loose_canvas, "strict": strict_canvas},
        "strict_tracks": [_public_track(track) for track in strict_tracks],
        "loose_tracks": [_public_track(track) for track in loose_tracks],
        "role_name_pairs": role_name_pairs,
        "review_items": review_items,
    }

    summary_path = output_dir / "text_layer_descroll_summary.json"
    report_path = output_dir / "text_layer_descroll_report.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(summary), encoding="utf-8")
    return TextLayerDescrollResult(
        output_dir=output_dir,
        summary_path=summary_path,
        report_path=report_path,
        strict_canvas_path=strict_canvas_path,
        loose_canvas_path=loose_canvas_path,
        ordered_text_path=ordered_text_path,
        structured_json_path=structured_json_path,
        review_pack_path=review_pack_path,
    )


def _build_tracks(records: list[dict[str, Any]], groups: dict[str, dict[str, Any]], *, engine_name: str, expected_language: str | None) -> list[dict[str, Any]]:
    by_group: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        group_id = str(record.get("line_group_id") or "")
        if not group_id or not record.get("bbox"):
            continue
        text = str(record.get("text") or "").strip()
        normalized = str(record.get("normalized_text") or normalize_text(text))
        if not _looks_like_text(normalized):
            continue
        by_group.setdefault(group_id, []).append(record)

    tracks: list[dict[str, Any]] = []
    for group_id, group_records in by_group.items():
        meta = groups.get(group_id, {})
        winner = str(meta.get("winner_text") or _best_text(group_records))
        winner_norm = str(meta.get("winner_normalized_text") or normalize_text(winner))
        confidences = [_as_float(record.get("confidence")) for record in group_records if _as_float(record.get("confidence")) is not None]
        timestamps = [_as_float(record.get("timestamp_seconds")) for record in group_records if _as_float(record.get("timestamp_seconds")) is not None]
        bboxes = [record.get("bbox") for record in group_records if _valid_bbox(record.get("bbox"))]
        if not timestamps or not bboxes:
            continue
        best_record = _best_record_for_crop(group_records, winner_norm)
        if best_record is None:
            continue
        tracks.append(
            {
                "line_group_id": group_id,
                "engine": engine_name,
                "winner_text": winner,
                "winner_normalized_text": winner_norm,
                "corrected_text": _correct_display_text(winner, expected_language=expected_language),
                "records": group_records,
                "record_count": len(group_records),
                "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
                "first_timestamp_seconds": min(timestamps),
                "last_timestamp_seconds": max(timestamps),
                "median_timestamp_seconds": median(timestamps),
                "median_bbox": _median_bbox(bboxes),
                "best_record": best_record,
                "motion": _track_motion(group_records),
            }
        )

    tracks.sort(key=lambda track: (track["median_timestamp_seconds"], _bbox_center_y(track["median_bbox"])))
    return _dedupe_tracks(tracks)


def _select_tracks(tracks: list[dict[str, Any]], *, min_records: int, min_confidence: float) -> list[dict[str, Any]]:
    selected = []
    for track in tracks:
        if int(track.get("record_count") or 0) < min_records:
            continue
        if (track.get("mean_confidence") or 0.0) < min_confidence:
            continue
        normalized = str(track.get("winner_normalized_text") or "")
        if not _looks_like_credit_line(normalized):
            continue
        selected.append(track)
    return selected


def _normalize_fusion_engines(primary_engine: str, fusion_engines: list[str] | None, available_engines: list[str]) -> list[str]:
    requested = fusion_engines or available_engines or [primary_engine]
    ordered: list[str] = []
    for name in [primary_engine, *requested]:
        normalized = str(name or "").strip()
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    return ordered


def _score_and_fuse_tracks(tracks: list[dict[str, Any]], all_tracks: list[dict[str, Any]], *, expected_language: str | None) -> list[dict[str, Any]]:
    scored = []
    for track in tracks:
        enriched = dict(track)
        agreement = _engine_agreement(track, all_tracks)
        enriched["engine_agreement"] = agreement
        enriched["position_consistency_score"] = _position_consistency_score(track)
        enriched["text_length_score"] = _text_length_score(str(track.get("winner_normalized_text") or ""))
        enriched["temporal_stability_score"] = _temporal_stability_score(track)
        enriched["quality_score"] = _credit_quality_score(enriched)
        fused_text, fused_source = _fused_text(track, agreement, expected_language=expected_language)
        enriched["corrected_text"] = fused_text
        enriched["correction_source"] = fused_source
        flags = _review_flags(enriched)
        enriched["needs_review"] = bool(flags)
        enriched["review_flags"] = flags
        scored.append(enriched)
    scored.sort(key=lambda track: (track["median_timestamp_seconds"], _bbox_center_y(track["median_bbox"])))
    return scored


def _engine_agreement(track: dict[str, Any], all_tracks: list[dict[str, Any]]) -> dict[str, Any]:
    matches = []
    for other in all_tracks:
        if other is track or other.get("engine") == track.get("engine"):
            continue
        if not _tracks_spatially_close(track, other):
            continue
        ratio = SequenceMatcher(None, str(track.get("winner_normalized_text") or ""), str(other.get("winner_normalized_text") or "")).ratio()
        if ratio < 0.45:
            continue
        matches.append(
            {
                "engine": other.get("engine"),
                "text": other.get("winner_text"),
                "corrected_text": other.get("corrected_text") or other.get("winner_text"),
                "normalized_text": other.get("winner_normalized_text"),
                "ratio": round(ratio, 4),
                "quality": round(_track_quality(other), 4),
                "record_count": other.get("record_count"),
                "mean_confidence": other.get("mean_confidence"),
            }
        )
    matches.sort(key=lambda item: (-float(item["ratio"]), -float(item["quality"])))
    best_ratio = float(matches[0]["ratio"]) if matches else 0.0
    return {"score": round(best_ratio, 4), "matches": matches[:5]}


def _tracks_spatially_close(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a_box = a.get("median_bbox")
    b_box = b.get("median_bbox")
    if not _valid_bbox(a_box) or not _valid_bbox(b_box):
        return False
    time_delta = abs(float(a.get("median_timestamp_seconds") or 0.0) - float(b.get("median_timestamp_seconds") or 0.0))
    if time_delta > 1.2:
        return False
    center_delta = math.hypot(_bbox_center_x(a_box) - _bbox_center_x(b_box), _bbox_center_y(a_box) - _bbox_center_y(b_box))
    return center_delta < 95.0


def _fused_text(track: dict[str, Any], agreement: dict[str, Any], *, expected_language: str | None) -> tuple[str, str]:
    own_text = _correct_display_text(str(track.get("winner_text") or ""), expected_language=expected_language)
    own_norm = normalize_text(own_text)
    own_quality = _track_quality(track)
    best_text = own_text
    best_source = str(track.get("engine") or "primary")
    best_quality = own_quality
    for match in agreement.get("matches") or []:
        ratio = float(match.get("ratio") or 0.0)
        if ratio < 0.72:
            continue
        match_text = _correct_display_text(str(match.get("corrected_text") or match.get("text") or ""), expected_language=expected_language)
        match_norm = normalize_text(match_text)
        if own_norm and own_norm in match_norm and len(match_norm) > len(own_norm) + 4:
            # Combined OCR lines such as "Taylor MICHAEL BIEHN" are useful for
            # role extraction, but they should not replace the cleaner name.
            continue
        match_quality = float(match.get("quality") or 0.0)
        if _text_preference_score(match_text) + match_quality * 0.02 > _text_preference_score(best_text) + best_quality * 0.02:
            best_text = match_text
            best_source = str(match.get("engine") or "engine_agreement")
            best_quality = match_quality
    return best_text, best_source


def _text_preference_score(text: str) -> float:
    normalized = normalize_text(text)
    if not normalized:
        return -1.0
    score = 0.0
    if _looks_like_person_or_credit_name(text):
        score += 1.0
    score += min(len(normalized) / 24.0, 1.0) * 0.35
    if _has_obvious_ocr_noise(text):
        score -= 1.0
    if re.search(r"[!|_»—]{2,}", text):
        score -= 0.4
    return score


def _credit_quality_score(track: dict[str, Any]) -> float:
    ocr = float(track.get("mean_confidence") or 0.0)
    temporal = float(track.get("temporal_stability_score") or 0.0)
    position = float(track.get("position_consistency_score") or 0.0)
    length = float(track.get("text_length_score") or 0.0)
    agreement = float((track.get("engine_agreement") or {}).get("score") or 0.0)
    return round(ocr * 0.38 + temporal * 0.24 + position * 0.16 + length * 0.12 + agreement * 0.10, 4)


def _temporal_stability_score(track: dict[str, Any]) -> float:
    count = int(track.get("record_count") or 0)
    return round(min(1.0, count / 12.0), 4)


def _text_length_score(normalized: str) -> float:
    length = len(normalized.replace(" ", ""))
    if length <= 1:
        return 0.0
    if 4 <= length <= 36:
        return 1.0
    if length < 4:
        return round(length / 4.0, 4)
    return round(max(0.2, 1.0 - ((length - 36) / 60.0)), 4)


def _position_consistency_score(track: dict[str, Any]) -> float:
    boxes = [record.get("bbox") for record in track.get("records") or [] if _valid_bbox(record.get("bbox"))]
    if len(boxes) < 3:
        return 0.6
    centers_x = [_bbox_center_x(box) for box in boxes]
    widths = [float(box[2]) for box in boxes]
    x_stability = 1.0 - min(1.0, (pstdev(centers_x) if len(centers_x) > 1 else 0.0) / 90.0)
    width_stability = 1.0 - min(1.0, (pstdev(widths) if len(widths) > 1 else 0.0) / 80.0)
    return round(max(0.0, (x_stability * 0.65) + (width_stability * 0.35)), 4)


def _review_flags(track: dict[str, Any]) -> list[str]:
    flags = []
    text = str(track.get("corrected_text") or track.get("winner_text") or "")
    normalized = normalize_text(text)
    if float(track.get("quality_score") or 0.0) < 0.68:
        flags.append("low_quality_score")
    if float(track.get("mean_confidence") or 0.0) < 0.78:
        flags.append("low_ocr_confidence")
    if int(track.get("record_count") or 0) < 4:
        flags.append("low_temporal_support")
    if _has_obvious_ocr_noise(text):
        flags.append("ocr_noise_pattern")
    if len(normalized.replace(" ", "")) < 3:
        flags.append("too_short")
    if float((track.get("engine_agreement") or {}).get("score") or 0.0) < 0.55:
        flags.append("no_engine_agreement")
    return flags


def _detect_bbox_layout(loose_tracks: list[dict[str, Any]], strict_tracks: list[dict[str, Any]], *, frame_size: tuple[int, int] | None) -> dict[str, Any]:
    all_tracks = loose_tracks or strict_tracks
    frame_width = frame_size[0] if frame_size else _max_track_right(all_tracks)
    name_centers = []
    role_centers = []
    for track in all_tracks:
        bbox = track.get("median_bbox")
        if not _valid_bbox(bbox):
            continue
        center = _bbox_center_x(bbox)
        text = str(track.get("corrected_text") or track.get("winner_text") or "")
        if _looks_like_person_or_credit_name(text):
            name_centers.append(center)
        elif _looks_like_credit_line(normalize_text(text)):
            role_centers.append(center)

    role_name = {"status": "insufficient_data", "role_band": None, "name_band": None, "split_x": None}
    if name_centers and role_centers:
        role_band = [round(min(role_centers), 2), round(max(role_centers), 2)]
        name_band = [round(min(name_centers), 2), round(max(name_centers), 2)]
        gap = min(name_centers) - max(role_centers)
        role_name = {
            "status": "detected" if gap > 8 else "overlapping",
            "role_band": role_band,
            "name_band": name_band,
            "split_x": round((max(role_centers) + min(name_centers)) / 2.0, 2) if gap > 8 else None,
        }

    columns = [{"id": 1, "left": 0.0, "right": float(frame_width)}]
    if len(name_centers) >= 6:
        sorted_names = sorted(name_centers)
        gaps = [(sorted_names[index + 1] - sorted_names[index], index) for index in range(len(sorted_names) - 1)]
        largest_gap, gap_index = max(gaps, key=lambda item: item[0])
        left_count = gap_index + 1
        right_count = len(sorted_names) - left_count
        if largest_gap > frame_width * 0.22 and left_count >= 3 and right_count >= 3:
            split = (sorted_names[gap_index] + sorted_names[gap_index + 1]) / 2.0
            columns = [
                {"id": 1, "left": 0.0, "right": round(split, 2)},
                {"id": 2, "left": round(split, 2), "right": float(frame_width)},
            ]

    return {
        "frame_width": frame_width,
        "role_name_layout": role_name,
        "columns": columns,
        "column_count": len(columns),
    }


def _assign_column_ids(tracks: list[dict[str, Any]], bbox_layout: dict[str, Any]) -> None:
    columns = bbox_layout.get("columns") or [{"id": 1, "left": 0.0, "right": float("inf")}]
    for track in tracks:
        bbox = track.get("median_bbox")
        if not _valid_bbox(bbox):
            track["column_id"] = None
            continue
        center = _bbox_center_x(bbox)
        column_id = columns[-1].get("id", 1)
        for column in columns:
            if float(column.get("left") or 0.0) <= center <= float(column.get("right") or 0.0):
                column_id = column.get("id", 1)
                break
        track["column_id"] = column_id


def _build_role_name_pairs(
    strict_tracks: list[dict[str, Any]],
    loose_tracks: list[dict[str, Any]],
    *,
    frame_size: tuple[int, int] | None,
    expected_language: str | None,
    bbox_layout: dict[str, Any],
) -> list[dict[str, Any]]:
    frame_width = frame_size[0] if frame_size else _max_track_right(strict_tracks + loose_tracks)
    name_tracks = [track for track in strict_tracks if _is_likely_name_track(track, frame_width)]
    role_tracks = [track for track in loose_tracks if _is_likely_role_track(track, frame_width)]
    pairs = []
    used_roles: set[str] = set()
    for index, name_track in enumerate(name_tracks, 1):
        embedded_role = _role_from_engine_match(name_track, expected_language=expected_language)
        role_track = None if embedded_role else _best_role_for_name(name_track, role_tracks, used_roles, frame_width=frame_width)
        if role_track:
            used_roles.add(str(role_track.get("line_group_id")))
        confidence = _pair_confidence(name_track, role_track)
        flags = []
        if confidence < 0.72:
            flags.append("low_pair_confidence")
        if role_track is None and not embedded_role:
            flags.append("missing_role")
        if name_track.get("needs_review"):
            flags.append("name_needs_review")
        if role_track and role_track.get("needs_review"):
            flags.append("role_needs_review")
        pair = {
            "index": index,
            "role": embedded_role or (_correct_role_text(str((role_track or {}).get("corrected_text") or (role_track or {}).get("winner_text") or ""), expected_language=expected_language) if role_track else None),
            "name": _correct_display_text(str(name_track.get("corrected_text") or name_track.get("winner_text") or ""), expected_language=expected_language),
            "confidence": confidence,
            "needs_review": confidence < 0.72 or bool(flags),
            "review_flags": flags,
            "role_track_id": role_track.get("line_group_id") if role_track else None,
            "role_source": "engine_embedded_line" if embedded_role else ("bbox_pair" if role_track else None),
            "name_track_id": name_track.get("line_group_id"),
            "column_id": name_track.get("column_id"),
            "role_bbox": role_track.get("median_bbox") if role_track else None,
            "name_bbox": name_track.get("median_bbox"),
            "role_quality": role_track.get("quality_score") if role_track else None,
            "name_quality": name_track.get("quality_score"),
            "timestamp_seconds": name_track.get("median_timestamp_seconds"),
        }
        pairs.append(pair)
    return pairs


def _best_role_for_name(name_track: dict[str, Any], role_tracks: list[dict[str, Any]], used_roles: set[str], *, frame_width: float | None = None) -> dict[str, Any] | None:
    name_box = name_track.get("median_bbox")
    if not _valid_bbox(name_box):
        return None
    candidates = []
    for role_track in role_tracks:
        if str(role_track.get("line_group_id")) in used_roles:
            continue
        if name_track.get("column_id") and role_track.get("column_id") and name_track.get("column_id") != role_track.get("column_id"):
            continue
        role_box = role_track.get("median_bbox")
        if not _valid_bbox(role_box):
            continue
        min_x_separation = max(14.0, float(frame_width or 0.0) * 0.012)
        if _bbox_center_x(role_box) >= _bbox_center_x(name_box) - min_x_separation:
            continue
        time_delta = abs(float(role_track.get("median_timestamp_seconds") or 0.0) - float(name_track.get("median_timestamp_seconds") or 0.0))
        y_delta = abs(_bbox_center_y(role_box) - _bbox_center_y(name_box))
        if time_delta > 1.4 or y_delta > 58:
            continue
        x_gap = max(0.0, float(name_box[0]) - (float(role_box[0]) + float(role_box[2])))
        score = (1.0 / (1.0 + y_delta)) * 3.0 + (1.0 / (1.0 + time_delta)) * 2.0 + min(1.0, x_gap / 80.0) + float(role_track.get("quality_score") or 0.0)
        candidates.append((score, role_track))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _role_from_engine_match(name_track: dict[str, Any], *, expected_language: str | None) -> str | None:
    name_text = str(name_track.get("winner_text") or "")
    name_norm = normalize_text(name_text)
    if not name_norm:
        return None
    name_tokens = name_norm.split()
    for match in (name_track.get("engine_agreement") or {}).get("matches") or []:
        raw = str(match.get("text") or "")
        raw_norm = normalize_text(raw)
        if not raw_norm or raw_norm == name_norm:
            continue
        if name_norm not in raw_norm:
            continue
        prefix_norm = raw_norm.split(name_norm, 1)[0].strip()
        if not prefix_norm or len(prefix_norm) < 3:
            continue
        # Extract the raw prefix using a tolerant token boundary. This handles
        # combined OCR like "Harold MATT CRAVEN" and "Cindy JULIA NICKSON-SOUL".
        raw_prefix = _raw_prefix_before_name(raw, name_tokens)
        role = _clean_ocr_punctuation(raw_prefix or prefix_norm.title())
        if role and not _has_obvious_ocr_noise(role):
            return _correct_role_text(role, expected_language=expected_language)
    return None


def _raw_prefix_before_name(raw: str, name_tokens: list[str]) -> str | None:
    raw_tokens = raw.split()
    if not raw_tokens or not name_tokens:
        return None
    normalized_tokens = [normalize_text(token) for token in raw_tokens]
    for index in range(len(normalized_tokens)):
        window = " ".join(normalized_tokens[index : index + len(name_tokens)])
        if SequenceMatcher(None, window, " ".join(name_tokens)).ratio() >= 0.86:
            return " ".join(raw_tokens[:index]).strip()
    return None


def _pair_confidence(name_track: dict[str, Any], role_track: dict[str, Any] | None) -> float:
    name_score = float(name_track.get("quality_score") or 0.0)
    if role_track is None:
        return round(name_score * 0.72, 4)
    role_score = float(role_track.get("quality_score") or 0.0)
    name_box = name_track.get("median_bbox")
    role_box = role_track.get("median_bbox")
    y_score = 0.5
    if _valid_bbox(name_box) and _valid_bbox(role_box):
        y_score = 1.0 - min(1.0, abs(_bbox_center_y(role_box) - _bbox_center_y(name_box)) / 60.0)
    return round(name_score * 0.58 + role_score * 0.24 + y_score * 0.18, 4)


def _is_likely_name_track(track: dict[str, Any], frame_width: int) -> bool:
    text = str(track.get("corrected_text") or track.get("winner_text") or "")
    bbox = track.get("median_bbox")
    if not _valid_bbox(bbox):
        return False
    if _bbox_center_x(bbox) < frame_width * 0.36 and float(bbox[2]) < frame_width * 0.22:
        return False
    if not _looks_like_person_or_credit_name(text):
        return False
    if _has_obvious_ocr_noise(text):
        return False
    return True


def _is_likely_role_track(track: dict[str, Any], frame_width: int) -> bool:
    text = str(track.get("corrected_text") or track.get("winner_text") or "")
    bbox = track.get("median_bbox")
    if not _valid_bbox(bbox):
        return False
    if _bbox_center_x(bbox) > frame_width * 0.62:
        return False
    if _has_obvious_ocr_noise(text):
        return False
    if _is_mostly_uppercase_name(text) and len(normalize_text(text).split()) >= 2:
        return False
    return _looks_like_credit_line(normalize_text(text))


def _build_review_items(tracks: list[dict[str, Any]], role_name_pairs: list[dict[str, Any]], *, output_dir: Path) -> list[dict[str, Any]]:
    items = []
    review_crops_dir = output_dir / "review_crops"
    review_crops_dir.mkdir(parents=True, exist_ok=True)
    track_crop_paths: dict[str, str] = {}
    paired_name_ids = {pair.get("name_track_id") for pair in role_name_pairs}
    paired_role_ids = {pair.get("role_track_id") for pair in role_name_pairs if pair.get("role_track_id")}
    for track in tracks:
        track_id = track.get("line_group_id")
        flags = list(track.get("review_flags") or [])
        if track_id not in paired_name_ids and track_id not in paired_role_ids:
            flags.append("unpaired_track")
        crop_path = _write_review_crop(review_crops_dir, track)
        if crop_path:
            track_crop_paths[str(track_id)] = crop_path
        items.append(
            {
                "type": "track",
                "id": track_id,
                "text": track.get("corrected_text") or track.get("winner_text"),
                "raw_text": track.get("winner_text"),
                "suggested_text": track.get("corrected_text") or track.get("winner_text"),
                "accepted_text": "",
                "quality_score": track.get("quality_score"),
                "mean_confidence": track.get("mean_confidence"),
                "record_count": track.get("record_count"),
                "timestamp_seconds": track.get("median_timestamp_seconds"),
                "bbox": track.get("median_bbox"),
                "source_frame": str((track.get("best_record") or {}).get("frame") or ""),
                "engine": track.get("engine"),
                "column_id": track.get("column_id"),
                "crop_path": crop_path,
                "needs_review": bool(flags),
                "review_flags": sorted(set(flags)),
            }
        )
    for pair in role_name_pairs:
        items.append(
            {
                "type": "role_name_pair",
                "id": f"pair_{pair.get('index'):04d}",
                "role": pair.get("role"),
                "name": pair.get("name"),
                "suggested_role": pair.get("role") or "",
                "suggested_name": pair.get("name") or "",
                "accepted_role": "",
                "accepted_name": "",
                "name_track_id": pair.get("name_track_id"),
                "role_track_id": pair.get("role_track_id"),
                "column_id": pair.get("column_id"),
                "crop_path": track_crop_paths.get(str(pair.get("name_track_id")), ""),
                "quality_score": pair.get("confidence"),
                "needs_review": pair.get("needs_review"),
                "review_flags": pair.get("review_flags"),
            }
        )
    return items


def _write_review_crop(review_crops_dir: Path, track: dict[str, Any]) -> str:
    track_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(track.get("line_group_id") or "track"))
    output = review_crops_dir / f"{track_id}.png"
    try:
        crop = _masked_text_crop(track["best_record"], scale=2)
        if crop is None:
            return ""
        background = Image.new("RGBA", crop.size, (0, 0, 0, 255))
        background.alpha_composite(crop, (0, 0))
        background.convert("RGB").save(output)
        return str(output)
    except Exception:
        return ""


def _write_review_csv(path: Path, review_items: list[dict[str, Any]]) -> None:
    fieldnames = [
        "type",
        "id",
        "role",
        "name",
        "text",
        "raw_text",
        "suggested_text",
        "accepted_text",
        "suggested_role",
        "accepted_role",
        "suggested_name",
        "accepted_name",
        "quality_score",
        "mean_confidence",
        "record_count",
        "timestamp_seconds",
        "engine",
        "column_id",
        "crop_path",
        "needs_review",
        "review_flags",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in review_items:
            writer.writerow({name: _csv_value(item.get(name)) for name in fieldnames})


def _csv_value(value: Any) -> str:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _build_text_layer_canvas(
    tracks: list[dict[str, Any]],
    output_path: Path,
    *,
    frame_size: tuple[int, int] | None,
    scale: int,
) -> dict[str, Any]:
    if not tracks:
        image = Image.new("RGB", (1200, 120), "black")
        ImageDraw.Draw(image).text((24, 45), "No stable text tracks", fill="white", font=_font(28))
        image.save(output_path)
        return {"path": str(output_path), "track_count": 0, "size": list(image.size)}

    frame_width = frame_size[0] if frame_size else _max_track_right(tracks)
    margin_x = 28 * scale
    margin_y = 18 * scale
    gap = 8 * scale
    canvas_width = max(900, int(frame_width * scale) + margin_x * 2)

    prepared = []
    y = margin_y
    for track in tracks:
        crop = _masked_text_crop(track["best_record"], scale=scale)
        if crop is None:
            continue
        bbox = track["best_record"].get("bbox") or track["median_bbox"]
        x = max(margin_x, int(round(float(bbox[0]) * scale)) + margin_x)
        prepared.append((track, crop, x, y))
        y += crop.height + gap

    canvas_height = max(120, y + margin_y)
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 255))
    for _track, crop, x, y_pos in prepared:
        canvas.alpha_composite(crop, (min(x, max(0, canvas_width - crop.width - margin_x)), y_pos))
    rgb_canvas = canvas.convert("RGB")
    rgb_canvas.save(output_path)
    return {"path": str(output_path), "track_count": len(prepared), "size": list(rgb_canvas.size)}


def _masked_text_crop(record: dict[str, Any], *, scale: int) -> Image.Image | None:
    frame_path = Path(str(record.get("frame") or record.get("source_frame") or ""))
    bbox = record.get("bbox")
    if not frame_path.exists() or not _valid_bbox(bbox):
        return None
    with Image.open(frame_path) as image:
        rgb = image.convert("RGB")
        x, y, w, h = [float(value) for value in bbox[:4]]
        pad_x = max(4, int(round(w * 0.08)))
        pad_y = max(3, int(round(h * 0.45)))
        left = max(0, int(math.floor(x - pad_x)))
        top = max(0, int(math.floor(y - pad_y)))
        right = min(rgb.width, int(math.ceil(x + w + pad_x)))
        bottom = min(rgb.height, int(math.ceil(y + h + pad_y)))
        if right <= left or bottom <= top:
            return None
        crop = rgb.crop((left, top, right, bottom))
    crop = ImageEnhance.Contrast(crop).enhance(1.25)
    mask = _text_mask(crop)
    rgba = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    rgba.paste(crop, (0, 0), mask)
    if scale > 1:
        rgba = rgba.resize((rgba.width * scale, rgba.height * scale), Image.Resampling.BICUBIC)
    return rgba


def _text_mask(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    import numpy as np

    hsv = np.asarray(rgb.convert("HSV"), dtype=np.uint8)
    gray_array = np.asarray(rgb.convert("L"), dtype=np.uint8)
    width, height = rgb.size
    med = float(np.median(gray_array)) if gray_array.size else 0.0
    threshold = max(88, min(210, med + 20))
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    saturated_text = (sat > 48) & (val > 80)
    bright_text = (gray_array > threshold) & (val > 95)
    mask_array = np.where(saturated_text | bright_text, 255, 0).astype(np.uint8)
    mask = Image.fromarray(mask_array, mode="L").resize((width, height)) if mask_array.shape[::-1] != (width, height) else Image.fromarray(mask_array, mode="L")
    return mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(radius=0.45))


def _render_ordered_text(tracks: list[dict[str, Any]], output_path: Path) -> None:
    font = _font(34)
    small = _font(22)
    width = 1200
    line_height = 52
    height = max(160, 70 + len(tracks) * line_height)
    image = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(image)
    draw.text((40, 24), "Ordered OCR candidates - strict stable tracks", fill=(180, 220, 255), font=small)
    y = 70
    for index, track in enumerate(tracks, 1):
        text = str(track.get("corrected_text") or track["winner_text"])
        conf = track.get("mean_confidence")
        count = track.get("record_count")
        quality = track.get("quality_score")
        flag = " !" if track.get("needs_review") else ""
        draw.text((40, y), f"{index:02d}", fill=(100, 150, 180), font=small)
        draw.text((105, y - 5), text, fill=(230, 245, 255), font=font)
        draw.text((820, y), f"n={count} conf={conf} q={quality}{flag}", fill=(130, 170, 190), font=small)
        y += line_height
    image.save(output_path)


def _render_role_name_pairs(pairs: list[dict[str, Any]], output_path: Path) -> None:
    font = _font(30)
    small = _font(21)
    width = 1500
    line_height = 50
    height = max(160, 70 + len(pairs) * line_height)
    image = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(image)
    draw.text((40, 24), "Structured role/name candidates", fill=(180, 220, 255), font=small)
    y = 70
    for pair in pairs:
        idx = int(pair.get("index") or 0)
        role = str(pair.get("role") or "")
        name = str(pair.get("name") or "")
        conf = pair.get("confidence")
        flag = " REVIEW" if pair.get("needs_review") else ""
        draw.text((40, y), f"{idx:02d}", fill=(100, 150, 180), font=small)
        draw.text((100, y - 3), role[:34], fill=(210, 210, 210), font=font)
        draw.text((555, y - 3), name[:38], fill=(210, 238, 255), font=font)
        draw.text((1130, y), f"conf={conf}{flag}", fill=(130, 170, 190), font=small)
        y += line_height
    image.save(output_path)


def _estimate_scroll(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    velocities = []
    for track in tracks:
        motion = track.get("motion") or {}
        dy_per_sec = motion.get("dy_per_second")
        if dy_per_sec is not None and math.isfinite(float(dy_per_sec)):
            velocities.append(float(dy_per_sec))
    if not velocities:
        return {"status": "unknown", "median_dy_per_second": None, "direction": "unknown"}
    med = median(velocities)
    direction = "up" if med < -0.5 else "down" if med > 0.5 else "static"
    return {"status": "estimated", "median_dy_per_second": round(med, 3), "direction": direction, "sample_count": len(velocities)}


def _track_motion(records: list[dict[str, Any]]) -> dict[str, Any]:
    points = []
    for record in records:
        timestamp = _as_float(record.get("timestamp_seconds"))
        bbox = record.get("bbox")
        if timestamp is None or not _valid_bbox(bbox):
            continue
        points.append((timestamp, _bbox_center_x(bbox), _bbox_center_y(bbox)))
    points.sort()
    if len(points) < 2:
        return {"dx_per_second": None, "dy_per_second": None}
    dt = points[-1][0] - points[0][0]
    if abs(dt) < 1e-6:
        return {"dx_per_second": None, "dy_per_second": None}
    return {
        "dx_per_second": round((points[-1][1] - points[0][1]) / dt, 3),
        "dy_per_second": round((points[-1][2] - points[0][2]) / dt, 3),
    }


def _dedupe_tracks(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for track in tracks:
        normalized = str(track.get("winner_normalized_text") or "")
        duplicate = False
        for existing in kept:
            existing_norm = str(existing.get("winner_normalized_text") or "")
            if SequenceMatcher(None, normalized, existing_norm).ratio() > 0.94:
                duplicate = True
                if _track_quality(track) > _track_quality(existing):
                    existing.update(track)
                break
        if not duplicate:
            kept.append(track)
    kept.sort(key=lambda track: (track["median_timestamp_seconds"], _bbox_center_y(track["median_bbox"])))
    return kept


def _track_quality(track: dict[str, Any]) -> float:
    return float(track.get("record_count") or 0) * float(track.get("mean_confidence") or 0.0)


def _best_record_for_crop(records: list[dict[str, Any]], winner_norm: str) -> dict[str, Any] | None:
    candidates = []
    for record in records:
        bbox = record.get("bbox")
        if not _valid_bbox(bbox):
            continue
        text_norm = str(record.get("normalized_text") or normalize_text(str(record.get("text") or "")))
        similarity = SequenceMatcher(None, text_norm, winner_norm).ratio() if winner_norm else 0.0
        conf = _as_float(record.get("confidence")) or 0.0
        area = float(bbox[2]) * float(bbox[3])
        candidates.append((conf + similarity * 0.2 + min(area / 10000.0, 0.15), record))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _best_text(records: list[dict[str, Any]]) -> str:
    counts: dict[str, tuple[int, str]] = {}
    for record in records:
        text = str(record.get("text") or "").strip()
        normalized = str(record.get("normalized_text") or normalize_text(text))
        if normalized:
            count, _old_text = counts.get(normalized, (0, text))
            counts[normalized] = (count + 1, text)
    if not counts:
        return ""
    return max(counts.values(), key=lambda item: item[0])[1]


def _median_bbox(bboxes: list[Any]) -> list[float]:
    return [round(median(float(bbox[index]) for bbox in bboxes), 3) for index in range(4)]


def _frame_size(frame_paths: list[Path]) -> tuple[int, int] | None:
    for path in frame_paths:
        if path.exists():
            with Image.open(path) as image:
                return image.size
    return None


def _max_track_right(tracks: list[dict[str, Any]]) -> int:
    right = 0
    for track in tracks:
        bbox = track.get("median_bbox")
        if _valid_bbox(bbox):
            right = max(right, int(float(bbox[0]) + float(bbox[2])))
    return max(900, right)


def _public_track(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "line_group_id": track.get("line_group_id"),
        "engine": track.get("engine"),
        "winner_text": track.get("winner_text"),
        "winner_normalized_text": track.get("winner_normalized_text"),
        "corrected_text": track.get("corrected_text"),
        "record_count": track.get("record_count"),
        "mean_confidence": track.get("mean_confidence"),
        "quality_score": track.get("quality_score"),
        "temporal_stability_score": track.get("temporal_stability_score"),
        "position_consistency_score": track.get("position_consistency_score"),
        "text_length_score": track.get("text_length_score"),
        "engine_agreement": track.get("engine_agreement"),
        "column_id": track.get("column_id"),
        "needs_review": track.get("needs_review"),
        "review_flags": track.get("review_flags"),
        "first_timestamp_seconds": round(float(track.get("first_timestamp_seconds") or 0.0), 3),
        "last_timestamp_seconds": round(float(track.get("last_timestamp_seconds") or 0.0), 3),
        "median_bbox": track.get("median_bbox"),
        "motion": track.get("motion"),
    }


def _build_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Text-Layer De-scroll v2",
        "",
        f"- Item dir: {summary.get('item_dir')}",
        f"- Engine: {summary.get('engine')}",
        f"- Fusion engines: {', '.join(summary.get('fusion_engines') or [])}",
        f"- Input records: {summary.get('input_records')}",
        f"- Input groups: {summary.get('input_groups')}",
        f"- Loose tracks: {summary.get('loose_track_count')}",
        f"- Strict tracks: {summary.get('strict_track_count')}",
        f"- Role/name pairs: {summary.get('role_name_pair_count')}",
        f"- Needs review: {summary.get('needs_review_count')}",
        f"- Estimated scroll: {json.dumps(summary.get('estimated_scroll'), ensure_ascii=False)}",
        f"- Bbox layout: {json.dumps(summary.get('bbox_layout'), ensure_ascii=False)}",
        "",
        "## Outputs",
        "",
        f"- Loose canvas: {summary['outputs']['loose_canvas']}",
        f"- Strict canvas: {summary['outputs']['strict_canvas']}",
        f"- Ordered text render: {summary['outputs']['ordered_text_render']}",
        f"- Role/name render: {summary['outputs']['role_name_render']}",
        f"- Ordered text: {summary['outputs']['ordered_text']}",
        f"- Structured JSON: {summary['outputs']['structured_json']}",
        f"- Review pack: {summary['outputs']['review_pack']}",
        f"- Review CSV: {summary['outputs']['review_csv']}",
        "",
        "## Role/Name Pairs",
        "",
        "| # | Confidence | Review | Role | Name |",
        "| ---: | ---: | --- | --- | --- |",
    ]
    for pair in summary.get("role_name_pairs") or []:
        role = str(pair.get("role") or "").replace("|", "\\|")
        name = str(pair.get("name") or "").replace("|", "\\|")
        flags = ",".join(pair.get("review_flags") or [])
        lines.append(f"| {pair.get('index')} | {pair.get('confidence')} | {flags} | {role} | {name} |")
    lines.extend(
        [
            "",
            "## Strict Tracks",
            "",
            "| # | Time | Count | Conf | Quality | Review | Text |",
            "| ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for index, track in enumerate(summary.get("strict_tracks") or [], 1):
        first = float(track.get("first_timestamp_seconds") or 0.0)
        count = track.get("record_count")
        conf = track.get("mean_confidence")
        quality = track.get("quality_score")
        review = ",".join(track.get("review_flags") or [])
        text = str(track.get("corrected_text") or track.get("winner_text") or "").replace("|", "\\|")
        lines.append(f"| {index} | {first:.1f} | {count} | {conf} | {quality} | {review} | {text} |")
    return "\n".join(lines) + "\n"


def _correct_display_text(text: str, *, expected_language: str | None) -> str:
    cleaned = _clean_ocr_punctuation(text)
    cleaned = _apply_text_corrections(cleaned, expected_language=expected_language)
    if expected_language == "tr":
        return _restore_turkish_text(cleaned)
    return cleaned


def _correct_role_text(text: str, *, expected_language: str | None) -> str:
    cleaned = _correct_display_text(text, expected_language=expected_language)
    normalized = normalize_text(cleaned)
    phrase_map = _TR_ROLE_PHRASES if expected_language == "tr" else _EN_ROLE_PHRASES
    return phrase_map.get(normalized, cleaned)


def _clean_ocr_punctuation(text: str) -> str:
    text = str(text or "").strip()
    text = text.strip("|_»—- ")
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" / ", "/")
    text = text.replace("\\", "/")
    return text.strip()


_TR_ROLE_PHRASES = {
    "YONETMEN": "YÖNETMEN",
    "YAPIMCI": "YAPIMCI",
    "GORUNTU YONETMENI": "GÖRÜNTÜ YÖNETMENİ",
    "SANAT YONETMENI": "SANAT YÖNETMENİ",
    "MUZIK": "MÜZİK",
    "KURGU": "KURGU",
    "SES": "SES",
    "OYUNCULAR": "OYUNCULAR",
    "GENEL KOORDINATOR": "GENEL KOORDİNATÖR",
}

_EN_ROLE_PHRASES = {
    "DIRECTOR": "Director",
    "PRODUCER": "Producer",
    "EXECUTIVE PRODUCER": "Executive Producer",
    "SCRIPT SUPERVISOR": "Script Supervisor",
    "ART DIRECTOR": "Art Director",
    "SET DECORATOR": "Set Decorator",
    "SET DRESSER": "Set Dresser",
    "PRODUCTION MANAGER": "Production Manager",
    "LOCATION MANAGER": "Location Manager",
}


_DEFAULT_TEXT_CORRECTIONS = {
    "tr": {
        "YONETMEN": "YÖNETMEN",
        "GORUNTU YONETMENI": "GÖRÜNTÜ YÖNETMENİ",
        "SANAT YONETMENI": "SANAT YÖNETMENİ",
        "MUZIK": "MÜZİK",
        "GENEL KOORDINATOR": "GENEL KOORDİNATÖR",
    }
}


def _apply_text_corrections(text: str, *, expected_language: str | None) -> str:
    language = (expected_language or "").lower()
    corrections = dict(_DEFAULT_TEXT_CORRECTIONS.get(language, {}))
    corrections.update(_load_user_text_corrections().get(language, {}))
    if not corrections:
        return text
    normalized = normalize_text(text)
    if normalized in corrections:
        return corrections[normalized]
    tokens = text.split()
    changed = False
    corrected_tokens = []
    for token in tokens:
        key = normalize_text(token)
        if key in corrections:
            corrected_tokens.append(corrections[key])
            changed = True
        else:
            corrected_tokens.append(token)
    return " ".join(corrected_tokens) if changed else text


_USER_TEXT_CORRECTIONS_CACHE: tuple[float | None, dict[str, dict[str, str]]] | None = None


def _load_user_text_corrections() -> dict[str, dict[str, str]]:
    global _USER_TEXT_CORRECTIONS_CACHE
    current_mtime = TEXT_CORRECTIONS_PATH.stat().st_mtime if TEXT_CORRECTIONS_PATH.exists() else None
    if _USER_TEXT_CORRECTIONS_CACHE is not None and _USER_TEXT_CORRECTIONS_CACHE[0] == current_mtime:
        return _USER_TEXT_CORRECTIONS_CACHE[1]
    if not TEXT_CORRECTIONS_PATH.exists():
        _USER_TEXT_CORRECTIONS_CACHE = (None, {})
        return _USER_TEXT_CORRECTIONS_CACHE[1]
    try:
        raw = json.loads(TEXT_CORRECTIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        _USER_TEXT_CORRECTIONS_CACHE = (current_mtime, {})
        return _USER_TEXT_CORRECTIONS_CACHE[1]
    parsed: dict[str, dict[str, str]] = {}
    if isinstance(raw, dict):
        for language, mapping in raw.items():
            if not isinstance(mapping, dict):
                continue
            parsed[str(language).lower()] = {normalize_text(str(key)): str(value) for key, value in mapping.items()}
    _USER_TEXT_CORRECTIONS_CACHE = (current_mtime, parsed)
    return _USER_TEXT_CORRECTIONS_CACHE[1]


def _restore_turkish_text(text: str) -> str:
    normalized = normalize_text(text)
    if normalized in _TR_ROLE_PHRASES:
        return _TR_ROLE_PHRASES[normalized]
    # Conservative display restoration: only common role words are restored.
    replacements = {
        " YONETMEN ": " YÖNETMEN ",
        " GORUNTU ": " GÖRÜNTÜ ",
        " MUZIK ": " MÜZİK ",
        " KOORDINATOR ": " KOORDİNATÖR ",
    }
    padded = f" {text} "
    upper = padded.upper()
    for old, new in replacements.items():
        upper = upper.replace(old, new)
    return upper.strip() if text.isupper() else upper.strip().title()


def _looks_like_person_or_credit_name(text: str) -> bool:
    normalized = normalize_text(text)
    tokens = normalized.split()
    if not tokens:
        return False
    if len(tokens) == 1 and len(tokens[0]) < 4:
        return False
    if _has_obvious_ocr_noise(text):
        return False
    if _is_mostly_uppercase_name(text):
        return True
    return len(tokens) >= 2 and all(len(token) >= 2 or token in {"J", "K", "L"} for token in tokens)


def _is_mostly_uppercase_name(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(char.isupper() for char in letters) / len(letters)
    return upper_ratio >= 0.72


def _has_obvious_ocr_noise(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    compact = normalized.replace(" ", "")
    if len(compact) >= 10 and len(set(compact)) <= 4:
        return True
    if re.search(r"(.)\1{4,}", compact):
        return True
    if re.search(r"[0-9]{3,}", compact) and sum(char.isalpha() for char in compact) < 5:
        return True
    vowel_ratio = sum(char in "AEIOU" for char in compact) / max(1, sum(char.isalpha() for char in compact))
    if len(compact) > 12 and vowel_ratio < 0.12:
        return True
    symbol_ratio = sum(not char.isalnum() and not char.isspace() for char in text) / max(1, len(text))
    return symbol_ratio > 0.28


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return _read_json(path)
    except Exception:
        return {}


def _looks_like_text(normalized: str) -> bool:
    return sum(char.isalpha() for char in normalized) >= 3


def _looks_like_credit_line(normalized: str) -> bool:
    normalized = str(normalized or "").strip()
    if not _looks_like_text(normalized):
        return False
    compact = normalized.replace(" ", "")
    if len(compact) < 3:
        return False
    alpha_ratio = sum(char.isalpha() for char in compact) / max(1, len(compact))
    if alpha_ratio < 0.62:
        return False
    if compact.isdigit():
        return False
    if len(compact) >= 8 and len(set(compact)) <= 3:
        return False
    if re.search(r"(.)\1{4,}", compact):
        return False
    # Accept initials and abbreviations such as J. J. MAKARO after normalization.
    if len(normalized.split()) <= 1 and len(compact) <= 3:
        return False
    return True


def _valid_bbox(value: Any) -> bool:
    if not isinstance(value, list | tuple) or len(value) < 4:
        return False
    try:
        return float(value[2]) > 1 and float(value[3]) > 1
    except (TypeError, ValueError):
        return False


def _bbox_center_x(bbox: Any) -> float:
    return float(bbox[0]) + float(bbox[2]) / 2.0


def _bbox_center_y(bbox: Any) -> float:
    return float(bbox[1]) + float(bbox[3]) / 2.0


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in [Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/calibri.ttf"), Path("C:/Windows/Fonts/segoeui.ttf")]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()
