"""Unit tests for K-BoxTrack pipeline helpers and unified pipeline smoke test."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from core.pipelines.ocr.box_tracker import (
    TextTrack,
    TextTrackObservation,
    _card_grouping_mode,
    build_text_tracks,
    classify_track_motion,
    group_static_tracks_into_cards,
    select_best_frame_per_card,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _obs(frame_index: int, y: float, confidence: float = 0.95) -> TextTrackObservation:
    return TextTrackObservation(
        record_index=frame_index,
        frame_index=frame_index,
        frame=f"frame_{frame_index:05d}.png",
        timestamp_seconds=float(frame_index),
        bbox=(100.0, y, 80.0, 24.0),
        text="TEXT",
        normalized_text="TEXT",
        confidence=confidence,
        area=80.0 * 24.0,
    )


def _track(track_id: str, observations: list[TextTrackObservation], vy: float = 0.0) -> TextTrack:
    return TextTrack(
        track_id=track_id,
        engine="fake",
        observations=tuple(observations),
        velocity_x_px_frame=0.0,
        velocity_y_px_frame=vy,
    )


def _record(text: str, frame_index: int, *, x: float = 140.0, y: float = 80.0, confidence: float = 0.99) -> dict:
    return {
        "engine": "fake",
        "frame": f"frame_{frame_index:05d}.png",
        "timestamp_seconds": float(frame_index),
        "bbox": [x, y, max(40.0, len(text) * 9.0), 24.0],
        "text": text,
        "normalized_text": text,
        "confidence": confidence,
    }


def _frames(count: int) -> list[str]:
    return [f"frame_{i:05d}.png" for i in range(count)]


# ---------------------------------------------------------------------------
# Test 1: classify_track_motion — static
# ---------------------------------------------------------------------------


def test_classify_track_motion_static() -> None:
    """5 observations at a fixed y → static_text."""
    observations = [_obs(i, y=100.0) for i in range(5)]
    track = _track("t1", observations, vy=0.3)
    result = classify_track_motion(track)
    assert result == "static_text", f"Expected 'static_text', got {result!r}"


# ---------------------------------------------------------------------------
# Test 2: classify_track_motion — scrolling
# ---------------------------------------------------------------------------


def test_classify_track_motion_scroll() -> None:
    """y increases 5px per frame → scrolling_text."""
    observations = [_obs(i, y=float(i * 5)) for i in range(5)]
    # Build via build_text_tracks so velocity is correctly computed
    records = [_record("SCROLL", i, y=float(i * 5)) for i in range(5)]
    tracks = build_text_tracks(records, frames=_frames(5), frame_size=(640, 360))
    assert tracks, "Expected at least one track"
    track = tracks[0]
    result = classify_track_motion(track)
    assert result == "scrolling_text", f"Expected 'scrolling_text', got {result!r} (vy={track.velocity_y_px_frame})"


# ---------------------------------------------------------------------------
# Test 3: group_static_tracks_into_cards — two separate time windows → 2 cards
# ---------------------------------------------------------------------------


def test_group_static_tracks_two_cards() -> None:
    """Tracks in two distinct time windows (gap > 1.5s) → 2 cards."""
    # Card 1: frames 0-2
    group1 = [
        _track(f"g1_{i}", [_obs(i, y=100.0) for _ in range(3)], vy=0.0)
        for i in range(3)
    ]
    # Card 2: frames 10-12 (gap = 7s)
    group2 = [
        _track(f"g2_{i}", [_obs(10 + i, y=100.0) for _ in range(3)], vy=0.0)
        for i in range(3)
    ]
    all_tracks = group1 + group2
    cards = group_static_tracks_into_cards(all_tracks, max_time_gap_seconds=1.5)
    assert len(cards) == 2, f"Expected 2 cards, got {len(cards)}: {[c['card_id'] for c in cards]}"
    assert cards[0]["member_count"] == 3
    assert cards[1]["member_count"] == 3


# ---------------------------------------------------------------------------
# Test 4: select_best_frame_per_card — highest confidence frame wins
# ---------------------------------------------------------------------------


def test_select_best_frame_uses_max_confidence() -> None:
    """3 frames; frame 1 has highest confidence → it's selected."""
    track = TextTrack(
        track_id="t_conf",
        engine="fake",
        observations=(
            _obs(0, y=100.0, confidence=0.50),
            _obs(1, y=100.0, confidence=0.99),  # highest
            _obs(2, y=100.0, confidence=0.70),
        ),
        velocity_x_px_frame=0.0,
        velocity_y_px_frame=0.0,
    )
    card = {
        "card_id": "card_001",
        "track_ids": ["t_conf"],
        "first_timestamp": 0.0,
        "last_timestamp": 2.0,
        "y_range": [100.0, 124.0],
        "member_count": 1,
    }
    frame_paths = [f"frame_{i:05d}.png" for i in range(3)]
    result = select_best_frame_per_card(card, [track], frame_paths)
    assert result["best_frame_index"] == 1, f"Expected frame 1, got {result['best_frame_index']}"
    assert result["best_frame_path"] == "frame_00001.png"


