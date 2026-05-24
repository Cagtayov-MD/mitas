"""Unit tests for `core.pipelines.ocr.manifest_profiles` (Faz 2).

Coverage targets:
- LEGACY `kind: end_credits` keeps single-segment behavior driven by
  manifest's start_seconds/end_seconds.
- `kind: film_credits` produces opening + closing segments with defaults.
- Custom opening/closing window_min are honored.
- Stub kinds raise NotImplementedError.
- `normalize_manifest_item` fills schema defaults.
- Short-video overlap collapses to a single 'full' segment.
"""

from __future__ import annotations

import pytest

from core.pipelines.ocr import manifest_profiles
from core.pipelines.ocr.manifest_profiles import (
    KIND_END_CREDITS,
    KIND_FILM_CREDITS,
    KIND_FULL_SCAN,
    KIND_KJ_SCAN,
    KIND_SCENE_TEXT,
    build_segments_for_item,
    normalize_manifest_item,
)


def test_kind_end_credits_uses_legacy_window():
    item = {
        "id": "x",
        "path": "/tmp/x.mp4",
        "kind": KIND_END_CREDITS,
        "start_seconds": 100.0,
        "end_seconds": 520.0,
    }
    segments = build_segments_for_item(item, video_duration_sec=5400.0)
    assert len(segments) == 1
    seg = segments[0]
    assert seg["segment_id"] == "legacy"
    assert seg["start_sec"] == 100.0
    assert seg["end_sec"] == 520.0


def test_kind_film_credits_creates_two_segments():
    item = {
        "id": "x",
        "path": "/tmp/x.mp4",
        "kind": KIND_FILM_CREDITS,
        # opening_window_min/closing_window_min default → 3 + 5
    }
    segments = build_segments_for_item(item, video_duration_sec=5000.0)
    assert len(segments) == 2
    opening, closing = segments
    assert opening["segment_id"] == "opening"
    assert opening["start_sec"] == 0.0
    assert opening["end_sec"] == 3 * 60.0  # 180
    assert closing["segment_id"] == "closing"
    assert closing["start_sec"] == 5000.0 - 5 * 60.0  # 4700
    assert closing["end_sec"] == 5000.0


def test_kind_film_credits_custom_windows():
    item = {
        "id": "x",
        "path": "/tmp/x.mp4",
        "kind": KIND_FILM_CREDITS,
        "opening_window_min": 2,
        "closing_window_min": 10,
    }
    segments = build_segments_for_item(item, video_duration_sec=8000.0)
    assert len(segments) == 2
    opening, closing = segments
    assert opening["end_sec"] == pytest.approx(2 * 60.0)
    assert closing["start_sec"] == pytest.approx(8000.0 - 10 * 60.0)
    assert closing["end_sec"] == pytest.approx(8000.0)


@pytest.mark.parametrize("kind", [KIND_KJ_SCAN, KIND_SCENE_TEXT, KIND_FULL_SCAN])
def test_stub_kinds_raise_not_implemented(kind: str):
    item = {"id": "x", "path": "/tmp/x.mp4", "kind": kind}
    with pytest.raises(NotImplementedError):
        build_segments_for_item(item, video_duration_sec=1000.0)


def test_normalize_fills_defaults():
    item = {"id": "x", "path": "/tmp/x.mp4", "kind": KIND_FILM_CREDITS}
    out = normalize_manifest_item(item)
    assert out["opening_window_min"] == 3
    assert out["closing_window_min"] == 5
    assert out["max_opening_min"] == 8
    assert out["max_closing_min"] == 15
    assert out["dynamic_window"] is True
    assert out["expected_language"] == "tr"
    assert out["fps"] == 6


def test_normalize_unknown_kind_raises():
    with pytest.raises(ValueError):
        normalize_manifest_item({"id": "x", "path": "/tmp/x.mp4", "kind": "wat"})


def test_film_credits_short_video_collapses_to_full():
    # 300s video + opening=3 (=180) + closing=5 (=300) → closing_start=0 ≤ opening_end=180 → MERGE
    item = {
        "id": "x",
        "path": "/tmp/x.mp4",
        "kind": KIND_FILM_CREDITS,
    }
    segments = build_segments_for_item(item, video_duration_sec=300.0)
    assert len(segments) == 1
    seg = segments[0]
    assert seg["segment_id"] == "full"
    assert seg["start_sec"] == 0.0
    assert seg["end_sec"] == 300.0


def test_film_credits_opening_zero_only_closing():
    item = {
        "id": "x",
        "path": "/tmp/x.mp4",
        "kind": KIND_FILM_CREDITS,
        "opening_window_min": 0,
        "closing_window_min": 5,
    }
    segments = build_segments_for_item(item, video_duration_sec=5000.0)
    # opening skipped (=0 window) → single closing
    assert len(segments) == 1
    assert segments[0]["segment_id"] == "closing"


def test_end_credits_requires_start_end_seconds():
    item = {"id": "x", "path": "/tmp/x.mp4", "kind": KIND_END_CREDITS}
    with pytest.raises(ValueError):
        build_segments_for_item(item, video_duration_sec=1000.0)


def test_dispatch_runner_for_film_credits_returns_callable():
    item = {"id": "x", "path": "/tmp/x.mp4", "kind": KIND_FILM_CREDITS}
    runner = manifest_profiles.dispatch_runner(item, video_duration_sec=1000.0)
    assert callable(runner)


def test_dispatch_runner_for_stub_kind_raises():
    item = {"id": "x", "path": "/tmp/x.mp4", "kind": KIND_KJ_SCAN}
    with pytest.raises(NotImplementedError):
        manifest_profiles.dispatch_runner(item, video_duration_sec=1000.0)


def test_negative_duration_rejected():
    item = {"id": "x", "path": "/tmp/x.mp4", "kind": KIND_FILM_CREDITS}
    with pytest.raises(ValueError):
        build_segments_for_item(item, video_duration_sec=0.0)
