from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import yaml


ROOT = Path(r"E:\MITAS")
TARGET_VENV = ROOT / "venvs" / "asr"
TARGET_PYTHON = TARGET_VENV / "Scripts" / "python.exe"
LOCK_DIR = ROOT / "locks"
FREEZE_FILE = LOCK_DIR / "asr.faster_whisper.freeze.txt"
INSPECT_FILE = LOCK_DIR / "asr.faster_whisper.inspect.json"
REPORT_PATH = ROOT / "outputs" / "faster_whisper_smoke_report.json"
MANIFEST_PATH = ROOT / "model_manifest.yaml"
INSTALL_PACKAGES = ["faster-whisper"]


def safe_env() -> dict[str, str]:
    env = os.environ.copy()
    cache_dir = ROOT / "cache" / "pip"
    tmp_dir = ROOT / "tmp" / "faster_whisper_install"
    hf_home = ROOT / "cache" / "huggingface"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    hf_home.mkdir(parents=True, exist_ok=True)
    env["PIP_CACHE_DIR"] = str(cache_dir)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env["TMP"] = str(tmp_dir)
    env["TEMP"] = str(tmp_dir)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["HF_HOME"] = str(hf_home)
    env["HF_HUB_CACHE"] = str(hf_home / "hub")
    env["HUGGINGFACE_HUB_CACHE"] = str(hf_home / "hub")
    env["TRANSFORMERS_CACHE"] = str(hf_home / "transformers")
    return env


def run_command(args: list[str], timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            env=safe_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "output": completed.stdout.strip(),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "returncode": None,
            "output": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
        }
    except Exception as exc:
        return {
            "status": "failed",
            "returncode": None,
            "output": f"{type(exc).__name__}: {exc}",
        }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("\n" if text and not text.endswith("\n") else ""), encoding="utf-8")


def selected_as_engine_count() -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return sum(1 for candidate in manifest.get("candidates", []) if candidate.get("selected_as_engine") is True)


def install_faster_whisper(timeout: int) -> dict[str, Any]:
    command = [str(TARGET_PYTHON), "-m", "pip", "install", *INSTALL_PACKAGES]
    if not TARGET_PYTHON.exists():
        return {"command": command, "status": "failed", "returncode": None, "output": "ASR venv python missing"}
    result = run_command(command, timeout=timeout)
    return {"command": command, **result}


def pip_freeze(timeout: int) -> dict[str, Any]:
    result = run_command([str(TARGET_PYTHON), "-m", "pip", "freeze"], timeout=timeout)
    write_text(FREEZE_FILE, result["output"])
    return {"file": str(FREEZE_FILE), **result}


def pip_inspect(timeout: int) -> dict[str, Any]:
    result = run_command([str(TARGET_PYTHON), "-m", "pip", "inspect"], timeout=timeout)
    write_text(INSPECT_FILE, result["output"])
    parse_status = "not_parsed"
    installed_count = None
    parse_error = None
    if result["status"] == "passed":
        try:
            parsed = json.loads(result["output"])
            parse_status = "passed"
            installed_count = len(parsed.get("installed", []))
        except Exception as exc:
            result["status"] = "failed"
            parse_status = "failed"
            parse_error = f"{type(exc).__name__}: {exc}"
    return {
        "file": str(INSPECT_FILE),
        "status": result["status"],
        "returncode": result["returncode"],
        "output": "inspect json written" if result["status"] == "passed" else result["output"],
        "json_parse_status": parse_status,
        "installed_count": installed_count,
        "parse_error": parse_error,
    }


def pip_check(timeout: int) -> dict[str, Any]:
    return run_command([str(TARGET_PYTHON), "-m", "pip", "check"], timeout=timeout)


