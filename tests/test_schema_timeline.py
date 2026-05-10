from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.schemas import TimelineEvent


def valid_event() -> dict:
    return {
        "event_id": "event-1",
        "media_id": "media-1",
        "event_type": "song_performance",
        "subtype": "live",
        "start_time": 730.0,
        "end_time": 814.0,
        "confidence": 0.86,
        "status": "needs_review",
        "source_module": "core_schema_test",
        "payload": {"title": "example"},
        "evidence_ids": ["ev-1"],
        "created_at": datetime.now(timezone.utc),
    }


def test_timeline_event_valid() -> None:
    event = TimelineEvent(**valid_event())
    assert event.start_time == 730.0


def test_timeline_event_rejects_string_start_time() -> None:
    data = valid_event()
    data["start_time"] = "730.0"
    with pytest.raises(ValidationError):
        TimelineEvent(**data)


def test_timeline_event_rejects_confidence_above_one() -> None:
    data = valid_event()
    data["confidence"] = 1.01
    with pytest.raises(ValidationError):
        TimelineEvent(**data)


def test_timeline_event_rejects_end_before_start() -> None:
    data = valid_event()
    data["end_time"] = 700.0
    with pytest.raises(ValidationError):
        TimelineEvent(**data)


def test_timeline_event_rejects_invalid_status() -> None:
    data = valid_event()
    data["status"] = "done"
    with pytest.raises(ValidationError):
        TimelineEvent(**data)


def test_timeline_event_rejects_invalid_event_type() -> None:
    data = valid_event()
    data["event_type"] = "unknown_event"
    with pytest.raises(ValidationError):
        TimelineEvent(**data)
