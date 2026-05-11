from __future__ import annotations

from pathlib import Path
import wave

import pytest

from core.pipelines.asr.vad import AudioVadError, read_wav_duration_seconds, run_silero_vad, segments_from_timestamps


def test_read_wav_duration_seconds(tmp_path: Path) -> None:
    wav_path = tmp_path / "one_second.wav"
    _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=1.0)

    assert read_wav_duration_seconds(wav_path) == 1.0


def test_segments_from_timestamps_clamps_and_drops_invalid_ranges() -> None:
    segments = segments_from_timestamps(
        [
            {"start": -1.0, "end": 0.5},
            {"start": 1.0, "end": 1.0},
            {"start": 1.5, "end": 3.0},
        ],
        audio_duration=2.0,
    )

    assert [(segment.start, segment.end, segment.duration) for segment in segments] == [
        (0.0, 0.5, 0.5),
        (1.5, 2.0, 0.5),
    ]


def test_run_silero_vad_rejects_non_normalized_wav_before_model_load(tmp_path: Path) -> None:
    wav_path = tmp_path / "stereo_8khz.wav"
    _write_silent_wav(wav_path, sample_rate=8_000, channels=2, seconds=0.5)

    with pytest.raises(AudioVadError, match="expects normalized"):
        run_silero_vad(wav_path)


def _write_silent_wav(path: Path, *, sample_rate: int, channels: int, seconds: float) -> None:
    frames = int(sample_rate * seconds)
    sample_width_bytes = 2
    silent_frame = b"\x00" * sample_width_bytes * channels

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frame * frames)
