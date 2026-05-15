from __future__ import annotations

import math
from pathlib import Path
import shutil
import wave

import pytest

from core.pipelines.asr.channel_analysis import decide_channel_mode, measure_lr_correlation
from core.pipelines.asr.normalize import AudioStreamInfo


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg is required for channel analysis tests",
)


def test_identical_lr_has_high_correlation_and_auto_mono(tmp_path: Path) -> None:
    source = tmp_path / "identical.wav"
    _write_stereo_sine(source, same=True)

    corr = measure_lr_correlation(source, ffmpeg_executable="ffmpeg")
    decision = decide_channel_mode(
        source,
        requested_mode="auto",
        input_stream=_stream(source, channels=2),
        ffmpeg_executable="ffmpeg",
    )

    assert corr > 0.99
    assert decision.effective_mode == "mono"
    assert decision.auto_decided is True


def test_different_lr_has_low_correlation_and_auto_split(tmp_path: Path) -> None:
    source = tmp_path / "different.wav"
    _write_stereo_sine(source, same=False)

    corr = measure_lr_correlation(source, ffmpeg_executable="ffmpeg")
    decision = decide_channel_mode(
        source,
        requested_mode="auto",
        input_stream=_stream(source, channels=2),
        ffmpeg_executable="ffmpeg",
    )

    assert corr <= 0.92
    assert decision.effective_mode == "split"


def test_mono_input_auto_decides_mono_without_correlation(tmp_path: Path) -> None:
    source = tmp_path / "mono.wav"
    _write_mono_sine(source)

    decision = decide_channel_mode(
        source,
        requested_mode="auto",
        input_stream=_stream(source, channels=1),
        ffmpeg_executable="ffmpeg",
    )

    assert decision.effective_mode == "mono"
    assert decision.lr_correlation is None


def _stream(path: Path, *, channels: int) -> AudioStreamInfo:
    return AudioStreamInfo(path=path, codec_name="pcm_s16le", sample_rate=16_000, channels=channels, sample_fmt="s16")


def _write_stereo_sine(path: Path, *, same: bool, seconds: float = 1.0, sample_rate: int = 16_000) -> None:
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        payload = bytearray()
        for index in range(frames):
            left = int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            right_freq = 440 if same else 880
            right = int(12000 * math.sin(2 * math.pi * right_freq * index / sample_rate))
            payload.extend(left.to_bytes(2, "little", signed=True))
            payload.extend(right.to_bytes(2, "little", signed=True))
        wav_file.writeframes(bytes(payload))


def _write_mono_sine(path: Path, *, seconds: float = 1.0, sample_rate: int = 16_000) -> None:
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        payload = bytearray()
        for index in range(frames):
            sample = int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            payload.extend(sample.to_bytes(2, "little", signed=True))
        wav_file.writeframes(bytes(payload))