def smoke_test(timeout: int) -> dict[str, Any]:
    code = r"""
import importlib
import importlib.metadata as md
import json

out = {
    "faster_whisper_installed": False,
    "faster_whisper_version": None,
    "ctranslate2_installed": False,
    "ctranslate2_version": None,
    "ctranslate2_cuda_device_count": None,
    "ctranslate2_cuda_compute_types": None,
    "ctranslate2_cpu_compute_types": None,
    "model_instantiated": False,
    "model_download_executed": False,
    "audio_video_processed": False,
    "errors": [],
}

try:
    faster_whisper = importlib.import_module("faster_whisper")
    out["faster_whisper_installed"] = True
    out["faster_whisper_version"] = getattr(faster_whisper, "__version__", None) or md.version("faster-whisper")
except Exception as exc:
    out["errors"].append("faster_whisper_import: " + type(exc).__name__ + ": " + str(exc))

try:
    ctranslate2 = importlib.import_module("ctranslate2")
    out["ctranslate2_installed"] = True
    out["ctranslate2_version"] = getattr(ctranslate2, "__version__", None) or md.version("ctranslate2")
    try:
        out["ctranslate2_cuda_device_count"] = int(ctranslate2.get_cuda_device_count())
    except AttributeError:
        out["errors"].append("ctranslate2_get_cuda_device_count: missing")
    except Exception as exc:
        out["errors"].append("ctranslate2_get_cuda_device_count: " + type(exc).__name__ + ": " + str(exc))
    try:
        out["ctranslate2_cuda_compute_types"] = list(ctranslate2.get_supported_compute_types("cuda"))
    except AttributeError:
        out["errors"].append("ctranslate2_cuda_compute_types: missing")
    except Exception as exc:
        out["errors"].append("ctranslate2_cuda_compute_types: " + type(exc).__name__ + ": " + str(exc))
    try:
        out["ctranslate2_cpu_compute_types"] = list(ctranslate2.get_supported_compute_types("cpu"))
    except AttributeError:
        out["errors"].append("ctranslate2_cpu_compute_types: missing")
    except Exception as exc:
        out["errors"].append("ctranslate2_cpu_compute_types: " + type(exc).__name__ + ": " + str(exc))
except Exception as exc:
    out["errors"].append("ctranslate2_import: " + type(exc).__name__ + ": " + str(exc))

print(json.dumps(out, ensure_ascii=False))
"""
    result = run_command([str(TARGET_PYTHON), "-c", code], timeout=timeout)
    if result["status"] != "passed":
        return {"status": result["status"], "errors": [result["output"]]}
    try:
        parsed = json.loads(result["output"])
    except Exception as exc:
        return {"status": "failed", "errors": [f"{type(exc).__name__}: {exc}"], "raw_output": result["output"]}
    parsed["status"] = "passed" if parsed["faster_whisper_installed"] and parsed["ctranslate2_installed"] else "failed"
    return parsed


def build_report(timeout: int = 600) -> dict[str, Any]:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    install_result = install_faster_whisper(timeout=timeout)
    smoke = smoke_test(timeout=120) if install_result["status"] == "passed" else {"status": "failed", "errors": [install_result["output"]]}
    check_result = pip_check(timeout=120)
    freeze_result = pip_freeze(timeout=120)
    inspect_result = pip_inspect(timeout=120)
    selected_count = selected_as_engine_count()
    status = "passed"
    if install_result["status"] != "passed":
        status = "failed"
    if smoke.get("status") != "passed":
        status = "failed"
    if check_result["status"] != "passed":
        status = "failed"
    if freeze_result["status"] != "passed" or inspect_result["status"] != "passed":
        status = "failed"
    if selected_count != 0:
        status = "failed"
    if status == "passed" and smoke.get("ctranslate2_cuda_compute_types") is None:
        status = "needs_review"

    return {
        "target_venv": str(TARGET_VENV),
        "install_executed": True,
        "install_result": install_result,
        "installed_packages": INSTALL_PACKAGES,
        "faster_whisper_installed": bool(smoke.get("faster_whisper_installed")),
        "faster_whisper_version": smoke.get("faster_whisper_version"),
        "ctranslate2_installed": bool(smoke.get("ctranslate2_installed")),
        "ctranslate2_version": smoke.get("ctranslate2_version"),
        "ctranslate2_cuda_device_count": smoke.get("ctranslate2_cuda_device_count"),
        "ctranslate2_cuda_compute_types": smoke.get("ctranslate2_cuda_compute_types"),
        "ctranslate2_cpu_compute_types": smoke.get("ctranslate2_cpu_compute_types"),
        "model_instantiated": False,
        "model_download_executed": False,
        "audio_video_processed": False,
        "benchmark_executed": False,
        "pip_check_status": check_result["status"],
        "pip_check_output": check_result["output"],
        "freeze_file": str(FREEZE_FILE),
        "freeze_status": freeze_result["status"],
        "inspect_file": str(INSPECT_FILE),
        "inspect_status": inspect_result["status"],
        "inspect_json_parse_status": inspect_result["json_parse_status"],
        "smoke_errors": smoke.get("errors", []),
        "selected_as_engine_count": selected_count,
        "status": status,
    }


def write_report(report: dict[str, Any], output_path: Path = REPORT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install faster-whisper in ASR venv and run import smoke")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    report = build_report(timeout=args.timeout)
    write_report(report, Path(args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"passed", "needs_review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
