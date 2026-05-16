"""ASR module runner that writes MITAS-standard output artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import shutil
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from core.pipelines.asr.channel_analysis import ChannelDecision, decide_channel_mode
from core.pipelines.asr.channel_merge import merge_channel_results, tag_result_channel
from core.pipelines.asr.diarize import AudioDiarizeError, DiarizationResult, diarize_audio
from core.pipelines.asr.merge import (
    SpeakerMergeConfig,
    SpeakerMergeResult,
    merge_speakers_into_segments,
)
from core.pipelines.asr.normalize import AudioNormalizeError, NormalizeResult, PROJECT_ROOT, normalize_audio, probe_audio_stream
from core.pipelines.asr.profiles import ContentProfile, ContentProfileName, get_content_profile
from core.pipelines.asr.result import ProductionTranscribeResult
from core.pipelines.asr.transcribe import DEFAULT_FFMPEG_EXECUTABLE, AsrPipelineError, transcribe
from core.pipelines.asr.models import ProfileName
from core.schemas import EventStatus, EventType, ModuleRun, TimelineEvent
from core.schemas.common import JobStatus


ASR_MODULE_NAME = "asr"
ASR_MODULE_VERSION = "1.0"
ASR_PIPELINE_VERSION = "asr_v1_0"
DEFAULT_ASR_RUNS_DIR = PROJECT_ROOT / "outputs" / "asr_runs"


@dataclass(frozen=True)
class AsrPipelineRunResult:
    """File-level result of a single ASR module run."""

    input_path: Path
    output_dir: Path
    normalized_audio_path: Path
    archive_path: Path
    module_run_path: Path
    summary_path: Path
    transcript_review_path: Path
    timeline_events_path: Path
    transcribe_result: ProductionTranscribeResult
    module_run: ModuleRun
    timeline_events: list[TimelineEvent]


DEFAULT_LEGACY_MODEL_PROFILE: ProfileName = "fast_with_fallback"


@dataclass(frozen=True)
class _ProfileResolution:
    """Outcome of resolving the content/model profile inputs.

    `content_profile_name` is None when the caller used the legacy path
    (no `content_profile` argument). Downstream code reads `model_profile`
    and `diarize_intent`; the rest is surfaced in the summary so that
    operators can see *why* a given run took the path it did.
    """

    content_profile_name: str | None
    content_profile: ContentProfile | None
    model_profile: ProfileName
    diarize_intent: bool
    metadata: dict[str, Any]


def _resolve_profile_inputs(
    *,
    content_profile: ContentProfileName | None,
    legacy_profile: ProfileName | None,
    model_profile_override: ProfileName | None,
    diarize_override: bool | None,
) -> _ProfileResolution:
    """Merge `content_profile`, legacy `profile`, and overrides into one view.

    Priority for the model profile:
      1. `model_profile_override` (explicit caller intent — wins regardless)
      2. `ContentProfile.model_profile` if `content_profile` given
      3. `legacy_profile` if provided (old call shape)
      4. `DEFAULT_LEGACY_MODEL_PROFILE` (`fast_with_fallback`)

    Priority for the diarization intent:
      1. `diarize_override` (True/False explicitly set)
      2. `ContentProfile.diarize` when content profile given
      3. False otherwise (legacy callers had no diarization at all)

    The function does NOT call diarization — Paket 1 surfaces the intent in
    summary; Paket 2 will wire up the actual `diarize_audio()` invocation.
    """
    if content_profile is not None:
        profile = get_content_profile(content_profile)
        chosen_model_profile = model_profile_override or profile.model_profile
        chosen_diarize = diarize_override if diarize_override is not None else profile.diarize
        metadata = {
            "model_profile_source": (
                "model_profile_override" if model_profile_override is not None
                else "content_profile"
            ),
            "diarize_source": (
                "diarize_override" if diarize_override is not None
                else "content_profile"
            ),
            "beam_size": profile.beam_size,
            "initial_prompt": profile.initial_prompt,
            "denoise_hint": profile.denoise,
            "notes": profile.notes,
        }
        return _ProfileResolution(
            content_profile_name=profile.name,
            content_profile=profile,
            model_profile=chosen_model_profile,
            diarize_intent=chosen_diarize,
            metadata=metadata,
        )

    chosen_model_profile = (
        model_profile_override
        or legacy_profile
        or DEFAULT_LEGACY_MODEL_PROFILE
    )
    chosen_diarize = diarize_override if diarize_override is not None else False
    metadata = {
        "model_profile_source": (
            "model_profile_override" if model_profile_override is not None
            else "legacy_profile" if legacy_profile is not None
            else "default"
        ),
        "diarize_source": (
            "diarize_override" if diarize_override is not None else "legacy_default"
        ),
        "beam_size": None,
        "initial_prompt": None,
        "denoise_hint": None,
        "notes": "legacy_call_no_content_profile",
    }
    return _ProfileResolution(
        content_profile_name=None,
        content_profile=None,
        model_profile=chosen_model_profile,
        diarize_intent=chosen_diarize,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Paket 2: Diarization wiring
# ---------------------------------------------------------------------------


# Diarization statuses surfaced in summary.quality_report.diarization.status
DIARIZATION_STATUS_OK = "ok"
DIARIZATION_STATUS_DEGRADED = "degraded"
DIARIZATION_STATUS_FAILED = "failed"
DIARIZATION_STATUS_SKIPPED = "skipped"
DIARIZATION_STATUS_NOT_APPLICABLE = "not_applicable"

# Degraded threshold: if more than this fraction of segments fall below the
# speaker-overlap floor we mark the run "degraded" rather than "ok".
DIARIZATION_DEGRADED_LOW_CONFIDENCE_RATIO = 0.5


@dataclass(frozen=True)
class _DiarizationOutcome:
    """Internal record of what diarization did during a pipeline run."""

    status: str
    updated_result: ProductionTranscribeResult
    diarization: DiarizationResult | None
    merge_result: SpeakerMergeResult | None
    runtime_sec: float
    error_message: str | None
    skipped_reason: str | None


def _run_diarization_if_requested(
    *,
    normalized_audio: Path,
    channel_mode: str,
    profile_resolution: _ProfileResolution,
    diarize_required: bool,
    asr_result: ProductionTranscribeResult,
) -> _DiarizationOutcome:
    """Run pyannote diarization when the resolved profile asks for it.

    Skipped paths:
      - Legacy call (no `content_profile`) → `not_applicable`. The legacy
        callers never expected speaker tags; we keep their summary stable.
      - `diarize_intent` is False (`film` / `belgesel` default, or override) →
        `skipped`.
      - `channel_mode == "split"` → `skipped`. Diarizing per-channel and then
        cross-channel merging is a separate sprint; Paket 2 is mono-only.

    Failure handling (Karar 16):
      - With `diarize_required=True`, exceptions propagate so the pipeline
        fails the run.
      - Otherwise the transcript is preserved, `speaker_id` stays None on all
        segments, and the status becomes `failed`.
    """
    if profile_resolution.content_profile_name is None:
        return _diarization_skipped(asr_result, DIARIZATION_STATUS_NOT_APPLICABLE, "legacy_call")
    if not profile_resolution.diarize_intent:
        return _diarization_skipped(asr_result, DIARIZATION_STATUS_SKIPPED, "diarize_intent_false")
    if channel_mode == "split":
        # Split-channel diarization is intentionally deferred; keep transcript intact.
        return _diarization_skipped(asr_result, DIARIZATION_STATUS_SKIPPED, "split_channel_unsupported_v0_1_x")

    started = perf_counter()
    try:
        diarization = diarize_audio(normalized_audio)
    except (AudioDiarizeError, FileNotFoundError, RuntimeError) as exc:
        if diarize_required:
            raise
        runtime = perf_counter() - started
        return _DiarizationOutcome(
            status=DIARIZATION_STATUS_FAILED,
            updated_result=asr_result,
            diarization=None,
            merge_result=None,
            runtime_sec=runtime,
            error_message=str(exc),
            skipped_reason=None,
        )

    runtime = perf_counter() - started
    merge_result = merge_speakers_into_segments(asr_result.clean_segments, diarization)
    updated_result = _apply_speaker_merge(asr_result, merge_result)
    status = _classify_diarization_status(merge_result)
    return _DiarizationOutcome(
        status=status,
        updated_result=updated_result,
        diarization=diarization,
        merge_result=merge_result,
        runtime_sec=runtime,
        error_message=None,
        skipped_reason=None,
    )


def _diarization_skipped(
    asr_result: ProductionTranscribeResult,
    status: str,
    reason: str,
) -> _DiarizationOutcome:
    return _DiarizationOutcome(
        status=status,
        updated_result=asr_result,
        diarization=None,
        merge_result=None,
        runtime_sec=0.0,
        error_message=None,
        skipped_reason=reason,
    )


def _apply_speaker_merge(
    asr_result: ProductionTranscribeResult,
    merge_result: SpeakerMergeResult,
) -> ProductionTranscribeResult:
    """Return a new result with merged segments and a refreshed transcript."""
    from dataclasses import replace as dc_replace

    return dc_replace(
        asr_result,
        clean_segments=merge_result.segments,
        # Verbatim text is unchanged; the speaker assignment is metadata.
    )


def _classify_diarization_status(merge_result: SpeakerMergeResult) -> str:
    """Tell apart `ok` vs `degraded` runs by low-confidence ratio."""
    total = len(merge_result.segments)
    if total == 0:
        return DIARIZATION_STATUS_OK
    low_conf_ratio = merge_result.low_confidence_count / total
    if low_conf_ratio > DIARIZATION_DEGRADED_LOW_CONFIDENCE_RATIO:
        return DIARIZATION_STATUS_DEGRADED
    return DIARIZATION_STATUS_OK


def _resolve_job_status(
    safety: Any,  # ResultSafetyDecision | None — keep loose to avoid forward import
    diarization_status: str,
) -> JobStatus:
    """Combine ASR safety and diarization status into a single job status.

    Karar 16: a failed diarization with `diarize_required=False` should leave
    the job in `partial` so downstream UI flags it for review.
    """
    if safety is not None and not safety.safe:
        return JobStatus.partial
    if diarization_status == DIARIZATION_STATUS_FAILED:
        return JobStatus.partial
    return JobStatus.done


def _resolve_error_message(
    *,
    status: JobStatus,
    safety: Any,
    diarization_status: str,
    diarization_error: str | None,
) -> str | None:
    if status == JobStatus.done:
        return None
    if safety is not None and not safety.safe:
        return safety.failure_reason or "asr_safety_failed"
    if diarization_status == DIARIZATION_STATUS_FAILED:
        return f"diarization_failed:{diarization_error or 'unknown'}"
    return None


def run_asr_pipeline(
    input_path: str | Path,
    *,
    content_profile: ContentProfileName | None = None,
    profile: ProfileName | None = None,
    model_profile_override: ProfileName | None = None,
    diarize_override: bool | None = None,
    diarize_required: bool = False,
    channel_mode: Literal["mono", "split", "auto"] = "mono",
    output_dir: str | Path | None = None,
    media_id: str | None = None,
    job_id: str | None = None,
    module_run_id: str | None = None,
    ffmpeg_executable: str = DEFAULT_FFMPEG_EXECUTABLE,
    ffprobe_executable: str | None = None,
) -> AsrPipelineRunResult:
    """Run the first MITAS module: normalize media, transcribe, and write artifacts.

    Profile resolution (Karar 15 / v0.1.x Paket 1):

    - If `content_profile` is given, the registered `ContentProfile` decides
      the model profile (`fast_with_fallback`, `quality`, ...) and the
      diarization intent. `model_profile_override` and `diarize_override`
      replace those fields when explicitly set.
    - If `content_profile` is None, the legacy `profile` parameter (model
      profile only) is used directly; this keeps existing callers working
      while content profiles are being adopted.

    `diarize_required=True` is a strict-mode signal for Paket 2; v0.1.x Paket
    1 only records intent in summary, the actual diarize call lives in Paket 2.
    """
    profile_resolution = _resolve_profile_inputs(
        content_profile=content_profile,
        legacy_profile=profile,
        model_profile_override=model_profile_override,
        diarize_override=diarize_override,
    )
    source = Path(input_path)
    media = media_id or source.stem
    job = job_id or f"job-{media}"
    module_id = module_run_id or f"asr-{media}-{uuid4().hex[:8]}"
    run_dir = Path(output_dir) if output_dir is not None else _default_output_dir(media, module_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    asr_logger = logging.getLogger("mitas.asr")
    asr_logger.setLevel(logging.INFO)
    log_handler = logging.FileHandler(run_dir / "asr.log", encoding="utf-8")
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    asr_logger.addHandler(log_handler)
    asr_logger.info("ASR pipeline started: media=%s module_run=%s", media, module_id)

    started_at = datetime.now(timezone.utc)
    total_started = perf_counter()
    normalize_seconds = 0.0
    ffprobe = ffprobe_executable or _derive_ffprobe(ffmpeg_executable)

    try:
        input_stream = probe_audio_stream(source, ffprobe_executable=ffprobe)
        channel_decision = decide_channel_mode(
            source,
            requested_mode=channel_mode,
            input_stream=input_stream,
            ffmpeg_executable=ffmpeg_executable,
        )
        normalize_started = perf_counter()
        normalize_result = normalize_audio(
            source,
            output_dir=run_dir / "normalized",
            ffmpeg_executable=ffmpeg_executable,
            ffprobe_executable=ffprobe,
            channel_mode=channel_decision.effective_mode,  # type: ignore[arg-type]
        )
        normalize_seconds = perf_counter() - normalize_started
        normalized_outputs = _materialize_normalized_outputs(normalize_result, run_dir, channel_decision)
        normalized_audio = normalized_outputs.get("mono") or normalized_outputs.get("L") or normalize_result.output_path

        if channel_decision.effective_mode == "split":
            left_result = tag_result_channel(
                transcribe(
                    normalized_outputs["L"],
                    profile=profile_resolution.model_profile,
                    ffmpeg_executable=ffmpeg_executable,
                    ffprobe_executable=ffprobe,
                ),
                "L",
            )
            right_result = tag_result_channel(
                transcribe(
                    normalized_outputs["R"],
                    profile=profile_resolution.model_profile,
                    ffmpeg_executable=ffmpeg_executable,
                    ffprobe_executable=ffprobe,
                ),
                "R",
            )
            asr_result = merge_channel_results(left_result, right_result)
        else:
            asr_result = transcribe(
                normalized_outputs["mono"],
                profile=profile_resolution.model_profile,
                ffmpeg_executable=ffmpeg_executable,
                ffprobe_executable=ffprobe,
            )
        asr_result = _apply_channel_metadata(asr_result, channel_decision)

        diarization_outcome = _run_diarization_if_requested(
            normalized_audio=normalized_audio,
            channel_mode=channel_decision.effective_mode,
            profile_resolution=profile_resolution,
            diarize_required=diarize_required,
            asr_result=asr_result,
        )
        asr_result = diarization_outcome.updated_result

        completed_at = datetime.now(timezone.utc)
        total_seconds = perf_counter() - total_started
        status = _resolve_job_status(asr_result.safety, diarization_outcome.status)
        error_msg = _resolve_error_message(
            status=status,
            safety=asr_result.safety,
            diarization_status=diarization_outcome.status,
            diarization_error=diarization_outcome.error_message,
        )

        archive_path = run_dir / "archive.json"
        module_run_path = run_dir / "module_run.json"
        summary_path = run_dir / "summary.json"
        transcript_review_path = run_dir / "transcript_review.md"
        timeline_events_path = run_dir / "timeline_events.json"

        timeline_events = _build_timeline_events(
            asr_result,
            media_id=media,
            module_run_id=module_id,
            created_at=completed_at,
        )

        archive = asr_result.to_archive_dict()
        summary = _build_summary(
            source=source,
            normalized_audio=normalized_audio,
            normalized_outputs=normalized_outputs,
            profile_resolution=profile_resolution,
            diarize_required=diarize_required,
            diarization_outcome=diarization_outcome,
            normalize_seconds=normalize_seconds,
            total_seconds=total_seconds,
            asr_result=asr_result,
            channel_decision=channel_decision,
            timeline_event_count=len(timeline_events),
        )
        module_run = _build_module_run(
            module_run_id=module_id,
            job_id=job,
            media_id=media,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            runtime_sec=total_seconds,
            model_name=asr_result.model_name or None,
            gpu_used=True,
            error_msg=error_msg,
            output_summary=summary,
        )

        _write_json(archive_path, archive)
        _write_json(summary_path, summary)
        _write_json(module_run_path, module_run.model_dump(mode="json"))
        _write_json(
            timeline_events_path,
            {
                "module_run_id": module_id,
                "media_id": media,
                "event_count": len(timeline_events),
                "events": [event.model_dump(mode="json") for event in timeline_events],
            },
        )
        transcript_review_path.write_text(_build_transcript_review(summary, asr_result), encoding="utf-8")

        return AsrPipelineRunResult(
            input_path=source,
            output_dir=run_dir,
            normalized_audio_path=normalized_audio,
            archive_path=archive_path,
            module_run_path=module_run_path,
            summary_path=summary_path,
            transcript_review_path=transcript_review_path,
            timeline_events_path=timeline_events_path,
            transcribe_result=asr_result,
            module_run=module_run,
            timeline_events=timeline_events,
        )
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        total_seconds = perf_counter() - total_started
        module_run = _build_module_run(
            module_run_id=module_id,
            job_id=job,
            media_id=media,
            status=JobStatus.failed,
            started_at=started_at,
            completed_at=completed_at,
            runtime_sec=total_seconds,
            model_name=None,
            gpu_used=False,
            error_msg=str(exc),
            output_summary={
                "pipeline_version": ASR_PIPELINE_VERSION,
                "input_path": str(source),
                "content_profile": profile_resolution.content_profile_name,
                "profile_requested": profile_resolution.model_profile,
                "channel_mode_requested": channel_mode,
                "normalize_seconds": round(normalize_seconds, 3),
                "total_seconds": round(total_seconds, 3),
                "error": str(exc),
            },
        )
        _write_json(run_dir / "module_run.json", module_run.model_dump(mode="json"))
        _write_json(run_dir / "summary.json", module_run.output_summary)
        asr_logger.exception("ASR pipeline failed: %s", exc)
        if isinstance(exc, AudioNormalizeError):
            raise
        raise AsrPipelineError(f"ASR pipeline failed: {exc}") from exc
    finally:
        asr_logger.removeHandler(log_handler)
        log_handler.close()


def _build_summary(
    *,
    source: Path,
    normalized_audio: Path,
    normalized_outputs: dict[str, Path],
    profile_resolution: "_ProfileResolution",
    diarize_required: bool,
    diarization_outcome: "_DiarizationOutcome",
    normalize_seconds: float,
    total_seconds: float,
    asr_result: ProductionTranscribeResult,
    channel_decision: ChannelDecision,
    timeline_event_count: int,
) -> dict[str, Any]:
    safety = asr_result.safety
    timing = asr_result.timing
    return {
        "pipeline_version": ASR_PIPELINE_VERSION,
        "input_path": str(source),
        "normalized_audio_path": str(normalized_audio),
        "normalized_audio_paths": {key: str(path) for key, path in normalized_outputs.items()},
        "content_profile": profile_resolution.content_profile_name,
        "content_profile_metadata": profile_resolution.metadata,
        "diarize_intent": profile_resolution.diarize_intent,
        "diarize_required": diarize_required,
        "profile_requested": profile_resolution.model_profile,
        "profile_used": asr_result.profile_used,
        "model_name": asr_result.model_name,
        "fallback_triggered": asr_result.fallback_triggered,
        "fallback_reason": asr_result.fallback_reason,
        "selection_reason": asr_result.selection_reason,
        "fallback_mode": timing.fallback_mode if timing else None,
        "fallback_chunk_count": timing.fallback_chunk_count if timing else None,
        "fallback_total_chunk_count": timing.fallback_total_chunk_count if timing else None,
        "audio_duration": asr_result.audio_duration,
        "raw_segments": len(asr_result.raw_segments),
        "clean_segments": len(asr_result.clean_segments),
        "quality_drops": len(asr_result.quality_drops),
        "duplicate_drops": len(asr_result.duplicate_drops),
        "clean_words": len(asr_result.clean_transcript.split()),
        "timeline_event_count": timeline_event_count,
        "vad": {
            "speech_seconds": asr_result.vad_speech_seconds,
            "speech_ratio": asr_result.vad_speech_ratio,
            "segment_count": asr_result.vad_segment_count,
        },
        "quality_report": _build_quality_report(asr_result, diarization_outcome),
        "channels": {
            "requested_mode": channel_decision.requested_mode,
            "mode": channel_decision.effective_mode,
            "auto_decided": channel_decision.auto_decided,
            "lr_correlation": channel_decision.lr_correlation,
            "tracks": sorted(key for key in normalized_outputs if key != "mono"),
            "duplicate_drops": len(asr_result.duplicate_drops),
        },
        "safety": {
            "safe": safety.safe if safety else None,
            "failure_reason": safety.failure_reason if safety else None,
            "diagnostics": safety.diagnostics if safety else None,
        },
        "timing": {
            "normalize_seconds": round(normalize_seconds, 3),
            "transcribe_total_seconds": timing.total_seconds if timing else None,
            "decode_seconds": timing.decode_seconds if timing else None,
            "fallback_seconds": timing.fallback_seconds if timing else None,
            "fallback_chunk_count": timing.fallback_chunk_count if timing else None,
            "fallback_total_chunk_count": timing.fallback_total_chunk_count if timing else None,
            "fallback_mode": timing.fallback_mode if timing else None,
            "chunk_count": timing.chunk_count if timing else None,
            "total_seconds": round(total_seconds, 3),
        },
        "outputs": {
            "archive": "archive.json",
            "module_run": "module_run.json",
            "summary": "summary.json",
            "transcript_review": "transcript_review.md",
            "timeline_events": "timeline_events.json",
        },
    }


def _build_quality_report(
    asr_result: ProductionTranscribeResult,
    diarization_outcome: "_DiarizationOutcome",
) -> dict[str, Any]:
    """Master plan §2.1 ASR kalite raporu sözleşmesine birebir karşılık veren blok.

    v0.1.x sonrası `diarization` bloğu artık gerçek değer üretiyor:
    Paket 2 wiring'i sonucunda `status` `ok` / `degraded` / `failed` /
    `skipped` / `not_applicable` değerlerinden birini alır. WhisperX (Paket 1
    WhisperX entegrasyonu) hala `not_applicable` plak; Paket 3 ile doldurulacak.
    Karar 25 / Mutfak 05.3.4.
    """
    # Audit MED-1: error_flags kategoriktir; literal drop payload'i (orn.
    # "stock_artifact:abone olmayi") summary.json'a sizmamali. archive.json
    # zaten tam metni tutar.
    drop_reason_categories = sorted({drop.reason.split(":", 1)[0] for drop in asr_result.quality_drops})
    segment_flags = sorted({flag for segment in asr_result.clean_segments for flag in segment.flags})
    safety_failure = asr_result.safety.failure_reason if asr_result.safety else None
    safety_category = (
        {safety_failure.split(":", 1)[0]} if safety_failure else set()
    )
    error_flags = sorted(set(segment_flags) | set(drop_reason_categories) | safety_category)

    return {
        "word_timestamp_coverage": {
            "status": "not_applicable",
            "reason": "whisperx_not_integrated_in_v0_1",
            "value": None,
        },
        "alignment_success": {
            "status": "not_applicable",
            "reason": "whisperx_not_integrated_in_v0_1",
            "value": None,
        },
        "vad_speech_ratio": asr_result.vad_speech_ratio,
        "diarization": _build_diarization_quality_block(diarization_outcome),
        "error_flags": error_flags,
    }


def _build_diarization_quality_block(outcome: "_DiarizationOutcome") -> dict[str, Any]:
    """Render the diarization block of the quality report."""
    block: dict[str, Any] = {
        "status": outcome.status,
        "runtime_sec": round(outcome.runtime_sec, 3),
    }
    if outcome.skipped_reason is not None:
        block["reason"] = outcome.skipped_reason
    if outcome.error_message is not None:
        block["error"] = outcome.error_message
    if outcome.merge_result is not None:
        block["speaker_count"] = outcome.merge_result.speaker_count
        block["speakers"] = outcome.merge_result.speakers
        block["low_confidence_segments"] = outcome.merge_result.low_confidence_count
    elif outcome.diarization is not None:
        block["speaker_count"] = outcome.diarization.speaker_count
        block["speakers"] = outcome.diarization.speakers
    return block


def _build_timeline_events(
    asr_result: ProductionTranscribeResult,
    *,
    media_id: str,
    module_run_id: str,
    created_at: datetime,
) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for index, segment in enumerate(asr_result.clean_segments):
        start_time = max(0.0, float(segment.start))
        end_time = max(start_time, float(segment.end))
        payload: dict[str, Any] = {
            "text": segment.text,
            "avg_logprob": float(segment.avg_logprob),
            "no_speech_prob": float(segment.no_speech_prob),
            "flags": list(segment.flags),
            # Audit LOW-2: hangi chunk'in hangi event'i urettigini debug icin sakla.
            "source_chunk_index": segment.source_chunk_index,
        }
        if segment.speaker_id is not None:
            payload["speaker_id"] = segment.speaker_id
        if segment.channel is not None:
            payload["channel"] = segment.channel
        events.append(
            TimelineEvent(
                event_id=f"{module_run_id}-asr-{index:04d}",
                media_id=media_id,
                event_type=EventType.asr_segment,
                subtype=segment.language,
                start_time=start_time,
                end_time=end_time,
                confidence=_segment_confidence(segment.avg_logprob),
                status=EventStatus.auto,
                source_module=ASR_MODULE_NAME,
                payload=payload,
                # Audit MED-3: module_run_id provenance'tir, evidence degil.
                # Gercek Evidence kayitlari v0.2 WhisperX entegrasyonuyla gelecek.
                evidence_ids=[],
                created_at=created_at,
            )
        )
    return events


def _segment_confidence(avg_logprob: float) -> float:
    # Audit LOW-1: NaN logprob "maksimum guven" sinyali degildir; defensive guard.
    if not math.isfinite(avg_logprob):
        return 0.0
    try:
        value = math.exp(avg_logprob)
    except OverflowError:
        return 1.0
    return max(0.0, min(1.0, value))


def _build_module_run(
    *,
    module_run_id: str,
    job_id: str,
    media_id: str,
    status: JobStatus,
    started_at: datetime,
    completed_at: datetime,
    runtime_sec: float,
    model_name: str | None,
    gpu_used: bool,
    error_msg: str | None,
    output_summary: dict[str, Any],
) -> ModuleRun:
    return ModuleRun(
        module_run_id=module_run_id,
        job_id=job_id,
        media_id=media_id,
        module_name=ASR_MODULE_NAME,
        module_version=ASR_MODULE_VERSION,
        model_name=model_name,
        model_version=None,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        runtime_sec=round(runtime_sec, 3),
        gpu_used=gpu_used,
        vram_peak_mb=None,
        error_msg=error_msg,
        output_summary=output_summary,
    )


def _build_transcript_review(summary: dict[str, Any], asr_result: ProductionTranscribeResult) -> str:
    return (
        "# ASR Module Run Transcript Review\n\n"
        "## Summary\n\n"
        f"```json\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```\n\n"
        "## Clean Transcript\n\n"
        f"{asr_result.clean_transcript.strip() or '[bos transcript]'}\n\n"
        "## Verbatim Transcript\n\n"
        f"{asr_result.verbatim_transcript.strip() or '[bos transcript]'}\n"
    )


def _materialize_normalized_audio(normalize_result: NormalizeResult, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if normalize_result.output_path.resolve() != destination.resolve():
        shutil.copy2(normalize_result.output_path, destination)
    return destination


def _materialize_normalized_outputs(
    normalize_result: NormalizeResult,
    run_dir: Path,
    channel_decision: ChannelDecision,
) -> dict[str, Path]:
    if channel_decision.effective_mode == "split":
        outputs: dict[str, Path] = {}
        for channel, filename in {"L": "normalized_L.wav", "R": "normalized_R.wav"}.items():
            destination = run_dir / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = normalize_result.outputs[channel]
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            outputs[channel] = destination
        return outputs
    return {"mono": _materialize_normalized_audio(normalize_result, run_dir / "normalized.wav")}


def _apply_channel_metadata(
    asr_result: ProductionTranscribeResult,
    channel_decision: ChannelDecision,
) -> ProductionTranscribeResult:
    from dataclasses import replace

    return replace(
        asr_result,
        channel_mode=channel_decision.effective_mode,
        channel_auto_decided=channel_decision.auto_decided,
        lr_correlation=channel_decision.lr_correlation,
    )


def _default_output_dir(media_id: str, module_run_id: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_ASR_RUNS_DIR / f"{media_id}_{timestamp}_{module_run_id}"


def _derive_ffprobe(ffmpeg_executable: str) -> str:
    path = Path(ffmpeg_executable)
    if path.name.lower() in {"ffmpeg.exe", "ffmpeg"}:
        candidate = path.with_name("ffprobe.exe" if path.suffix.lower() == ".exe" else "ffprobe")
        if candidate.exists():
            return str(candidate)
    return "ffprobe"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
