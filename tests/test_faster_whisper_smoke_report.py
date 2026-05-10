from __future__ import annotations

import json
from pathlib import Path


REPORT_PATH = Path(r"E:\MITAS\outputs\faster_whisper_smoke_report.json")


def load_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_faster_whisper_smoke_report_flags() -> None:
    report = load_report()

    assert report["target_venv"] == r"E:\MITAS\venvs\asr"
    assert report["install_executed"] is True
    assert report["faster_whisper_installed"] is True
    assert report["ctranslate2_installed"] is True
    assert report["model_instantiated"] is False
    assert report["model_download_executed"] is False
    assert report["audio_video_processed"] is False
    assert report["benchmark_executed"] is False
    assert report["selected_as_engine_count"] == 0
    assert report["status"] in {"passed", "needs_review"}


def test_faster_whisper_versions_and_ctranslate2_capabilities() -> None:
    report = load_report()

    assert report["faster_whisper_version"]
    assert report["ctranslate2_version"]
    assert report["ctranslate2_cpu_compute_types"]
    assert report["ctranslate2_cuda_device_count"] is None or isinstance(report["ctranslate2_cuda_device_count"], int)
    assert report["ctranslate2_cuda_compute_types"] is None or isinstance(report["ctranslate2_cuda_compute_types"], list)


def test_faster_whisper_lock_files_and_pip_check() -> None:
    report = load_report()

    freeze_path = Path(report["freeze_file"])
    inspect_path = Path(report["inspect_file"])
    assert report["pip_check_status"] == "passed"
    assert report["freeze_status"] == "passed"
    assert report["inspect_status"] == "passed"
    assert report["inspect_json_parse_status"] == "passed"
    assert freeze_path.exists()
    assert inspect_path.exists()
    assert "faster-whisper==" in freeze_path.read_text(encoding="utf-8")
    json.loads(inspect_path.read_text(encoding="utf-8"))
