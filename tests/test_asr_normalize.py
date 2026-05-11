from __future__ import annotations

from pathlib import Path
import shutil
import wave

import pytest

from core.pipelines.asr.normalize import AudioNormalizeError, normalize_audio, probe_audio_stream


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_WAV = ROOT / "samples" / "torchcodec_smoke.wav"


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required for ASR audio normalization tests",
)


def test_probe_audio_stream_reads_target_sample() -> None:
    info = probe_audio_stream(SAMPLE_WAV)

    assert info.codec_name == "pcm_s16le"
    assert info.sample_rate == 16_000
    assert info.channels == 1
    assert info.sample_fmt == "s16"
    assert info.is_target_wav is True


def test_normalize_audio_reuses_target_wav() -> None:
    result = normalize_audio(SAMPLE_WAV)

    assert result.reused_input is True
    assert result.command is None
    assert result.output_path == SAMPLE_WAV
    assert result.output_stream.is_target_wav is True


def test_normalize_audio_converts_non_target_wav(tmp_path: Path) -> None:
    source = tmp_path / "stereo_8khz.wav"
    _write_silent_wav(source, sample_rate=8_000, channels=2)

    result = normalize_audio(source, output_dir=tmp_path / "normalized")

    assert result.reused_input is False
    assert result.output_path.exists()
    assert result.output_stream.codec_name == "pcm_s16le"
    assert result.output_stream.sample_rate == 16_000
    assert result.output_stream.channels == 1
    assert result.output_stream.sample_fmt == "s16"
    assert result.output_stream.is_target_wav is True


def test_normalize_audio_missing_input_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.wav"

    with pytest.raises(AudioNormalizeError):
        normalize_audio(missing)


def _write_silent_wav(path: Path, *, sample_rate: int, channels: int) -> None:
    frames = sample_rate // 10
    sample_width_bytes = 2
    silent_frame = b"\x00" * sample_width_bytes * channels

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frame * frames)
