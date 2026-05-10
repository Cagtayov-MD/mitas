from __future__ import annotations

import json
from pathlib import Path


REPORT_PATH = Path(r"E:\MITAS\outputs\asr_model_cache_strategy_report.json")


def load_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_asr_model_cache_strategy_report_flags() -> None:
    report = load_report()

    assert report["model_download_executed"] is False
    assert report["model_instantiated"] is False
    assert report["audio_video_processed"] is False
    assert report["benchmark_executed"] is False
    assert report["selected_as_engine_count"] == 0
    assert report["status"] == "passed"


def test_asr_model_cache_strategy_dirs_exist() -> None:
    report = load_report()

    for path in report["created_dirs"]:
        assert Path(path).exists()
        assert Path(path).is_dir()
    assert report["hf_home_plan"] == r"E:\MITAS\cache\huggingface"
    assert report["hf_hub_cache_plan"] == r"E:\MITAS\cache\huggingface\hub"


def test_asr_model_cache_strategy_no_download_guard() -> None:
    report = load_report()

    guard = report["offline_guard_default"]
    assert guard["model_download_executed"] is False
    assert guard["model_instantiated"] is False
    assert "HF_HUB_OFFLINE" in guard
    assert "tiny" in report["first_model_load_candidate"].lower()