# ---------------------------------------------------------------------------
# Test 5: unified pipeline smoke — mock engine, 5 frames, no crash
# ---------------------------------------------------------------------------


def test_unified_pipeline_mock_smoke(tmp_path: Path) -> None:
    """Minimal mock engine, 5 synthetic frames → pipeline completes without error."""
    from core.pipelines.ocr.unified_credit_pipeline import run_unified_credit_pipeline

    # Create 5 dummy frame files
    frame_paths = []
    for i in range(5):
        fp = tmp_path / f"frame_{i:05d}.png"
        fp.write_bytes(b"")  # empty file, engine is mocked
        frame_paths.append(fp)

    # Mock engine returns minimal OCR records
    mock_engine = MagicMock()
    mock_engine.recognize.return_value = [
        {
            "engine": "mock",
            "frame": str(frame_paths[i]),
            "timestamp_seconds": float(i),
            "bbox": [100.0, 80.0, 120.0, 24.0],
            "text": f"LINE{i}",
            "normalized_text": f"LINE{i}",
            "confidence": 0.95,
        }
        for i in range(5)
    ]

    result = run_unified_credit_pipeline(
        frames=frame_paths,
        output_dir=tmp_path / "unified_out",
        paddle_engine=mock_engine,
        detection_stride=1,
    )

    assert result.summary_path.exists(), "summary.json not written"
    assert result.runtime_sec >= 0.0
    assert isinstance(result.summary, dict)
    assert "total_tracks" in result.summary
    assert result.cards_dir.exists()


# ---------------------------------------------------------------------------
# Test 6: group_static_tracks_into_cards — overlap mode merges overlapping lifespans
# ---------------------------------------------------------------------------


def test_group_static_tracks_overlap_mode_merges_overlapping_lifespans() -> None:
    """3 track aynı sahnede [0,5][1,5.5][2,6] overlap → tek kart. 4. track [10,15] → ayrı kart."""

    def mk_track(tid: str, first: float, last: float, y: float = 100.0) -> TextTrack:
        mid = (first + last) / 2.0
        return TextTrack(
            track_id=tid,
            engine="fake",
            observations=tuple([
                TextTrackObservation(
                    record_index=int(first * 6),
                    frame_index=int(first * 6),
                    frame=f"frame_{int(first*6):05d}.png",
                    timestamp_seconds=first,
                    bbox=(100.0, y, 200.0, 30.0),
                    text="x",
                    normalized_text="x",
                    confidence=0.9,
                    area=200.0 * 30.0,
                ),
                TextTrackObservation(
                    record_index=int(mid * 6),
                    frame_index=int(mid * 6),
                    frame=f"frame_{int(mid*6):05d}.png",
                    timestamp_seconds=mid,
                    bbox=(100.0, y, 200.0, 30.0),
                    text="x",
                    normalized_text="x",
                    confidence=0.9,
                    area=200.0 * 30.0,
                ),
                TextTrackObservation(
                    record_index=int(last * 6),
                    frame_index=int(last * 6),
                    frame=f"frame_{int(last*6):05d}.png",
                    timestamp_seconds=last,
                    bbox=(100.0, y, 200.0, 30.0),
                    text="x",
                    normalized_text="x",
                    confidence=0.9,
                    area=200.0 * 30.0,
                ),
            ]),
            velocity_x_px_frame=0.0,
            velocity_y_px_frame=0.0,
        )

    tracks = [
        mk_track("t1", 0.0, 5.0, y=100.0),
        mk_track("t2", 1.0, 5.5, y=150.0),
        mk_track("t3", 2.0, 6.0, y=200.0),
        mk_track("t4", 10.0, 15.0, y=100.0),
    ]
    cards = group_static_tracks_into_cards(tracks, mode="overlap", min_window_overlap_ratio=0.3)
    assert len(cards) == 2, f"2 kart bekleniyor, görülen: {[c['track_ids'] for c in cards]}"
    assert set(cards[0]["track_ids"]) == {"t1", "t2", "t3"}
    assert cards[1]["track_ids"] == ["t4"]


