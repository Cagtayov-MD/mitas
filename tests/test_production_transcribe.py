from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any
import wave

import pytest

from core.pipelines.asr import ProductionTranscribeResult, transcribe
from core.pipelines.asr.vad import VadSpeechSegment


asr_transcribe = importlib.import_module("core.pipelines.asr.transcribe")


@dataclass
class _FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float = -0.2
    no_speech_prob: float = 0.01
    language: str | None = "tr"


@dataclass
class _FakeInfo:
    language: str | None = "tr"


class _FakeModel:
    def __init__(self, segments: list[_FakeSegment], calls: list[dict[str, Any]]) -> None:
        self.segments = segments
        self.calls = calls

    def transcribe(self, audio: str, **kwargs: Any) -> tuple[list[_FakeSegment], _FakeInfo]:
        self.calls.append({"audio": audio, **kwargs})
        return self.segments, _FakeInfo("tr")


@pytest.fixture
def normalized_wav(tmp_path: Path) -> Path:
    wav_path = tmp_path / "fixture_16000hz_mono_s16.wav"
    _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=4.0)
    return wav_path


@pytest.fixture
def vad_segments() -> list[VadSpeechSegment]:
    return [VadSpeechSegment(start=0.5, end=2.5, duration=2.0)]


class TestProductionInterface:
    def test_quality_profile_basic(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[dict[str, Any]] = []

        def fake_load_model(config: Any) -> _FakeModel:
            assert config.name == "large-v3"
            return _FakeModel([_FakeSegment(0.1, 0.8, "Tüm hazırlıklar tamamlandı")], calls)

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(normalized_wav, profile="quality", vad_segments=vad_segments)

        assert isinstance(result, ProductionTranscribeResult)
        assert result.profile_used == "quality"
        assert result.model_name == "large-v3"
        assert not result.fallback_triggered
        assert len(result.clean_segments) == 1
        assert "İzlediğiniz için teşekkür ederim" not in result.clean_transcript
        assert calls[0]["initial_prompt"] is None
        # Karar 27 (2026-05-14): condition_on_previous_text=False default;
        # hallucination yayilimi engellemek + operasyonel scriptlerle uyum.
        assert calls[0]["condition_on_previous_text"] is False

    def test_fast_profile_drops_stock_artifacts(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_load_model(config: Any) -> _FakeModel:
            assert config.name == "large-v3-turbo"
            return _FakeModel(
                [
                    _FakeSegment(0.1, 0.5, "Altyazı M.K."),
                    _FakeSegment(0.6, 1.2, "Gerçek konuşma burada"),
                ],
                [],
            )

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(normalized_wav, profile="fast", vad_segments=vad_segments)

        assert result.model_name == "large-v3-turbo"
        assert "Altyazı M.K." not in result.clean_transcript
        assert "Abone olmayı" not in result.clean_transcript
        assert result.clean_transcript == "Gerçek konuşma burada"
        assert result.quality_drops[0].reason.startswith("stock_artifact")

    def test_fallback_triggered_on_repetition_drop(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_load_model(config: Any) -> _FakeModel:
            if config.name == "large-v3-turbo":
                return _FakeModel([_FakeSegment(0.1, 2.0, "ben " * 30)], [])
            return _FakeModel([_FakeSegment(0.1, 1.0, "Kaliteli fallback metni")], [])

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(normalized_wav, profile="fast_with_fallback", vad_segments=vad_segments)

        assert result.fallback_triggered
        assert result.model_name == "large-v3"
        assert result.profile_used == "quality"
        assert "repetition_collapse" in (result.fallback_reason or "")
        assert result.clean_transcript == "Kaliteli fallback metni"

    def test_tail_gap_triggers_fallback(
        self,
        normalized_wav: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_load_model(config: Any) -> _FakeModel:
            if config.name == "large-v3-turbo":
                return _FakeModel([_FakeSegment(0.1, 1.0, "Eksik turbo metni")], [])
            return _FakeModel([_FakeSegment(0.1, 3.8, "Tam kalite metni devam ediyor")], [])

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(
            normalized_wav,
            profile="fast_with_fallback",
            vad_segments=[VadSpeechSegment(start=0.0, end=4.0, duration=4.0)],
        )

        assert result.fallback_triggered
        assert result.model_name == "large-v3"
        assert result.profile_used == "quality"
        assert "tail_gap_uncovered" in (result.fallback_reason or "")
        assert result.selection_reason
        assert result.selection_reason.startswith("selected_quality:fast_unsafe")
        assert result.clean_transcript == "Tam kalite metni devam ediyor"

    def test_fallback_keeps_fast_when_quality_coverage_is_worse(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # 30s VAD window so the duration-aware tail-gap floor (audit HIGH-3)
        # keeps the quality result SAFE despite its shorter coverage, which is
        # what lets the coverage_worse selection branch fire. WAV must match
        # the VAD window because _map_production_segments clamps to chunk.end.
        wav_path = tmp_path / "fixture_long.wav"
        _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=30.0)

        def fake_load_model(config: Any) -> _FakeModel:
            if config.name == "large-v3-turbo":
                return _FakeModel(
                    [
                        _FakeSegment(0.1, 29.5, "Turbo tam metni burada koruyor"),
                        _FakeSegment(0.2, 0.4, "ben " * 30),
                    ],
                    [],
                )
            return _FakeModel([_FakeSegment(0.1, 27.0, "Daha kısa kalite metni burada")], [])

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(
            wav_path,
            profile="fast_with_fallback",
            vad_segments=[VadSpeechSegment(start=0.0, end=30.0, duration=30.0)],
        )

        assert result.fallback_triggered
        assert result.model_name == "large-v3-turbo"
        assert result.profile_used == "fast"
        assert "repetition_collapse" in (result.fallback_reason or "")
        assert result.selection_reason
        assert result.selection_reason.startswith("kept_fast:quality_coverage_worse")
        assert result.clean_transcript == "Turbo tam metni burada koruyor"

    def test_phase2_hooks_empty_but_present(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            asr_transcribe,
            "load_model",
            lambda config: _FakeModel([_FakeSegment(0.1, 0.8, "Merhaba dünya")], []),
        )

        result = transcribe(normalized_wav, profile="quality", vad_segments=vad_segments)

        assert result.normalized_transcript is None
        assert result.speaker_segments == []
        assert result.normalized_entities == []
        assert result.clean_segments[0].speaker_id is None
        assert result.clean_segments[0].normalized_text is None

    def test_archive_dict_serializable(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            asr_transcribe,
            "load_model",
            lambda config: _FakeModel([_FakeSegment(0.1, 0.8, "Arşiv metni")], []),
        )

        result = transcribe(normalized_wav, profile="quality", vad_segments=vad_segments)
        archive = result.to_archive_dict()

        json.dumps(archive)
        assert "transcript" in archive
        assert "verbatim" in archive["transcript"]
        assert archive["transcript"]["normalized"] is None


def _write_silent_wav(path: Path, *, sample_rate: int, channels: int, seconds: float) -> None:
    frames = int(sample_rate * seconds)
    sample_width_bytes = 2
    silent_frame = b"\x00" * sample_width_bytes * channels

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frame * frames)
