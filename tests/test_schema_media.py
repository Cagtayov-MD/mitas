from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.schemas import MediaItem


def valid_media() -> dict:
    return {
        "media_id": "media-1",
        "file_path": "E:/MITAS/test_assets/video/sample.mp4",
        "duration_sec": 120.5,
        "fps": 25.0,
        "width": 1920,
        "height": 1080,
        "created_at": datetime.now(timezone.utc),
    }


def test_media_item_valid() -> None:
    media = MediaItem(**valid_media())
    assert media.media_id == "media-1"


def test_media_item_rejects_string_duration() -> None:
    data = valid_media()
    data["duration_sec"] = "120.5"
    with pytest.raises(ValidationError):
        MediaItem(**data)
