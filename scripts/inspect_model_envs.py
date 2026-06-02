from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import yaml


ROOT = Path(r"E:\MITAS")
MANIFEST_PATH = ROOT / "model_manifest.yaml"
REPORT_PATH = ROOT / "outputs" / "model_env_inventory_report.json"

ACTIVE_VENV_NAMES = ["core", "ocr", "asr", "face", "visual", "audio", "tag"]
LEGACY_VENV_NAMES = ["stt"]
VENV_NAMES = [*ACTIVE_VENV_NAMES, *LEGACY_VENV_NAMES]
ASR_SUBMODULES = [
    "file_transcription",
    "streaming_transcription",
    "vad",
    "diarization",
    "alignment",
]
IMPORTANT_PACKAGES = [
    "pydantic",
    "pytest",
    "PyYAML",
    "torch",
    "torchaudio",
    "torchvision",
    "paddleocr",
    "paddlepaddle",
    "ctranslate2",
    "faster-whisper",
    "whisperx",
    "silero-vad",
    "pyannote.audio",
    "insightface",
    "onnxruntime",
    "onnxruntime-gpu",
    "fastapi",
    "uvicorn",
    "websockets",
    "supervision",
    "ultralytics",
    "transformers",
]
BINARY_TOOLS = ["fpcalc", "chromaprint", "tesseract"]


def run_checked(args: list[str], timeout: int = 10) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
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


def venv_python_path(venv_name: str) -> Path:
    return ROOT / "venvs" / venv_name / "Scripts" / "python.exe"


def inspect_packages(python_path: Path) -> dict[str, Any]:
    code = (
        "import importlib.metadata as md, json\n"
        "important = " + repr(IMPORTANT_PACKAGES) + "\n"
        "installed = {}\n"
        "for dist in md.distributions():\n"
        "    name = dist.metadata.get('Name', '').lower()\n"
        "    if name:\n"
        "        installed[name] = dist.version\n"
        "presence = {name: installed.get(name.lower()) for name in important}\n"
        "print(json.dumps({'package_count': len(installed), 'important_packages': presence}, ensure_ascii=False))\n"
    )
    result = run_checked([str(python_path), "-c", code], timeout=15)
    if result["status"] != "passed":
        return {"status": result["status"], "error": result["output"], "package_count": 0, "important_packages": {}}
    try:
        parsed = json.loads(result["output"])
        parsed["status"] = "passed"
        return parsed
    except Exception as exc:
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "package_count": 0, "important_packages": {}}


def inspect_torch(python_path: Path) -> dict[str, Any]:
    code = (
        "import json\n"
        "try:\n"
        "    import torch\n"
        "    out = {\n"
        "        'status': 'installed',\n"
        "        'torch_version': getattr(torch, '__version__', 'unknown'),\n"
        "        'cuda_available': bool(torch.cuda.is_available()),\n"
        "        'cuda_device_count': int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,\n"
        "        'cuda_device_name': torch.cuda.get_device_name(0) if torch.cuda.is_available() and torch.cuda.device_count() else None,\n"
        "    }\n"
        "except ModuleNotFoundError:\n"
        "    out = {'status': 'missing'}\n"
        "except Exception as exc:\n"
        "    out = {'status': 'failed', 'error': type(exc).__name__ + ': ' + str(exc)}\n"
        "print(json.dumps(out, ensure_ascii=False))\n"
    )
    result = run_checked([str(python_path), "-c", code], timeout=15)
    if result["status"] != "passed":
        return {"status": result["status"], "error": result["output"]}
    try:
        return json.loads(result["output"])
    except Exception as exc:
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def inspect_venvs() -> dict[str, Any]:
    checked_venvs: list[dict[str, Any]] = []
    existing_venvs: list[str] = []
    missing_venvs: list[str] = []
    python_versions: dict[str, Any] = {}
    package_presence: dict[str, Any] = {}
    torch_status: dict[str, Any] = {}
    cuda_status: dict[str, Any] = {}

    for name in VENV_NAMES:
        venv_path = ROOT / "venvs" / name
        python_path = venv_python_path(name)
        item = {
            "name": name,
            "path": str(venv_path),
            "exists": venv_path.exists(),
            "python_exists": python_path.exists(),
            "python_path": str(python_path),
        }
        checked_venvs.append(item)
        if not venv_path.exists() or not python_path.exists():
            missing_venvs.append(name)
            python_versions[name] = {"status": "missing"}
            package_presence[name] = {"status": "missing"}
            torch_status[name] = {"status": "missing"}
            cuda_status[name] = {"status": "missing"}
            continue

        existing_venvs.append(name)
        version_result = run_checked([str(python_path), "--version"], timeout=10)
        python_versions[name] = version_result
        package_presence[name] = inspect_packages(python_path)
        torch_status[name] = inspect_torch(python_path)
        cuda_status[name] = {
            "status": torch_status[name].get("status"),
            "cuda_available": torch_status[name].get("cuda_available"),
            "cuda_device_count": torch_status[name].get("cuda_device_count"),
            "cuda_device_name": torch_status[name].get("cuda_device_name"),
        }

    return {
        "active_venvs": ACTIVE_VENV_NAMES,
        "legacy_venvs": LEGACY_VENV_NAMES,
        "venv_status": {
            **{name: "active_primary_runtime" for name in ACTIVE_VENV_NAMES},
            "stt": "legacy_stt_venv/deprecated_as_primary_runtime/do_not_delete_yet",
        },
        "asr_submodules": ASR_SUBMODULES,
        "checked_venvs": checked_venvs,
        "existing_venvs": existing_venvs,
        "missing_venvs": missing_venvs,
        "python_versions": python_versions,
        "package_presence": package_presence,
        "torch_status": torch_status,
        "cuda_status": cuda_status,
    }


