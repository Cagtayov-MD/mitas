from __future__ import annotations

from pathlib import Path

import pytest

from core.pipelines.ocr.credit_pipeline_selector import select_credit_pipeline
from core.pipelines.ocr.credit_scene_router import analyze_credit_scene, refine_credit_scene_with_ocr


def test_router_detects_vertical_scroll_and_row_reconstruct(tmp_path: Path) -> None:
    frames = _make_text_frames(tmp_path, positions=[260, 252, 244, 236, 228, 220, 212, 204])

    profile = analyze_credit_scene(frames, segment_id="scroll")

    assert profile.text_motion.type == "vertical_scroll"
    assert profile.text_motion.confidence >= 0.55
    assert profile.layout.type == "center_single_column"
    assert profile.recommended_pipeline["temporal"] == "row_reconstruct"
    assert "center_strip_composite" in profile.recommended_pipeline["steps"]


def test_router_detects_static_lower_third_card(tmp_path: Path) -> None:
    frames = _make_text_frames(tmp_path, positions=[292] * 8, text="SON DAKIKA", x=120)

    profile = analyze_credit_scene(frames, segment_id="lower")

    assert profile.text_motion.type == "static_card"
    assert profile.layout.type == "lower_third"
    assert profile.recommended_pipeline["roi"] == "bottom_35"
    assert profile.recommended_pipeline["temporal"] == "best_frame_selection"


def test_router_marks_low_contrast_as_preprocess_need(tmp_path: Path) -> None:
    frames = _make_text_frames(tmp_path, positions=[170] * 6, background=(72, 72, 72), color=(118, 118, 118), text="LOW CONTRAST")

    profile = analyze_credit_scene(frames, segment_id="low_contrast")

    assert "low_contrast" in profile.difficulty.labels
    assert "clahe" in profile.recommended_pipeline["preprocess"]


def test_pipeline_selector_is_conservative_for_unknown_motion() -> None:
    recommendation = select_credit_pipeline(
        {
            "background": {"type": "moving_scene"},
            "text_motion": {"type": "unknown"},
            "layout": {"type": "multi_column"},
            "difficulty": {"labels": ["blur_or_lowres"], "score": 0.5},
        }
    )

    assert recommendation.temporal == "temporal_voting"
    assert "upscale2x" in recommendation.preprocess
    assert recommendation.parser == "column_aware_parser"


def test_router_ocr_refinement_recovers_vertical_scroll() -> None:
    profile = {
        "segment_id": "sample",
        "background": {"type": "moving_scene", "confidence": 0.82, "evidence": {}},
        "text_motion": {"type": "mixed", "confidence": 0.52, "evidence": {}},
        "layout": {"type": "center_single_column", "confidence": 0.78, "evidence": {}},
        "difficulty": {"labels": [], "score": 0.2, "confidence": 0.7, "evidence": {}},
        "recommended_pipeline": {},
        "raw_features": {},
    }
    records = []
    for group_index, x in enumerate([220, 260, 300], 1):
        for frame_index, timestamp in enumerate([0.0, 0.5, 1.0, 1.5]):
            records.append(
                {
                    "engine": "fake",
                    "line_group_id": f"lg_{group_index}",
                    "timestamp_seconds": timestamp,
                    "bbox": [x, 220 - frame_index * 10, 120, 24],
                    "text": f"NAME {group_index}",
                }
            )

    refined = refine_credit_scene_with_ocr(profile, records)

    assert refined["text_motion"]["type"] == "vertical_scroll"
    assert refined["recommended_pipeline"]["temporal"] == "row_reconstruct"


def _make_text_frames(
    directory: Path,
    *,
    positions: list[int],
    text: str = "TAYLOR  MICHAEL BIEHN",
    x: int = 92,
    background: tuple[int, int, int] = (0, 0, 0),
    color: tuple[int, int, int] = (255, 255, 255),
) -> list[Path]:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, y in enumerate(positions):
        image = np.full((360, 640, 3), background, dtype=np.uint8)
        cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.86, color, 2, cv2.LINE_AA)
        # Add small stable edge detail so background/layout metrics see a real frame.
        cv2.rectangle(image, (16, 16), (624, 344), (12, 12, 12), 1)
        path = directory / f"frame_{index:03d}.png"
        cv2.imwrite(str(path), image)
        paths.append(path)
    return paths
