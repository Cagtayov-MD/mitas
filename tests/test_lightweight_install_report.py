from __future__ import annotations

import json
from pathlib import Path


REPORT_PATH = Path(r"E:\MITAS\outputs\lightweight_install_report.json")


def test_lightweight_install_report_flags_are_safe() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["install_executed"] is True
    assert report["heavy_packages_installed"] is False
    assert report["model_download_executed"] is False
    assert report["benchmark_executed"] is False
    assert report["selected_as_engine_count"] == 0
    assert report["status"] == "passed"


def test_lightweight_install_report_has_no_failures() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["failed_installs"] == []
    assert report["failed_imports"] == []
    assert len(report["venv_results"]) == 7
    assert len(report["import_smoke_results"]) == 7


def test_lightweight_import_smokes_passed_for_expected_modules() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    expected = {
        "ocr": {"numpy", "PIL", "cv2"},
        "asr": {"numpy", "soundfile", "librosa"},
        "audio": {"numpy", "soundfile", "librosa", "pydub"},
        "tag": {"pydantic", "rapidfuzz", "regex", "yaml"},
        "stt": {"numpy", "soundfile", "websockets"},
        "face": {"numpy", "PIL", "cv2"},
        "visual": {"numpy", "PIL", "cv2"},
    }
    by_venv = {item["venv"]: item["imports"] for item in report["import_smoke_results"]}

    assert set(by_venv) == set(expected)
    for venv_name, imports in expected.items():
        assert set(by_venv[venv_name]) == imports
        assert all(result["status"] == "passed" for result in by_venv[venv_name].values())
