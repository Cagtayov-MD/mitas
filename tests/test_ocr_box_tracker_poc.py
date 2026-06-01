from __future__ import annotations

from core.pipelines.ocr.box_tracker import build_text_tracks
from core.pipelines.ocr.credit_segment_dispatcher import (
    SegmentDispatcherConfig,
    _bridge_unknowns_with_scene_router,
    _smooth_unknown_bridges,
    dispatch_credit_segments,
)
from core.pipelines.ocr.text_track_state import TextTrackState, classify_text_track_states


def test_adaptive_tracker_keeps_fast_scroll_identity_without_iou_overlap() -> None:
    records = _moving_records(["JAMES"], y0=40, dy=26, frames=6, height=18)

    tracks = build_text_tracks(records, frames=_frames(6), frame_size=(640, 360))

    assert len(tracks) == 1
    assert tracks[0].record_count == 6
    assert tracks[0].velocity_y_px_frame > 20


def test_tracker_ignores_low_confidence_ocr_noise() -> None:
    records = _moving_records(["NOISE"], y0=40, dy=26, frames=6, height=18, confidence=0.39)

    tracks = build_text_tracks(records, frames=_frames(6), frame_size=(640, 360))

    assert tracks == []


def test_tracker_keeps_identity_across_brief_ocr_gap() -> None:
    records = [
        _record("JAMES", 0, x=140, y=80),
        _record("JAMES", 1, x=140, y=92),
        _record("JAMES", 4, x=140, y=128),
        _record("JAMES", 5, x=140, y=140),
    ]

    tracks = build_text_tracks(records, frames=_frames(6), frame_size=(640, 360))

    assert len(tracks) == 1
    assert tracks[0].record_count == 4


def test_dispatcher_marks_single_scroll_segment() -> None:
    records = []
    for index, text in enumerate(["JAMES", "DIRECTOR", "MUSIC"]):
        records.extend(_moving_records([text], x=160 + index * 22, y0=70 + index * 34, dy=16, frames=7))

    result = _run(records, frame_count=7)

    assert result["status"] == "done"
    assert [segment["type"] for segment in result["segments"]] == ["MOVING_SCROLL"]


def test_dispatcher_detects_x_cluster_signal_for_two_column_scroll() -> None:
    records = []
    for text, x in [("LEFT ONE", 90), ("LEFT TWO", 110), ("RIGHT ONE", 430), ("RIGHT TWO", 450)]:
        records.extend(_moving_records([text], x=x, y0=80, dy=14, frames=7))

    result = _run(records, frame_count=7)

    assert result["segments"][0]["type"] == "MOVING_SCROLL"
    assert result["segments"][0]["x_clusters"]["cluster_count"] == 2


def test_static_card_is_not_marked_as_moving() -> None:
    records = []
    for index, text in enumerate(["ANDREA FERREOL", "GERARD DEPARDIEU", "CATHERINE DENEUVE"]):
        records.extend(_static_records(text, x=150, y=90 + index * 34, frames=6))

    result = _run(records, frame_count=6)

    assert result["status"] == "done"
    assert [segment["type"] for segment in result["segments"]] == ["STATIC_CARD"]


def test_hybrid_static_card_then_scroll_produces_two_signal_types() -> None:
    records = []
    for index, text in enumerate(["ANDREA FERREOL", "GERARD DEPARDIEU", "CATHERINE DENEUVE"]):
        records.extend(_static_records(text, x=150, y=80 + index * 34, start_frame=0, frames=5))
    for index, text in enumerate(["CASTING", "EDITOR", "MUSIC"]):
        records.extend(_moving_records([text], x=180 + index * 20, y0=260 + index * 28, dy=-18, start_frame=7, frames=6))

    result = _run(records, frame_count=13)
    segment_types = [segment["type"] for segment in result["segments"]]

    assert "STATIC_CARD" in segment_types
    assert "MOVING_SCROLL" in segment_types
    assert segment_types.index("STATIC_CARD") < segment_types.index("MOVING_SCROLL")


