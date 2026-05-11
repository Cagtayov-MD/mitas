from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from core.pipelines.asr.normalize import normalize_audio


ROOT = Path(__file__).resolve().parents[1]
REAL_MEDIA_CASES = [
    ROOT / "testklipler" / "erd_test_video.mp4",
    ROOT / "testklipler" / "trt_haber (1).mp4",
    ROOT / "testklipler" / "trt_haber (2).mp4",
    ROOT / "testklipler" / "trt_haber (3).mp4",
    ROOT / "testklipler" / "1.mp4",
]


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required for ASR real media normalization tests",
)


@pytest.mark.parametrize("media_path", REAL_MEDIA_CASES, ids=lambda path: path.name)
def test_normalize_audio_real_media_smoke(media_path: Path, tmp_path: Path) -> None:
    if not media_path.exists():
        pytest.skip(f"real media fixture is not available: {media_path}")

    result = normalize_audio(media_path, output_dir=tmp_path / "normalized")

    assert result.reused_input is False
    assert result.input_stream.codec_name == "aac"
    assert result.input_stream.channels == 2
    assert result.output_path.exists()
    assert result.output_path.stat().st_size > 0
    assert result.output_stream.codec_name == "pcm_s16le"
    assert result.output_stream.sample_rate == 16_000
    assert result.output_stream.channels == 1
    assert result.output_stream.sample_fmt == "s16"
    assert result.output_stream.is_target_wav is True
