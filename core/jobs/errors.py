from __future__ import annotations


class JobExecutionError(Exception):
    failure_code = "failed_runtime_error"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.failure_code)


class FailedResourceLimit(JobExecutionError):
    failure_code = "failed_resource_limit"


class FailedInvalidOutput(JobExecutionError):
    failure_code = "failed_invalid_output"


class FailedRuntimeError(JobExecutionError):
    failure_code = "failed_runtime_error"
