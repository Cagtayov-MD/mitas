from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(r"E:\MITAS")
MANIFEST_PATH = ROOT / "model_manifest.yaml"
REPORT_PATH = ROOT / "outputs" / "model_smoke_report.json"


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a mapping")
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("manifest candidates must be a list")
    return data


def venv_python(venv: str) -> str | None:
    if not venv or venv in {"none", "system_or_ocr", "system_or_audio"}:
        return None
    if "_or_" in venv:
        primary = venv.split("_or_", 1)[0]
    else:
        primary = venv
    python_path = ROOT / "venvs" / primary / "Scripts" / "python.exe"
    return str(python_path) if python_path.exists() else None


def command_for_venv(command: str, venv: str) -> tuple[list[str], str | None]:
    parts = shlex.split(command)
    if not parts:
        return [], "empty smoke_test_command"
    python_path = venv_python(venv)
    if python_path and Path(parts[0]).name.lower() in {"python", "python.exe"}:
        parts[0] = python_path
    elif Path(parts[0]).name.lower() in {"python", "python.exe"} and venv not in {"none", "system_or_ocr", "system_or_audio"}:
        return [], f"venv python not found for venv={venv}"
    return parts, None


def dry_result(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "module_area": candidate.get("module_area", ""),
        "candidate_name": candidate.get("candidate_name", ""),
        "venv": candidate.get("venv", ""),
        "smoke_test_command": candidate.get("smoke_test_command", ""),
        "status": "planned",
    }


def run_candidate(candidate: dict[str, Any], timeout: int) -> dict[str, Any]:
    result = dry_result(candidate)
    command = str(candidate.get("smoke_test_command", "")).strip()
    if not command or command.upper().startswith("TBD"):
        result["status"] = "skipped"
        result["reason"] = "smoke_test_command is TBD"
        return result

    args, command_error = command_for_venv(command, str(candidate.get("venv", "")))
    if command_error:
        result["status"] = "skipped"
        result["reason"] = command_error
        return result

    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        result["status"] = "timeout"
        result["returncode"] = None
        result["output"] = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return result
    except Exception as exc:
        result["status"] = "failed"
        result["returncode"] = None
        result["output"] = f"{type(exc).__name__}: {exc}"
        return result

    result["returncode"] = completed.returncode
    result["output"] = completed.stdout.strip()
    result["status"] = "passed" if completed.returncode == 0 else "failed"
    return result


def summarize(run_mode: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    planned_count = sum(1 for item in results if item["status"] == "planned")
    passed_count = sum(1 for item in results if item["status"] == "passed")
    failed_count = sum(1 for item in results if item["status"] == "failed")
    skipped_count = sum(1 for item in results if item["status"] == "skipped")
    timeout_count = sum(1 for item in results if item["status"] == "timeout")
    executed_count = passed_count + failed_count + timeout_count
    status = "passed" if failed_count == 0 and timeout_count == 0 else "failed"
    return {
        "run_mode": run_mode,
        "candidate_count": len(results),
        "planned_count": planned_count,
        "executed_count": executed_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "timeout_count": timeout_count,
        "results": results,
        "status": status,
    }


def run_smoke_tests(real_run: bool = False, timeout: int = 60, manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    results = []
    for candidate in manifest["candidates"]:
        if candidate.get("selected_as_engine") is not False:
            results.append({**dry_result(candidate), "status": "failed", "reason": "selected_as_engine must remain false"})
            continue
        if real_run:
            results.append(run_candidate(candidate, timeout=timeout))
        else:
            results.append(dry_result(candidate))
    return summarize("real_run" if real_run else "dry_run", results)


def write_report(report: dict[str, Any], output_path: Path = REPORT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="MITAS model smoke test runner")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH))
    parser.add_argument("--output", default=str(REPORT_PATH))
    parser.add_argument("--real-run", action="store_true", help="Execute smoke_test_command entries. Default is dry-run.")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    report = run_smoke_tests(real_run=args.real_run, timeout=args.timeout, manifest_path=Path(args.manifest))
    write_report(report, Path(args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
