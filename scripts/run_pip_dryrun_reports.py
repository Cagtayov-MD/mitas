from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import yaml


ROOT = Path(r"E:\MITAS")
OUTPUT_DIR = ROOT / "outputs"
REPORT_PATH = OUTPUT_DIR / "pip_dryrun_summary_report.json"
MANIFEST_PATH = ROOT / "model_manifest.yaml"

REQUIREMENT_FILES = {
    "ocr": ROOT / "requirements" / "ocr.txt",
    "asr": ROOT / "requirements" / "asr.txt",
    "face": ROOT / "requirements" / "face.txt",
    "visual": ROOT / "requirements" / "visual.txt",
    "audio": ROOT / "requirements" / "audio.txt",
    "tag": ROOT / "requirements" / "tag.txt",
}
LEGACY_REQUIREMENT_FILES = {
    "stt": ROOT / "requirements" / "stt.txt",
}

LIGHTWEIGHT_PACKAGES = {
    "numpy",
    "pillow",
    "soundfile",
    "pydub",
    "pydantic",
    "rapidfuzz",
    "regex",
    "pyyaml",
    "websockets",
}
MEDIUM_PACKAGES = {
    "opencv-python",
    "librosa",
    "faster-whisper",
    "silero-vad",
    "insightface",
    "transformers",
}
HEAVY_GPU_MARKERS = {
    "torch",
    "torchaudio",
    "onnxruntime-gpu",
    "tensorflow",
    "paddleocr",
    "paddlepaddle",
    "ultralytics",
    "yolo-world",
    "whisperx",
}
EXTERNAL_BINARY_MARKERS = {
    "tesseract",
    "fpcalc",
    "chromaprint",
}


def venv_python_path(venv_name: str) -> Path:
    return ROOT / "venvs" / venv_name / "Scripts" / "python.exe"


def pip_report_path(venv_name: str) -> Path:
    return OUTPUT_DIR / f"pip_dryrun_{venv_name}.json"


def parse_requirement_file(path: Path) -> dict[str, Any]:
    package_lines: list[str] = []
    placeholder_lines: list[str] = []
    placeholder_errors: list[str] = []
    heavy_gpu_detected: set[str] = set()
    external_binary_notes: set[str] = set()
    lightweight_count = 0
    medium_count = 0

    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if line.startswith("#"):
            if "placeholder" in lower or "external binary" in lower:
                placeholder_lines.append(f"{path.name}:{line_no}: {line}")
            for marker in HEAVY_GPU_MARKERS:
                if marker in lower:
                    heavy_gpu_detected.add(marker)
            for marker in EXTERNAL_BINARY_MARKERS:
                if marker in lower:
                    external_binary_notes.add(marker)
            continue

        if "placeholder" in lower or "tbd" in lower:
            placeholder_errors.append(f"{path.name}:{line_no}: {line}")

        package_lines.append(line)
        package_name = normalized_package_name(line)
        if package_name in LIGHTWEIGHT_PACKAGES:
            lightweight_count += 1
        if package_name in MEDIUM_PACKAGES:
            medium_count += 1
        if package_name in HEAVY_GPU_MARKERS:
            heavy_gpu_detected.add(package_name)
        if package_name in EXTERNAL_BINARY_MARKERS:
            external_binary_notes.add(package_name)

    return {
        "path": str(path),
        "package_lines": package_lines,
        "package_line_count": len(package_lines),
        "placeholder_lines": placeholder_lines,
        "placeholder_count": len(placeholder_lines),
        "placeholder_errors": placeholder_errors,
        "lightweight_count": lightweight_count,
        "medium_count": medium_count,
        "heavy_gpu_packages_detected": sorted(heavy_gpu_detected),
        "external_binary_notes": sorted(external_binary_notes),
    }


def normalized_package_name(requirement: str) -> str:
    token = requirement.split(";", 1)[0].strip()
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
        if separator in token:
            token = token.split(separator, 1)[0]
    return token.strip().lower().replace("_", "-")


def build_pip_dryrun_command(venv_name: str, requirement_path: Path, report_path: Path) -> list[str]:
    return [
        str(venv_python_path(venv_name)),
        "-m",
        "pip",
        "install",
        "--dry-run",
        "--ignore-installed",
        "--report",
        str(report_path),
        "-r",
        str(requirement_path),
    ]


def safe_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    cache_dir = ROOT / "cache" / "pip"
    temp_dir = ROOT / "tmp" / "pip_dryrun"
    cache_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    env["PIP_CACHE_DIR"] = str(cache_dir)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env["TMP"] = str(temp_dir)
    env["TEMP"] = str(temp_dir)
    return env


