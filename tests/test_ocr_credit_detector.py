from __future__ import annotations

from pathlib import Path

import pytest

from core.pipelines.ocr.credit_detector import detect_credit_segments_from_frames


def test_credit_detector_finds_late_scrolling_segment(tmp_path: Path) -> None:
    frames, timestamps = _make_detector_frames(tmp_path / "late_scroll", mode="late_scroll")

    result = detect_credit_segments_from_frames(frames, timestamps=timestamps, window_seconds=5.0, score_threshold=0.38)

    assert result.segments
    assert result.segments[0].start_seconds >= 10.0
    assert result.segments[0].label == "scrolling_credit"
    assert any(window.label == "vertical_scroll_credit" for window in result.windows)


def test_credit_detector_separates_static_credit_from_scroll(tmp_path: Path) -> None:
    frames, timestamps = _make_detector_frames(tmp_path / "static", mode="static_credit")

    result = detect_credit_segments_from_frames(frames, timestamps=timestamps, window_seconds=5.0, score_threshold=0.38)

    assert result.segments
    assert result.segments[0].label == "static_or_mixed_credit"
    assert any(window.label == "static_credit" for window in result.windows)


def test_credit_detector_does_not_call_bright_overlay_static_credit(tmp_path: Path) -> None:
    frames, timestamps = _make_detector_frames(tmp_path / "overlay", mode="bright_overlay")

    result = detect_credit_segments_from_frames(frames, timestamps=timestamps, window_seconds=5.0, score_threshold=0.38)

    assert not any(window.label == "static_credit" for window in result.windows)


def _make_detector_frames(directory: Path, *, mode: str) -> tuple[list[Path], list[float]]:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    directory.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    timestamps: list[float] = []
    for index in range(25):
        image = np.full((360, 640, 3), (48, 44, 38), dtype=np.uint8)
        if index < 10:
            cv2.rectangle(image, (40, 70), (590, 300), (80, 70, 60), -1)
        elif mode == "late_scroll":
            base_y = 390 - (index - 10) * 9
            for row_index, name in enumerate(["MICHAEL BIEHN", "ANNE DENMAN", "BETTINA McCALL", "MARTIN EVANS", "JAMES ASPINALL"]):
                y = base_y + row_index * 45
                if -30 <= y <= 390:
                    cv2.putText(image, name, (190, y), cv2.FONT_HERSHEY_SIMPLEX, 0.76, (255, 255, 255), 2, cv2.LINE_AA)
        elif mode == "static_credit":
            image[:] = 0
            for row_index, (role, name) in enumerate([("Director", "MICHAEL BIEHN"), ("Producer", "ANNE DENMAN"), ("Editor", "BETTINA McCALL")]):
                y = 145 + row_index * 48
                cv2.putText(image, role, (120, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (230, 230, 230), 2, cv2.LINE_AA)
                cv2.putText(image, name, (310, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
        elif mode == "bright_overlay":
            image[:] = (118, 112, 104)
            cv2.rectangle(image, (40, 70), (590, 300), (140, 130, 118), -1)
            for row_index, (role, name) in enumerate([("Director", "MICHAEL BIEHN"), ("Producer", "ANNE DENMAN"), ("Editor", "BETTINA McCALL")]):
                y = 145 + row_index * 48
                cv2.putText(image, role, (120, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (230, 230, 230), 2, cv2.LINE_AA)
                cv2.putText(image, name, (310, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
        path = directory / f"frame_{index:04d}.png"
        cv2.imwrite(str(path), image)
        frames.append(path)
        timestamps.append(float(index))
    return frames, timestamps
