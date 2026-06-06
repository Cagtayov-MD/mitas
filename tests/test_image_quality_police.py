from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("cv2")  # OCR testleri cv2 gerektirir (venvs\ocr); cv2 yoksa (asr venv) zarif atla

from core.pipelines.ocr.image_quality_police import assess_output


ROOT = Path(__file__).resolve().parents[1]
PILOT_ITEMS = ROOT / "outputs" / "filmtest_6clip_pilot_20260523" / "items"
FRESH_ITEMS = ROOT / "outputs" / "filmtest_6clip_fresh_20260523_boxtracker_guarded_b" / "items"


def test_quality_police_flags_dunyanin_background_leak_fixture() -> None:
    item_dir = PILOT_ITEMS / "filmtest_dunyanin_en_muthis_adami_last3min"
    png = item_dir / "text_layer_row_reconstruct" / "row_composite_sharpened.png"
    ocr_json = item_dir / "row_crop_ocr.json"
    _require_fixture(png, ocr_json)

    result = assess_output(png, ocr_json, expected_kind="row_canvas")

    assert result["status"] == "BROKEN_BACKGROUND_LEAK"
    assert "edges_outside_text_boxes" in result["reasons"]


def test_quality_police_accepts_pilkington_fixture() -> None:
    item_dir = PILOT_ITEMS / "filmtest_pilkingtondan_sonra_last3min"
    png = item_dir / "text_layer_row_reconstruct" / "row_composite_sharpened.png"
    ocr_json = item_dir / "row_crop_ocr.json"
    _require_fixture(png, ocr_json)

    result = assess_output(png, ocr_json, expected_kind="row_canvas")

    assert result["status"] == "OK"


def test_quality_police_flags_kukla_black_fused_fixture_when_available() -> None:
    pilot_png = PILOT_ITEMS / "filmtest_kukla_adam_last3min" / "temporal_fusion" / "fused.png"
    pilot_json = PILOT_ITEMS / "filmtest_kukla_adam_last3min" / "temporal_fusion.json"
    fresh_png = FRESH_ITEMS / "filmtest_kukla_adam_last3min" / "temporal_fusion" / "fused.png"
    fresh_json = FRESH_ITEMS / "filmtest_kukla_adam_last3min" / "temporal_fusion.json"
    png, ocr_json = (pilot_png, pilot_json) if pilot_png.exists() else (fresh_png, fresh_json)
    _require_fixture(png)

    result = assess_output(png, ocr_json if ocr_json.exists() else None, expected_kind="fused")

    assert result["status"] == "BROKEN_BLACK"


def _require_fixture(*paths: Path) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        pytest.skip("fixture missing: " + ", ".join(missing))
