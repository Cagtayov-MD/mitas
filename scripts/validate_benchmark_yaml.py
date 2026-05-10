from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(r"E:\MITAS")
YAML_FILES = [
    ROOT / "benchmark_registry.yaml",
    ROOT / "benchmark_templates" / "ocr_kj_benchmark.yaml",
    ROOT / "benchmark_templates" / "asr_benchmark.yaml",
    ROOT / "benchmark_templates" / "audio_activity_benchmark.yaml",
    ROOT / "benchmark_templates" / "face_benchmark.yaml",
    ROOT / "benchmark_templates" / "visual_tag_benchmark.yaml",
]
REPORT_PATH = ROOT / "outputs" / "benchmark_plan_report.json"


def parse_yaml_files() -> tuple[dict[Path, Any], list[str], list[str], list[str]]:
    parsed: dict[Path, Any] = {}
    parsed_files: list[str] = []
    failed_files: list[str] = []
    errors: list[str] = []

    for path in YAML_FILES:
        try:
            # yaml.safe_load intentionally limits parsing to standard YAML tags.
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            parsed[path] = data
            parsed_files.append(str(path))
        except Exception as exc:
            failed_files.append(str(path))
            errors.append(f"{path}: {type(exc).__name__}: {exc}")

    return parsed, parsed_files, failed_files, errors


def has_blocking_status(parsed: dict[Path, Any]) -> bool:
    registry = parsed.get(ROOT / "benchmark_registry.yaml")
    if not isinstance(registry, dict):
        return False
    benchmarks = registry.get("benchmarks")
    if not isinstance(benchmarks, list) or not benchmarks:
        return False
    registry_ok = all(item.get("blocking_before_model_install") is True for item in benchmarks if isinstance(item, dict))
    template_ok = True
    for path in YAML_FILES[1:]:
        data = parsed.get(path)
        template_ok = template_ok and isinstance(data, dict) and data.get("blocking_before_model_install") is True
    return registry_ok and template_ok


def validate() -> dict[str, Any]:
    parsed, parsed_files, failed_files, errors = parse_yaml_files()
    return {
        "yaml_parse_status": "passed" if not failed_files else "failed",
        "parsed_files": parsed_files,
        "failed_files": failed_files,
        "owners_status": "TBD_ALLOWED",
        "blocking_status_present": has_blocking_status(parsed),
        "errors": errors,
    }


def write_report(pytest_status: str, pytest_passed_count: int, pytest_failed_count: int) -> dict[str, Any]:
    report = validate()
    report.update(
        {
            "pytest_status": pytest_status,
            "pytest_passed_count": pytest_passed_count,
            "pytest_failed_count": pytest_failed_count,
            "created_files": [
                "scripts/validate_benchmark_yaml.py",
                "tests/test_benchmark_yaml_parse.py",
                "outputs/benchmark_plan_report.json",
            ],
        }
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["yaml_parse_status"] == "passed" and result["blocking_status_present"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
