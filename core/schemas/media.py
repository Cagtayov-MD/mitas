from __future__ import annotations

from datetime import datetime

from core.schemas.common import NonNegativeInt, StrictNonNegativeFloat, StrictSchemaModel, StrictStr


class MediaItem(StrictSchemaModel):
    media_id: StrictStr
    file_path: StrictStr
    duration_sec: StrictNonNegativeFloat
    fps: StrictNonNegativeFloat
    width: NonNegativeInt
    height: NonNegativeInt
    created_at: datetime
