"""Unit tests for `core.pipelines.ocr.dynamic_window` (Faz 4).

These tests exercise `find_dynamic_window` with an injected `has_text_fn`
so no real video / PaddleOCR is touched. The Faz 4 acceptance gate (real
POROROCA / FRANNY integration runs) is exercised via
`outputs/_phase4_*_smoke/` artifacts, not these unit tests.
"""

from __future__ import annotations

from core.pipelines.ocr.dynamic_window import (
    DynamicWindowResult,
    find_dynamic_window,
)


def _capturing_probe(answers: list[bool]) -> tuple:
    """Returns a probe fn that consumes ``answers`` in order and a call log.

    Each call also records the ``probe_t`` so callers can assert on the
    sequence of probe times.
    """
    calls: list[float] = []
    answers_iter = iter(answers)

    def probe(video_path, t_sec, *, paddle_engine, stride_sec, ffmpeg_executable=None):  # noqa: ARG001
        calls.append(float(t_sec))
        try:
            return next(answers_iter)
        except StopIteration:
            return False  # exhausted → assume clean

    return probe, calls


def test_dynamic_window_no_extension_when_boundary_clean() -> None:
    """Mock has_text=False → window stays at the initial size, no extension."""
    probe, calls = _capturing_probe([False])
    result = find_dynamic_window(
        "/fake/video.mp4",
        anchor_sec=0.0,
        direction=1,
        initial_window_min=3.0,
        max_window_min=8.0,
        paddle_engine=object(),  # sentinel; probe is injected
        has_text_fn=probe,
    )
    assert isinstance(result, DynamicWindowResult)
    assert result.start_sec == 0.0
    assert result.end_sec == 180.0  # 3 min
    assert result.iterations == 0
    assert result.initial_start_sec == 0.0
    assert result.initial_end_sec == 180.0
    assert result.max_reached is False
    assert calls == [180.0]
    assert any("boundary_clean" in entry for entry in result.extension_log)


def test_dynamic_window_extends_when_boundary_has_text() -> None:
    """First 3 probes True, then False → window = initial + 3*60s."""
    probe, calls = _capturing_probe([True, True, True, False])
    result = find_dynamic_window(
        "/fake/video.mp4",
        anchor_sec=0.0,
        direction=1,
        initial_window_min=3.0,
        max_window_min=8.0,
        paddle_engine=object(),
        has_text_fn=probe,
        step_sec=60.0,
    )
    assert result.iterations == 3
    # initial 180s + 3 extensions of 60s = 360s
    assert result.end_sec == 360.0
    assert result.max_reached is False
    # 4 probe times: 180, 240, 300, 360
    assert calls == [180.0, 240.0, 300.0, 360.0]
    # Log should show 3 "text_present" + 1 "boundary_clean"
    text_present = [e for e in result.extension_log if "text_present" in e]
    clean = [e for e in result.extension_log if "boundary_clean" in e]
    assert len(text_present) == 3
    assert len(clean) == 1


def test_dynamic_window_respects_max_limit() -> None:
    """Mock = always True → window pinned at max, max_reached=True."""
    # answers list intentionally long so we don't run out before the cap
    probe, calls = _capturing_probe([True] * 50)
    result = find_dynamic_window(
        "/fake/video.mp4",
        anchor_sec=0.0,
        direction=1,
        initial_window_min=3.0,
        max_window_min=5.0,  # 5 min cap → 2 minutes of headroom = 2 extensions
        paddle_engine=object(),
        has_text_fn=probe,
        step_sec=60.0,
    )
    assert result.max_reached is True
    assert result.end_sec == 300.0  # exactly 5 min
    # initial=180 → +60 → +60 = 300, capped. So 2 extensions.
    assert result.iterations == 2
    # Probes at 180 (true) and 240 (true) at minimum; the third would
    # be 300 but we should detect max-reached before probing past the cap.
    assert calls[:2] == [180.0, 240.0]


def test_dynamic_window_forward_direction() -> None:
    """Opening case — anchor=0, direction=+1 → window grows forward."""
    probe, _calls = _capturing_probe([True, False])
    result = find_dynamic_window(
        "/fake/video.mp4",
        anchor_sec=0.0,
        direction=1,
        initial_window_min=2.0,
        max_window_min=10.0,
        paddle_engine=object(),
        has_text_fn=probe,
        step_sec=60.0,
    )
    assert result.start_sec == 0.0
    assert result.end_sec == 180.0  # 120 + 1*60
    assert result.initial_end_sec == 120.0
    assert result.iterations == 1


