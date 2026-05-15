from __future__ import annotations

from pathlib import Path
import json
import math
import wave

import pytest

from core.pipelines.asr.normalize import AudioNormalizeError
from core.pipelines.asr.pipeline import run_asr_pipeline
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

    review = result.transcript_review_path.read_text(encoding="utf-8")
    assert "Tüm hazırlıklar tamamlandı" in review
    assert "Clean Transcript" in review
    assert "Verbatim Transcript" in review


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

    result = run_asr_pipeline(source, channel_mode="auto", output_dir=tmp_path / "asr_auto_mono")
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

    result = run_asr_pipeline(source, channel_mode="auto", output_dir=tmp_path / "asr_auto_split")
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

    assert summary["channels"]["requested_mode"] == "auto"
    assert summary["channels"]["mode"] == "split"
    assert summary["channels"]["auto_decided"] is True
    assert summary["channels"]["lr_correlation"] <= 0.92


def test_run_asr_pipeline_split_on_mono_input_raises_normalize_error(tmp_path) -> None:
    source = tmp_path / "mono.wav"
    _write_silent_wav(source, sample_rate=16_000, channels=1, seconds=1.0)

    with pytest.raises(AudioNormalizeError):
        run_asr_pipeline(source, channel_mode="split", output_dir=tmp_path / "asr_bad_split")


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
