from __future__ import annotations

from core.jobs import DummyStepRunner, DummyWorker, JobRepository, StepResult
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


def test_partial_result_is_preserved() -> None:
    repository = JobRepository()
    repository.add(JobRun(**job_fields("job-partial")))
    worker = DummyWorker(
        repository,
        DummyStepRunner(
            by_job_id={
                "job-partial": StepResult.partial(
                    output_artifacts=["outputs/partial.json"],
                    last_successful_step="dummy_step",
                    error_msg="partial result kept",
                )
            }
        ),
    )

    result = worker.run_next()

    assert result is not None
    assert result.status == "partial"
    assert result.output_artifacts == ["outputs/partial.json"]
    assert result.error_msg == "partial result kept"
    assert result.last_successful_step == "dummy_step"
    assert [job.status.value for job in repository.history("job-partial")] == ["pending", "running", "partial"]
