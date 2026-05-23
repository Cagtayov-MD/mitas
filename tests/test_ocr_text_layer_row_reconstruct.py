from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.pipelines.ocr.text_layer_row_reconstruct import (
    _trim_composite_by_row_gap,
    detect_auto_split,
    detect_rows,
    quality_score,
    run_text_layer_row_reconstruct,
)


def test_row_reconstruct_exports_composite_rows_and_auto_split(tmp_path: Path) -> None:
    frames = _make_scrolling_role_name_frames(tmp_path / "frames")
    output_dir = tmp_path / "row_reconstruct"

    result = run_text_layer_row_reconstruct(frame_paths=frames, output_dir=output_dir, max_frames=60, scale_for_rows=1)
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

    assert result.composite_path.exists()
    assert summary["composite_size"][1] > 360
    assert summary["motion"]["status"] == "ok"
    assert summary["row_count"] >= 8
    assert summary["auto_split"]["status"] == "detected"
    assert 230 <= summary["auto_split"]["split_x"] <= 380
    assert any("role_crop_path" in row for row in summary["rows"])
    assert any("name_crop_path" in row for row in summary["rows"])
    assert "quality" in summary
    assert summary["quality"]["score"] >= 0.0
    assert "frame_filter" in summary
    assert summary["candidate_selector"]["selected"] in {"current_displacement", "static_best_frame"}
    assert len(summary["candidate_selector"]["candidates"]) >= 2


def test_quality_score_flags_blank_lower_than_text_image() -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    blank = np.zeros((240, 360, 3), dtype=np.uint8)
    text = blank.copy()
    for index in range(5):
        cv2.putText(text, f"NAME {index}", (80, 55 + index * 34), cv2.FONT_HERSHEY_SIMPLEX, 0.74, (255, 255, 255), 2, cv2.LINE_AA)

    q_blank = quality_score(blank, cv2)
    q_text = quality_score(text, cv2)

    assert q_blank["score"] < 0.2
    assert q_text["score"] > q_blank["score"]


def test_auto_split_declines_single_center_column(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    image = np.zeros((360, 640, 3), dtype=np.uint8)
    for index, text in enumerate(["DIRECTED BY", "MICHAEL BIEHN", "PRODUCED BY", "ANNE DENMAN"]):
        cv2.putText(image, text, (210, 120 + index * 42), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)

    split = detect_auto_split(image)

    assert split["split_x"] is None
    assert split["status"] in {"no_clear_column_gap", "no_balanced_gap", "low_confidence_gap"}


def test_detect_rows_finds_physical_rows(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    image = np.zeros((480, 640, 3), dtype=np.uint8)
    for index in range(7):
        cv2.putText(image, f"ROLE {index}", (80, 70 + index * 55), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(image, f"NAME {index}", (360, 70 + index * 55), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)

    rows = detect_rows(image)

    assert len(rows) == 7
    assert rows[0]["y0"] < rows[0]["peak_y"] < rows[0]["y1"]


def test_trim_composite_by_row_gap_drops_tail_after_oversized_gap() -> None:
    np = pytest.importorskip("numpy")
    composite = np.zeros((1000, 200, 3), dtype=np.uint8)
    rows = [
        {"index": 1, "y0": 0, "y1": 30, "peak_y": 15},
        {"index": 2, "y0": 40, "y1": 70, "peak_y": 55},
        {"index": 3, "y0": 80, "y1": 110, "peak_y": 95},
        {"index": 4, "y0": 120, "y1": 150, "peak_y": 135},
        {"index": 5, "y0": 160, "y1": 190, "peak_y": 175},
        {"index": 6, "y0": 600, "y1": 630, "peak_y": 615},
        {"index": 7, "y0": 750, "y1": 780, "peak_y": 765},
    ]

    info, trimmed, kept = _trim_composite_by_row_gap(composite, rows)

    assert info["applied"] is True
    assert info["kept_rows"] == 5
    assert info["dropped_rows"] == 2
    assert info["cut_gap_px"] == 410
    assert trimmed.shape[0] == info["cut_y"]
    assert trimmed.shape[0] < composite.shape[0]
    assert [row["index"] for row in kept] == [1, 2, 3, 4, 5]


def test_trim_composite_by_row_gap_no_op_when_gaps_are_uniform() -> None:
    np = pytest.importorskip("numpy")
    composite = np.zeros((400, 200, 3), dtype=np.uint8)
    rows = [
        {"index": idx + 1, "y0": idx * 40, "y1": idx * 40 + 30, "peak_y": idx * 40 + 15}
        for idx in range(8)
    ]

    info, trimmed, kept = _trim_composite_by_row_gap(composite, rows)

    assert info["applied"] is False
    assert info["reason"] == "no_oversized_gap"
    assert trimmed is composite
    assert kept is rows


def test_trim_composite_by_row_gap_no_op_when_too_few_rows() -> None:
    np = pytest.importorskip("numpy")
    composite = np.zeros((400, 200, 3), dtype=np.uint8)
    rows = [
        {"index": 1, "y0": 0, "y1": 30, "peak_y": 15},
        {"index": 2, "y0": 200, "y1": 230, "peak_y": 215},
    ]

    info, trimmed, kept = _trim_composite_by_row_gap(composite, rows)

    assert info["applied"] is False
    assert info["reason"] == "too_few_rows"


def _make_scrolling_role_name_frames(directory: Path) -> list[Path]:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    directory.mkdir(parents=True, exist_ok=True)
    frame_count = 60
    rows = [
        ("Director", "MICHAEL BIEHN"),
        ("Producer", "ANNE DENMAN"),
        ("Editor", "BETTINA McCALL"),
        ("Sound", "MARTIN EVANS"),
        ("Camera", "JAMES ASPINALL"),
        ("Location", "EJAZ AHMED"),
        ("Carpenter", "NICK CUMMINS"),
        ("Costumer", "LYNN TALBOT"),
        ("Makeup", "SAUL SULTAN"),
        ("Paint", "MARKO LYTVIAK"),
        ("Chef", "SOREN TAMBOUR"),
        ("Assistant", "PENNY WOOLLEY"),
    ]
    paths: list[Path] = []
    for frame_index in range(frame_count):
        image = np.zeros((360, 640, 3), dtype=np.uint8)
        y_base = 390 - frame_index * 9
        for row_index, (role, name) in enumerate(rows):
            y = y_base + row_index * 42
            if -40 <= y <= 400:
                cv2.putText(image, role, (72, y), cv2.FONT_HERSHEY_SIMPLEX, 0.64, (230, 230, 230), 2, cv2.LINE_AA)
                cv2.putText(image, name, (370, y), cv2.FONT_HERSHEY_SIMPLEX, 0.64, (255, 255, 255), 2, cv2.LINE_AA)
        path = directory / f"frame_{frame_index:04d}.png"
        cv2.imwrite(str(path), image)
        paths.append(path)
    return paths
