from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from core.jobs import JobRepository
from core.schemas import JobRun


def job_fields(job_id: str = "job-1", status: str = "pending") -> dict:
    return {
        "job_id": job_id,
        "media_id": "media-1",
        "pipeline_name": "dummy_pipeline",
        "step_name": "dummy_step",
        "status": status,
        "started_at": None,
        "completed_at": None,
        "retry_count": 0,
        "error_msg": None,
        "input_artifacts": [],
        "output_artifacts": [],
        "last_successful_step": None,
    }


def test_repository_add_get_and_find_pending() -> None:
    repository = JobRepository()
    job = repository.create(**job_fields())

    assert repository.get("job-1") == job
    assert repository.find_next_pending() == job


def test_repository_json_storage_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "jobs.json"
    repository = JobRepository(path)
    repository.add(JobRun(**job_fields()))

    loaded = JobRepository(path)
    assert loaded.get("job-1").status == "pending"


def test_repository_rejects_invalid_status() -> None:
    repository = JobRepository()
    with pytest.raises(ValidationError):
        repository.create(**job_fields(status="not_a_status"))
