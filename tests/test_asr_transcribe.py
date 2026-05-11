from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import wave

import pytest

from core.pipelines.asr.transcribe import AudioTranscribeError, build_transcribe_chunks, transcribe_vad_segments
from core.pipelines.asr.vad import VadSpeechSegment


@dataclass
class _FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    language: str | None = None


@dataclass
class _FakeInfo:
    language: str | None


class _FakeWhisperModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def transcribe(self, audio: str, **kwargs: Any) -> tuple[list[_FakeSegment], _FakeInfo]:
        self.calls.append({"audio": audio, **kwargs})
        return ([_FakeSegment(0.1, 0.6, " Merhaba dünya ", -0.2, 0.01)], _FakeInfo("tr"))


def test_transcribe_vad_segments_maps_offsets_and_forces_multilingual_true(tmp_path: Path) -> None:
    wav_path = tmp_path / "normalized.wav"
    _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=2.0)
    model = _FakeWhisperModel()

    result = transcribe_vad_segments(
        wav_path,
        [VadSpeechSegment(start=1.0, end=2.0, duration=1.0)],
        model=model,
        chunk_output_dir=tmp_path / "chunks",
    )

    assert len(model.calls) == 1
    assert model.calls[0]["multilingual"] is True
    assert model.calls[0]["vad_filter"] is False
    assert model.calls[0]["word_timestamps"] is False
    assert result.multilingual is True
    assert result.vad_segments_count == 1
    assert result.transcript == "Merhaba dünya"
    assert result.language_distribution == {"tr": 1}
    assert result.chunk_padding_seconds == 1.5
    assert [(segment.start, segment.end, segment.text, segment.source_vad_index) for segment in result.segments] == [
        (0.1, 0.6, "Merhaba dünya", 0)
    ]


def test_build_transcribe_chunks_adds_padding_without_crossing_neighbor_speech() -> None:
    chunks = build_transcribe_chunks(
        [
            VadSpeechSegment(start=6.2, end=7.6, duration=1.4),
            VadSpeechSegment(start=7.8, end=11.6, duration=3.8),
        ],
        audio_duration=20.0,
        padding_seconds=1.5,
    )

    assert [(chunk.chunk_segment.start, chunk.chunk_segment.end) for chunk in chunks] == [
        (4.7, 7.8),
        (7.6, 13.1),
    ]


def test_transcribe_vad_segments_empty_vad_returns_empty_without_model_call(tmp_path: Path) -> None:
    wav_path = tmp_path / "normalized.wav"
    _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=1.0)
    model = _FakeWhisperModel()

    result = transcribe_vad_segments(wav_path, [], model=model)

    assert model.calls == []
    assert result.segments == []
    assert result.transcript == ""
    assert result.language_distribution == {}


def test_transcribe_vad_segments_rejects_non_normalized_wav_before_model_call(tmp_path: Path) -> None:
    wav_path = tmp_path / "stereo_8khz.wav"
    _write_silent_wav(wav_path, sample_rate=8_000, channels=2, seconds=1.0)
    model = _FakeWhisperModel()

    with pytest.raises(AudioTranscribeError, match="expects normalized"):
        transcribe_vad_segments(wav_path, [VadSpeechSegment(start=0.0, end=1.0, duration=1.0)], model=model)

    assert model.calls == []


def _write_silent_wav(path: Path, *, sample_rate: int, channels: int, seconds: float) -> None:
    frames = int(sample_rate * seconds)
    sample_width_bytes = 2
    silent_frame = b"\x00" * sample_width_bytes * channels

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frame * frames)
