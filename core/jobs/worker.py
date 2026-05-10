from __future__ import annotations

from datetime import datetime, timezone

from core.jobs.errors import FailedRuntimeError, JobExecutionError
from core.jobs.repository import JobRepository
from core.jobs.step_runner import DummyStepRunner, StepResult
from core.schemas import JobRun
from core.schemas.common import JobStatus


class DummyWorker:
    """Single-job dummy worker for Sprint 2 state-flow tests."""

    def __init__(self, repository: JobRepository, step_runner: DummyStepRunner | None = None):
        self.repository = repository
        self.step_runner = step_runner or DummyStepRunner()

    def run_next(self) -> JobRun | None:
        job = self.repository.find_next_pending()
        if job is None:
            return None
        return self.run_job(job.job_id)

    def run_job(self, job_id: str) -> JobRun:
        job = self.repository.get(job_id)
        running = self._mark_running(job)
        try:
            result = self.step_runner.run(running)
        except JobExecutionError as exc:
            return self._mark_failed(running, exc.failure_code)
        except Exception as exc:
            return self._mark_failed(running, FailedRuntimeError(str(exc)).failure_code)
        return self._apply_result(running, result)

    def _mark_running(self, job: JobRun) -> JobRun:
        return self.repository.update(
            job.model_copy(
                update={
                    "status": JobStatus.running,
                    "started_at": job.started_at or datetime.now(timezone.utc),
                    "completed_at": None,
                    "error_msg": None,
                }
            )
        )

    def _mark_failed(self, job: JobRun, error_msg: str) -> JobRun:
        return self.repository.update(
            job.model_copy(
                update={
                    "status": JobStatus.failed,
                    "completed_at": datetime.now(timezone.utc),
                    "retry_count": job.retry_count + 1,
                    "error_msg": error_msg,
                }
            )
        )

    def _apply_result(self, job: JobRun, result: StepResult) -> JobRun:
        return self.repository.update(
            job.model_copy(
                update={
                    "status": result.status,
                    "completed_at": datetime.now(timezone.utc),
                    "error_msg": result.error_msg,
                    "output_artifacts": result.output_artifacts,
                    "last_successful_step": result.last_successful_step or job.step_name,
                }
            )
        )