def test_dynamic_window_backward_direction() -> None:
    """Closing case — anchor=N, direction=-1 → window grows backward."""
    probe, calls = _capturing_probe([True, True, False])
    result = find_dynamic_window(
        "/fake/video.mp4",
        anchor_sec=8000.0,  # video duration sentinel
        direction=-1,
        initial_window_min=5.0,
        max_window_min=15.0,
        paddle_engine=object(),
        has_text_fn=probe,
        step_sec=60.0,
    )
    # Initial window: [8000 - 300, 8000] = [7700, 8000]
    assert result.initial_start_sec == 7700.0
    assert result.initial_end_sec == 8000.0
    # After 2 successful extensions: start = 7700 - 120 = 7580
    assert result.end_sec == 8000.0
    assert result.start_sec == 7580.0
    assert result.iterations == 2
    # Probes at left boundary: 7700, 7640, 7580
    assert calls == [7700.0, 7640.0, 7580.0]


def test_dynamic_window_two_frame_confirmation() -> None:
    """Real `_has_text_at` is the 2-frame gate; here we verify that a fn that
    *returns False on first call* keeps the window static (no false-positive
    extension even though somewhere else the boundary might briefly flash text).
    """
    # First probe returns False outright → no extension
    probe, calls = _capturing_probe([False])
    result = find_dynamic_window(
        "/fake/video.mp4",
        anchor_sec=0.0,
        direction=1,
        initial_window_min=1.0,
        max_window_min=5.0,
        paddle_engine=object(),
        has_text_fn=probe,
    )
    assert result.iterations == 0
    assert result.end_sec == 60.0
    assert calls == [60.0]


def test_dynamic_window_skips_when_paddle_engine_none() -> None:
    """No engine + no injected probe → return initial window, log skip."""
    result = find_dynamic_window(
        "/fake/video.mp4",
        anchor_sec=0.0,
        direction=1,
        initial_window_min=3.0,
        max_window_min=8.0,
        paddle_engine=None,
    )
    assert result.iterations == 0
    assert result.end_sec == 180.0
    assert result.extension_log == ["paddle_engine=None → skip dynamic extension"]
    assert result.max_reached is False


def test_manifest_profile_film_credits_emits_dynamic_telemetry() -> None:
    """When dynamic_window=True and no engine given, segment carries telemetry
    flagging static-fallback (skipped_no_engine=True). Verifies the integration
    seam between manifest_profiles and dynamic_window for the static path."""
    from core.pipelines.ocr.manifest_profiles import (
        KIND_FILM_CREDITS,
        build_segments_for_item,
    )

    item = {
        "id": "x",
        "path": "/tmp/x.mp4",
        "kind": KIND_FILM_CREDITS,
        # dynamic_window default = True from schema
    }
    segments = build_segments_for_item(item, video_duration_sec=5000.0)
    assert len(segments) == 2
    opening, closing = segments
    # Both segments expose dynamic_window telemetry
    assert opening["dynamic_window"] is not None
    assert closing["dynamic_window"] is not None
    assert opening["dynamic_window"]["skipped_no_engine"] is True
    assert closing["dynamic_window"]["skipped_no_engine"] is True
    # And the bounds match the static Faz 2 behavior
    assert opening["start_sec"] == 0.0
    assert opening["end_sec"] == 180.0
    assert closing["start_sec"] == 5000.0 - 300.0
    assert closing["end_sec"] == 5000.0


def test_manifest_profile_film_credits_dynamic_false_skips_telemetry() -> None:
    """When dynamic_window=False, no probing is even considered → telemetry
    field stays None so we don't pollute outputs of users who pinned static."""
    from core.pipelines.ocr.manifest_profiles import (
        KIND_FILM_CREDITS,
        build_segments_for_item,
    )

    item = {
        "id": "x",
        "path": "/tmp/x.mp4",
        "kind": KIND_FILM_CREDITS,
        "dynamic_window": False,
    }
    segments = build_segments_for_item(item, video_duration_sec=5000.0)
    assert len(segments) == 2
    for seg in segments:
        assert seg["dynamic_window"] is None