# ---------------------------------------------------------------------------
# Test 7: group_static_tracks_into_cards — default gap mode unchanged (env var)
# ---------------------------------------------------------------------------


def test_group_static_tracks_gap_mode_default_unchanged(monkeypatch: object) -> None:
    """OCR_CARD_GROUPING set edilmemişse default 'gap' mode, davranış değişmedi."""
    import os
    # monkeypatch is a pytest fixture; type: ignore below for mypy
    monkeypatch.delenv("OCR_CARD_GROUPING", raising=False)  # type: ignore[attr-defined]
    assert _card_grouping_mode() == "gap"

    def mk_track(tid: str, first: float, last: float, y: float = 100.0) -> TextTrack:
        mid = (first + last) / 2.0
        return TextTrack(
            track_id=tid,
            engine="fake",
            observations=tuple([
                TextTrackObservation(
                    record_index=int(first * 6),
                    frame_index=int(first * 6),
                    frame=f"frame_{int(first*6):05d}.png",
                    timestamp_seconds=first,
                    bbox=(100.0, y, 200.0, 30.0),
                    text="x",
                    normalized_text="x",
                    confidence=0.9,
                    area=200.0 * 30.0,
                ),
                TextTrackObservation(
                    record_index=int(mid * 6),
                    frame_index=int(mid * 6),
                    frame=f"frame_{int(mid*6):05d}.png",
                    timestamp_seconds=mid,
                    bbox=(100.0, y, 200.0, 30.0),
                    text="x",
                    normalized_text="x",
                    confidence=0.9,
                    area=200.0 * 30.0,
                ),
                TextTrackObservation(
                    record_index=int(last * 6),
                    frame_index=int(last * 6),
                    frame=f"frame_{int(last*6):05d}.png",
                    timestamp_seconds=last,
                    bbox=(100.0, y, 200.0, 30.0),
                    text="x",
                    normalized_text="x",
                    confidence=0.9,
                    area=200.0 * 30.0,
                ),
            ]),
            velocity_x_px_frame=0.0,
            velocity_y_px_frame=0.0,
        )

    # 2 track birbirine 0.5sn yakın (first_ts gap=0.5 < 1.5), 3. track 5sn sonra → gap mode'da 2 kart
    tracks = [
        mk_track("a", 0.0, 1.0),
        mk_track("b", 0.5, 1.5),
        mk_track("c", 5.0, 6.0),
    ]
    cards = group_static_tracks_into_cards(tracks)  # mode=None → env → "gap"
    assert len(cards) == 2, f"2 kart bekleniyor, görülen: {[c['track_ids'] for c in cards]}"


# ---------------------------------------------------------------------------
# Test 8: _scroll_track_fallback_lines — best obs per track, y-sorted, filtered
# ---------------------------------------------------------------------------


