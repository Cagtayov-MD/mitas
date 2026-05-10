from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(r"E:\MITAS")
MANIFEST_PATH = ROOT / "model_manifest.yaml"
REPORT_PATH = ROOT / "outputs" / "model_manifest_report.json"

REQUIRED_FIELDS = [
    "module_area",
    "candidate_name",
    "priority",
    "status",
    "venv",
    "install_state",
    "smoke_test_command",
    "expected_outputs",
    "benchmark_required",
    "selected_as_engine",
    "notes",
]


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a mapping")
    return data


def validate_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    errors: list[str] = []
    parsed_files: list[str] = []
    manifest: dict[str, Any] | None = None

    try:
        manifest = load_manifest(path)
        parsed_files.append(str(path))
    except Exception as exc:
        errors.append(f"{path}: {type(exc).__name__}: {exc}")

    candidates = manifest.get("candidates", []) if manifest else []
    if not isinstance(candidates, list):
        errors.append("candidates must be a list")
        candidates = []

    module_area_counts: Counter[str] = Counter()
    selected_as_engine_count = 0
    benchmark_required_count = 0

    for index, candidate in enumerate(candidates, start=1):
        label = f"candidate[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{label} must be a mapping")
            continue

        missing = [field for field in REQUIRED_FIELDS if field not in candidate]
        if missing:
            errors.append(f"{label} missing fields: {', '.join(missing)}")

        module_area = candidate.get("module_area")
        candidate_name = candidate.get("candidate_name")
        status = candidate.get("status")
        priority = candidate.get("priority")
        selected_as_engine = candidate.get("selected_as_engine")
        benchmark_required = candidate.get("benchmark_required")

        if not _non_empty_string(module_area):
            errors.append(f"{label}.module_area must be a non-empty string")
        else:
            module_area_counts[module_area] += 1

        if not _non_empty_string(candidate_name):
            errors.append(f"{label}.candidate_name must be a non-empty string")

        if isinstance(priority, bool) or not isinstance(priority, int):
            errors.append(f"{label}.priority must be an integer")

        if not _non_empty_string(status):
            errors.append(f"{label}.status must be a non-empty string")

        if selected_as_engine is not False:
            errors.append(f"{label}.selected_as_engine must be false before benchmark")
        if selected_as_engine is True:
            selected_as_engine_count += 1

        if not isinstance(benchmark_required, bool):
            errors.append(f"{label}.benchmark_required must be explicit true or false")
        elif benchmark_required:
            benchmark_required_count += 1

    manifest_parse_status = "passed" if manifest is not None and not errors else "failed"
    status = "passed" if manifest_parse_status == "passed" and selected_as_engine_count == 0 else "failed"

    return {
        "manifest_parse_status": manifest_parse_status,
        "candidate_count": len(candidates),
        "module_area_counts": dict(sorted(module_area_counts.items())),
        "selected_as_engine_count": selected_as_engine_count,
        "benchmark_required_count": benchmark_required_count,
        "errors": errors,
        "parsed_files": parsed_files,
        "status": status,
    }


def write_report(pytest_status: str = "not_run") -> dict[str, Any]:
    report = validate_manifest()
    report["pytest_status"] = pytest_status
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = write_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
