"""Faz 1 — TextEvent dataclass + schema validation tests.

Schema: core/pipelines/ocr/schemas/text_event.schema.json (v1.0.0)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.pipelines.ocr.text_event import (
    SCHEMA_VERSION,
    TextEvent,
    validate_events,
)


def _valid_event(**overrides) -> TextEvent:
    base = {
        "event_id": "evt_0001",
        "start_sec": 10.0,
        "end_sec": 14.5,
        "duration_sec": 4.5,
        "type": "card",
        "type_reason": "static_tracks=3 + duration=4.5s + grouped → card",
        "text": "DIRECTOR JAMES CAMERON",
        "confidence": 0.92,
        "bbox": [100.0, 200.0, 400.0, 50.0],
        "stability": "static",
        "frame_count": 12,
    }
    base.update(overrides)
    return TextEvent(**base)


def test_text_event_valid_to_dict_passes_schema_validation():
    """Valid TextEvent → to_dict → validate_events returns empty error list.

    If jsonschema is installed, also passes Draft7Validator.
    """
    ev = _valid_event()
    data = ev.to_dict()
    # required fields present
    for field_name in ("event_id", "start_sec", "end_sec", "type", "type_reason", "text", "confidence"):
        assert field_name in data, f"missing required field {field_name}"
    # validate_events returns no errors
    errors = validate_events([ev])
    assert errors == [], f"expected zero errors, got: {errors}"

    # If jsonschema is installed, validate against actual schema definition
    try:
        import jsonschema  # type: ignore
        schema_path = Path(__file__).parent.parent / "core" / "pipelines" / "ocr" / "schemas" / "text_event.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=data, schema=schema["definitions"]["TextEvent"])
    except ImportError:
        pytest.skip("jsonschema not installed in this venv — manual validator covers it")


def test_text_event_missing_required_field_fails():
    """event_id silinince validate_events bir hata döner."""
    ev = _valid_event()
    data = ev.to_dict()
    del data["event_id"]
    # Manual check
    from core.pipelines.ocr.text_event import _manual_check_event
    errors = _manual_check_event(data, "<missing>")
    assert any("event_id" in e for e in errors), f"expected event_id error, got: {errors}"


def test_text_event_empty_type_reason_fails():
    """type_reason='' validation hatasına neden olur."""
    ev = _valid_event(type_reason="")
    errors = validate_events([ev])
    assert any("type_reason" in e for e in errors), f"expected type_reason error, got: {errors}"


def test_text_event_invalid_type_enum_fails():
    """type='bogus' enum dışı → hata."""
    ev = _valid_event(type="bogus")
    errors = validate_events([ev])
    assert any("type" in e and "bogus" in e for e in errors), f"expected type enum error, got: {errors}"


def test_text_event_roundtrip_identity():
    """to_dict → from_dict → original ile equal."""
    original = _valid_event(
        secondary_text="JAMES CAMERON",
        tracker_id=42,
        lines=[{"text": "DIRECTOR", "confidence": 0.9, "bbox": [10.0, 20.0, 100.0, 30.0]}],
        paired_role_name={"role": "DIRECTOR", "name": "JAMES CAMERON"},
    )
    data = original.to_dict()
    rehydrated = TextEvent.from_dict(data)
    assert rehydrated == original, (
        f"roundtrip mismatch:\n  original={original}\n  rehydrated={rehydrated}"
    )
    # Also check schema_version constant
    assert SCHEMA_VERSION == "1.0.0"