def test_low_density_routes_to_unknown_with_legacy_fallback() -> None:
    records = _static_records("ONE LINE", x=100, y=100, frames=2)

    result = _run(records, frame_count=2)

    assert result["status"] == "insufficient_text"
    assert result["segments"][0]["type"] == "UNKNOWN"
    assert result["segments"][0]["reason"] == "INSUFFICIENT_TEXT"
    assert result["recommended_fallback"] == "legacy_credit_pipeline_selector"


def test_no_confident_aggregate_segment_collapses_to_unknown_fallback() -> None:
    states = [
        _state("t1", "UNKNOWN", first=0.0, last=8.0),
        _state("t2", "UNKNOWN", first=0.0, last=8.0),
    ]

    result = dispatch_credit_segments([], states, records=[{}] * 100, frame_size=(640, 360))

    assert result["status"] == "insufficient_text"
    assert len(result["segments"]) == 1
    assert result["segments"][0]["type"] == "UNKNOWN"
    assert result["segments"][0]["reason"] == "INSUFFICIENT_TEXT"
    assert result["segments"][0]["metrics"]["failure_reason"] == "no_confident_segment"


def test_short_unknown_bridge_between_same_segment_type_is_smoothed() -> None:
    segments = [
        {"type": "MOVING_SCROLL", "reason": "left", "start_timestamp_seconds": 0.0, "end_timestamp_seconds": 1.0, "metrics": {}},
        {"type": "UNKNOWN", "reason": "ocr_gap", "start_timestamp_seconds": 1.0, "end_timestamp_seconds": 1.4, "metrics": {}},
        {"type": "MOVING_SCROLL", "reason": "right", "start_timestamp_seconds": 1.4, "end_timestamp_seconds": 3.0, "metrics": {}},
    ]

    smoothed = _smooth_unknown_bridges(segments, unknown_bridge_seconds=0.5)

    assert len(smoothed) == 1
    assert smoothed[0]["type"] == "MOVING_SCROLL"
    assert smoothed[0]["end_timestamp_seconds"] == 3.0


def test_scene_router_bridge_converts_dunyanin_like_unknown_between_moving_segments() -> None:
    segments = [
        {"type": "MOVING_SCROLL", "reason": "left", "start_timestamp_seconds": 2871.8, "end_timestamp_seconds": 2873.3, "metrics": {}},
        {"type": "UNKNOWN", "reason": "long_ocr_gap", "start_timestamp_seconds": 2873.3, "end_timestamp_seconds": 2900.3, "metrics": {}},
        {"type": "MOVING_SCROLL", "reason": "middle", "start_timestamp_seconds": 2900.3, "end_timestamp_seconds": 2906.3, "metrics": {}},
        {"type": "UNKNOWN", "reason": "long_ocr_gap", "start_timestamp_seconds": 2906.3, "end_timestamp_seconds": 2952.8, "metrics": {}},
        {"type": "MOVING_SCROLL", "reason": "right", "start_timestamp_seconds": 2952.8, "end_timestamp_seconds": 2997.8, "metrics": {}},
    ]
    scene_profile = {"text_motion": {"type": "vertical_scroll", "confidence": 0.9581}}

    bridged = _bridge_unknowns_with_scene_router(segments, scene_profile)

    assert [segment["type"] for segment in bridged] == [
        "MOVING_SCROLL",
        "MOVING_SCROLL_INFERRED",
        "MOVING_SCROLL",
        "MOVING_SCROLL_INFERRED",
        "MOVING_SCROLL",
    ]
    assert bridged[1]["bridged_from"] == "scene_router_confidence"


def test_scene_router_bridge_does_not_touch_kukla_static_or_mixed_neighbors() -> None:
    segments = [
        {"type": "STATIC_CARD", "reason": "static", "start_timestamp_seconds": 0.0, "end_timestamp_seconds": 10.0, "metrics": {}},
        {"type": "UNKNOWN", "reason": "gap", "start_timestamp_seconds": 10.0, "end_timestamp_seconds": 25.0, "metrics": {}},
        {"type": "MOVING_SCROLL", "reason": "scroll", "start_timestamp_seconds": 25.0, "end_timestamp_seconds": 30.0, "metrics": {}},
        {"type": "UNKNOWN", "reason": "gap", "start_timestamp_seconds": 30.0, "end_timestamp_seconds": 45.0, "metrics": {}},
        {"type": "MIXED", "reason": "mixed", "start_timestamp_seconds": 45.0, "end_timestamp_seconds": 50.0, "metrics": {}},
    ]
    scene_profile = {"text_motion": {"type": "vertical_scroll", "confidence": 0.93}}

    bridged = _bridge_unknowns_with_scene_router(segments, scene_profile)

    assert [segment["type"] for segment in bridged] == ["STATIC_CARD", "UNKNOWN", "MOVING_SCROLL", "UNKNOWN", "MIXED"]


