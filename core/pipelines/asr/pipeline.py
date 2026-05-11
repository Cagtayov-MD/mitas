"""ASR module runner that writes MITAS-standard output artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from time import perf_counter
from typing import Any
from uuid import uuid4

from core.pipelines.asr.normalize import NormalizeResult, PROJECT_ROOT, normalize_audio
from core.pipelines.asr.result import ProductionTranscribeResult
from core.pipelines.asr.transcribe import DEFAULT_FFMPEG_EXECUTABLE, AsrPipelineError, transcribe
from core.pipelines.asr.models import ProfileName
from core.schemas import ModuleRun
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
    transcribe_result: ProductionTranscribeResult
    module_run: ModuleRun


def run_asr_pipeline(
    input_path: str | Path,
    *,
    profile: ProfileName = "fast_with_fallback",
    output_dir: str | Path | None = None,
    media_id: str | None = None,
    job_id: str | None = None,
    module_run_id: str | None = None,
    ffmpeg_executable: str = DEFAULT_FFMPEG_EXECUTABLE,
    ffprobe_executable: str | None = None,
) -> AsrPipelineRunResult:
    """Run the first MITAS module: normalize media, transcribe, and write artifacts."""
    source = Path(input_path)
    media = media_id or source.stem
    job = job_id or f"job-{media}"
    module_id = module_run_id or f"asr-{media}-{uuid4().hex[:8]}"
    run_dir = Path(output_dir) if output_dir is not None else _default_output_dir(media, module_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    total_started = perf_counter()
    normalize_seconds = 0.0

    try:
        normalize_started = perf_counter()
        normalize_result = normalize_audio(
            source,
            output_dir=run_dir / "normalized",
            ffmpeg_executable=ffmpeg_executable,
            ffprobe_executable=ffprobe_executable or _derive_ffprobe(ffmpeg_executable),
        )
        normalize_seconds = perf_counter() - normalize_started
        normalized_audio = _materialize_normalized_audio(normalize_result, run_dir / "normalized.wav")

        asr_result = transcribe(
            normalized_audio,
            profile=profile,
            ffmpeg_executable=ffmpeg_executable,
            ffprobe_executable=ffprobe_executable or _derive_ffprobe(ffmpeg_executable),
        )

        completed_at = datetime.now(timezone.utc)
        total_seconds = perf_counter() - total_started
        status = JobStatus.done if asr_result.safety is None or asr_result.safety.safe else JobStatus.partial
        error_msg = None if status == JobStatus.done else asr_result.safety.failure_reason if asr_result.safety else "asr_safety_failed"

        archive_path = run_dir / "archive.json"
        module_run_path = run_dir / "module_run.json"
        summary_path = run_dir / "summary.json"
        transcript_review_path = run_dir / "transcript_review.md"

        archive = asr_result.to_archive_dict()
        summary = _build_summary(
            source=source,
            normalized_audio=normalized_audio,
            profile=profile,
            normalize_seconds=normalize_seconds,
            total_seconds=total_seconds,
            asr_result=asr_result,
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
        transcript_review_path.write_text(_build_transcript_review(summary, asr_result), encoding="utf-8")

        return AsrPipelineRunResult(
            input_path=source,
            output_dir=run_dir,
            normalized_audio_path=normalized_audio,
            archive_path=archive_path,
            module_run_path=module_run_path,
            summary_path=summary_path,
            transcript_review_path=transcript_review_path,
            transcribe_result=asr_result,
            module_run=module_run,
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
                "profile_requested": profile,
                "normalize_seconds": round(normalize_seconds, 3),
                "total_seconds": round(total_seconds, 3),
                "error": str(exc),
            },
        )
        _write_json(run_dir / "module_run.json", module_run.model_dump(mode="json"))
        _write_json(run_dir / "summary.json", module_run.output_summary)
        raise AsrPipelineError(f"ASR pipeline failed: {exc}") from exc


def _build_summary(
    *,
    source: Path,
    normalized_audio: Path,
    profile: str,
    normalize_seconds: float,
    total_seconds: float,
    asr_result: ProductionTranscribeResult,
) -> dict[str, Any]:
    safety = asr_result.safety
    timing = asr_result.timing
    return {
        "pipeline_version": ASR_PIPELINE_VERSION,
        "input_path": str(source),
        "normalized_audio_path": str(normalized_audio),
        "profile_requested": profile,
        "profile_used": asr_result.profile_used,
        "model_name": asr_result.model_name,
        "fallback_triggered": asr_result.fallback_triggered,
        "fallback_reason": asr_result.fallback_reason,
        "audio_duration": asr_result.audio_duration,
        "raw_segments": len(asr_result.raw_segments),
        "clean_segments": len(asr_result.clean_segments),
        "quality_drops": len(asr_result.quality_drops),
        "clean_words": len(asr_result.clean_transcript.split()),
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
            "chunk_count": timing.chunk_count if timing else None,
            "total_seconds": round(total_seconds, 3),
        },
        "outputs": {
            "archive": "archive.json",
            "module_run": "module_run.json",
            "summary": "summary.json",
            "transcript_review": "transcript_review.md",
        },
    }


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
