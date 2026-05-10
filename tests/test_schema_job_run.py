from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.schemas import JobRun


def valid_job_run() -> dict:
    started_at = datetime.now(timezone.utc)
    return {
        "job_id": "job-1",
        "media_id": "media-1",
        "pipeline_name": "core_schema_only",
        "step_name": "schema_validation",
        "status": "running",
        "started_at": started_at,
        "completed_at": None,
        "retry_count": 0,
        "error_msg": None,
        "input_artifacts": ["E:/MITAS/input.json"],
        "output_artifacts": [],
        "last_successful_step": None,
    }


def test_job_run_valid() -> None:
    job = JobRun(**valid_job_run())
    assert job.status == "running"


def test_job_run_rejects_invalid_status() -> None:
    data = valid_job_run()
    data["status"] = "auto"
    with pytest.raises(ValidationError):
        JobRun(**data)


def test_job_run_rejects_negative_retry_count() -> None:
    data = valid_job_run()
    data["retry_count"] = -1
    with pytest.raises(ValidationError):
        JobRun(**data)