def test_suspicious_static_low_text_recommends_row_reconstruct_fallback() -> None:
    states = [
        _state(f"t{index}", "UNKNOWN", first=float(index), last=float(index) + 0.2, y=260 - index * 18, record_count=1)
        for index in range(6)
    ]

    result = dispatch_credit_segments(
        [],
        states,
        records=[{}] * 120,
        frame_size=(640, 360),
        config=SegmentDispatcherConfig(min_records=80),
    )

    segment = result["segments"][0]
    assert result["status"] == "insufficient_text"
    assert segment["type"] == "UNKNOWN"
    assert segment["fallback_recommended"] == "row_reconstruct"
    assert segment["metrics"]["scroll_suspicion"] >= 0.55


def test_suspicious_static_card_recommends_row_reconstruct_fallback() -> None:
    states = [
        _state(f"s{index}", "STATIC", first=float(index), last=float(index) + 0.2, y=260 - index * 18, record_count=3, confidence=0.45)
        for index in range(6)
    ]

    result = dispatch_credit_segments(
        [],
        states,
        records=[{}] * 120,
        frame_size=(640, 360),
        config=SegmentDispatcherConfig(min_records=80),
    )

    segment = result["segments"][0]
    assert result["status"] == "done"
    assert segment["type"] == "STATIC_CARD"
    assert segment["fallback_recommended"] == "row_reconstruct"


def _run(records: list[dict], *, frame_count: int) -> dict:
    tracks = build_text_tracks(records, frames=_frames(frame_count), frame_size=(640, 360))
    states = classify_text_track_states(tracks, frame_size=(640, 360))
    return dispatch_credit_segments(tracks, states, records=records, frame_size=(640, 360))


def _moving_records(
    texts: list[str],
    *,
    x: int = 140,
    y0: int = 80,
    dy: int = 12,
    start_frame: int = 0,
    frames: int = 5,
    height: int = 24,
    confidence: float = 0.99,
) -> list[dict]:
    records = []
    for text in texts:
        for offset in range(frames):
            frame_index = start_frame + offset
            records.append(_record(text, frame_index, x=x, y=y0 + dy * offset, height=height, confidence=confidence))
    return records


def _static_records(
    text: str,
    *,
    x: int,
    y: int,
    start_frame: int = 0,
    frames: int = 5,
) -> list[dict]:
    return [_record(text, start_frame + offset, x=x, y=y) for offset in range(frames)]


def _record(text: str, frame_index: int, *, x: int, y: int, height: int = 24, confidence: float = 0.99) -> dict:
    return {
        "engine": "fake",
        "strategy": "frame_ocr",
        "frame": f"frame_{frame_index:05d}.png",
        "timestamp_seconds": float(frame_index),
        "bbox": [float(x), float(y), float(max(40, len(text) * 9)), float(height)],
        "text": text,
        "normalized_text": text,
        "confidence": confidence,
    }


def _frames(count: int) -> list[str]:
    return [f"frame_{index:05d}.png" for index in range(count)]


def _state(
    track_id: str,
    state: str,
    *,
    first: float,
    last: float,
    y: float = 100.0,
    record_count: int = 8,
    confidence: float = 0.45,
) -> TextTrackState:
    return TextTrackState(
        track_id=track_id,
        state=state,
        confidence=confidence,
        record_count=record_count,
        first_timestamp_seconds=first,
        last_timestamp_seconds=last,
        first_frame_index=int(first),
        last_frame_index=int(last),
        duration_seconds=last - first,
        displacement_px=(0.0, 0.0),
        median_speed_px_s=0.0,
        median_velocity_px_s=(0.0, 0.0),
        direction_consistency=0.0,
        median_area=100.0,
        median_bbox=[100.0, y, 50.0, 20.0],
        winner_text=track_id,
        reason="test",
    )
