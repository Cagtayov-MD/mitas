from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from .config import SheriffConfig
from .store import Store


@dataclass(frozen=True)
class Admission:
    allowed: bool
    reason: str
    snapshot: dict[str, Any]


class ResourceManager:
    def __init__(self, config: SheriffConfig, store: Store) -> None:
        self.config = config
        self.store = store

    def snapshot(self) -> dict[str, Any]:
        memory = psutil.virtual_memory()
        disk = shutil.disk_usage(self.config.run_root.parent)
        gpu = self._gpu_snapshot()
        return {
            "cpu_count": os.cpu_count() or 1,
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_total_mb": memory.total // (1024 * 1024),
            "ram_available_mb": memory.available // (1024 * 1024),
            "disk_free_gb": disk.free / (1024 ** 3),
            **gpu,
        }

    def admit(self, profile_name: str, *, exclusive_override: bool = False) -> Admission:
        profile = self._effective_profile(profile_name, exclusive_override=exclusive_override)
        live = self.snapshot()
        cfg = self.config.raw["resources"]
        reservations = self.store.active_reservations()
        requested_exclusive = bool(profile.get("exclusive_gpu")) or exclusive_override
        requested_gpu = bool(profile.get("gpu"))
        gpu_reservations = [r for r in reservations if int(r["vram_mb"]) > 0]
        reserved_vram = sum(int(r["vram_mb"]) for r in gpu_reservations)
        reserved_ram = sum(int(r["ram_mb"]) for r in reservations)
        reserved_cpu = sum(int(r["cpu_threads"]) for r in reservations)
        if live["disk_free_gb"] < float(cfg["safety_disk_gb"]):
            return Admission(False, "disk safety payi", live)
        requested_ram = int(profile.get("ram_mb", 0))
        if live["ram_available_mb"] < requested_ram + int(cfg["safety_ram_mb"]):
            return Admission(False, "RAM safety payi", live)
        if reserved_ram + requested_ram > int(live["ram_total_mb"]) - int(cfg["safety_ram_mb"]):
            return Admission(False, "RAM rezervasyon tavani", live)
        usable_cpu = max(0, live["cpu_count"] - int(cfg["safety_cpu_threads"]))
        if (int(profile.get("cpu_threads", 0)) > 0
                and float(live.get("cpu_percent") or 0) >= float(cfg["max_cpu_percent"])):
            return Admission(False, "anlik CPU yuk tavani", live)
        if reserved_cpu + int(profile.get("cpu_threads", 0)) > usable_cpu:
            return Admission(False, "CPU rezervasyonu", live)
        if not requested_gpu:
            return Admission(True, "uygun", live)
        if requested_exclusive and gpu_reservations:
            return Admission(False, "GPU-exclusive gorev baska GPU isi bekliyor", live)
        if any(bool(r["exclusive_gpu"]) for r in gpu_reservations):
            return Admission(False, "GPU-exclusive gorev calisiyor", live)
        family = profile.get("family")
        if family == "deepseek":
            active_deepseek = sum(1 for r in gpu_reservations if r.get("family") == "deepseek")
            if active_deepseek >= int(cfg["max_deepseek_jobs"]):
                return Admission(False, "DeepSeek eszamanlilik tavani", live)
        requested = int(profile.get("vram_mb", 0))
        total = int(cfg.get("total_vram_mb") or live.get("vram_total_mb") or 0)
        safety = int(cfg["safety_vram_mb"])
        if reserved_vram + requested > total - safety:
            return Admission(False, "VRAM rezervasyon tavani", live)
        free = live.get("vram_free_mb")
        if free is None:
            return Admission(False, "GPU telemetrisi yok", live)
        if int(free) < requested + safety:
            return Admission(False, "anlik VRAM safety payi", live)
        return Admission(True, "uygun", live)

    def acquire(self, task_id: str, profile_name: str, *,
                exclusive_override: bool = False) -> str:
        profile = self._effective_profile(profile_name, exclusive_override=exclusive_override)
        return self.store.reserve(task_id, profile_name, profile)

    def _effective_profile(self, profile_name: str, *,
                           exclusive_override: bool = False) -> dict[str, Any]:
        profile = self.config.resource_profile(profile_name)
        if exclusive_override:
            profile["exclusive_gpu"] = True
            profile["vram_mb"] = max(
                int(profile.get("vram_mb", 0)),
                int(self.config.raw["resources"]["oom_retry_vram_mb"]))
        return profile

    @staticmethod
    def _gpu_snapshot() -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu",
                 "--format=csv,noheader,nounits"], capture_output=True, text=True,
                timeout=5, shell=False)
            if result.returncode:
                return {"vram_total_mb": None, "vram_used_mb": None,
                        "vram_free_mb": None, "gpu_util_percent": None}
            values = [int(part.strip()) for part in result.stdout.splitlines()[0].split(",")]
            return {"vram_total_mb": values[0], "vram_used_mb": values[1],
                    "vram_free_mb": values[2], "gpu_util_percent": values[3]}
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return {"vram_total_mb": None, "vram_used_mb": None,
                    "vram_free_mb": None, "gpu_util_percent": None}
