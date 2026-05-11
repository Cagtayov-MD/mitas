from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import wave

import pytest

from core.pipelines.asr.diarize import (
    AudioDiarizeError,
    _patched_pyannote_get_plda,
    diarize_audio,
    segments_from_pyannote_output,
)


@dataclass
class _FakeTurn:
    start: float
    end: float


class _FakeAnnotation:
    def itertracks(self, *, yield_label: bool):
        assert yield_label is True
        yield _FakeTurn(3.0, 5.5), None, "SPEAKER_01"
        yield _FakeTurn(0.5, 2.0), None, "SPEAKER_00"
        yield _FakeTurn(4.0, 4.0), None, "SPEAKER_02"


class _FakePipeline:
    def __init__(self, output) -> None:
        self.output = output
        self.calls = []

    def __call__(self, payload):
        self.calls.append(payload)
        return self.output


class _FakeWaveform:
    def unsqueeze(self, dim: int):
        assert dim == 0
        return "fake-waveform"


def test_segments_from_pyannote_output_sorts_and_drops_empty_ranges() -> None:
    segments = segments_from_pyannote_output(_FakeAnnotation())

    assert [(segment.start, segment.end, segment.duration, segment.speaker_id) for segment in segments] == [
        (0.5, 2.0, 1.5, "SPEAKER_00"),
        (3.0, 5.5, 2.5, "SPEAKER_01"),
    ]


def test_diarize_audio_rejects_non_normalized_wav_before_pipeline_call(tmp_path: Path) -> None:
    wav_path = tmp_path / "stereo_8khz.wav"
    _write_silent_wav(wav_path, sample_rate=8_000, channels=2, seconds=1.0)
    pipeline = _FakePipeline(_FakeAnnotation())

    with pytest.raises(AudioDiarizeError, match="expects normalized"):
        diarize_audio(wav_path, pipeline=pipeline)

    assert pipeline.calls == []


def test_diarize_audio_accepts_normalized_wav_with_fake_pipeline(tmp_path: Path) -> None:
    wav_path = tmp_path / "normalized.wav"
    _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=1.0)
    pipeline = _FakePipeline(_FakeAnnotation())

    result = diarize_audio(wav_path, pipeline=pipeline, waveform_loader=lambda _: _FakeWaveform())

    assert len(pipeline.calls) == 1
    assert pipeline.calls[0]["sample_rate"] == 16_000
    assert pipeline.calls[0]["waveform"] == "fake-waveform"
    assert result.speaker_count == 2
    assert result.speakers == ["SPEAKER_00", "SPEAKER_01"]
    assert len(result.segments) == 2


def test_pyannote_get_plda_patch_is_restored_after_loading_scope() -> None:
    def original_get_plda():
        return "original"

    module = SimpleNamespace(get_plda=original_get_plda)

    with pytest.raises(RuntimeError, match="forced"):
        with _patched_pyannote_get_plda(module):
            assert module.get_plda() is None
            raise RuntimeError("forced")

    assert module.get_plda is original_get_plda
    assert module.get_plda() == "original"


def _write_silent_wav(path: Path, *, sample_rate: int, channels: int, seconds: float) -> None:
    frames = int(sample_rate * seconds)
    sample_width_bytes = 2
    silent_frame = b"\x00" * sample_width_bytes * channels

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frame * frames)
