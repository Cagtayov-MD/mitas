"""Run MITAS ASR/OCR modules for queued Tedial assets."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable

from core.api.tedial.import_queue import TedialImportQueue
from core.api.tedial.media_resolver import (
    TedialMediaResolveError,
    download_tedial_media,
    safe_artifact_id,
    select_mpd_media_url,
    tedial_media_cache_path,
)
from core.api.tedial.proxy import TedialProxyPlan, TedialProxyService, rewrite_mpd_base_urls
from core.api.tedial.session import TedialSessionNotConnected
from core.schemas import JobRun
from core.schemas.common import JobStatus


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TEDIAL_RUN_ROOT = PROJECT_ROOT / "outputs" / "tedial" / "runs"
DEFAULT_TEDIAL_MEDIA_ROOT = PROJECT_ROOT / "outputs" / "tedial" / "media"


@dataclass(frozen=True)
class TedialModuleResult:
    status: JobStatus
    output_artifacts: list[str]
    last_successful_step: str | None = None
    error_msg: str | None = None


@dataclass(frozen=True)
class TedialJobRunResult:
    job: JobRun
    modules: list[str]
    media_url: str
    media_path: Path
    run_dir: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "job": self.job.model_dump(mode="json"),
            "modules": self.modules,
            "media_url": self.media_url,
            "media_path": str(self.media_path),
            "run_dir": str(self.run_dir),
        }


AsrRunner = Callable[..., TedialModuleResult]
OcrRunner = Callable[..., TedialModuleResult]


class TedialJobRunner:
    """Resolve a Tedial asset, cache its low-res media, then run MITAS modules."""

    def __init__(
        self,
        *,
        service: TedialProxyService,
        queue: TedialImportQueue,
        run_root: str | Path | None = None,
        media_root: str | Path | None = None,
        asr_runner: AsrRunner | None = None,
        ocr_runner: OcrRunner | None = None,
        httpx_module: Any | None = None,
    ) -> None:
        self.service = service
        self.queue = queue
        self.run_root = Path(run_root) if run_root else DEFAULT_TEDIAL_RUN_ROOT
        self.media_root = Path(media_root) if media_root else DEFAULT_TEDIAL_MEDIA_ROOT
        self.asr_runner = asr_runner or _run_asr_pipeline
        self.ocr_runner = ocr_runner or _run_ocr_pipeline
        self.httpx_module = httpx_module

    async def run_job(
        self,
        *,
        job_id: str,
        user_id: str,
        modules: list[str] | None = None,
        asr_profile: str = "fast_with_fallback",
        max_seconds: float | None = None,
        ocr_interval_seconds: float = 10.0,
        ocr_max_frames: int = 24,
    ) -> TedialJobRunResult:
        if self.httpx_module is None:
            try:
                import httpx
            except ImportError as exc:  # pragma: no cover - runtime guard
                raise RuntimeError("Tedial job runner requires httpx in the active runtime") from exc
        else:
            httpx = self.httpx_module

        selected_modules = _normalize_modules(modules)
        job = self._mark_running(self.queue.get_job(job_id))
        run_dir = self.run_root / safe_artifact_id(job.job_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        output_artifacts = list(job.output_artifacts)
        media_url = ""
        media_path = Path()

        try:
            repository_id, asset_id = _tedial_source_from_job(job)
            raw_mpd = await self._fetch_manifest(user_id=user_id, repository_id=repository_id, asset_id=asset_id, httpx=httpx)
            raw_manifest_path = run_dir / "manifest.raw.mpd"
            rewritten_manifest_path = run_dir / "manifest.mpd"
            raw_manifest_path.write_text(raw_mpd, encoding="utf-8")
            rewritten_manifest_path.write_text(rewrite_mpd_base_urls(raw_mpd, self.service.config), encoding="utf-8")
            output_artifacts = _unique(output_artifacts, [str(raw_manifest_path), str(rewritten_manifest_path)])

            media_url = select_mpd_media_url(raw_mpd, self.service.config)
            media_path = tedial_media_cache_path(self.media_root, repository_id, asset_id, media_url)
            cookie_header = self.service.broker.cookie_header_if_any(user_id)
            download = await download_tedial_media(
                media_url=media_url,
                destination=media_path,
                config=self.service.config,
                httpx=httpx,
                cookie_header=cookie_header,
            )
            output_artifacts = _unique(output_artifacts, [str(download.path)])

            analysis_input = media_path
            if max_seconds is not None and max_seconds > 0:
                analysis_input = await asyncio.to_thread(_extract_analysis_clip, media_path, run_dir / "analysis_clip.wav", max_seconds)
                output_artifacts = _unique(output_artifacts, [str(analysis_input)])

            module_results: list[TedialModuleResult] = []
            if "asr" in selected_modules:
                asr_result = await asyncio.to_thread(
                    self.asr_runner,
                    input_path=analysis_input,
                    output_dir=run_dir / "asr",
                    media_id=job.media_id,
                    job_id=job.job_id,
                    profile=asr_profile,
                )
                module_results.append(asr_result)
                output_artifacts = _unique(output_artifacts, asr_result.output_artifacts)

            if "ocr" in selected_modules:
                ocr_result = await asyncio.to_thread(
                    self.ocr_runner,
                    input_path=analysis_input,
                    output_dir=run_dir / "ocr",
                    media_id=job.media_id,
                    job_id=job.job_id,
                    interval_seconds=ocr_interval_seconds,
                    max_frames=ocr_max_frames,
                )
                module_results.append(ocr_result)
                output_artifacts = _unique(output_artifacts, ocr_result.output_artifacts)

            final_status = _combine_status(module_results)
            error_msg = "; ".join(result.error_msg for result in module_results if result.error_msg) or None
            completed = self.queue.update_job(
                job.model_copy(
                    update={
                        "status": final_status,
                        "completed_at": datetime.now(timezone.utc),
                        "error_msg": error_msg,
                        "output_artifacts": output_artifacts,
                        "last_successful_step": _last_successful_step(module_results) or job.step_name,
                    }
                )
            )
            return TedialJobRunResult(
                job=completed,
                modules=selected_modules,
                media_url=media_url,
                media_path=media_path,
                run_dir=run_dir,
            )
        except Exception as exc:
            self.queue.update_job(
                job.model_copy(
                    update={
                        "status": JobStatus.failed,
                        "completed_at": datetime.now(timezone.utc),
                        "retry_count": job.retry_count + 1,
                        "error_msg": str(exc),
                        "output_artifacts": output_artifacts,
                    }
                )
            )
            raise

    async def _fetch_manifest(self, *, user_id: str, repository_id: str, asset_id: str, httpx: Any) -> str:
        try:
            plan = self.service.plan_manifest(user_id, repository_id=repository_id, asset_id=asset_id)
        except TedialSessionNotConnected:
            raise
        response = await _send_plan(plan, verify=self.service.config.verify_tls, httpx=httpx)
        if response.status_code in (401, 403):
            self.service.broker.mark_checked(user_id, connected=False, error=f"Tedial manifest authorization failed ({response.status_code})")
            raise TedialMediaResolveError("Tedial session expired; please reconnect")
        if response.status_code != 200:
            raise TedialMediaResolveError(f"Tedial manifest failed ({response.status_code})")
        return response.text

    def _mark_running(self, job: JobRun) -> JobRun:
        return self.queue.update_job(
            job.model_copy(
                update={
                    "status": JobStatus.running,
                    "started_at": job.started_at or datetime.now(timezone.utc),
                    "completed_at": None,
                    "error_msg": None,
                }
            )
        )


async def _send_plan(plan: TedialProxyPlan, verify: bool, httpx: Any):
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=180.0), verify=verify, trust_env=False) as client:
        return await client.request(plan.method, plan.url, headers=plan.headers, content=plan.body)


def _run_asr_pipeline(*, input_path: str | Path, output_dir: str | Path, media_id: str, job_id: str, profile: str) -> TedialModuleResult:
    from core.pipelines.asr.pipeline import run_asr_pipeline

    result = run_asr_pipeline(
        input_path,
        content_profile="bulten_haber",
        model_profile_override=profile,  # type: ignore[arg-type]
        channel_mode="auto",
        word_alignment_mode="whisperx",
        output_dir=output_dir,
        media_id=media_id,
        job_id=job_id,
    )
    return TedialModuleResult(
        status=result.module_run.status,
        output_artifacts=[
            str(result.archive_path),
            str(result.module_run_path),
            str(result.summary_path),
            str(result.transcript_review_path),
            str(result.normalized_audio_path),
        ],
        last_successful_step="asr",
        error_msg=result.module_run.error_msg,
    )


def _run_ocr_pipeline(
    *,
    input_path: str | Path,
    output_dir: str | Path,
    media_id: str,
    job_id: str,
    interval_seconds: float,
    max_frames: int,
) -> TedialModuleResult:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    python = _default_ocr_python()
    command = [
        str(python),
        "-m",
        "core.pipelines.ocr.simple",
        "--input",
        str(input_path),
        "--output-dir",
        str(output),
        "--media-id",
        media_id,
        "--job-id",
        job_id,
        "--interval-seconds",
        str(interval_seconds),
        "--max-frames",
        str(max_frames),
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, check=False, timeout=1800)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "OCR subprocess failed").strip())

    summary_path = output / "ocr_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    status = JobStatus(summary.get("status", "partial"))
    return TedialModuleResult(
        status=status,
        output_artifacts=[
            str(summary_path),
            str(output / "ocr_results.json"),
            str(output / "ocr_review.md"),
        ],
        last_successful_step="ocr" if status == JobStatus.done else None,
        error_msg=summary.get("error_msg"),
    )


def _default_ocr_python() -> Path:
    configured = os.environ.get("MITAS_OCR_PYTHON", "").strip()
    if configured:
        return Path(configured)
    candidates = [PROJECT_ROOT / "venvs" / "ocr" / "Scripts" / "python.exe"]
    for parent in PROJECT_ROOT.parents:
        candidates.append(parent / "venvs" / "ocr" / "Scripts" / "python.exe")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    import sys

    return Path(sys.executable)


def _extract_analysis_clip(input_path: Path, output_path: Path, max_seconds: float) -> Path:
    from core.pipelines.asr.transcribe import DEFAULT_FFMPEG_EXECUTABLE

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        DEFAULT_FFMPEG_EXECUTABLE,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-t",
        str(max_seconds),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "ffmpeg clip extraction failed").strip())
    return output_path


def _tedial_source_from_job(job: JobRun) -> tuple[str, str]:
    for artifact in job.input_artifacts:
        if artifact.startswith("tedial://"):
            source = artifact.removeprefix("tedial://")
            if "/" in source:
                repository_id, asset_id = source.split("/", 1)
                if repository_id and asset_id:
                    return repository_id, asset_id
    raise ValueError(f"job does not contain a Tedial source reference: {job.job_id}")


def _normalize_modules(modules: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for item in modules or ["asr"]:
        value = item.strip().lower()
        if value not in {"asr", "ocr"}:
            raise ValueError(f"unsupported Tedial module: {item}")
        if value not in normalized:
            normalized.append(value)
    return normalized


def _combine_status(results: list[TedialModuleResult]) -> JobStatus:
    if not results:
        return JobStatus.skipped
    if any(result.status == JobStatus.failed for result in results):
        return JobStatus.failed
    if any(result.status == JobStatus.partial for result in results):
        return JobStatus.partial
    return JobStatus.done


def _last_successful_step(results: list[TedialModuleResult]) -> str | None:
    for result in reversed(results):
        if result.last_successful_step:
            return result.last_successful_step
    return None


def _unique(existing: list[str], new_items: list[str]) -> list[str]:
    output = list(existing)
    for item in new_items:
        if item and item not in output:
            output.append(item)
    return output
