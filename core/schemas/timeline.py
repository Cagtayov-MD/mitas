from __future__ import annotations

from datetime import datetime

from pydantic import model_validator

from core.schemas.common import Confidence, EventStatus, EventType, Payload, StrictSchemaModel, StrictSeconds, StrictStr


class TimelineEvent(StrictSchemaModel):
    event_id: StrictStr
    media_id: StrictStr
    event_type: EventType
    subtype: StrictStr | None
    start_time: StrictSeconds
    end_time: StrictSeconds
    confidence: Confidence
    status: EventStatus
    source_module: StrictStr
    payload: Payload
    evidence_ids: list[StrictStr]
    created_at: datetime

    @model_validator(mode="after")
    def validate_time_range(self) -> "TimelineEvent":
        if self.end_time < self.start_time:
            raise ValueError("end_time must be greater than or equal to start_time")
        return self
