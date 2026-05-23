"""Aggregate OCR text-track states into POC credit segment suggestions."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable, Mapping

from core.pipelines.ocr.box_tracker import TextTrack
from core.pipelines.ocr.text_track_state import TextTrackState


@dataclass(frozen=True)
class SegmentDispatcherConfig:
    min_records: int = 12
    min_supported_tracks: int = 2
    min_track_observations: int = 3
    window_seconds: float = 1.5
    moving_track_ratio: float = 0.50
    moving_text_area_ratio: float = 0.40
    direction_consistency: float = 0.70
    static_text_area_ratio: float = 0.50
    merge_gap_seconds: float = 1.0
    unknown_bridge_seconds: float = 1.5
    suspicious_text_count_threshold: int = 10
    suspicious_min_duration_seconds: float = 3.0
    suspicious_scroll_threshold: float = 0.55
    churn_short_duration_seconds: float = 1.0
    low_static_confidence_threshold: float = 0.65


def dispatch_credit_segments(
    tracks: Iterable[TextTrack],
    states: Iterable[TextTrackState],
    *,
    records: Iterable[Mapping[str, Any]] | None = None,
    frame_size: tuple[int, int] | None = None,
    scene_profile: Mapping[str, Any] | None = None,
    config: SegmentDispatcherConfig | None = None,
) -> dict[str, Any]:
    """Return segment suggestions without running any production OCR pipeline."""

    cfg = config or SegmentDispatcherConfig()
    track_list = list(tracks)
    state_list = list(states)
    state_by_id = {state.track_id: state for state in state_list}
    record_count = len(list(records or []))
    supported = [state for state in state_list if state.record_count >= cfg.min_track_observations and state.state != "GONE"]

    if record_count < cfg.min_records or len(supported) < cfg.min_supported_tracks:
        return _insufficient_result(
            track_list,
            state_list,
            record_count,
            len(supported),
            failure_reason="low_support",
            config=cfg,
        )

    windows = _build_windows(state_list, cfg.window_seconds)
    labelled = [_label_window(window, supported, cfg) for window in windows]
    segments = _merge_windows(labelled, cfg.merge_gap_seconds)
    segments = _smooth_unknown_bridges(segments, cfg.unknown_bridge_seconds)
    segments = _bridge_unknowns_with_scene_router(segments, scene_profile)
    _attach_layout_signals(segments, track_list, state_by_id, frame_size=frame_size)
    _attach_suspicious_static_fallback(segments, state_list, config=cfg)
    status = "done" if any(segment["type"] in {"MOVING_SCROLL", "MOVING_SCROLL_INFERRED", "STATIC_CARD"} for segment in segments) else "insufficient_text"
    if status == "insufficient_text":
        return _insufficient_result(
            track_list,
            state_list,
            record_count,
            len(supported),
            failure_reason="no_confident_segment",
            config=cfg,
        )

    return {
        "strategy": "box_tracker_segment_dispatch_poc_v1",
        "status": status,
        "recommended_fallback": "legacy_credit_pipeline_selector",
        "record_count": record_count,
        "track_count": len(track_list),
        "supported_track_count": len(supported),
        "segments": segments,
        "tracks": [track.to_dict() for track in track_list],
        "track_states": [state.to_dict() for state in state_list],
    }


def _insufficient_result(
    tracks: list[TextTrack],
    states: list[TextTrackState],
    record_count: int,
    supported_track_count: int,
    *,
    failure_reason: str,
    config: SegmentDispatcherConfig,
) -> dict[str, Any]:
    start = _min_timestamp(states)
    end = _max_timestamp(states)
    segment = {
        "type": "UNKNOWN",
        "reason": "INSUFFICIENT_TEXT",
        "start_timestamp_seconds": start,
        "end_timestamp_seconds": end,
        "metrics": {
            "record_count": record_count,
            "supported_track_count": supported_track_count,
            "failure_reason": failure_reason,
        },
    }
    _attach_suspicious_static_fallback([segment], states, config=config)
    return {
        "strategy": "box_tracker_segment_dispatch_poc_v1",
        "status": "insufficient_text",
        "recommended_fallback": "legacy_credit_pipeline_selector",
        "record_count": record_count,
        "track_count": len(tracks),
        "supported_track_count": supported_track_count,
        "segments": [segment],
        "tracks": [track.to_dict() for track in tracks],
        "track_states": [state.to_dict() for state in states],
    }


def _build_windows(states: list[TextTrackState], window_seconds: float) -> list[dict[str, float]]:
    start = _min_timestamp(states)
    end = _max_timestamp(states)
    if start is None or end is None:
        return [{"start": 0.0, "end": 0.0}]
    if end <= start:
        return [{"start": start, "end": end}]
    windows: list[dict[str, float]] = []
    cursor = start
    while cursor < end:
        window_end = min(end, cursor + window_seconds)
        windows.append({"start": cursor, "end": window_end})
        cursor = window_end
    return windows


def _label_window(window: dict[str, float], states: list[TextTrackState], config: SegmentDispatcherConfig) -> dict[str, Any]:
    active = [state for state in states if _state_overlaps_window(state, window)]
    supported = [state for state in active if state.record_count >= config.min_track_observations]
    if not supported:
        return _window_payload(window, "UNKNOWN", "NO_SUPPORTED_TRACKS", {})

    moving = [state for state in supported if state.state == "MOVING"]
    static = [state for state in supported if state.state == "STATIC"]
    total_area = sum(max(0.0, state.median_area) for state in supported) or 1.0
    moving_area = sum(max(0.0, state.median_area) for state in moving)
    static_area = sum(max(0.0, state.median_area) for state in static)
    moving_track_ratio = len(moving) / len(supported)
    moving_area_ratio = moving_area / total_area
    static_area_ratio = static_area / total_area
    direction_consistency = _aggregate_direction_consistency(moving)
    median_track_support = median([state.record_count for state in supported])

    metrics = {
        "supported_track_count": len(supported),
        "moving_track_count": len(moving),
        "static_track_count": len(static),
        "moving_track_ratio": round(moving_track_ratio, 4),
        "moving_text_area_ratio": round(moving_area_ratio, 4),
        "static_text_area_ratio": round(static_area_ratio, 4),
        "direction_consistency": round(direction_consistency, 4),
        "track_duration_support": round(float(median_track_support), 4),
    }

    if (
        moving_track_ratio >= config.moving_track_ratio
        and moving_area_ratio >= config.moving_text_area_ratio
        and direction_consistency >= config.direction_consistency
    ):
        return _window_payload(window, "MOVING_SCROLL", "aggregate_motion_support", metrics)
    if static_area_ratio >= config.static_text_area_ratio and not moving:
        return _window_payload(window, "STATIC_CARD", "aggregate_static_support", metrics)
    if moving and static:
        return _window_payload(window, "MIXED", "static_and_moving_tracks", metrics)
    return _window_payload(window, "UNKNOWN", "aggregate_uncertain", metrics)


def _merge_windows(windows: list[dict[str, Any]], merge_gap_seconds: float) -> list[dict[str, Any]]:
    if not windows:
        return []
    segments: list[dict[str, Any]] = []
    for window in windows:
        if not segments:
            segments.append(_segment_from_window(window))
            continue
        previous = segments[-1]
        gap = float(window["start_timestamp_seconds"]) - float(previous["end_timestamp_seconds"])
        if previous["type"] == window["type"] and gap <= merge_gap_seconds:
            previous["end_timestamp_seconds"] = window["end_timestamp_seconds"]
            previous["metrics"] = _combine_metrics(previous["metrics"], window["metrics"])
            if window["reason"] not in previous["reason"]:
                previous["reason"] = f"{previous['reason']}+{window['reason']}"
        else:
            segments.append(_segment_from_window(window))
    return segments


def _smooth_unknown_bridges(segments: list[dict[str, Any]], unknown_bridge_seconds: float) -> list[dict[str, Any]]:
    if len(segments) < 3:
        return segments
    smoothed: list[dict[str, Any]] = []
    index = 0
    while index < len(segments):
        current = segments[index]
        if (
            index + 2 < len(segments)
            and current["type"] == segments[index + 2]["type"]
            and segments[index + 1]["type"] == "UNKNOWN"
            and _segment_duration(segments[index + 1]) <= unknown_bridge_seconds
        ):
            merged = _segment_from_window(current)
            bridge = segments[index + 1]
            next_segment = segments[index + 2]
            merged["end_timestamp_seconds"] = next_segment["end_timestamp_seconds"]
            merged["reason"] = f"{merged['reason']}+smoothed_unknown_bridge+{next_segment['reason']}"
            merged["metrics"] = _combine_metrics(
                _combine_metrics(merged.get("metrics") or {}, bridge.get("metrics") or {}),
                next_segment.get("metrics") or {},
            )
            smoothed.append(merged)
            index += 3
        else:
            smoothed.append(current)
            index += 1
    return smoothed


def _bridge_unknowns_with_scene_router(
    segments: list[dict[str, Any]],
    scene_profile: Mapping[str, Any] | None,
    *,
    max_unknown_seconds: float = 60.0,
) -> list[dict[str, Any]]:
    confidence = _scene_router_vertical_scroll_confidence(scene_profile)
    if confidence < 0.85 or len(segments) < 3:
        return segments
    bridged: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        current = _segment_from_window(segment)
        if (
            0 < index < len(segments) - 1
            and segment.get("type") == "UNKNOWN"
            and segments[index - 1].get("type") == "MOVING_SCROLL"
            and segments[index + 1].get("type") == "MOVING_SCROLL"
            and _segment_duration(segment) <= max_unknown_seconds
        ):
            current["type"] = "MOVING_SCROLL_INFERRED"
            current["bridged_from"] = "scene_router_confidence"
            current["reason"] = f"{current.get('reason') or 'UNKNOWN'}+scene_router_vertical_scroll_bridge"
            current.setdefault("metrics", {})["scene_router_vertical_scroll_confidence"] = round(confidence, 4)
        bridged.append(current)
    return bridged


def _scene_router_vertical_scroll_confidence(scene_profile: Mapping[str, Any] | None) -> float:
    if not isinstance(scene_profile, Mapping):
        return 0.0
    direct = scene_profile.get("vertical_scroll_confidence")
    if isinstance(direct, (int, float)):
        return float(direct)
    text_motion = scene_profile.get("text_motion")
    if not isinstance(text_motion, Mapping):
        return 0.0
    if text_motion.get("type") != "vertical_scroll":
        return 0.0
    confidence = text_motion.get("confidence")
    return float(confidence) if isinstance(confidence, (int, float)) else 0.0


def _attach_layout_signals(
    segments: list[dict[str, Any]],
    tracks: list[TextTrack],
    state_by_id: dict[str, TextTrackState],
    *,
    frame_size: tuple[int, int] | None,
) -> None:
    for segment in segments:
        if segment["type"] not in {"MOVING_SCROLL", "MOVING_SCROLL_INFERRED", "MIXED"}:
            continue
        active_tracks = [
            track
            for track in tracks
            if (state_by_id.get(track.track_id) and _track_overlaps_segment(state_by_id[track.track_id], segment))
        ]
        centers = [_bbox_center_x(track.median_bbox) for track in active_tracks if len(track.median_bbox) >= 4]
        segment["x_clusters"] = _x_cluster_signal(centers, frame_size=frame_size)


def _attach_suspicious_static_fallback(
    segments: list[dict[str, Any]],
    states: list[TextTrackState],
    *,
    config: SegmentDispatcherConfig,
) -> None:
    for segment in segments:
        if segment["type"] not in {"STATIC_CARD", "UNKNOWN"}:
            continue
        active_states = [state for state in states if _track_overlaps_segment(state, segment)]
        suspicion = _scroll_suspicion(active_states, segment, config)
        segment_metrics = segment.setdefault("metrics", {})
        segment_metrics.update(
            {
                "text_count": suspicion["text_count"],
                "scroll_suspicion": suspicion["score"],
                "track_churn_ratio": suspicion["track_churn_ratio"],
                "vertical_motion_hint": suspicion["vertical_motion_hint"],
                "static_confidence": suspicion["static_confidence"],
            }
        )
        if suspicion["should_fallback"]:
            segment["fallback_recommended"] = "row_reconstruct"
            segment["fallback_reason"] = suspicion["reason"]
            segment["fallback_compare"] = {
                "accept_if_line_count_gain_at_least": 5,
                "accept_if_quality_multiplier_at_least": 1.25,
            }


def _scroll_suspicion(
    states: list[TextTrackState],
    segment: dict[str, Any],
    config: SegmentDispatcherConfig,
) -> dict[str, Any]:
    duration = _segment_duration(segment)
    texts = {state.winner_text for state in states if state.winner_text}
    text_count = len(texts)
    if not states:
        return {
            "score": 0.0,
            "text_count": text_count,
            "track_churn_ratio": 0.0,
            "vertical_motion_hint": 0.0,
            "static_confidence": None,
            "should_fallback": False,
            "reason": "",
        }

    short_tracks = [
        state
        for state in states
        if state.record_count < config.min_track_observations
        or (state.duration_seconds is not None and state.duration_seconds <= config.churn_short_duration_seconds)
    ]
    track_churn_ratio = len(short_tracks) / len(states)
    vertical_motion_hint = _cross_track_vertical_motion_hint(states)
    static_states = [state for state in states if state.state == "STATIC"]
    static_confidence = (
        round(sum(state.confidence for state in static_states) / len(static_states), 4)
        if static_states
        else None
    )
    low_static_confidence = (
        1.0 if static_confidence is None else max(0.0, (config.low_static_confidence_threshold - static_confidence) / config.low_static_confidence_threshold)
    )
    long_low_text = (
        1.0
        if duration >= config.suspicious_min_duration_seconds and text_count < config.suspicious_text_count_threshold
        else 0.0
    )
    score = round(
        min(
            1.0,
            0.36 * track_churn_ratio
            + 0.36 * vertical_motion_hint
            + 0.18 * low_static_confidence
            + 0.10 * long_low_text,
        ),
        4,
    )
    should_fallback = (
        text_count < config.suspicious_text_count_threshold
        and duration >= config.suspicious_min_duration_seconds
        and score >= config.suspicious_scroll_threshold
    )
    reasons = []
    if track_churn_ratio >= 0.45:
        reasons.append("high_track_churn")
    if vertical_motion_hint >= 0.50:
        reasons.append("vertical_motion_hint")
    if static_confidence is None or static_confidence < config.low_static_confidence_threshold:
        reasons.append("low_static_confidence")
    if text_count < config.suspicious_text_count_threshold:
        reasons.append("low_text_count")
    return {
        "score": score,
        "text_count": text_count,
        "track_churn_ratio": round(track_churn_ratio, 4),
        "vertical_motion_hint": round(vertical_motion_hint, 4),
        "static_confidence": static_confidence,
        "should_fallback": should_fallback,
        "reason": "suspicious_static_low_text_" + "_".join(reasons or ["weak_segment"]),
    }


def _window_payload(window: dict[str, float], label: str, reason: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": label,
        "reason": reason,
        "start_timestamp_seconds": round(float(window["start"]), 4),
        "end_timestamp_seconds": round(float(window["end"]), 4),
        "metrics": metrics,
    }


def _segment_from_window(window: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": window["type"],
        "reason": window["reason"],
        "start_timestamp_seconds": window["start_timestamp_seconds"],
        "end_timestamp_seconds": window["end_timestamp_seconds"],
        "metrics": dict(window.get("metrics") or {}),
    }


def _combine_metrics(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    combined = dict(a)
    for key, value in b.items():
        if key not in combined:
            combined[key] = value
            continue
        if isinstance(value, (int, float)) and isinstance(combined[key], (int, float)):
            combined[key] = round((float(combined[key]) + float(value)) / 2.0, 4)
    return combined


def _segment_duration(segment: dict[str, Any]) -> float:
    start = segment.get("start_timestamp_seconds")
    end = segment.get("end_timestamp_seconds")
    if start is None or end is None:
        return 0.0
    return max(0.0, float(end) - float(start))


def _state_overlaps_window(state: TextTrackState, window: dict[str, float]) -> bool:
    first = state.first_timestamp_seconds
    last = state.last_timestamp_seconds
    if first is None or last is None:
        return False
    return float(first) <= float(window["end"]) and float(last) >= float(window["start"])


def _track_overlaps_segment(state: TextTrackState, segment: dict[str, Any]) -> bool:
    first = state.first_timestamp_seconds
    last = state.last_timestamp_seconds
    if first is None or last is None:
        return False
    return float(first) <= float(segment["end_timestamp_seconds"]) and float(last) >= float(segment["start_timestamp_seconds"])


def _aggregate_direction_consistency(states: list[TextTrackState]) -> float:
    if not states:
        return 0.0
    directions = []
    for state in states:
        vx, vy = state.median_velocity_px_s
        if abs(vy) >= abs(vx):
            directions.append(1 if vy >= 0 else -1)
        else:
            directions.append(1 if vx >= 0 else -1)
    positive = sum(1 for direction in directions if direction > 0)
    negative = len(directions) - positive
    sign_consistency = max(positive, negative) / len(directions)
    track_consistency = sum(state.direction_consistency for state in states) / len(states)
    return min(sign_consistency, track_consistency)


def _cross_track_vertical_motion_hint(states: list[TextTrackState]) -> float:
    points = []
    for state in states:
        timestamp = state.first_timestamp_seconds
        if timestamp is None or len(state.median_bbox) < 4:
            continue
        points.append((float(timestamp), _bbox_center_y(state.median_bbox)))
    points.sort()
    if len(points) < 3:
        return 0.0

    votes = []
    for (previous_time, previous_y), (current_time, current_y) in zip(points, points[1:]):
        if current_time - previous_time < 0.25:
            continue
        delta_y = current_y - previous_y
        if abs(delta_y) < 8.0:
            continue
        votes.append(1 if delta_y > 0 else -1)
    if len(votes) < 2:
        return 0.0
    positive = sum(1 for vote in votes if vote > 0)
    negative = len(votes) - positive
    consistency = max(positive, negative) / len(votes)
    support = min(1.0, len(votes) / 5.0)
    return round(consistency * support, 4)


def _x_cluster_signal(centers: list[float], *, frame_size: tuple[int, int] | None) -> dict[str, Any]:
    if len(centers) < 4:
        return {"cluster_count": 1 if centers else 0, "centers": [round(value, 3) for value in sorted(centers)], "confidence": 0.0}
    ordered = sorted(centers)
    gaps = [(ordered[index + 1] - ordered[index], index) for index in range(len(ordered) - 1)]
    largest_gap, gap_index = max(gaps, key=lambda item: item[0])
    frame_width = float(frame_size[0]) if frame_size and len(frame_size) >= 1 else max(ordered) if ordered else 1.0
    threshold = max(80.0, frame_width * 0.18)
    if largest_gap < threshold:
        return {"cluster_count": 1, "centers": [round(float(median(ordered)), 3)], "confidence": 0.35}
    left = ordered[: gap_index + 1]
    right = ordered[gap_index + 1 :]
    confidence = min(1.0, largest_gap / max(threshold * 2.0, 1.0))
    return {
        "cluster_count": 2,
        "centers": [round(float(median(left)), 3), round(float(median(right)), 3)],
        "largest_gap_px": round(largest_gap, 3),
        "confidence": round(confidence, 4),
    }


def _bbox_center_x(bbox: list[float]) -> float:
    return float(bbox[0]) + float(bbox[2]) / 2.0


def _bbox_center_y(bbox: list[float]) -> float:
    return float(bbox[1]) + float(bbox[3]) / 2.0


def _min_timestamp(states: list[TextTrackState]) -> float | None:
    values = [state.first_timestamp_seconds for state in states if state.first_timestamp_seconds is not None]
    return min(values) if values else None


def _max_timestamp(states: list[TextTrackState]) -> float | None:
    values = [state.last_timestamp_seconds for state in states if state.last_timestamp_seconds is not None]
    return max(values) if values else None
