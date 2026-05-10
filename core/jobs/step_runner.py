from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from core.jobs.errors import FailedInvalidOutput, JobExecutionError
from core.schemas import JobRun
from core.schemas.common import JobStatus


@dataclass(frozen=True)
class StepResult:
    status: JobStatus = JobStatus.done
    output_artifacts: list[str] = field(default_factory=list)
    last_successful_step: str | None = None
    error_msg: str | None = None

    @classmethod
    def done(cls, output_artifacts: list[str] | None = None, last_successful_step: str | None = None) -> "StepResult":
        return cls(
            status=JobStatus.done,
            output_artifacts=output_artifacts or [],
            last_successful_step=last_successful_step,
        )

    @classmethod
    def partial(
        cls,
        output_artifacts: list[str] | None = None,
        last_successful_step: str | None = None,
        error_msg: str | None = None,
    ) -> "StepResult":
        return cls(
            status=JobStatus.partial,
            output_artifacts=output_artifacts or [],
            last_successful_step=last_successful_step,
            error_msg=error_msg,
        )


RunnerValue = StepResult | JobExecutionError | Exception | Callable[[JobRun], StepResult]


class DummyStepRunner:
    """Configurable dummy runner; no real pipeline or media work is performed."""

    def __init__(self, by_job_id: dict[str, RunnerValue] | None = None, by_step_name: dict[str, RunnerValue] | None = None):
        self.by_job_id = by_job_id or {}
        self.by_step_name = by_step_name or {}

    def run(self, job: JobRun) -> StepResult:
        value = self.by_job_id.get(job.job_id, self.by_step_name.get(job.step_name))
        if value is None:
            return StepResult.done(last_successful_step=job.step_name)
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value(job)
        if not isinstance(value, StepResult):
            raise FailedInvalidOutput("dummy step returned an invalid result")
        if value.status not in (JobStatus.done, JobStatus.partial):
            raise FailedInvalidOutput(f"dummy step returned unsupported status: {value.status}")
        return value
