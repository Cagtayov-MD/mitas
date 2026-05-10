from __future__ import annotations

from core.jobs import DummyStepRunner, DummyWorker, FailedRuntimeError, JobRepository
from core.schemas import JobRun


def job_fields(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "media_id": "media-1",
        "pipeline_name": "dummy_pipeline",
        "step_name": "dummy_step",
        "status": "pending",
        "started_at": None,
        "completed_at": None,
        "retry_count": 0,
        "error_msg": None,
        "input_artifacts": [],
        "output_artifacts": [],
        "last_successful_step": None,
    }


def test_failed_job_sets_failed_and_increments_retry_count() -> None:
    repository = JobRepository()
    repository.add(JobRun(**job_fields("job-failed")))
    worker = DummyWorker(
        repository,
        DummyStepRunner(by_job_id={"job-failed": FailedRuntimeError("boom")}),
    )

    result = worker.run_next()

    assert result is not None
    assert result.status == "failed"
    assert result.retry_count == 1
    assert result.error_msg == "failed_runtime_error"
    assert [job.status.value for job in repository.history("job-failed")] == ["pending", "running", "failed"]
