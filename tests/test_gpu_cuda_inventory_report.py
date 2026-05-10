from __future__ import annotations

import json
from pathlib import Path


REPORT_PATH = Path(r"E:\MITAS\outputs\gpu_cuda_inventory_report.json")


def load_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_gpu_cuda_inventory_report_has_required_fields() -> None:
    report = load_report()
    required = {
        "nvidia_smi_found",
        "nvidia_smi_path",
        "gpu_count",
        "gpus",
        "driver_versions",
        "cuda_version_from_nvidia_smi",
        "total_vram_mb",
        "free_vram_mb",
        "recommended_next_cuda_track",
        "heavy_install_ready",
        "warnings",
        "selected_as_engine_count",
        "status",
    }

    assert required.issubset(report)
    assert isinstance(report["nvidia_smi_found"], bool)
    assert isinstance(report["gpu_count"], int)
    assert isinstance(report["gpus"], list)
    assert isinstance(report["warnings"], list)


def test_gpu_cuda_inventory_report_safety_flags() -> None:
    report = load_report()

    assert report["selected_as_engine_count"] == 0
    assert report["status"] == "passed"


def test_gpu_cuda_inventory_readiness_rules() -> None:
    report = load_report()

    if not report["nvidia_smi_found"] or report["gpu_count"] == 0:
        assert report["heavy_install_ready"] is False
    elif report["cuda_version_from_nvidia_smi"] is None:
        assert report["heavy_install_ready"] == "needs_review"
    else:
        assert report["heavy_install_ready"] in {True, "needs_review"}
