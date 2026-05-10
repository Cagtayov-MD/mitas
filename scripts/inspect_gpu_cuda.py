from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

import yaml


ROOT = Path(r"E:\MITAS")
MANIFEST_PATH = ROOT / "model_manifest.yaml"
REPORT_PATH = ROOT / "outputs" / "gpu_cuda_inventory_report.json"


def run_command(args: list[str], timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
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


def parse_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_gpu_query(output: str) -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    reader = csv.reader(output.splitlines())
    for index, row in enumerate(reader):
        if len(row) < 5:
            continue
        name, driver_version, total, used, free = [part.strip() for part in row[:5]]
        gpus.append(
            {
                "index": index,
                "name": name,
                "driver_version": driver_version,
                "memory_total_mb": parse_int(total),
                "memory_used_mb": parse_int(used),
                "memory_free_mb": parse_int(free),
            }
        )
    return gpus


def parse_cuda_version(output: str) -> str | None:
    match = re.search(r"CUDA Version:\s*([0-9.]+)", output)
    return match.group(1) if match else None


def recommended_track(cuda_version: str | None, gpu_count: int, nvidia_smi_found: bool) -> str:
    if not nvidia_smi_found:
        return "nvidia_smi_missing_no_cuda_track_recommended"
    if gpu_count == 0:
        return "gpu_not_visible_no_cuda_track_recommended"
    if not cuda_version:
        return "cuda_driver_version_needs_manual_review"
    major = cuda_version.split(".", 1)[0]
    if major == "12":
        return "cuda_12_x_track_review_only"
    if major == "11":
        return "cuda_11_x_track_review_only"
    return f"cuda_{major}_x_track_review_only"


def readiness(nvidia_smi_found: bool, gpu_count: int, cuda_version: str | None) -> bool | str:
    if not nvidia_smi_found or gpu_count == 0:
        return False
    if not cuda_version:
        return "needs_review"
    return "needs_review"


def build_report(timeout: int = 15) -> dict[str, Any]:
    nvidia_smi_path = shutil.which("nvidia-smi")
    selected_count = selected_as_engine_count()
    warnings: list[str] = []

    if not nvidia_smi_path:
        warnings.append("nvidia-smi PATH içinde bulunamadı; GPU/CUDA driver görünürlüğü doğrulanamadı.")
        return {
            "nvidia_smi_found": False,
            "nvidia_smi_path": None,
            "gpu_count": 0,
            "gpus": [],
            "driver_versions": [],
            "cuda_version_from_nvidia_smi": None,
            "total_vram_mb": 0,
            "free_vram_mb": 0,
            "recommended_next_cuda_track": recommended_track(None, 0, False),
            "heavy_install_ready": False,
            "warnings": warnings,
            "selected_as_engine_count": selected_count,
            "status": "passed" if selected_count == 0 else "failed",
        }

    query_args = [
        nvidia_smi_path,
        "--query-gpu=name,driver_version,memory.total,memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ]
    query_result = run_command(query_args, timeout=timeout)
    general_result = run_command([nvidia_smi_path], timeout=timeout)

    gpus = parse_gpu_query(query_result["output"]) if query_result["status"] == "passed" else []
    cuda_version = parse_cuda_version(general_result["output"]) if general_result["status"] == "passed" else None
    driver_versions = sorted({gpu["driver_version"] for gpu in gpus if gpu.get("driver_version")})
    total_vram_mb = sum(gpu.get("memory_total_mb") or 0 for gpu in gpus)
    free_vram_mb = sum(gpu.get("memory_free_mb") or 0 for gpu in gpus)

    if query_result["status"] != "passed":
        warnings.append(f"nvidia-smi query failed: {query_result['output']}")
    if general_result["status"] != "passed":
        warnings.append(f"nvidia-smi general output failed: {general_result['output']}")
    if not gpus:
        warnings.append("nvidia-smi bulundu ama GPU listesi okunamadı veya GPU görünmüyor.")
    if gpus and not cuda_version:
        warnings.append("GPU görünüyor ancak nvidia-smi genel çıktısından CUDA Version okunamadı.")
    if gpus and cuda_version:
        warnings.append("CUDA/driver görünürlüğü mevcut; PyTorch/ONNX/TensorFlow kurulum kararı bu sprintte verilmedi.")

    heavy_install_ready = readiness(bool(nvidia_smi_path), len(gpus), cuda_version)
    status = "passed" if selected_count == 0 and query_result["status"] in {"passed", "failed"} else "failed"

    return {
        "nvidia_smi_found": True,
        "nvidia_smi_path": nvidia_smi_path,
        "gpu_count": len(gpus),
        "gpus": gpus,
        "driver_versions": driver_versions,
        "cuda_version_from_nvidia_smi": cuda_version,
        "total_vram_mb": total_vram_mb,
        "free_vram_mb": free_vram_mb,
        "recommended_next_cuda_track": recommended_track(cuda_version, len(gpus), True),
        "heavy_install_ready": heavy_install_ready,
        "warnings": warnings,
        "selected_as_engine_count": selected_count,
        "status": status,
    }


def write_report(report: dict[str, Any], output_path: Path = REPORT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="MITAS NVIDIA GPU/CUDA driver inventory")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    report = build_report(timeout=args.timeout)
    write_report(report, Path(args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
