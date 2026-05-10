from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.schemas import Evidence


def valid_evidence() -> dict:
    return {
        "evidence_id": "ev-1",
        "media_id": "media-1",
        "source_module": "ocr",
        "time_sec": 12.0,
        "frame_id": "frame-300",
        "artifact_path": "E:/MITAS/outputs/evidence/frame-300.png",
        "text": "KJ example",
        "bbox": [10.0, 20.0, 300.0, 60.0],
        "confidence": 0.91,
        "metadata": {"roi": "lower_third"},
        "created_at": datetime.now(timezone.utc),
    }


def test_evidence_valid() -> None:
    evidence = Evidence(**valid_evidence())
    assert evidence.evidence_id == "ev-1"


def test_evidence_rejects_string_time_sec() -> None:
    data = valid_evidence()
    data["time_sec"] = "12.0"
    with pytest.raises(ValidationError):
        Evidence(**data)


def test_evidence_rejects_confidence_above_one() -> None:
    data = valid_evidence()
    data["confidence"] = 1.2
    with pytest.raises(ValidationError):
        Evidence(**data)
