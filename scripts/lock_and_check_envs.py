from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import yaml


ROOT = Path(r"E:\MITAS")
LOCK_DIR = ROOT / "locks"
REPORT_PATH = ROOT / "outputs" / "env_lock_health_report.json"
MANIFEST_PATH = ROOT / "model_manifest.yaml"

PRIMARY_VENV_NAMES = ["ocr", "asr", "face", "visual", "audio", "tag", "core"]
LEGACY_VENV_NAMES = ["stt"]
VENV_NAMES = [*PRIMARY_VENV_NAMES, *LEGACY_VENV_NAMES]
ASR_SUBMODULES = [
    "file_transcription",
    "streaming_transcription",
    "vad",
    "diarization",
    "alignment",
]

IMPORT_PLAN: dict[str, dict[str, str]] = {
    "ocr": {"numpy": "numpy", "PIL": "PIL", "cv2": "cv2"},
    "asr": {
        "numpy": "numpy",
        "soundfile": "soundfile",
        "librosa": "librosa",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "websockets": "websockets",
        "onnxruntime": "onnxruntime",
    },
    "face": {"numpy": "numpy", "PIL": "PIL", "cv2": "cv2"},
    "visual": {"numpy": "numpy", "PIL": "PIL", "cv2": "cv2"},
    "audio": {"numpy": "numpy", "soundfile": "soundfile", "librosa": "librosa", "pydub": "pydub"},
    "tag": {"pydantic": "pydantic", "rapidfuzz": "rapidfuzz", "regex": "regex", "yaml": "yaml"},
    "core": {"pydantic": "pydantic", "pytest": "pytest", "yaml": "yaml"},
    "stt": {"numpy": "numpy", "soundfile": "soundfile", "websockets": "websockets"},
}

FORBIDDEN_PACKAGES = {
    "torch",
    "torchaudio",
    "tensorflow",
    "onnxruntime-gpu",
    "whisperx",
    "faster-whisper",
    "paddleocr",
    "easyocr",
    "insightface",
    "ultralytics",
    "transformers",
}


def venv_python_path(venv_name: str) -> Path:
    return ROOT / "venvs" / venv_name / "Scripts" / "python.exe"


def safe_env() -> dict[str, str]:
    env = os.environ.copy()
    cache_dir = ROOT / "cache" / "pip"
    tmp_dir = ROOT / "tmp" / "env_lock_health"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    env["PIP_CACHE_DIR"] = str(cache_dir)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["TMP"] = str(tmp_dir)
    env["TEMP"] = str(tmp_dir)
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


def write_text_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("\n" if text and not text.endswith("\n") else ""), encoding="utf-8")


def freeze_venv(venv_name: str, timeout: int) -> dict[str, Any]:
    python_path = venv_python_path(venv_name)
    output_path = LOCK_DIR / f"{venv_name}.freeze.txt"
    if not python_path.exists():
        return {"venv": venv_name, "file": str(output_path), "status": "failed", "output": "venv python missing"}
    result = run_command([str(python_path), "-m", "pip", "freeze"], timeout=timeout)
    write_text_output(output_path, result["output"])
    return {"venv": venv_name, "file": str(output_path), **result}


def inspect_venv(venv_name: str, timeout: int) -> dict[str, Any]:
    python_path = venv_python_path(venv_name)
    output_path = LOCK_DIR / f"{venv_name}.inspect.json"
    if not python_path.exists():
        write_text_output(output_path, json.dumps({"error": "venv python missing"}, ensure_ascii=False, indent=2))
        return {"venv": venv_name, "file": str(output_path), "status": "failed", "output": "venv python missing"}
    result = run_command([str(python_path), "-m", "pip", "inspect"], timeout=timeout)
    write_text_output(output_path, result["output"])
    parsed_status = "not_parsed"
    installed_count = None
    parse_error = None
    if result["status"] == "passed":
        try:
            parsed = json.loads(result["output"])
            parsed_status = "passed"
            installed_count = len(parsed.get("installed", []))
        except Exception as exc:
            parsed_status = "failed"
            parse_error = f"{type(exc).__name__}: {exc}"
            result["status"] = "failed"
    return {
        "venv": venv_name,
        "file": str(output_path),
        "status": result["status"],
        "returncode": result["returncode"],
        "output": "inspect json written" if result["status"] == "passed" else result["output"],
        "json_parse_status": parsed_status,
        "installed_count": installed_count,
        "parse_error": parse_error,
    }


def pip_check_venv(venv_name: str, timeout: int) -> dict[str, Any]:
    python_path = venv_python_path(venv_name)
    if not python_path.exists():
        return {
            "venv": venv_name,
            "status": "failed",
            "returncode": None,
            "output": "venv python missing",
            "broken": True,
        }
    result = run_command([str(python_path), "-m", "pip", "check"], timeout=timeout)
    return {"venv": venv_name, **result, "broken": result["returncode"] != 0}


