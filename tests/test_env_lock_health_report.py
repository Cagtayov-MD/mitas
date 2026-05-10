from __future__ import annotations

import json
from pathlib import Path


REPORT_PATH = Path(r"E:\MITAS\outputs\env_lock_health_report.json")
EXPECTED_VENVS = ["ocr", "asr", "face", "visual", "audio", "tag", "stt", "core"]


def load_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_env_lock_health_report_status_and_flags() -> None:
    report = load_report()

    assert report["checked_venvs"] == EXPECTED_VENVS
    assert report["broken_dependency_count"] == 0
    assert report["heavy_packages_installed"] is False
    assert report["model_download_executed"] is False
    assert report["benchmark_executed"] is False
    assert report["selected_as_engine_count"] == 0
    assert report["status"] == "passed"


def test_env_lock_files_exist_and_inspect_json_parses() -> None:
    report = load_report()

    for venv_name in EXPECTED_VENVS:
        freeze_path = Path(report["freeze_files"][venv_name])
        inspect_path = Path(report["inspect_files"][venv_name])
        assert freeze_path.exists()
        assert inspect_path.exists()
        json.loads(inspect_path.read_text(encoding="utf-8"))


def test_env_lock_pip_check_and_imports_passed() -> None:
    report = load_report()

    assert all(item["status"] == "passed" for item in report["pip_check_results"])
    assert all(item["broken"] is False for item in report["pip_check_results"])
    assert report["failed_imports"] == []
    for venv_result in report["import_smoke_results"]:
        assert all(result["status"] == "passed" for result in venv_result["imports"].values())
