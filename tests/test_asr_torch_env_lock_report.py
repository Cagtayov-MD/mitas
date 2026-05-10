from __future__ import annotations

import json
from pathlib import Path


REPORT_PATH = Path(r"E:\MITAS\outputs\asr_torch_env_lock_report.json")


def load_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_asr_torch_env_lock_report_status() -> None:
    report = load_report()

    assert report["target_venv"] == r"E:\MITAS\venvs\asr"
    assert report["pip_check_status"] == "passed"
    assert report["cuda_available"] is True
    assert report["cuda_tensor_test"] == "passed"
    assert report["faster_whisper_installed"] is False
    assert report["whisperx_installed"] is False
    assert report["model_download_executed"] is False
    assert report["benchmark_executed"] is False
    assert report["selected_as_engine_count"] == 0
    assert report["status"] == "passed"


def test_asr_torch_lock_files_exist_and_inspect_parses() -> None:
    report = load_report()

    freeze_path = Path(report["freeze_file"])
    inspect_path = Path(report["inspect_file"])
    assert freeze_path.exists()
    assert inspect_path.exists()
    assert "torch==" in freeze_path.read_text(encoding="utf-8")
    assert report["inspect_json_parse_status"] == "passed"
    json.loads(inspect_path.read_text(encoding="utf-8"))


def test_asr_torch_versions_and_vram_present() -> None:
    report = load_report()

    assert report["torch_version"]
    assert report["torchaudio_version"]
    assert report["torch_cuda_version"]
    assert report["cuda_device_name"]
    assert report["vram_total_mb"] is None or report["vram_total_mb"] > 0
