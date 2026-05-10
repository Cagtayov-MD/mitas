from __future__ import annotations

from datetime import datetime

from pydantic import model_validator

from core.schemas.common import JobStatus, NonNegativeInt, StrictSchemaModel, StrictStr


class JobRun(StrictSchemaModel):
    job_id: StrictStr
    media_id: StrictStr
    pipeline_name: StrictStr
    step_name: StrictStr
    status: JobStatus
    started_at: datetime | None
    completed_at: datetime | None
    retry_count: NonNegativeInt
    error_msg: StrictStr | None
    input_artifacts: list[StrictStr]
    output_artifacts: list[StrictStr]
    last_successful_step: StrictStr | None

    @model_validator(mode="after")
    def validate_completed_at(self) -> "JobRun":
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValueError("completed_at must be greater than or equal to started_at")
        return self
