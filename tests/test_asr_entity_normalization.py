from __future__ import annotations

import json
from pathlib import Path
import wave

from core.pipelines.asr.phase2.entity_normalization import normalize_entities
from core.pipelines.asr.pipeline import run_asr_pipeline
from core.pipelines.asr.quality import ResultSafetyDecision
from core.pipelines.asr.result import ProductionTranscribeResult, TranscriptSegment, TranscribeTiming


def test_entity_normalization_attaches_reviewable_normalized_text() -> None:
    segment = TranscriptSegment(
        index=0,
        start=1.0,
        end=3.0,
        text="Barış Mango TRT haber arşivinde anıldı",
        language="tr",
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        source_chunk_index=0,
    )
    result = _fake_result(Path("normalized.wav"), [segment])

    updated = normalize_entities(result)

    assert updated.clean_transcript == result.clean_transcript
    assert updated.normalized_transcript == "Barış Manço TRT Haber arşivinde anıldı"
    assert updated.clean_segments[0].text == segment.text
    assert updated.clean_segments[0].normalized_text == "Barış Manço TRT Haber arşivinde anıldı"
    assert [item["canonical"] for item in updated.normalized_entities] == ["Barış Manço", "TRT Haber"]
    assert updated.normalized_entities[0]["evidence"]["source_text"] == "Barış Mango TRT haber arşivinde anıldı"
    assert updated.normalized_entities[0]["evidence"]["normalized_text"] == "Barış Manço TRT Haber arşivinde anıldı"


def test_pipeline_surfaces_entity_normalization_artifacts(tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.wav"
    _write_silent_wav(source)

    def fake_transcribe(audio_path, **kwargs):
        segment = TranscriptSegment(
            index=0,
            start=0.1,
            end=1.1,
            text="Barış Mango TRT haber programında konuştu",
            language="tr",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            source_chunk_index=0,
        )
        return _fake_result(Path(audio_path), [segment], profile=kwargs["profile"])

    monkeypatch.setattr("core.pipelines.asr.pipeline.transcribe", fake_transcribe)

    result = run_asr_pipeline(
        source,
        profile="fast_with_fallback",
        output_dir=tmp_path / "asr_run",
        media_id="media-entity",
        job_id="job-entity",
        module_run_id="module-entity",
        word_alignment_mode="interpolated",
    )

    archive = json.loads(result.archive_path.read_text(encoding="utf-8"))
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    timeline = json.loads(result.timeline_events_path.read_text(encoding="utf-8"))
    review = result.transcript_review_path.read_text(encoding="utf-8")

    assert archive["transcript"]["clean"] == "Barış Mango TRT haber programında konuştu"
    assert archive["transcript"]["normalized"] == "Barış Manço TRT Haber programında konuştu"
    assert archive["segments"][0]["normalized_text"] == "Barış Manço TRT Haber programında konuştu"
    assert [item["canonical"] for item in archive["normalized_entities"]] == ["Barış Manço", "TRT Haber"]

    entity_block = summary["quality_report"]["entity_normalization"]
    assert summary["normalized_entities"] == 2
    assert entity_block["status"] == "ok"
    assert entity_block["count"] == 2
    assert timeline["events"][0]["payload"]["normalized_text"] == "Barış Manço TRT Haber programında konuştu"
    assert "Normalized Transcript" in review
    assert "Barış Manço TRT Haber programında konuştu" in review


def _fake_result(
    audio_path: Path,
    segments: list[TranscriptSegment],
    *,
    profile: str = "fast_with_fallback",
) -> ProductionTranscribeResult:
    text = " ".join(segment.text for segment in segments)
    return ProductionTranscribeResult(
        audio_path=audio_path,
        audio_duration=2.0,
        profile_requested=profile,
        profile_used="fast",
        model_name="large-v3-turbo",
        fallback_triggered=False,
        fallback_reason=None,
        raw_segments=segments,
        clean_segments=segments,
        verbatim_transcript=text,
        clean_transcript=text,
        normalized_transcript=None,
        quality_drops=[],
        safety=ResultSafetyDecision(safe=True, failure_reason=None, diagnostics={"max_run": 1}),
        timing=TranscribeTiming(total_seconds=1.0, chunk_count=1, decode_seconds=0.5),
    )


def _write_silent_wav(path: Path, *, sample_rate: int = 16_000, seconds: float = 1.0) -> None:
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)
