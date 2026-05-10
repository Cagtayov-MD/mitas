from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.schemas import ModuleRun


def valid_module_run() -> dict:
    return {
        "module_run_id": "module-run-1",
        "job_id": "job-1",
        "media_id": "media-1",
        "module_name": "core_schema",
        "module_version": "0.1.0",
        "model_name": None,
        "model_version": None,
        "status": "done",
        "started_at": datetime.now(timezone.utc),
        "completed_at": datetime.now(timezone.utc),
        "runtime_sec": 1.5,
        "gpu_used": False,
        "vram_peak_mb": 0,
        "error_msg": None,
        "output_summary": {"created": 6},
    }


def test_module_run_valid() -> None:
    module_run = ModuleRun(**valid_module_run())
    assert module_run.vram_peak_mb == 0


def test_module_run_rejects_invalid_status() -> None:
    data = valid_module_run()
    data["status"] = "auto"
    with pytest.raises(ValidationError):
        ModuleRun(**data)


def test_module_run_rejects_string_runtime_sec() -> None:
    data = valid_module_run()
    data["runtime_sec"] = "1.5"
    with pytest.raises(ValidationError):
        ModuleRun(**data)
