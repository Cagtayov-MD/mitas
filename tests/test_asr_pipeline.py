from __future__ import annotations

from pathlib import Path
import json
import math
import wave

import pytest

from core.pipelines.asr.normalize import AudioNormalizeError
from core.pipelines.asr.language_intelligence import LanguageIntelligenceConfig, LanguageIntelligenceResult
from core.pipelines.asr.channel_analysis import StereoRedundancyAnalysis
from core.pipelines.asr.pipeline import DEFAULT_ASR_RUNS_DIR, run_asr_pipeline
from core.pipelines.asr.quality import ResultSafetyDecision
from core.pipelines.asr.result import ProductionTranscribeResult, TranscriptSegment, TranscribeTiming
from core.schemas import ModuleRun


def test_run_asr_pipeline_writes_standard_artifacts(tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.wav"
    _write_silent_wav(source, sample_rate=16_000, channels=1, seconds=2.0)

    def fake_transcribe(audio_path, **kwargs):
        segment = TranscriptSegment(
            index=0,
            start=0.1,
            end=1.1,
            text="Tüm hazırlıklar tamamlandı",
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
            timing=TranscribeTiming(total_seconds=1.25, chunk_count=1, decode_seconds=0.75),
        )

    monkeypatch.setattr("core.pipelines.asr.pipeline.transcribe", fake_transcribe)

    result = run_asr_pipeline(
        source,
        profile="fast_with_fallback",
        output_dir=tmp_path / "asr_run",
        media_id="media-1",
        job_id="job-1",
        module_run_id="module-1",
        word_alignment_mode="interpolated",
    )

    assert result.archive_path.exists()
    assert result.module_run_path.exists()
    assert result.summary_path.exists()
    assert result.transcript_review_path.exists()
    assert result.normalized_audio_path.exists()

    module_run = ModuleRun.model_validate(json.loads(result.module_run_path.read_text(encoding="utf-8")))
    archive = json.loads(result.archive_path.read_text(encoding="utf-8"))
    assert module_run.status == "done"
    assert module_run.module_name == "asr"
    assert module_run.output_summary["clean_words"] == 3
    assert module_run.output_summary["outputs"]["transcript_review"] == "transcript_review.md"
    assert archive["segments"][0]["avg_logprob"] == -0.2
    assert archive["segments"][0]["no_speech_prob"] == 0.01
    assert archive["segments"][0]["source_chunk_index"] == 0
    assert archive["segments"][0]["word_timestamps"] == [
        {"word": "Tüm", "start": 0.1, "end": 0.433, "source": "segment_interpolated"},
        {"word": "hazırlıklar", "start": 0.433, "end": 0.767, "source": "segment_interpolated"},
        {"word": "tamamlandı", "start": 0.767, "end": 1.1, "source": "segment_interpolated"},
    ]

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    coverage = summary["quality_report"]["word_timestamp_coverage"]
    assert coverage["status"] == "ok"
    assert coverage["method"] == "segment_interpolated"
    assert coverage["value"] == 1.0
    assert coverage["aligned_words"] == 3
    assert coverage["expected_words"] == 3
    assert summary["quality_report"]["alignment_success"]["value"] is True

    timeline = json.loads(result.timeline_events_path.read_text(encoding="utf-8"))
    assert timeline["events"][0]["payload"]["word_timestamps"] == archive["segments"][0]["word_timestamps"]

    review = result.transcript_review_path.read_text(encoding="utf-8")
    assert "Tüm hazırlıklar tamamlandı" in review
    assert "Clean Transcript" in review
    assert "Verbatim Transcript" in review


def test_run_asr_pipeline_threads_language_intelligence_shadow_artifacts(tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.wav"
    _write_silent_wav(source, sample_rate=16_000, channels=1, seconds=2.0)

    monkeypatch.setattr("core.pipelines.asr.pipeline.transcribe", _fake_channel_transcribe)

    def fake_language_intelligence(audio_path, **kwargs):
        cfg = LanguageIntelligenceConfig(mode="shadow")
        return LanguageIntelligenceResult(
            enabled=True,
            mode="shadow",
            status="ok",
            model_name="fake-lid",
            model_source="test",
            pilot_languages=cfg.pilot_languages,
            unsupported_asr_languages=cfg.unsupported_asr_languages,
            timeline_granularity="vad_region_min_3s",
            min_region_seconds=3.0,
            max_windows=20,
            max_sample_seconds=90.0,
            runtime_budget_seconds=15.0,
            runtime_sec=0.25,
            audio_duration=2.0,
            vad_segment_count=1,
            eligible_vad_segment_count=1,
            sampled_speech_seconds=6.0,
            master_language="ar",
            master_raw_score=0.88,
            language_distribution={"ar": 1.0},
            decision_reason="dominant_language",
            pilot_language=True,
            notes=("ASR routing is disabled; transcription output was not changed.",),
        )

    monkeypatch.setattr("core.pipelines.asr.pipeline.run_language_intelligence", fake_language_intelligence)

    result = run_asr_pipeline(
        source,
        profile="fast",
        output_dir=tmp_path / "asr_lid",
        word_alignment_mode="interpolated",
        language_intelligence_mode="shadow",
    )

    archive = json.loads(result.archive_path.read_text(encoding="utf-8"))
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

    assert summary["language_intelligence"]["mode"] == "shadow"
    assert summary["language_intelligence"]["master_language"] == "ar"
    assert summary["language_intelligence"]["routing"]["applied"] is False
    assert archive["language_intelligence"]["master_raw_score"] == 0.88
    assert result.module_run.output_summary["language_intelligence"]["status"] == "ok"


def test_default_asr_runs_dir_is_grouped_under_outputs_runs_asr() -> None:
    assert DEFAULT_ASR_RUNS_DIR.parts[-3:] == ("outputs", "runs", "asr")


def test_run_asr_pipeline_split_threads_channel_fields_through_artifacts(tmp_path, monkeypatch) -> None:
    source = tmp_path / "stereo.wav"
    _write_stereo_wav(source, same=False)

    monkeypatch.setattr("core.pipelines.asr.pipeline.transcribe", _fake_channel_transcribe)

    result = run_asr_pipeline(
        source,
        channel_mode="split",
        output_dir=tmp_path / "asr_split",
        media_id="media-split",
        job_id="job-split",
        module_run_id="module-split",
        word_alignment_mode="interpolated",
    )

    archive = json.loads(result.archive_path.read_text(encoding="utf-8"))
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

    assert archive["channels"]["mode"] == "split"
    assert summary["channels"]["mode"] == "split"
    assert {segment["channel"] for segment in archive["segments"]} == {"L", "R"}
    assert (result.output_dir / "normalized_L.wav").exists()
    assert (result.output_dir / "normalized_R.wav").exists()


def test_run_asr_pipeline_auto_high_correlation_chooses_mono(tmp_path, monkeypatch) -> None:
    source = tmp_path / "same.wav"
    _write_stereo_wav(source, same=True)
    calls: list[Path] = []

    def fake_transcribe(audio_path, **kwargs):
        calls.append(Path(audio_path))
        return _fake_channel_transcribe(audio_path, **kwargs)

    monkeypatch.setattr("core.pipelines.asr.pipeline.transcribe", fake_transcribe)

    result = run_asr_pipeline(source, channel_mode="auto", output_dir=tmp_path / "asr_auto_mono", word_alignment_mode="interpolated")
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    archive = json.loads(result.archive_path.read_text(encoding="utf-8"))

    assert len(calls) == 1
    assert summary["channels"]["requested_mode"] == "auto"
    assert summary["channels"]["mode"] == "mono"
    assert summary["channels"]["auto_decided"] is True
    assert archive["channels"]["mode"] == "mono"


def test_run_asr_pipeline_auto_low_correlation_chooses_split(tmp_path, monkeypatch) -> None:
    source = tmp_path / "different.wav"
    _write_stereo_wav(source, same=False)
    monkeypatch.setattr("core.pipelines.asr.pipeline.transcribe", _fake_channel_transcribe)

    result = run_asr_pipeline(source, channel_mode="auto", output_dir=tmp_path / "asr_auto_split", word_alignment_mode="interpolated")
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

    assert summary["channels"]["requested_mode"] == "auto"
    assert summary["channels"]["mode"] == "split"
    assert summary["channels"]["auto_decided"] is True
    assert summary["channels"]["lr_correlation"] <= 0.92


def test_run_asr_pipeline_auto_redundancy_analysis_revises_split_to_mono(tmp_path, monkeypatch) -> None:
    source = tmp_path / "football_broadcast.wav"
    _write_stereo_wav(source, same=False)
    calls: list[Path] = []

    def fake_transcribe(audio_path, **kwargs):
        calls.append(Path(audio_path))
        return _fake_channel_transcribe(audio_path, **kwargs)

    def fake_redundancy(left_wav, right_wav):
        return StereoRedundancyAnalysis(
            speech_windows_sampled=20,
            speech_windows_used=12,
            pearson_min=0.96,
            pearson_p10=0.98,
            pearson_median=0.99,
            pearson_max=1.0,
            midside_db_median=-28.0,
            is_redundant_stereo=True,
            redundancy_confidence="high",
        )

    monkeypatch.setattr("core.pipelines.asr.pipeline.transcribe", fake_transcribe)
    monkeypatch.setattr("core.pipelines.asr.pipeline.analyze_stereo_redundancy", fake_redundancy)

    result = run_asr_pipeline(
        source,
        channel_mode="auto",
        output_dir=tmp_path / "asr_auto_redundant_mono",
        word_alignment_mode="interpolated",
    )
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    archive = json.loads(result.archive_path.read_text(encoding="utf-8"))

    assert len(calls) == 1
    assert calls[0].name == "normalized.wav"
    assert summary["channels"]["requested_mode"] == "auto"
    assert summary["channels"]["mode"] == "mono"
    assert summary["channels"]["channel_decision_override"] == "auto_mono_after_redundant_stereo_analysis"
    assert summary["channels"]["tracks"] == []
    assert archive["channels"]["mode"] == "mono"


def test_run_asr_pipeline_split_on_mono_input_raises_normalize_error(tmp_path) -> None:
    source = tmp_path / "mono.wav"
    _write_silent_wav(source, sample_rate=16_000, channels=1, seconds=1.0)

    with pytest.raises(AudioNormalizeError):
        run_asr_pipeline(source, channel_mode="split", output_dir=tmp_path / "asr_bad_split", word_alignment_mode="interpolated")


def _fake_channel_transcribe(audio_path, **kwargs):
    audio = Path(audio_path)
    channel = "R" if audio.name.endswith("_R.wav") else "L" if audio.name.endswith("_L.wav") else None
    text = "sağ kanal farklı konuşma burada" if channel == "R" else "sol kanal haber metni burada"
    segment = TranscriptSegment(
        index=0,
        start=0.1,
        end=1.1,
        text=text,
        language="tr",
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        source_chunk_index=0,
    )
    return ProductionTranscribeResult(
        audio_path=audio,
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
        timing=TranscribeTiming(total_seconds=1.25, chunk_count=1, decode_seconds=0.75),
    )


def _write_silent_wav(path: Path, *, sample_rate: int, channels: int, seconds: float) -> None:
    frames = int(sample_rate * seconds)
    sample_width_bytes = 2
    silent_frame = b"\x00" * sample_width_bytes * channels

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frame * frames)


def _write_stereo_wav(path: Path, *, same: bool, seconds: float = 2.0, sample_rate: int = 16_000) -> None:
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        payload = bytearray()
        for index in range(frames):
            left = int(10000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            right_freq = 440 if same else 880
            right = int(10000 * math.sin(2 * math.pi * right_freq * index / sample_rate))
            payload.extend(left.to_bytes(2, "little", signed=True))
            payload.extend(right.to_bytes(2, "little", signed=True))
        wav_file.writeframes(bytes(payload))
