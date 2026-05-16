"""Bridge Tedial assets into the MITAS job repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re

from core.jobs import JobRepository
from core.schemas import JobRun
from core.schemas.common import JobStatus


DEFAULT_TEDIAL_JOB_STORE = Path("outputs") / "tedial" / "jobs.json"


@dataclass(frozen=True)
class TedialEnqueueResult:
    job: JobRun
    created: bool
    import_plan: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "created": self.created,
            "job": self.job.model_dump(mode="json"),
            "import_plan": self.import_plan,
        }


class TedialImportQueue:
    """Create persistent MITAS jobs from Tedial import plans."""

    def __init__(self, repository: JobRepository | None = None, storage_path: str | Path | None = None) -> None:
        if repository is not None:
            self.repository = repository
        else:
            self.repository = JobRepository(storage_path or _default_storage_path())

    def enqueue(self, import_plan: dict[str, object]) -> TedialEnqueueResult:
        draft = _job_fields_from_plan(import_plan)
        try:
            existing = self.repository.get(draft["job_id"])
        except KeyError:
            job = self.repository.create(**draft)
            return TedialEnqueueResult(job=job, created=True, import_plan=import_plan)
        return TedialEnqueueResult(job=existing, created=False, import_plan=import_plan)

    def list_jobs(self) -> list[JobRun]:
        return self.repository.list()

    def get_job(self, job_id: str) -> JobRun:
        return self.repository.get(job_id)

    def update_job(self, job: JobRun) -> JobRun:
        return self.repository.update(job)


def _default_storage_path() -> Path:
    configured = os.environ.get("MITAS_TEDIAL_JOB_STORE", "").strip()
    return Path(configured) if configured else DEFAULT_TEDIAL_JOB_STORE


def _job_fields_from_plan(import_plan: dict[str, object]) -> dict[str, object]:
    draft = dict(import_plan.get("mitas_job_draft") or {})
    asset_id = str(import_plan.get("asset_id") or "").strip()
    repository_id = str(import_plan.get("repository_id") or "").strip()
    manifest_url = str(import_plan.get("manifest_url") or "").strip()
    if not asset_id:
        raise ValueError("Tedial import plan is missing asset_id")
    if not repository_id:
        raise ValueError("Tedial import plan is missing repository_id")
    if not manifest_url:
        raise ValueError("Tedial import plan is missing manifest_url")

    media_id = str(draft.get("media_id") or f"tedial_{_safe_id(asset_id)}")
    job_id = str(draft.get("job_id") or f"job_tedial_{_safe_id(repository_id)}_{_safe_id(asset_id)}")
    input_artifacts = [str(item) for item in draft.get("input_artifacts") or [] if str(item)]
    if manifest_url not in input_artifacts:
        input_artifacts.insert(0, manifest_url)
    source_ref = f"tedial://{repository_id}/{asset_id}"
    if source_ref not in input_artifacts:
        input_artifacts.append(source_ref)

    return {
        "job_id": job_id,
        "media_id": media_id,
        "pipeline_name": str(draft.get("pipeline_name") or "asr"),
        "step_name": str(draft.get("step_name") or "tedial_lowres_import"),
        "status": JobStatus.pending,
        "started_at": None,
        "completed_at": None,
        "retry_count": 0,
        "error_msg": None,
        "input_artifacts": input_artifacts,
        "output_artifacts": [str(item) for item in draft.get("output_artifacts") or [] if str(item)],
        "last_successful_step": None,
    }


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("._-") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
