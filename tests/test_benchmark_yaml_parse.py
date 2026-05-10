from __future__ import annotations

import yaml

from scripts.validate_benchmark_yaml import YAML_FILES, validate


def test_benchmark_yaml_files_parse_with_safe_load() -> None:
    for path in YAML_FILES:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)


def test_benchmark_validation_passes() -> None:
    result = validate()
    assert result["yaml_parse_status"] == "passed"
    assert result["failed_files"] == []
    assert result["owners_status"] == "TBD_ALLOWED"
    assert result["blocking_status_present"] is True
