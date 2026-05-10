from __future__ import annotations

from datetime import datetime

from pydantic import model_validator

from core.schemas.common import JobStatus, NonNegativeInt, Payload, StrictBool, StrictNonNegativeFloat, StrictSchemaModel, StrictStr


class ModuleRun(StrictSchemaModel):
    module_run_id: StrictStr
    job_id: StrictStr
    media_id: StrictStr
    module_name: StrictStr
    module_version: StrictStr | None
    model_name: StrictStr | None
    model_version: StrictStr | None
    status: JobStatus
    started_at: datetime | None
    completed_at: datetime | None
    runtime_sec: StrictNonNegativeFloat | None
    gpu_used: StrictBool
    vram_peak_mb: NonNegativeInt | None
    error_msg: StrictStr | None
    output_summary: Payload

    @model_validator(mode="after")
    def validate_completed_at(self) -> "ModuleRun":
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValueError("completed_at must be greater than or equal to started_at")
        return self
