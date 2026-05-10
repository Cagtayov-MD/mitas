from __future__ import annotations

from datetime import datetime

from core.schemas.common import BBox, Confidence, Payload, StrictSchemaModel, StrictSeconds, StrictStr


class Evidence(StrictSchemaModel):
    evidence_id: StrictStr
    media_id: StrictStr
    source_module: StrictStr
    time_sec: StrictSeconds
    frame_id: StrictStr | None
    artifact_path: StrictStr | None
    text: StrictStr | None
    bbox: BBox | None
    confidence: Confidence
    metadata: Payload
    created_at: datetime
