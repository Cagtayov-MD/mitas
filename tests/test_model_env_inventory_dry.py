from __future__ import annotations

from scripts.inspect_model_envs import build_report


def test_env_inventory_runs_without_model_loading() -> None:
    report = build_report()

    assert report["status"] == "passed"
    assert "core" in report["existing_venvs"]
    assert report["manifest_candidates_seen"]["count"] == 28
    assert report["selected_as_engine_count"] == 0


def test_env_inventory_reports_skeleton_model_venvs() -> None:
    report = build_report()

    for name in ["ocr", "asr", "face", "visual", "audio", "tag"]:
        assert name in report["existing_venvs"]
        assert name in report["active_venvs"]
        assert report["python_versions"][name]["status"] == "passed"
        assert report["package_presence"][name]["status"] == "passed"
    assert report["legacy_venvs"] == ["stt"]
    assert report["venv_status"]["stt"] == "legacy_stt_venv/deprecated_as_primary_runtime/do_not_delete_yet"
    assert report["package_presence"]["asr"]["important_packages"]["torch"] is not None
    assert report["package_presence"]["asr"]["important_packages"]["torchaudio"] is not None
    assert report["package_presence"]["asr"]["important_packages"]["fastapi"] == "0.136.1"
    assert report["package_presence"]["asr"]["important_packages"]["uvicorn"] == "0.46.0"
    assert report["package_presence"]["asr"]["important_packages"]["websockets"] == "16.0"
    assert report["package_presence"]["asr"]["important_packages"]["onnxruntime"] == "1.23.2"
    assert report["asr_submodules"] == [
        "file_transcription",
        "streaming_transcription",
        "vad",
        "diarization",
        "alignment",
    ]
    for name in ["audio", "tag"]:
        assert report["package_presence"][name]["important_packages"]["torch"] is None
        assert report["package_presence"][name]["important_packages"]["torchaudio"] is None


def test_env_inventory_keeps_tbd_and_ready_lists_separate() -> None:
    report = build_report()

    assert report["manifest_candidates_with_tbd_smoke_command"]["count"] >= 1
    ready_names = {item["candidate_name"] for item in report["manifest_candidates_ready_for_real_smoke"]["items"]}
    tbd_names = {item["candidate_name"] for item in report["manifest_candidates_with_tbd_smoke_command"]["items"]}
    assert ready_names.isdisjoint(tbd_names)