def import_smoke_for_venv(venv_name: str, imports: dict[str, str], timeout: int) -> dict[str, Any]:
    python_path = venv_python_path(venv_name)
    results: dict[str, Any] = {}
    for label, module_name in imports.items():
        code = (
            "import importlib, json\n"
            f"module_name = {module_name!r}\n"
            "try:\n"
            "    module = importlib.import_module(module_name)\n"
            "    version = getattr(module, '__version__', 'NO_VERSION_ATTR')\n"
            "    out = {'status': 'passed', 'version': str(version)}\n"
            "except Exception as exc:\n"
            "    out = {'status': 'failed', 'error': type(exc).__name__ + ': ' + str(exc)}\n"
            "print(json.dumps(out, ensure_ascii=False))\n"
        )
        result = run_command([str(python_path), "-c", code], timeout=timeout)
        if result["status"] == "passed":
            try:
                results[label] = json.loads(result["output"])
            except Exception as exc:
                results[label] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        else:
            results[label] = {"status": result["status"], "error": result["output"]}
    return {"venv": venv_name, "imports": results}


def forbidden_installed_for_venv(venv_name: str, timeout: int) -> dict[str, Any]:
    python_path = venv_python_path(venv_name)
    code = (
        "import importlib.metadata as md, json\n"
        f"forbidden = {sorted(FORBIDDEN_PACKAGES)!r}\n"
        "installed = {dist.metadata.get('Name', '').lower(): dist.version for dist in md.distributions()}\n"
        "present = {name: installed.get(name) for name in forbidden if installed.get(name)}\n"
        "print(json.dumps(present, ensure_ascii=False))\n"
    )
    result = run_command([str(python_path), "-c", code], timeout=timeout)
    if result["status"] != "passed":
        return {"venv": venv_name, "status": result["status"], "present": {}, "error": result["output"]}
    try:
        present = json.loads(result["output"])
    except Exception as exc:
        return {"venv": venv_name, "status": "failed", "present": {}, "error": f"{type(exc).__name__}: {exc}"}
    return {"venv": venv_name, "status": "passed", "present": present}


def selected_as_engine_count() -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return sum(1 for candidate in manifest.get("candidates", []) if candidate.get("selected_as_engine") is True)


def build_report(timeout: int = 120) -> dict[str, Any]:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    freeze_results = [freeze_venv(venv, timeout=timeout) for venv in VENV_NAMES]
    inspect_results = [inspect_venv(venv, timeout=timeout) for venv in VENV_NAMES]
    pip_check_results = [pip_check_venv(venv, timeout=timeout) for venv in VENV_NAMES]
    import_smoke_results = [
        import_smoke_for_venv(venv, IMPORT_PLAN[venv], timeout=60) for venv in VENV_NAMES
    ]
    forbidden_checks = {venv: forbidden_installed_for_venv(venv, timeout=60) for venv in VENV_NAMES}
    failed_imports = []
    for venv_result in import_smoke_results:
        for label, result in venv_result["imports"].items():
            if result["status"] != "passed":
                failed_imports.append({"venv": venv_result["venv"], "import": label, **result})
    forbidden_present = {
        venv: result["present"]
        for venv, result in forbidden_checks.items()
        if result.get("present")
    }
    broken_dependency_count = sum(1 for item in pip_check_results if item["broken"])
    selected_count = selected_as_engine_count()
    heavy_packages_installed = bool(forbidden_present)
    status = "passed"
    if any(item["status"] != "passed" for item in freeze_results):
        status = "failed"
    if any(item["status"] != "passed" for item in inspect_results):
        status = "failed"
    if broken_dependency_count:
        status = "failed"
    if failed_imports:
        status = "failed"
    if heavy_packages_installed or selected_count != 0:
        status = "failed"
    return {
        "primary_venvs": PRIMARY_VENV_NAMES,
        "legacy_venvs": LEGACY_VENV_NAMES,
        "venv_status": {
            **{name: "active_primary_runtime" for name in PRIMARY_VENV_NAMES},
            "stt": "legacy_stt_venv/deprecated_as_primary_runtime/do_not_delete_yet",
        },
        "asr_submodules": ASR_SUBMODULES,
        "checked_venvs": VENV_NAMES,
        "freeze_files": {item["venv"]: item["file"] for item in freeze_results},
        "inspect_files": {item["venv"]: item["file"] for item in inspect_results},
        "freeze_results": freeze_results,
        "inspect_results": inspect_results,
        "pip_check_results": pip_check_results,
        "import_smoke_results": import_smoke_results,
        "broken_dependency_count": broken_dependency_count,
        "heavy_packages_installed": heavy_packages_installed,
        "forbidden_package_presence": forbidden_present,
        "model_download_executed": False,
        "benchmark_executed": False,
        "selected_as_engine_count": selected_count,
        "failed_imports": failed_imports,
        "status": status,
    }


def write_report(report: dict[str, Any], output_path: Path = REPORT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="MITAS environment lock and health check")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    report = build_report(timeout=args.timeout)
    write_report(report, Path(args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
