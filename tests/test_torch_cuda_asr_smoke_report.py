from __future__ import annotations

import json
from pathlib import Path


REPORT_PATH = Path(r"E:\MITAS\outputs\torch_cuda_asr_smoke_report.json")


def load_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_torch_cuda_asr_smoke_report_flags() -> None:
    report = load_report()

    assert report["target_venv"] == r"E:\MITAS\venvs\asr"
    assert report["install_executed"] is True
    assert report["model_download_executed"] is False
    assert report["benchmark_executed"] is False
    assert report["selected_as_engine_count"] == 0
    assert report["status"] in {"passed", "needs_review"}


def test_torch_cuda_asr_smoke_report_versions_present() -> None:
    report = load_report()

    assert report["installed_packages"] == ["torch", "torchaudio"]
    assert report["torch_version"]
    assert report["torchaudio_version"]
    assert report["torch_cuda_version"]


def test_torch_cuda_asr_smoke_cuda_fields() -> None:
    report = load_report()

    assert isinstance(report["cuda_available"], bool)
    assert isinstance(report["cuda_device_count"], int)
    if report["cuda_available"]:
        assert report["cuda_device_count"] >= 1
        assert report["cuda_device_name"]
        assert report["cuda_tensor_test"] is True
        assert report["vram_total_mb"] is None or report["vram_total_mb"] > 0