def inspect_binary_tools() -> dict[str, Any]:
    return {
        tool: {
            "status": "available" if shutil.which(tool) else "missing",
            "path": shutil.which(tool),
        }
        for tool in BINARY_TOOLS
    }


def load_manifest() -> dict[str, Any]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("model_manifest.yaml root must be a mapping")
    if not isinstance(data.get("candidates"), list):
        raise ValueError("model_manifest.yaml candidates must be a list")
    return data


def primary_venv_name(venv: str) -> str | None:
    if not venv or venv == "none":
        return None
    if venv.startswith("system_or_"):
        return None
    if "_or_" in venv:
        return venv.split("_or_", 1)[0]
    return venv


def command_is_tbd(command: str) -> bool:
    return not command.strip() or command.strip().upper().startswith("TBD")


def binary_for_command(command: str) -> str | None:
    first = command.strip().split(maxsplit=1)[0] if command.strip() else ""
    if first in {"fpcalc", "tesseract", "chromaprint"}:
        return first
    return None


def inspect_manifest(existing_venvs: list[str], binary_tools: dict[str, Any]) -> dict[str, Any]:
    manifest = load_manifest()
    candidates = manifest["candidates"]
    seen = []
    tbd = []
    ready = []
    selected_count = 0
    module_counts = Counter()

    for candidate in candidates:
        module_area = candidate.get("module_area", "")
        candidate_name = candidate.get("candidate_name", "")
        command = str(candidate.get("smoke_test_command", ""))
        venv = str(candidate.get("venv", ""))
        seen.append({"module_area": module_area, "candidate_name": candidate_name})
        module_counts[module_area] += 1
        if candidate.get("selected_as_engine") is True:
            selected_count += 1
        if command_is_tbd(command):
            tbd.append({"module_area": module_area, "candidate_name": candidate_name, "smoke_test_command": command})
            continue

        binary = binary_for_command(command)
        if binary:
            if binary_tools.get(binary, {}).get("status") == "available":
                ready.append({"module_area": module_area, "candidate_name": candidate_name, "reason": f"{binary} available"})
            continue

        primary = primary_venv_name(venv)
        if primary and primary in existing_venvs:
            ready.append({"module_area": module_area, "candidate_name": candidate_name, "reason": f"venv {primary} available"})

    return {
        "manifest_candidates_seen": {"count": len(seen), "items": seen},
        "manifest_candidates_with_tbd_smoke_command": {"count": len(tbd), "items": tbd},
        "manifest_candidates_ready_for_real_smoke": {"count": len(ready), "items": ready},
        "manifest_module_area_counts": dict(sorted(module_counts.items())),
        "selected_as_engine_count": selected_count,
    }


def build_report() -> dict[str, Any]:
    venv_report = inspect_venvs()
    binary_tools = inspect_binary_tools()
    manifest_report = inspect_manifest(venv_report["existing_venvs"], binary_tools)
    status = "passed" if manifest_report["selected_as_engine_count"] == 0 else "failed"
    return {
        **venv_report,
        "binary_tools": binary_tools,
        **manifest_report,
        "status": status,
    }


def write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    report = build_report()
    write_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