def test_scroll_track_fallback_lines_picks_best_per_track() -> None:
    """Her track için en yüksek conf observation seçilir, y-sıralı döner."""
    from core.pipelines.ocr.unified_credit_pipeline import _scroll_track_fallback_lines

    t1 = TextTrack(
        track_id="t1",
        engine="fake",
        observations=(
            TextTrackObservation(
                record_index=0,
                frame_index=0,
                frame="frame_00000.png",
                timestamp_seconds=0.0,
                bbox=(100.0, 50.0, 200.0, 30.0),
                text="HELMUT SCHNEIDER",
                normalized_text="HELMUT SCHNEIDER",
                confidence=0.8,
                area=200.0 * 30.0,
            ),
            TextTrackObservation(
                record_index=3,
                frame_index=3,
                frame="frame_00003.png",
                timestamp_seconds=0.5,
                bbox=(100.0, 50.0, 200.0, 30.0),
                text="HELMUT SCHNEIDER",
                normalized_text="HELMUT SCHNEIDER",
                confidence=0.99,
                area=200.0 * 30.0,
            ),
        ),
        velocity_x_px_frame=0.0,
        velocity_y_px_frame=3.0,
    )
    t2 = TextTrack(
        track_id="t2",
        engine="fake",
        observations=(
            TextTrackObservation(
                record_index=0,
                frame_index=0,
                frame="frame_00000.png",
                timestamp_seconds=0.0,
                bbox=(100.0, 100.0, 200.0, 30.0),
                text="ALY BEN AYED",
                normalized_text="ALY BEN AYED",
                confidence=0.95,
                area=200.0 * 30.0,
            ),
        ),
        velocity_x_px_frame=0.0,
        velocity_y_px_frame=3.0,
    )
    t3 = TextTrack(
        track_id="t3",
        engine="fake",
        observations=(
            TextTrackObservation(
                record_index=0,
                frame_index=0,
                frame="frame_00000.png",
                timestamp_seconds=0.0,
                bbox=(100.0, 30.0, 200.0, 30.0),
                text="BRUNO DIETRICH",
                normalized_text="BRUNO DIETRICH",
                confidence=0.45,  # below threshold
                area=200.0 * 30.0,
            ),
        ),
        velocity_x_px_frame=0.0,
        velocity_y_px_frame=3.0,
    )

    lines = _scroll_track_fallback_lines([t1, t2, t3], min_confidence=0.5)

    # t3 düşük conf, filtrelendi; t1 ve t2 kaldı
    assert len(lines) == 2
    # Y-sıralı: t1 (y=50) önce, t2 (y=100) sonra
    assert lines[0]["text"] == "HELMUT SCHNEIDER"
    assert lines[0]["confidence"] == 0.99  # best obs seçildi
    assert lines[0]["source"] == "track_observation_fallback"
    assert lines[1]["text"] == "ALY BEN AYED"


# ---------------------------------------------------------------------------
# Test 9: _scroll_track_fallback_lines — dedupe by uppercase text
# ---------------------------------------------------------------------------


def test_scroll_track_fallback_lines_dedupes_by_text() -> None:
    """Aynı text'e sahip iki track varsa en yüksek conf olanı kalır."""
    from core.pipelines.ocr.unified_credit_pipeline import _scroll_track_fallback_lines

    t1 = TextTrack(
        track_id="t1",
        engine="fake",
        observations=(
            TextTrackObservation(
                record_index=0,
                frame_index=0,
                frame="frame_00000.png",
                timestamp_seconds=0.0,
                bbox=(100.0, 50.0, 200.0, 30.0),
                text="SAME LINE",
                normalized_text="SAME LINE",
                confidence=0.7,
                area=200.0 * 30.0,
            ),
        ),
        velocity_x_px_frame=0.0,
        velocity_y_px_frame=3.0,
    )
    t2 = TextTrack(
        track_id="t2",
        engine="fake",
        observations=(
            TextTrackObservation(
                record_index=6,
                frame_index=6,
                frame="frame_00006.png",
                timestamp_seconds=1.0,
                bbox=(100.0, 200.0, 200.0, 30.0),
                text="same line",  # case-insensitive dupe
                normalized_text="same line",
                confidence=0.95,
                area=200.0 * 30.0,
            ),
        ),
        velocity_x_px_frame=0.0,
        velocity_y_px_frame=3.0,
    )

    lines = _scroll_track_fallback_lines([t1, t2], min_confidence=0.5)
    assert len(lines) == 1
    assert lines[0]["confidence"] == 0.95
