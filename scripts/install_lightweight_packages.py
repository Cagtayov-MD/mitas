from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import yaml


ROOT = Path(r"E:\MITAS")
MANIFEST_PATH = ROOT / "model_manifest.yaml"
REPORT_PATH = ROOT / "outputs" / "lightweight_install_report.json"

INSTALL_PLAN: dict[str, list[str]] = {
    "ocr": ["numpy", "pillow", "opencv-python"],
    "asr": [
        "numpy",
        "soundfile",
        "librosa",
        "fastapi==0.136.1",
        "uvicorn==0.46.0",
        "websockets==16.0",
        "onnxruntime==1.23.2",
    ],
    "audio": ["numpy", "soundfile", "librosa", "pydub"],
    "tag": ["pydantic", "rapidfuzz", "regex", "pyyaml"],
    "face": ["numpy", "pillow", "opencv-python"],
    "visual": ["numpy", "pillow", "opencv-python"],
}

LEGACY_VENV_STATUS = {
    "stt": "legacy_stt_venv/deprecated_as_primary_runtime/do_not_delete_yet",
}

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
    "audio": {"numpy": "numpy", "soundfile": "soundfile", "librosa": "librosa", "pydub": "pydub"},
    "tag": {"pydantic": "pydantic", "rapidfuzz": "rapidfuzz", "regex": "regex", "yaml": "yaml"},
    "face": {"numpy": "numpy", "PIL": "PIL", "cv2": "cv2"},
    "visual": {"numpy": "numpy", "PIL": "PIL", "cv2": "cv2"},
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
    tmp_dir = ROOT / "tmp" / "pip_install_lightweight"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    env["PIP_CACHE_DIR"] = str(cache_dir)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env["TMP"] = str(tmp_dir)
    env["TEMP"] = str(tmp_dir)
    return env


def validate_install_plan() -> None:
    requested = {
        normalized_package_name(package)
        for packages in INSTALL_PLAN.values()
        for package in packages
    }
    forbidden_requested = sorted(requested & FORBIDDEN_PACKAGES)
    if forbidden_requested:
        raise ValueError(f"Forbidden heavy packages in lightweight install plan: {forbidden_requested}")


def normalized_package_name(requirement: str) -> str:
    token = requirement.split(";", 1)[0].strip()
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
        if separator in token:
            token = token.split(separator, 1)[0]
    return token.strip().lower().replace("_", "-")


def run_command(args: list[str], timeout: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
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


def install_for_venv(venv_name: str, packages: list[str], timeout: int) -> dict[str, Any]:
    python_path = venv_python_path(venv_name)
    command = [str(python_path), "-m", "pip", "install", *packages]
    if not python_path.exists():
        return {
            "venv": venv_name,
            "packages": packages,
            "command": command,
            "status": "failed",
            "returncode": None,
            "output": "venv python missing",
        }
    result = run_command(command, timeout=timeout, env=safe_env())
    return {"venv": venv_name, "packages": packages, "command": command, **result}


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
        result = run_command([str(python_path), "-c", code], timeout=timeout, env=safe_env())
        if result["status"] == "passed":
            try:
                results[label] = json.loads(result["output"])
            except Exception as exc:
                results[label] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        else:
            results[label] = {"status": result["status"], "error": result["output"]}
    return {"venv": venv_name, "imports": results}


def selected_as_engine_count() -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return sum(1 for candidate in manifest.get("candidates", []) if candidate.get("selected_as_engine") is True)


def forbidden_installed_for_venv(venv_name: str, timeout: int) -> dict[str, Any]:
    python_path = venv_python_path(venv_name)
    code = (
        "import importlib.metadata as md, json\n"
        f"forbidden = {sorted(FORBIDDEN_PACKAGES)!r}\n"
        "installed = {dist.metadata.get('Name', '').lower(): dist.version for dist in md.distributions()}\n"
        "present = {name: installed.get(name) for name in forbidden if installed.get(name)}\n"
        "print(json.dumps(present, ensure_ascii=False))\n"
    )
    result = run_command([str(python_path), "-c", code], timeout=timeout, env=safe_env())
    if result["status"] != "passed":
        return {"status": result["status"], "error": result["output"], "present": {}}
    try:
        present = json.loads(result["output"])
    except Exception as exc:
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "present": {}}
    return {"status": "passed", "present": present}


def build_report(timeout: int = 300) -> dict[str, Any]:
    validate_install_plan()
    venv_results = [install_for_venv(venv_name, packages, timeout=timeout) for venv_name, packages in INSTALL_PLAN.items()]
    import_smoke_results = [
        import_smoke_for_venv(venv_name, imports, timeout=60) for venv_name, imports in IMPORT_PLAN.items()
    ]
    forbidden_checks = {
        venv_name: forbidden_installed_for_venv(venv_name, timeout=60) for venv_name in INSTALL_PLAN
    }
    failed_installs = [
        {"venv": item["venv"], "status": item["status"], "returncode": item.get("returncode"), "output": item.get("output", "")}
        for item in venv_results
        if item["status"] != "passed"
    ]
    failed_imports = []
    for venv_result in import_smoke_results:
        for label, result in venv_result["imports"].items():
            if result["status"] != "passed":
                failed_imports.append({"venv": venv_result["venv"], "import": label, **result})
    forbidden_present = {
        venv_name: result["present"]
        for venv_name, result in forbidden_checks.items()
        if result.get("present")
    }
    selected_count = selected_as_engine_count()
    heavy_packages_installed = bool(forbidden_present)
    status = (
        "passed"
        if not failed_installs and not failed_imports and not heavy_packages_installed and selected_count == 0
        else "failed"
    )
    return {
        "install_executed": True,
        "legacy_venv_status": LEGACY_VENV_STATUS,
        "heavy_packages_installed": heavy_packages_installed,
        "forbidden_package_presence": forbidden_present,
        "model_download_executed": False,
        "benchmark_executed": False,
        "selected_as_engine_count": selected_count,
        "venv_results": venv_results,
        "import_smoke_results": import_smoke_results,
        "failed_installs": failed_installs,
        "failed_imports": failed_imports,
        "status": status,
    }


def write_report(report: dict[str, Any], output_path: Path = REPORT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="MITAS lightweight package installer")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    report = build_report(timeout=args.timeout)
    write_report(report, Path(args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
