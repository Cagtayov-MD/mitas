from __future__ import annotations

import math
from pathlib import Path
import wave

import pytest

from core.pipelines.asr.channel_analysis import analyze_stereo_redundancy


def _write_mono_sine(path: Path, *, freq: float = 440.0, amplitude: int = 12000, seconds: float = 6.0, sample_rate: int = 16_000) -> None:
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        payload = bytearray()
        for i in range(frames):
            s = int(amplitude * math.sin(2 * math.pi * freq * i / sample_rate))
            payload.extend(s.to_bytes(2, "little", signed=True))
        wf.writeframes(bytes(payload))


def _write_mono_silence(path: Path, *, seconds: float = 6.0, sample_rate: int = 16_000) -> None:
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * frames)


def test_identical_channels_detected_as_redundant(tmp_path: Path) -> None:
    left = tmp_path / "L.wav"
    right = tmp_path / "R.wav"
    _write_mono_sine(left)
    _write_mono_sine(right)

    result = analyze_stereo_redundancy(left, right)

    assert result.is_redundant_stereo is True
    assert result.pearson_median is not None
    assert result.pearson_median > 0.99
    assert result.midside_db_median is not None
    assert result.midside_db_median < -40.0
    assert result.redundancy_confidence in ("high", "medium")


def test_independent_channels_not_redundant(tmp_path: Path) -> None:
    left = tmp_path / "L.wav"
    right = tmp_path / "R.wav"
    _write_mono_sine(left, freq=440.0)
    _write_mono_sine(right, freq=880.0)

    result = analyze_stereo_redundancy(left, right)

    assert result.is_redundant_stereo is False
    assert result.pearson_median is not None
    assert result.pearson_median < 0.5


def test_silent_channels_return_insufficient_data(tmp_path: Path) -> None:
    left = tmp_path / "L.wav"
    right = tmp_path / "R.wav"
    _write_mono_silence(left)
    _write_mono_silence(right)

    result = analyze_stereo_redundancy(left, right)

    assert result.speech_windows_used == 0
    assert result.is_redundant_stereo is False
    assert result.redundancy_confidence == "insufficient_data"


def test_small_level_difference_still_redundant(tmp_path: Path) -> None:
    """Two mics on same source with slightly different gain — still redundant."""
    left = tmp_path / "L.wav"
    right = tmp_path / "R.wav"
    _write_mono_sine(left, amplitude=12000)
    _write_mono_sine(right, amplitude=8000)

    result = analyze_stereo_redundancy(left, right)

    assert result.is_redundant_stereo is True
    assert result.pearson_median is not None
    assert result.pearson_median > 0.99


def test_to_dict_serializable(tmp_path: Path) -> None:
    left = tmp_path / "L.wav"
    right = tmp_path / "R.wav"
    _write_mono_sine(left)
    _write_mono_sine(right)

    result = analyze_stereo_redundancy(left, right)
    d = result.to_dict()

    assert isinstance(d, dict)
    assert "pearson_median" in d
    assert "is_redundant_stereo" in d
    assert "redundancy_confidence" in d
    import json
    json.dumps(d)
