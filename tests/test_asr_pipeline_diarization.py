"""Pipeline-level diarization wiring tests (v0.1.x Paket 2)."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any
import wave

import pytest

from core.pipelines.asr.diarize import (
    AudioDiarizeError,
    DiarizationResult,
    DiarizationSegment,
)
from core.pipelines.asr.pipeline import run_asr_pipeline
from core.pipelines.asr.quality import ResultSafetyDecision
from core.pipelines.asr.result import (
    ProductionTranscribeResult,
    TranscribeTiming,
    TranscriptSegment,
)


asr_pipeline = importlib.import_module("core.pipelines.asr.pipeline")


def _silent_wav(path: Path, *, sample_rate: int = 16_000, seconds: float = 2.0) -> None:
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)


def _fake_transcribe_two_segments(audio_path: Any, **kwargs: Any) -> ProductionTranscribeResult:
    """Two segments at clearly separated time windows for diarization tests."""
    seg_a = TranscriptSegment(
        index=0,
        start=0.1,
        end=1.0,
        text="ilk konusmaci metni",
        language="tr",
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        source_chunk_index=0,
    )
    seg_b = TranscriptSegment(
        index=1,
        start=1.1,
        end=2.0,
        text="ikinci konusmaci metni",
        language="tr",
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        source_chunk_index=0,
    )
    return ProductionTranscribeResult(
        audio_path=Path(audio_path),
        audio_duration=2.0,
        profile_requested=kwargs["profile"],
        profile_used="fast",
        model_name="large-v3-turbo",
        fallback_triggered=False,
        fallback_reason=None,
        raw_segments=[seg_a, seg_b],
        clean_segments=[seg_a, seg_b],
        verbatim_transcript=f"{seg_a.text} {seg_b.text}",
        clean_transcript=f"{seg_a.text} {seg_b.text}",
        normalized_transcript=None,
        quality_drops=[],
        safety=ResultSafetyDecision(safe=True, failure_reason=None, diagnostics={"max_run": 1}),
        timing=TranscribeTiming(total_seconds=1.0, chunk_count=1, decode_seconds=0.6),
    )


def _diarization_two_speakers(audio_path: Any) -> DiarizationResult:
    return DiarizationResult(
        audio_path=Path(audio_path),
        model_id="pyannote/fake-3.1",
        device="cpu",
        segments=[
            DiarizationSegment(start=0.0, end=1.0, duration=1.0, speaker_id="SPEAKER_00"),
            DiarizationSegment(start=1.0, end=2.0, duration=1.0, speaker_id="SPEAKER_01"),
        ],
        speaker_count=2,
        speakers=["SPEAKER_00", "SPEAKER_01"],
    )


class TestDiarizationDispatch:
    def test_bulten_haber_runs_diarization_and_fills_speakers(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)
        monkeypatch.setattr(asr_pipeline, "transcribe", _fake_transcribe_two_segments)
        monkeypatch.setattr(asr_pipeline, "diarize_audio", _diarization_two_speakers)

        result = run_asr_pipeline(
            source,
            content_profile="bulten_haber",
            output_dir=tmp_path / "asr_bulten",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

        diarization = summary["quality_report"]["diarization"]
        assert diarization["status"] == "ok"
        assert diarization["speaker_count"] == 2
        assert diarization["speakers"] == ["SPEAKER_00", "SPEAKER_01"]
        assert diarization["low_confidence_segments"] == 0
        speaker_word = summary["quality_report"]["speaker_word_timeline"]
        assert speaker_word["status"] == "ok"
        assert speaker_word["speaker_word_segments"] == 2
        assert speaker_word["speaker_timed_words"] > 0

        archive = json.loads(result.archive_path.read_text(encoding="utf-8"))
        speakers = [segment["speaker"] for segment in archive["segments"]]
        assert speakers == ["SPEAKER_00", "SPEAKER_01"]
        assert summary["safety"]["safe"] is True

    @pytest.mark.parametrize("content_profile", ["film", "belgesel"])
    def test_diarization_skipped_for_film_and_belgesel(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        content_profile: str,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)
        calls: list[Any] = []

        def diarize_should_not_run(audio_path: Any) -> DiarizationResult:
            calls.append(audio_path)
            raise AssertionError("diarize_audio must not run for this profile")

        monkeypatch.setattr(asr_pipeline, "transcribe", _fake_transcribe_two_segments)
        monkeypatch.setattr(asr_pipeline, "diarize_audio", diarize_should_not_run)

        result = run_asr_pipeline(
            source,
            content_profile=content_profile,
            output_dir=tmp_path / f"asr_{content_profile}",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

        assert calls == []
        assert summary["quality_report"]["diarization"]["status"] == "skipped"
        assert summary["quality_report"]["diarization"]["reason"] == "diarize_intent_false"

    def test_diarize_override_true_forces_diarization_on_film(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)
        captured: list[Any] = []

        def diarize_record(audio_path: Any) -> DiarizationResult:
            captured.append(audio_path)
            return _diarization_two_speakers(audio_path)

        monkeypatch.setattr(asr_pipeline, "transcribe", _fake_transcribe_two_segments)
        monkeypatch.setattr(asr_pipeline, "diarize_audio", diarize_record)

        result = run_asr_pipeline(
            source,
            content_profile="film",
            diarize_override=True,
            output_dir=tmp_path / "asr_film_override",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

        assert len(captured) == 1
        assert summary["quality_report"]["diarization"]["status"] == "ok"
        assert summary["diarize_intent"] is True
        assert summary["content_profile_metadata"]["diarize_source"] == "diarize_override"

    def test_legacy_call_marks_diarization_not_applicable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)

        def diarize_should_not_run(audio_path: Any) -> DiarizationResult:
            raise AssertionError("diarize_audio must not run for legacy call")

        monkeypatch.setattr(asr_pipeline, "transcribe", _fake_transcribe_two_segments)
        monkeypatch.setattr(asr_pipeline, "diarize_audio", diarize_should_not_run)

        result = run_asr_pipeline(
            source,
            profile="fast_with_fallback",
            output_dir=tmp_path / "asr_legacy",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

        diarization = summary["quality_report"]["diarization"]
        assert diarization["status"] == "not_applicable"
        assert diarization["reason"] == "legacy_call"


class TestDiarizationFailure:
    def test_graceful_failure_marks_partial_and_keeps_transcript(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)

        def diarize_explodes(audio_path: Any) -> DiarizationResult:
            raise AudioDiarizeError("simulated pyannote crash")

        monkeypatch.setattr(asr_pipeline, "transcribe", _fake_transcribe_two_segments)
        monkeypatch.setattr(asr_pipeline, "diarize_audio", diarize_explodes)

        result = run_asr_pipeline(
            source,
            content_profile="bulten_haber",
            diarize_required=False,
            output_dir=tmp_path / "asr_bulten_fail",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
        module_run = json.loads(result.module_run_path.read_text(encoding="utf-8"))

        diarization = summary["quality_report"]["diarization"]
        assert diarization["status"] == "failed"
        assert "simulated pyannote crash" in diarization["error"]
        assert module_run["status"] == "partial"
        assert "diarization_failed" in (module_run["error_msg"] or "")

        # Transcript itself is intact; just no speaker labels.
        archive = json.loads(result.archive_path.read_text(encoding="utf-8"))
        assert len(archive["segments"]) == 2
        assert all(segment["speaker"] is None for segment in archive["segments"])

    def test_strict_mode_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)

        def diarize_explodes(audio_path: Any) -> DiarizationResult:
            raise AudioDiarizeError("simulated pyannote crash")

        monkeypatch.setattr(asr_pipeline, "transcribe", _fake_transcribe_two_segments)
        monkeypatch.setattr(asr_pipeline, "diarize_audio", diarize_explodes)

        from core.pipelines.asr.transcribe import AsrPipelineError

        with pytest.raises(AsrPipelineError):
            run_asr_pipeline(
                source,
                content_profile="bulten_haber",
                diarize_required=True,
                output_dir=tmp_path / "asr_bulten_strict",
                word_alignment_mode="interpolated",
            )


class TestDiarizationDegraded:
    def test_majority_low_confidence_marks_degraded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "input.wav"
        _silent_wav(source)

        def diarize_too_short(audio_path: Any) -> DiarizationResult:
            # Both transcript segments span ~0.9s; this turn only covers 0.1s of the
            # first one. Overlap ratios are well below the 0.5 default.
            return DiarizationResult(
                audio_path=Path(audio_path),
                model_id="pyannote/fake",
                device="cpu",
                segments=[DiarizationSegment(start=0.0, end=0.2, duration=0.2, speaker_id="SPEAKER_00")],
                speaker_count=1,
                speakers=["SPEAKER_00"],
            )

        monkeypatch.setattr(asr_pipeline, "transcribe", _fake_transcribe_two_segments)
        monkeypatch.setattr(asr_pipeline, "diarize_audio", diarize_too_short)

        result = run_asr_pipeline(
            source,
            content_profile="bulten_haber",
            output_dir=tmp_path / "asr_bulten_degraded",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

        diarization = summary["quality_report"]["diarization"]
        assert diarization["status"] == "degraded"
        assert diarization["low_confidence_segments"] == 2
        # Both segments end up with speaker_id=None despite diarization having run.
        archive = json.loads(result.archive_path.read_text(encoding="utf-8"))
        assert all(segment["speaker"] is None for segment in archive["segments"])


class TestSplitChannelDiarization:
    def test_split_channel_with_diarize_profile_uses_mono_mix_for_speakers(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import math

        source = tmp_path / "stereo.wav"
        sample_rate = 16_000
        seconds = 2.0
        frames = int(sample_rate * seconds)
        with wave.open(str(source), "wb") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            payload = bytearray()
            for index in range(frames):
                left = int(10000 * math.sin(2 * math.pi * 440 * index / sample_rate))
                right = int(10000 * math.sin(2 * math.pi * 880 * index / sample_rate))
                payload.extend(left.to_bytes(2, "little", signed=True))
                payload.extend(right.to_bytes(2, "little", signed=True))
            wav_file.writeframes(bytes(payload))

        diarize_calls: list[Path] = []

        def diarize_record(audio_path: Any) -> DiarizationResult:
            diarize_calls.append(Path(audio_path))
            return DiarizationResult(
                audio_path=Path(audio_path),
                model_id="pyannote/fake",
                device="cpu",
                segments=[DiarizationSegment(start=0.0, end=1.2, duration=1.2, speaker_id="SPEAKER_00")],
                speaker_count=1,
                speakers=["SPEAKER_00"],
            )

        def fake_channel_transcribe(audio_path: Any, **kwargs: Any) -> ProductionTranscribeResult:
            channel = "R" if str(audio_path).endswith("_R.wav") else "L"
            segment = TranscriptSegment(
                index=0,
                start=0.1,
                end=1.0,
                text=f"{channel} kanal",
                language="tr",
                avg_logprob=-0.2,
                no_speech_prob=0.01,
                source_chunk_index=0,
            )
            return ProductionTranscribeResult(
                audio_path=Path(audio_path),
                audio_duration=2.0,
                profile_requested=kwargs["profile"],
                profile_used="fast",
                model_name="large-v3-turbo",
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

        monkeypatch.setattr(asr_pipeline, "transcribe", fake_channel_transcribe)
        monkeypatch.setattr(asr_pipeline, "diarize_audio", diarize_record)

        result = run_asr_pipeline(
            source,
            content_profile="studio_panel",
            channel_mode="split",
            output_dir=tmp_path / "asr_split_panel",
            word_alignment_mode="interpolated",
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

        diarization = summary["quality_report"]["diarization"]
        assert diarization["status"] == "ok"
        assert diarization["speaker_count"] == 1
        assert diarize_calls and diarize_calls[0].name == "normalized.wav"
        archive = json.loads(result.archive_path.read_text(encoding="utf-8"))
        assert {segment["channel"] for segment in archive["segments"]} == {"L", "R"}
        assert all(segment["speaker"] == "SPEAKER_00" for segment in archive["segments"])
