from __future__ import annotations

import yaml

from scripts.validate_model_manifest import MANIFEST_PATH, validate_manifest


def test_model_manifest_yaml_parses_with_safe_load() -> None:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert isinstance(data["candidates"], list)


def test_model_manifest_validation_passes() -> None:
    report = validate_manifest()
    assert report["manifest_parse_status"] == "passed"
    assert report["status"] == "passed"
    assert report["candidate_count"] == 24
    assert report["selected_as_engine_count"] == 0
    assert report["errors"] == []


def test_no_candidate_is_selected_as_engine() -> None:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert all(candidate["selected_as_engine"] is False for candidate in data["candidates"])


def test_all_candidates_have_explicit_benchmark_required() -> None:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert all(isinstance(candidate["benchmark_required"], bool) for candidate in data["candidates"])