def parse_generated_pip_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "resolved_packages": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "resolved_packages": []}
    resolved = []
    for item in data.get("install", []):
        metadata = item.get("metadata", {})
        resolved.append(
            {
                "name": metadata.get("name"),
                "version": metadata.get("version"),
                "download_info": item.get("download_info", {}).get("url"),
            }
        )
    return {"status": "passed", "resolved_packages": resolved}


def run_one_dryrun(venv_name: str, execute: bool, timeout: int) -> dict[str, Any]:
    requirement_path = REQUIREMENT_FILES[venv_name]
    parsed = parse_requirement_file(requirement_path)
    report_path = pip_report_path(venv_name)
    command = build_pip_dryrun_command(venv_name, requirement_path, report_path)
    result: dict[str, Any] = {
        "venv": venv_name,
        "requirement_file": str(requirement_path),
        "pip_report": str(report_path),
        "command": command,
        "package_lines": parsed["package_lines"],
        "package_line_count": parsed["package_line_count"],
        "placeholder_errors": parsed["placeholder_errors"],
    }

    python_path = venv_python_path(venv_name)
    if not python_path.exists():
        result.update({"status": "skipped", "reason": "venv python missing"})
        return result
    if parsed["placeholder_errors"]:
        result.update({"status": "failed", "reason": "placeholder text found as package line"})
        return result
    if not execute:
        result.update({"status": "skipped", "reason": "execute_pip_dryrun flag not set"})
        return result

    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            env=safe_subprocess_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        result.update(
            {
                "status": "timeout",
                "returncode": None,
                "output": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            }
        )
        return result
    except Exception as exc:
        result.update({"status": "failed", "returncode": None, "output": f"{type(exc).__name__}: {exc}"})
        return result

    pip_report = parse_generated_pip_report(report_path)
    result.update(
        {
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "output": completed.stdout.strip(),
            "resolved_package_count": len(pip_report["resolved_packages"]),
            "resolved_packages": pip_report["resolved_packages"],
        }
    )
    return result


def selected_as_engine_count() -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return sum(1 for candidate in manifest.get("candidates", []) if candidate.get("selected_as_engine") is True)


def build_report(execute: bool = False, timeout: int = 120) -> dict[str, Any]:
    parsed_files = {venv: parse_requirement_file(path) for venv, path in REQUIREMENT_FILES.items()}
    results = [run_one_dryrun(venv, execute=execute, timeout=timeout) for venv in REQUIREMENT_FILES]
    passed_count = sum(1 for item in results if item["status"] == "passed")
    failed_count = sum(1 for item in results if item["status"] == "failed")
    skipped_count = sum(1 for item in results if item["status"] == "skipped")
    timeout_count = sum(1 for item in results if item["status"] == "timeout")
    placeholder_errors = [
        error
        for parsed in parsed_files.values()
        for error in parsed["placeholder_errors"]
    ]
    package_resolution_summary = {
        venv: {
            "package_line_count": parsed["package_line_count"],
            "package_lines": parsed["package_lines"],
            "lightweight_count": parsed["lightweight_count"],
            "medium_count": parsed["medium_count"],
        }
        for venv, parsed in parsed_files.items()
    }
    heavy_gpu_packages = sorted(
        {
            item
            for parsed in parsed_files.values()
            for item in parsed["heavy_gpu_packages_detected"]
        }
    )
    external_binary_notes = sorted(
        {
            item
            for parsed in parsed_files.values()
            for item in parsed["external_binary_notes"]
        }
    )
    selected_count = selected_as_engine_count()
    status = "passed" if failed_count == 0 and timeout_count == 0 and selected_count == 0 else "failed"
    return {
        "run_mode": "pip_dryrun_execute" if execute else "pip_dryrun_plan_only",
        "checked_requirement_files": [str(path) for path in REQUIREMENT_FILES.values()],
        "legacy_requirement_files": [str(path) for path in LEGACY_REQUIREMENT_FILES.values()],
        "legacy_venvs_skipped": {
            "stt": "legacy_stt_venv/deprecated_as_primary_runtime/do_not_delete_yet"
        },
        "dryrun_reports": results,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "timeout_count": timeout_count,
        "package_resolution_summary": package_resolution_summary,
        "placeholder_errors": placeholder_errors,
        "heavy_gpu_packages_detected": heavy_gpu_packages,
        "external_binary_notes": external_binary_notes,
        "install_executed": false_bool(),
        "model_download_executed": false_bool(),
        "selected_as_engine_count": selected_count,
        "status": status,
    }


def false_bool() -> bool:
    return False


def write_report(report: dict[str, Any], output_path: Path = REPORT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="MITAS pip dry-run report runner")
    parser.add_argument("--execute-pip-dryrun", action="store_true", help="Run pip install --dry-run --report commands.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    report = build_report(execute=args.execute_pip_dryrun, timeout=args.timeout)
    write_report(report, Path(args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
