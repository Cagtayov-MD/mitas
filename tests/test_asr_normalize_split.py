from __future__ import annotations

from pathlib import Path
import math
import shutil
import wave

import pytest

from core.pipelines.asr.normalize import AudioNormalizeError, normalize_audio


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required for split normalization tests",
)


def test_split_stereo_input_emits_left_and_right_target_wavs(tmp_path: Path) -> None:
    source = tmp_path / "stereo.wav"
    _write_stereo_sine(source)

    result = normalize_audio(source, output_dir=tmp_path / "normalized", channel_mode="split")

    assert set(result.outputs) == {"L", "R"}
    assert result.output_path == result.outputs["L"]
    assert result.outputs["L"].exists()
    assert result.outputs["R"].exists()
    assert result.output_stream.is_target_wav is True


def test_split_mono_input_raises(tmp_path: Path) -> None:
    source = tmp_path / "mono.wav"
    _write_mono_wav(source)

    with pytest.raises(AudioNormalizeError):
        normalize_audio(source, output_dir=tmp_path / "normalized", channel_mode="split")


def test_default_mono_behavior_still_emits_mono_output(tmp_path: Path) -> None:
    source = tmp_path / "stereo.wav"
    _write_stereo_sine(source)

    result = normalize_audio(source, output_dir=tmp_path / "normalized")

    assert set(result.outputs) == {"mono"}
    assert result.output_path == result.outputs["mono"]
    assert result.output_stream.channels == 1


def _write_stereo_sine(path: Path, *, seconds: float = 1.0, sample_rate: int = 8_000) -> None:
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        payload = bytearray()
        for index in range(frames):
            left = int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            right = int(12000 * math.sin(2 * math.pi * 880 * index / sample_rate))
            payload.extend(left.to_bytes(2, "little", signed=True))
            payload.extend(right.to_bytes(2, "little", signed=True))
        wav_file.writeframes(bytes(payload))


def _write_mono_wav(path: Path, *, seconds: float = 1.0, sample_rate: int = 16_000) -> None:
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)
