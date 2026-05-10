from __future__ import annotations

from scripts.run_pip_dryrun_reports import (
    LEGACY_REQUIREMENT_FILES,
    REQUIREMENT_FILES,
    build_pip_dryrun_command,
    build_report,
    pip_report_path,
)


def test_pip_dryrun_plan_only_does_not_execute_subprocess(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called in plan-only mode")

    monkeypatch.setattr("scripts.run_pip_dryrun_reports.subprocess.run", fail_if_called)
    report = build_report(execute=False)

    assert report["run_mode"] == "pip_dryrun_plan_only"
    assert report["passed_count"] == 0
    assert report["failed_count"] == 0
    assert report["skipped_count"] == len(REQUIREMENT_FILES)
    assert report["install_executed"] is False
    assert report["model_download_executed"] is False
    assert report["selected_as_engine_count"] == 0
    assert report["legacy_requirement_files"] == [str(path) for path in LEGACY_REQUIREMENT_FILES.values()]
    assert report["legacy_venvs_skipped"]["stt"] == "legacy_stt_venv/deprecated_as_primary_runtime/do_not_delete_yet"
    assert report["status"] == "passed"


def test_pip_dryrun_commands_use_dry_run_and_report() -> None:
    for venv_name, requirement_path in REQUIREMENT_FILES.items():
        command = build_pip_dryrun_command(venv_name, requirement_path, pip_report_path(venv_name))

        assert "-m" in command
        assert "pip" in command
        assert "install" in command
        assert "--dry-run" in command
        assert "--ignore-installed" in command
        assert "--report" in command
        assert "-r" in command
        assert str(requirement_path) in command


def test_pip_dryrun_detects_no_placeholder_package_lines() -> None:
    report = build_report(execute=False)

    assert report["placeholder_errors"] == []
    assert report["heavy_gpu_packages_detected"]
    assert "tesseract" in report["external_binary_notes"]
    assert "fpcalc" in report["external_binary_notes"]
