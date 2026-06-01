"""Tests for the content-profile dispatch layer (v0.1.x Paket 1)."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any
import wave

import pytest

from core.pipelines.asr import (
    CONTENT_PROFILES,
    ContentProfile,
    get_content_profile,
    list_content_profiles,
)
from core.pipelines.asr.pipeline import _resolve_profile_inputs, run_asr_pipeline
from core.pipelines.asr.quality import ResultSafetyDecision
from core.pipelines.asr.result import (
    ProductionTranscribeResult,
    TranscribeTiming,
    TranscriptSegment,
)


asr_pipeline = importlib.import_module("core.pipelines.asr.pipeline")


# ---------------------------------------------------------------------------
# Registry shape
# ---------------------------------------------------------------------------


class TestContentProfileRegistry:
    def test_all_content_profiles_registered(self) -> None:
        expected = {"bulten_haber", "studio_panel", "muzik_programi", "film", "belgesel", "spor"}
        assert set(CONTENT_PROFILES) == expected

    def test_list_returns_sorted_names(self) -> None:
        assert list_content_profiles() == sorted(CONTENT_PROFILES)

    @pytest.mark.parametrize(
        "name,model_profile,diarize",
        [
            ("bulten_haber", "fast_with_fallback", True),
            ("studio_panel", "fast_with_fallback", True),
            ("muzik_programi", "fast_with_fallback", True),
            ("film", "fast_with_fallback", False),
            ("belgesel", "quality", False),
            ("spor", "fast_with_fallback", False),
        ],
    )
    def test_profile_behavior_matrix(self, name: str, model_profile: str, diarize: bool) -> None:
        profile = get_content_profile(name)
        assert isinstance(profile, ContentProfile)
        assert profile.name == name
        assert profile.model_profile == model_profile
        assert profile.diarize is diarize

    def test_unknown_profile_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown content profile"):
            get_content_profile("unknown_profile")


# ---------------------------------------------------------------------------
# Resolution logic
# ---------------------------------------------------------------------------


class TestProfileResolution:
    def test_content_profile_drives_model_and_diarize(self) -> None:
        resolution = _resolve_profile_inputs(
            content_profile="bulten_haber",
            legacy_profile=None,
            model_profile_override=None,
            diarize_override=None,
        )
        assert resolution.content_profile_name == "bulten_haber"
        assert resolution.model_profile == "fast_with_fallback"
        assert resolution.diarize_intent is True
        assert resolution.metadata["model_profile_source"] == "content_profile"
        assert resolution.metadata["diarize_source"] == "content_profile"

    def test_model_profile_override_wins_over_content_profile(self) -> None:
        resolution = _resolve_profile_inputs(
            content_profile="belgesel",
            legacy_profile=None,
            model_profile_override="fast",
            diarize_override=None,
        )
        assert resolution.model_profile == "fast"
        assert resolution.metadata["model_profile_source"] == "model_profile_override"

    def test_diarize_override_wins_over_content_profile(self) -> None:
        resolution = _resolve_profile_inputs(
            content_profile="film",
            legacy_profile=None,
            model_profile_override=None,
            diarize_override=True,
        )
        assert resolution.diarize_intent is True
        assert resolution.metadata["diarize_source"] == "diarize_override"

    def test_legacy_profile_used_when_no_content_profile(self) -> None:
        resolution = _resolve_profile_inputs(
            content_profile=None,
            legacy_profile="quality",
            model_profile_override=None,
            diarize_override=None,
        )
        assert resolution.content_profile_name is None
        assert resolution.model_profile == "quality"
        assert resolution.diarize_intent is False
        assert resolution.metadata["model_profile_source"] == "legacy_profile"

    def test_default_model_profile_when_neither_given(self) -> None:
        resolution = _resolve_profile_inputs(
            content_profile=None,
            legacy_profile=None,
            model_profile_override=None,
            diarize_override=None,
        )
        assert resolution.model_profile == "fast_with_fallback"
        assert resolution.diarize_intent is False
        assert resolution.metadata["model_profile_source"] == "default"


# ---------------------------------------------------------------------------
# End-to-end via run_asr_pipeline
# ---------------------------------------------------------------------------


@dataclass
class _FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float = -0.2
    no_speech_prob: float = 0.01
    language: str | None = "tr"


def _fake_transcribe(audio_path: str | Path, **kwargs: Any) -> ProductionTranscribeResult:
    segment = TranscriptSegment(
        index=0,
        start=0.1,
        end=1.1,
        text="Sahte transcript",
        language="tr",
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        source_chunk_index=0,
    )
    return ProductionTranscribeResult(
        audio_path=Path(audio_path),
        audio_duration=2.0,
        profile_requested=kwargs["profile"],
        profile_used=kwargs["profile"] if kwargs["profile"] != "fast_with_fallback" else "fast",
        model_name="large-v3" if kwargs["profile"] == "quality" else "large-v3-turbo",
        fallback_triggered=False,
        fallback_reason=None,
        raw_segments=[segment],
        clean_segments=[segment],
        verbatim_transcript=segment.text,
        clean_transcript=segment.text,
        normalized_transcript=None,
        quality_drops=[],
        safety=ResultSafetyDecision(safe=True, failure_reason=None, diagnostics={"max_run": 1}),
        timing=TranscribeTiming(total_seconds=1.0, chunk_count=1, decode_seconds=0.6),
    )


def _silent_wav(path: Path, *, sample_rate: int = 16_000, seconds: float = 2.0) -> None:
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)


class TestPipelineDispatch:
    @pytest.mark.parametrize(
        "content_profile,expected_model_profile,expected_diarize",
        [
            ("bulten_haber", "fast_with_fallback", True),
            ("studio_panel", "fast_with_fallback", True),
            ("muzik_programi", "fast_with_fallback", True),
            ("film", "fast_with_fallback", False),
            ("belgesel", "quality", False),
            ("spor", "fast_with_fallback", False),
        ],
    )
    def test_each_content_profile_resolves_into_summary(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        content_profile: str,
        expected_model_profile: str,
        expected_diarize: bool,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)
        captured: list[dict[str, Any]] = []

        def fake_call(audio_path: Any, **kwargs: Any) -> ProductionTranscribeResult:
            captured.append(kwargs)
            return _fake_transcribe(audio_path, **kwargs)

        monkeypatch.setattr(asr_pipeline, "transcribe", fake_call)

        result = run_asr_pipeline(
            source,
            content_profile=content_profile,
            output_dir=tmp_path / f"asr_{content_profile}",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

        assert captured[0]["profile"] == expected_model_profile
        assert summary["content_profile"] == content_profile
        assert summary["profile_requested"] == expected_model_profile
        assert summary["diarize_intent"] is expected_diarize
        assert summary["diarize_required"] is False
        assert summary["content_profile_metadata"]["model_profile_source"] == "content_profile"

    def test_diarize_required_surfaced_in_summary(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)
        monkeypatch.setattr(asr_pipeline, "transcribe", _fake_transcribe)

        # Paket 2 wires real diarization on diarize-True profiles; stub it so this
        # Paket 1 test stays focused on summary surfacing.
        from core.pipelines.asr.diarize import DiarizationResult

        def fake_diarize(audio_path: Any) -> DiarizationResult:
            return DiarizationResult(
                audio_path=Path(audio_path),
                model_id="pyannote/fake",
                device="cpu",
                segments=[],
                speaker_count=0,
                speakers=[],
            )

        monkeypatch.setattr(asr_pipeline, "diarize_audio", fake_diarize)

        result = run_asr_pipeline(
            source,
            content_profile="bulten_haber",
            diarize_required=True,
            output_dir=tmp_path / "asr_strict",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
        assert summary["diarize_required"] is True

    def test_model_profile_override_threads_into_transcribe_call(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)
        captured: list[dict[str, Any]] = []

        def fake_call(audio_path: Any, **kwargs: Any) -> ProductionTranscribeResult:
            captured.append(kwargs)
            return _fake_transcribe(audio_path, **kwargs)

        monkeypatch.setattr(asr_pipeline, "transcribe", fake_call)

        # belgesel default = "quality"; override forces fast_with_fallback
        result = run_asr_pipeline(
            source,
            content_profile="belgesel",
            model_profile_override="fast_with_fallback",
            output_dir=tmp_path / "asr_belgesel_override",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

        assert captured[0]["profile"] == "fast_with_fallback"
        assert summary["profile_requested"] == "fast_with_fallback"
        assert summary["content_profile_metadata"]["model_profile_source"] == "model_profile_override"

    def test_legacy_profile_call_still_works(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Calling without `content_profile` must keep the old behavior intact."""
        source = tmp_path / "input.wav"
        _silent_wav(source)
        captured: list[dict[str, Any]] = []

        def fake_call(audio_path: Any, **kwargs: Any) -> ProductionTranscribeResult:
            captured.append(kwargs)
            return _fake_transcribe(audio_path, **kwargs)

        monkeypatch.setattr(asr_pipeline, "transcribe", fake_call)

        result = run_asr_pipeline(
            source,
            profile="fast_with_fallback",
            output_dir=tmp_path / "asr_legacy",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

        assert captured[0]["profile"] == "fast_with_fallback"
        assert summary["content_profile"] is None
        assert summary["profile_requested"] == "fast_with_fallback"
        assert summary["diarize_intent"] is False
        assert summary["content_profile_metadata"]["model_profile_source"] == "legacy_profile"
