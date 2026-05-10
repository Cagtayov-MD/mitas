from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictInt, StrictStr


class StrictSchemaModel(BaseModel):
    """Shared base: strict primitive fields plus forbidden unknown fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EventType(str, Enum):
    asr_segment = "asr_segment"
    screen_text = "screen_text"
    audio_activity = "audio_activity"
    song_announcement = "song_announcement"
    song_recognition_match = "song_recognition_match"
    song_performance = "song_performance"
    face_track = "face_track"
    face_cluster = "face_cluster"
    visual_tag = "visual_tag"
    credit_event = "credit_event"
    system_event = "system_event"


class EventStatus(str, Enum):
    auto = "auto"
    needs_review = "needs_review"
    confirmed = "confirmed"
    rejected = "rejected"
    ignored = "ignored"
    failed = "failed"
    partial = "partial"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    partial = "partial"
    cancelled = "cancelled"
    skipped = "skipped"


class RelationType(str, Enum):
    face_matches_kj_name_candidate = "face_matches_kj_name_candidate"
    speaker_overlaps_face_candidate = "speaker_overlaps_face_candidate"
    kj_mentions_song_candidate = "kj_mentions_song_candidate"
    asr_supports_song_candidate = "asr_supports_song_candidate"
    fingerprint_supports_song_candidate = "fingerprint_supports_song_candidate"
    screen_text_context_for_face = "screen_text_context_for_face"
    visual_tag_context_for_scene = "visual_tag_context_for_scene"


def _require_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, float):
        raise ValueError("value must be a float")
    return value


StrictSeconds = Annotated[float, BeforeValidator(_require_float), Field(ge=0.0)]
StrictNonNegativeFloat = Annotated[float, BeforeValidator(_require_float), Field(ge=0.0)]
Confidence = Annotated[float, BeforeValidator(_require_float), Field(ge=0.0, le=1.0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
Payload = dict[StrictStr, Any]
BBox = list[StrictNonNegativeFloat]

__all__ = [
    "BBox",
    "Confidence",
    "EventStatus",
    "EventType",
    "JobStatus",
    "NonNegativeInt",
    "Payload",
    "RelationType",
    "StrictBool",
    "StrictNonNegativeFloat",
    "StrictSchemaModel",
    "StrictSeconds",
    "StrictStr",
]
