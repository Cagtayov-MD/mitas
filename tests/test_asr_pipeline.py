from __future__ import annotations

from pathlib import Path
import json
import wave

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
    assert module_run.status == "done"
    assert module_run.module_name == "asr"
    assert module_run.output_summary["clean_words"] == 3
    assert module_run.output_summary["outputs"]["transcript_review"] == "transcript_review.md"

    review = result.transcript_review_path.read_text(encoding="utf-8")
    assert "Tüm hazırlıklar tamamlandı" in review
    assert "Clean Transcript" in review
    assert "Verbatim Transcript" in review


def _write_silent_wav(path: Path, *, sample_rate: int, channels: int, seconds: float) -> None:
    frames = int(sample_rate * seconds)
    sample_width_bytes = 2
    silent_frame = b"\x00" * sample_width_bytes * channels

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frame * frames)
