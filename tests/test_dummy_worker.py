from __future__ import annotations

from core.jobs import DummyStepRunner, DummyWorker, JobRepository, StepResult
from core.schemas import JobRun


def job_fields(job_id: str, status: str = "pending") -> dict:
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


def test_pending_job_becomes_running_then_done() -> None:
    repository = JobRepository()
    repository.add(JobRun(**job_fields("job-done")))
    worker = DummyWorker(
        repository,
        DummyStepRunner(by_job_id={"job-done": StepResult.done(["outputs/done.json"], "dummy_step")}),
    )

    result = worker.run_next()

    assert result is not None
    assert result.status == "done"
    assert result.output_artifacts == ["outputs/done.json"]
    assert result.last_successful_step == "dummy_step"
    assert [job.status.value for job in repository.history("job-done")] == ["pending", "running", "done"]
