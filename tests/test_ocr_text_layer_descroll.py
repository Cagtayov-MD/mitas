from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from PIL import Image, ImageDraw

from core.pipelines.ocr.credit_experiment import normalize_text
from core.pipelines.ocr.text_layer_descroll import run_text_layer_descroll


def test_text_layer_descroll_writes_structured_pairs_and_review_pack(tmp_path: Path) -> None:
    item_dir = tmp_path / "item"
    item_dir.mkdir()
    frame = item_dir / "frame_0001.png"
    image = Image.new("RGB", (640, 360), "black")
    draw = ImageDraw.Draw(image)
    draw.text((130, 160), "Taylor", fill="white")
    draw.text((260, 160), "MICHAEL BIEHN", fill=(20, 200, 255))
    image.save(frame)

    records = []
    for index in range(8):
        timestamp = 10.0 + index * 0.5
        records.append(_record("paddle", "lg_name", "MICHAEL BIEHN", frame, timestamp, [260, 160 - index * 3, 160, 24], 0.95))
        records.append(_record("paddle", "lg_role", "Taylor", frame, timestamp, [130, 160 - index * 3, 72, 22], 0.90))
        records.append(_record("oneocr", "lg_combo", "Taylor MICHAEL BIEHN", frame, timestamp, [130, 160 - index * 3, 292, 25], 0.88))

    temporal = {
        "strategy": "temporal_voting",
        "records": records,
        "groups": [
            _group("paddle", "lg_name", "MICHAEL BIEHN", 8, 0.95),
            _group("paddle", "lg_role", "Taylor", 8, 0.90),
            _group("oneocr", "lg_combo", "Taylor MICHAEL BIEHN", 8, 0.88),
        ],
        "stable_groups": 3,
        "unique_lines": 3,
    }
    (item_dir / "temporal_voting.json").write_text(json.dumps(temporal), encoding="utf-8")
    (item_dir / "frame_ocr.json").write_text(json.dumps({"frames": [str(frame)], "records": records}), encoding="utf-8")
    (item_dir / "item_summary.json").write_text(json.dumps({"expected_language": "en"}), encoding="utf-8")

    result = run_text_layer_descroll(item_dir, engine="paddle", fusion_engines=["paddle", "oneocr"], strict_min_records=4, strict_min_confidence=0.7)

    structured = json.loads(result.structured_json_path.read_text(encoding="utf-8"))
    review = json.loads(result.review_pack_path.read_text(encoding="utf-8"))

    assert structured["credits"][0]["role"] == "Taylor"
    assert structured["credits"][0]["name"] == "MICHAEL BIEHN"
    assert result.strict_canvas_path.exists()
    assert result.ordered_text_path.exists()
    assert review["items"]


def _record(engine: str, group: str, text: str, frame: Path, timestamp: float, bbox: list[float], confidence: float) -> dict:
    return {
        "engine": engine,
        "strategy": "frame_ocr",
        "frame": str(frame),
        "timestamp_seconds": timestamp,
        "bbox": bbox,
        "text": text,
        "confidence": confidence,
        "normalized_text": normalize_text(text),
        "line_group_id": group,
        "warnings": [],
    }


def _group(engine: str, group: str, text: str, count: int, confidence: float) -> dict:
    return {
        "line_group_id": group,
        "engine": engine,
        "winner_text": text,
        "winner_normalized_text": normalize_text(text),
        "first_timestamp_seconds": 10.0,
        "last_timestamp_seconds": 13.5,
        "record_count": count,
        "mean_confidence": confidence,
        "variants": [{"normalized_text": normalize_text(text), "count": count}],
    }
