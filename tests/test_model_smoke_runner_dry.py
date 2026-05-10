from __future__ import annotations

import yaml

from scripts.run_model_smoke_tests import MANIFEST_PATH, run_smoke_tests


def test_smoke_runner_dry_run_does_not_execute_commands(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called in dry_run")

    monkeypatch.setattr("scripts.run_model_smoke_tests.subprocess.run", fail_if_called)
    report = run_smoke_tests(real_run=False)

    assert report["run_mode"] == "dry_run"
    assert report["candidate_count"] == 24
    assert report["planned_count"] == 24
    assert report["executed_count"] == 0
    assert report["passed_count"] == 0
    assert report["failed_count"] == 0
    assert report["skipped_count"] == 0
    assert report["timeout_count"] == 0
    assert report["status"] == "passed"
    assert all(item["status"] == "planned" for item in report["results"])


def test_smoke_runner_result_fields_are_present() -> None:
    report = run_smoke_tests(real_run=False)
    for item in report["results"]:
        assert set(item) == {"module_area", "candidate_name", "venv", "smoke_test_command", "status"}
        assert item["module_area"]
        assert item["candidate_name"]
        assert item["status"] == "planned"


def test_smoke_runner_does_not_modify_selected_as_engine() -> None:
    before = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    run_smoke_tests(real_run=False)
    after = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert before == after
    assert all(candidate["selected_as_engine"] is False for candidate in after["candidates"])
