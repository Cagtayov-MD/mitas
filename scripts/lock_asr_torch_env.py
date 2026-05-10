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
FREEZE_FILE = LOCK_DIR / "asr.torch.freeze.txt"
INSPECT_FILE = LOCK_DIR / "asr.torch.inspect.json"
REPORT_PATH = ROOT / "outputs" / "asr_torch_env_lock_report.json"
MANIFEST_PATH = ROOT / "model_manifest.yaml"


def safe_env() -> dict[str, str]:
    env = os.environ.copy()
    cache_dir = ROOT / "cache" / "pip"
    tmp_dir = ROOT / "tmp" / "asr_torch_lock"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    env["PIP_CACHE_DIR"] = str(cache_dir)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env["TMP"] = str(tmp_dir)
    env["TEMP"] = str(tmp_dir)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
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


def package_presence() -> dict[str, bool]:
    code = (
        "import importlib.metadata as md, json\n"
        "names = {'faster-whisper': False, 'whisperx': False, 'ctranslate2': False}\n"
        "installed = {dist.metadata.get('Name', '').lower() for dist in md.distributions()}\n"
        "for name in names:\n"
        "    names[name] = name in installed\n"
        "print(json.dumps(names, ensure_ascii=False))\n"
    )
    result = run_command([str(TARGET_PYTHON), "-c", code], timeout=30)
    if result["status"] != "passed":
        return {"faster-whisper": True, "whisperx": True, "ctranslate2": True}
    return json.loads(result["output"])


def pip_freeze(timeout: int) -> dict[str, Any]:
    result = run_command([str(TARGET_PYTHON), "-m", "pip", "freeze"], timeout=timeout)
    write_text(FREEZE_FILE, result["output"])
    return {"file": str(FREEZE_FILE), **result}


def pip_inspect(timeout: int) -> dict[str, Any]:
    result = run_command([str(TARGET_PYTHON), "-m", "pip", "inspect"], timeout=timeout)
    write_text(INSPECT_FILE, result["output"])
    installed_count = None
    parse_status = "not_parsed"
    parse_error = None
    if result["status"] == "passed":
        try:
            parsed = json.loads(result["output"])
            installed_count = len(parsed.get("installed", []))
            parse_status = "passed"
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


def torch_cuda_smoke(timeout: int) -> dict[str, Any]:
    code = r"""
import json

out = {
    "torch_version": None,
    "torchaudio_version": None,
    "torch_cuda_version": None,
    "cuda_available": False,
    "cuda_device_count": 0,
    "cuda_device_name": None,
    "cuda_tensor_test": "failed",
    "vram_total_mb": None,
    "vram_free_mb": None,
    "errors": [],
}

try:
    import torch
    out["torch_version"] = getattr(torch, "__version__", None)
    out["torch_cuda_version"] = getattr(torch.version, "cuda", None)
    out["cuda_available"] = bool(torch.cuda.is_available())
    out["cuda_device_count"] = int(torch.cuda.device_count()) if out["cuda_available"] else 0
    if out["cuda_available"] and out["cuda_device_count"] > 0:
        out["cuda_device_name"] = torch.cuda.get_device_name(0)
        try:
            free_bytes, total_bytes = torch.cuda.mem_get_info()
            out["vram_free_mb"] = int(free_bytes // (1024 * 1024))
            out["vram_total_mb"] = int(total_bytes // (1024 * 1024))
        except Exception as exc:
            out["errors"].append("mem_get_info: " + type(exc).__name__ + ": " + str(exc))
        try:
            tensor = torch.tensor([1.0, 2.0, 3.0], device="cuda")
            out["cuda_tensor_test"] = "passed" if float(tensor.sum().item()) == 6.0 else "failed"
        except Exception as exc:
            out["errors"].append("cuda_tensor_test: " + type(exc).__name__ + ": " + str(exc))
except Exception as exc:
    out["errors"].append("torch_import: " + type(exc).__name__ + ": " + str(exc))

try:
    import torchaudio
    out["torchaudio_version"] = getattr(torchaudio, "__version__", None)
except Exception as exc:
    out["errors"].append("torchaudio_import: " + type(exc).__name__ + ": " + str(exc))

print(json.dumps(out, ensure_ascii=False))
"""
    result = run_command([str(TARGET_PYTHON), "-c", code], timeout=timeout)
    if result["status"] != "passed":
        return {"status": result["status"], "errors": [result["output"]]}
    try:
        parsed = json.loads(result["output"])
    except Exception as exc:
        return {"status": "failed", "errors": [f"{type(exc).__name__}: {exc}"], "raw_output": result["output"]}
    parsed["status"] = "passed" if parsed.get("cuda_available") and parsed.get("cuda_tensor_test") == "passed" else "failed"
    return parsed


def build_report(timeout: int = 120) -> dict[str, Any]:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    freeze_result = pip_freeze(timeout=timeout)
    inspect_result = pip_inspect(timeout=timeout)
    check_result = pip_check(timeout=timeout)
    smoke = torch_cuda_smoke(timeout=timeout)
    packages = package_presence()
    selected_count = selected_as_engine_count()
    faster_whisper_installed = bool(packages.get("faster-whisper"))
    whisperx_installed = bool(packages.get("whisperx"))
    ctranslate2_installed = bool(packages.get("ctranslate2"))

    status = "passed"
    if freeze_result["status"] != "passed":
        status = "failed"
    if inspect_result["status"] != "passed":
        status = "failed"
    if check_result["status"] != "passed":
        status = "failed"
    if smoke.get("status") != "passed":
        status = "failed"
    if faster_whisper_installed or whisperx_installed or ctranslate2_installed:
        status = "failed"
    if selected_count != 0:
        status = "failed"

    return {
        "target_venv": str(TARGET_VENV),
        "freeze_file": str(FREEZE_FILE),
        "inspect_file": str(INSPECT_FILE),
        "freeze_status": freeze_result["status"],
        "inspect_status": inspect_result["status"],
        "inspect_json_parse_status": inspect_result["json_parse_status"],
        "pip_check_status": check_result["status"],
        "pip_check_output": check_result["output"],
        "torch_version": smoke.get("torch_version"),
        "torchaudio_version": smoke.get("torchaudio_version"),
        "torch_cuda_version": smoke.get("torch_cuda_version"),
        "cuda_available": bool(smoke.get("cuda_available")),
        "cuda_device_count": smoke.get("cuda_device_count", 0),
        "cuda_device_name": smoke.get("cuda_device_name"),
        "cuda_tensor_test": smoke.get("cuda_tensor_test", "failed"),
        "vram_total_mb": smoke.get("vram_total_mb"),
        "vram_free_mb": smoke.get("vram_free_mb"),
        "smoke_errors": smoke.get("errors", []),
        "faster_whisper_installed": faster_whisper_installed,
        "whisperx_installed": whisperx_installed,
        "ctranslate2_installed": ctranslate2_installed,
        "model_download_executed": False,
        "benchmark_executed": False,
        "selected_as_engine_count": selected_count,
        "status": status,
    }


def write_report(report: dict[str, Any], output_path: Path = REPORT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Lock ASR torch environment and run CUDA health check")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    report = build_report(timeout=args.timeout)
    write_report(report, Path(args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
