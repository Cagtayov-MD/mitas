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
MANIFEST_PATH = ROOT / "model_manifest.yaml"
REPORT_PATH = ROOT / "outputs" / "torch_cuda_asr_smoke_report.json"
PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu126"
INSTALL_PACKAGES = ["torch", "torchaudio"]


def safe_env() -> dict[str, str]:
    env = os.environ.copy()
    cache_dir = ROOT / "cache" / "pip"
    tmp_dir = ROOT / "tmp" / "torch_cuda_asr"
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


def selected_as_engine_count() -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return sum(1 for candidate in manifest.get("candidates", []) if candidate.get("selected_as_engine") is True)


def install_torch(timeout: int) -> dict[str, Any]:
    command = [
        str(TARGET_PYTHON),
        "-m",
        "pip",
        "install",
        *INSTALL_PACKAGES,
        "--index-url",
        PYTORCH_INDEX_URL,
    ]
    if not TARGET_PYTHON.exists():
        return {
            "status": "failed",
            "returncode": None,
            "output": "ASR venv python missing",
            "command": command,
        }
    result = run_command(command, timeout=timeout)
    return {"command": command, **result}


def smoke_test(timeout: int) -> dict[str, Any]:
    code = r"""
import json

out = {
    "torch_import_ok": False,
    "torchaudio_import_ok": False,
    "torch_version": None,
    "torchaudio_version": None,
    "torch_cuda_version": None,
    "cuda_available": False,
    "cuda_device_count": 0,
    "cuda_device_name": None,
    "cuda_tensor_test": False,
    "vram_total_mb": None,
    "vram_free_mb": None,
    "errors": [],
}

try:
    import torch
    out["torch_import_ok"] = True
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
            out["cuda_tensor_test"] = bool(float(tensor.sum().item()) == 6.0)
        except Exception as exc:
            out["errors"].append("cuda_tensor_test: " + type(exc).__name__ + ": " + str(exc))
except Exception as exc:
    out["errors"].append("torch_import: " + type(exc).__name__ + ": " + str(exc))

try:
    import torchaudio
    out["torchaudio_import_ok"] = True
    out["torchaudio_version"] = getattr(torchaudio, "__version__", None)
except Exception as exc:
    out["errors"].append("torchaudio_import: " + type(exc).__name__ + ": " + str(exc))

print(json.dumps(out, ensure_ascii=False))
"""
    result = run_command([str(TARGET_PYTHON), "-c", code], timeout=timeout)
    if result["status"] != "passed":
        return {"status": result["status"], "error": result["output"]}
    try:
        parsed = json.loads(result["output"])
    except Exception as exc:
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "raw_output": result["output"]}
    parsed["status"] = "passed" if parsed["torch_import_ok"] and parsed["torchaudio_import_ok"] else "failed"
    return parsed


def build_report(timeout: int = 1200) -> dict[str, Any]:
    install_result = install_torch(timeout=timeout)
    smoke = smoke_test(timeout=120) if install_result["status"] == "passed" else {"status": "failed", "errors": [install_result["output"]]}
    selected_count = selected_as_engine_count()
    cuda_available = bool(smoke.get("cuda_available"))
    cuda_tensor_test = bool(smoke.get("cuda_tensor_test"))
    status = "passed"
    if install_result["status"] != "passed" or smoke.get("status") != "passed" or selected_count != 0:
        status = "failed"
    elif not cuda_available or not cuda_tensor_test:
        status = "needs_review"

    return {
        "target_venv": str(TARGET_VENV),
        "install_executed": True,
        "install_result": install_result,
        "installed_packages": INSTALL_PACKAGES,
        "torch_version": smoke.get("torch_version"),
        "torchaudio_version": smoke.get("torchaudio_version"),
        "torch_cuda_version": smoke.get("torch_cuda_version"),
        "cuda_available": cuda_available,
        "cuda_device_count": smoke.get("cuda_device_count", 0),
        "cuda_device_name": smoke.get("cuda_device_name"),
        "cuda_tensor_test": cuda_tensor_test,
        "vram_total_mb": smoke.get("vram_total_mb"),
        "vram_free_mb": smoke.get("vram_free_mb"),
        "smoke_errors": smoke.get("errors", []),
        "model_download_executed": False,
        "benchmark_executed": False,
        "selected_as_engine_count": selected_count,
        "status": status,
    }


def write_report(report: dict[str, Any], output_path: Path = REPORT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install PyTorch CUDA in ASR venv and run CUDA smoke test")
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    report = build_report(timeout=args.timeout)
    write_report(report, Path(args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"passed", "needs_review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
