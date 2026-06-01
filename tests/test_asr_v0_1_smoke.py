"""ASR v0.1 smoke test.

Validates the demo run produced by ``scripts/asr_v0_1_demo.py``. The demo runs
the full ASR pipeline on the TRT smoke clip (001_h1, ~102 sec haber kameramanlari)
and writes archive.json, summary.json, module_run.json, transcript_review.md,
and timeline_events.json to ``outputs/asr_v0_1_demo/``.

This test does not run the model itself; it loads the golden demo output and
checks that the v0.1 contract holds:
  - all five artifacts exist
  - schemas validate (ModuleRun, TimelineEvent)
  - counts agree between summary, archive, and timeline_events
  - the quality report carries the v0.1 required fields
  - the chosen clip produced a sane transcript

Reproduce the demo output with:

    E:\\MITAS\\venvs\\asr\\Scripts\\python.exe scripts\\asr_v0_1_demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.schemas import ModuleRun, TimelineEvent


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = PROJECT_ROOT / "outputs" / "asr_v0_1_demo"
SMOKE_CLIP_ID = "001_h1"
EXPECTED_MODELS = {"large-v3-turbo", "large-v3"}


pytestmark = pytest.mark.skipif(
    not DEMO_DIR.exists(),
    reason=(
        f"ASR v0.1 demo output not found at {DEMO_DIR}. "
        "Run scripts/asr_v0_1_demo.py with the asr venv first."
    ),
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return json.loads((DEMO_DIR / "summary.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def archive() -> dict:
    return json.loads((DEMO_DIR / "archive.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def module_run() -> ModuleRun:
    payload = json.loads((DEMO_DIR / "module_run.json").read_text(encoding="utf-8"))
    return ModuleRun.model_validate(payload)


@pytest.fixture(scope="module")
def timeline_events_payload() -> dict:
    return json.loads((DEMO_DIR / "timeline_events.json").read_text(encoding="utf-8"))


def test_all_five_artifacts_present() -> None:
    for filename in ("archive.json", "summary.json", "module_run.json", "transcript_review.md", "timeline_events.json"):
        artifact = DEMO_DIR / filename
        assert artifact.exists(), f"Missing demo artifact: {filename}"
        assert artifact.stat().st_size > 0, f"Empty demo artifact: {filename}"


def test_module_run_validates_against_schema(module_run: ModuleRun) -> None:
    assert module_run.module_name == "asr"
    assert module_run.media_id == SMOKE_CLIP_ID
    assert module_run.status in {"done", "partial"}
    assert module_run.model_name in EXPECTED_MODELS
    assert module_run.runtime_sec > 0.0


def test_summary_has_v0_1_quality_report_fields(summary: dict) -> None:
    required_top_level = {
        "model_name",
        "fallback_triggered",
        "fallback_reason",
        "selection_reason",
        "clean_segments",
        "quality_drops",
        "timeline_event_count",
        "vad",
        "safety",
        "timing",
    }
    missing = required_top_level - set(summary)
    assert not missing, f"summary.json missing v0.1 required fields: {sorted(missing)}"

    assert summary["model_name"] in EXPECTED_MODELS
    assert summary["profile_requested"] == "fast_with_fallback"
    assert summary["profile_used"] in {"fast", "quality"}
    assert summary["selection_reason"]
    assert summary["clean_segments"] >= 1
    assert summary["clean_words"] >= 10


def test_summary_vad_block_is_populated(summary: dict) -> None:
    vad = summary["vad"]
    assert vad["speech_seconds"] is not None and vad["speech_seconds"] > 0.0
    assert vad["speech_ratio"] is not None and 0.0 < vad["speech_ratio"] <= 1.0
    assert vad["segment_count"] is not None and vad["segment_count"] >= 1


def test_summary_safety_diagnostics_present(summary: dict) -> None:
    safety = summary["safety"]
    assert safety["safe"] is True
    assert safety["failure_reason"] is None
    diagnostics = safety["diagnostics"]
    assert diagnostics is not None
    for key in ("max_run", "max_token_length", "words_per_second", "uncovered_tail_seconds", "uncovered_tail_ratio"):
        assert key in diagnostics, f"safety.diagnostics missing key: {key}"


def test_quality_report_matches_master_plan_2_1_contract(summary: dict) -> None:
    """Master plan §2.1 ASR kalite raporu beş zorunlu alan ister.

    Eski demo çıktıları WhisperX yokken `not_applicable` taşır; yeni pipeline
    koşuları segment-interpolated word timing ile bu alanları doldurabilir.
    """
    report = summary["quality_report"]
    for field in ("word_timestamp_coverage", "alignment_success", "vad_speech_ratio", "diarization", "error_flags"):
        assert field in report, f"quality_report missing §2.1 field: {field}"

    assert report["word_timestamp_coverage"]["status"] in {"not_applicable", "ok", "degraded", "missing", "failed", "skipped"}
    assert report["alignment_success"]["status"] in {"not_applicable", "ok", "degraded", "missing", "failed", "skipped"}
    assert report["diarization"]["status"] == "not_applicable"
    assert isinstance(report["vad_speech_ratio"], float)
    assert 0.0 < report["vad_speech_ratio"] <= 1.0
    assert isinstance(report["error_flags"], list)


def test_timeline_events_validate_against_schema(timeline_events_payload: dict, summary: dict) -> None:
    events_data = timeline_events_payload["events"]
    assert len(events_data) == summary["timeline_event_count"]
    assert len(events_data) == summary["clean_segments"]

    for event_data in events_data:
        event = TimelineEvent.model_validate(event_data)
        assert event.event_type.value == "asr_segment"
        assert event.source_module == "asr"
        assert event.status.value == "auto"
        assert event.media_id == SMOKE_CLIP_ID
        assert event.end_time >= event.start_time
        assert 0.0 <= event.confidence <= 1.0
        assert "text" in event.payload
        assert "avg_logprob" in event.payload
        assert "no_speech_prob" in event.payload


def test_archive_segments_match_summary(archive: dict, summary: dict) -> None:
    assert len(archive["segments"]) == summary["clean_segments"]
    assert archive["model"] == summary["model_name"]
    assert archive["profile"] == summary["profile_used"]
    assert archive["selection_reason"] == summary["selection_reason"]
    assert archive["quality"]["safety_passed"] is True


def test_transcript_review_contains_clean_transcript() -> None:
    review = (DEMO_DIR / "transcript_review.md").read_text(encoding="utf-8")
    assert "Clean Transcript" in review
    assert "Verbatim Transcript" in review
    assert "Summary" in review


def test_smoke_clip_speech_density_is_news_like(summary: dict) -> None:
    """001_h1 is a TRT haber kesiti — speech ratio should be high (>0.5)."""
    assert summary["vad"]["speech_ratio"] > 0.5, (
        f"VAD speech ratio {summary['vad']['speech_ratio']} unexpectedly low for a news clip"
    )
