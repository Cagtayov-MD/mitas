from __future__ import annotations

import json
from pathlib import Path


REPORT_PATH = Path(r"E:\MITAS\outputs\faster_whisper_env_lock_report.json")
SCRIPT_PATH = Path(r"E:\MITAS\scripts\lock_faster_whisper_env.py")


def load_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_faster_whisper_env_lock_report_status() -> None:
    report = load_report()

    assert report["target_venv"] == r"E:\MITAS\venvs\asr"
    assert report["pip_check_status"] == "passed"
    assert report["faster_whisper_installed"] is True
    assert report["ctranslate2_installed"] is True
    assert report["model_instantiated"] is False
    assert report["model_download_executed"] is False
    assert report["audio_video_processed"] is False
    assert report["benchmark_executed"] is False
    assert report["selected_as_engine_count"] == 0
    assert report["status"] == "passed"


def test_faster_whisper_env_lock_capabilities_and_files() -> None:
    report = load_report()

    freeze_path = Path(report["freeze_file"])
    inspect_path = Path(report["inspect_file"])
    assert report["faster_whisper_version"]
    assert report["ctranslate2_version"]
    assert isinstance(report["ctranslate2_cuda_device_count"], int)
    assert report["ctranslate2_cpu_compute_types"]
    assert report["ctranslate2_cuda_compute_types"]
    assert freeze_path.exists()
    assert inspect_path.exists()
    assert "faster-whisper==" in freeze_path.read_text(encoding="utf-8")
    assert report["inspect_json_parse_status"] == "passed"
    json.loads(inspect_path.read_text(encoding="utf-8"))


def test_faster_whisper_env_lock_script_has_no_model_instantiation() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "WhisperModel" not in source
    assert "large-v3" not in source
    assert "transcribe(" not in source
