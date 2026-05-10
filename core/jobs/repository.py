from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from core.schemas import JobRun
from core.schemas.common import JobStatus


class JobRepository:
    """Small repository abstraction that can run in memory or persist to JSON."""

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self._jobs: dict[str, JobRun] = {}
        self._history: dict[str, list[JobRun]] = {}
        if self.storage_path and self.storage_path.exists():
            self._load()

    def add(self, job: JobRun) -> JobRun:
        if job.job_id in self._jobs:
            raise ValueError(f"job already exists: {job.job_id}")
        self._jobs[job.job_id] = job
        self._history[job.job_id] = [job]
        self._save()
        return job

    def create(self, **fields) -> JobRun:
        return self.add(JobRun(**fields))

    def get(self, job_id: str) -> JobRun:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError(f"job not found: {job_id}") from exc

    def update(self, job: JobRun) -> JobRun:
        if job.job_id not in self._jobs:
            raise KeyError(f"job not found: {job.job_id}")
        self._jobs[job.job_id] = job
        self._history.setdefault(job.job_id, []).append(job)
        self._save()
        return job

    def list(self) -> list[JobRun]:
        return list(self._jobs.values())

    def history(self, job_id: str) -> list[JobRun]:
        return list(self._history.get(job_id, []))

    def find_next_pending(self) -> JobRun | None:
        for job in self._jobs.values():
            if job.status == JobStatus.pending:
                return job
        return None

    def pending_jobs(self) -> Iterable[JobRun]:
        return (job for job in self._jobs.values() if job.status == JobStatus.pending)

    def _load(self) -> None:
        raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
        for item in raw.get("jobs", []):
            job = JobRun.model_validate(item)
            self._jobs[job.job_id] = job
            self._history[job.job_id] = [job]

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"jobs": [job.model_dump(mode="json") for job in self._jobs.values()]}
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
