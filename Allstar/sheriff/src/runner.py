from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import psutil

from .util import now_iso


@dataclass
class ProcessResult:
    exit_code: int
    timed_out: bool
    cancelled: bool
    duration_s: float
    peak_rss_mb: float
    peak_cpu_percent: float
    peak_vram_mb: float | None
    stdout_path: str
    stderr_path: str
    command: list[str]
    pid: int
    pgid: int
    process_create_time: float | None

    def metrics(self) -> dict:
        return {"duration_s": self.duration_s, "peak_rss_mb": self.peak_rss_mb,
                "peak_cpu_percent": self.peak_cpu_percent,
                "peak_vram_mb": self.peak_vram_mb,
                "timed_out": self.timed_out, "cancelled": self.cancelled}


def run_process(command: list[str], *, cwd: Path, env: dict[str, str],
                stdout_path: Path, stderr_path: Path, timeout_s: float,
                heartbeat: Callable[[], None] | None = None,
                should_cancel: Callable[[], bool] | None = None,
                on_start: Callable[[int, int, float | None], None] | None = None) -> ProcessResult:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    peak_rss = 0.0
    peak_cpu = 0.0
    peak_vram: float | None = None
    timed_out = False
    cancelled = False
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout,
                                   stderr=stderr, shell=False, start_new_session=True)
        ps = psutil.Process(process.pid)
        pgid = os.getpgid(process.pid)
        try:
            create_time = ps.create_time()
        except psutil.Error:
            create_time = None
        if on_start:
            on_start(process.pid, pgid, create_time)
        ps.cpu_percent(interval=None)
        last_heartbeat = 0.0
        last_gpu_sample = 0.0
        while process.poll() is None:
            now = time.monotonic()
            if now - started > timeout_s:
                timed_out = True
                _terminate_group(process.pid)
                break
            if should_cancel and should_cancel():
                cancelled = True
                _terminate_group(process.pid)
                break
            try:
                family = [ps, *ps.children(recursive=True)]
                peak_rss = max(peak_rss, sum(p.memory_info().rss for p in family
                                             if p.is_running()) / (1024 * 1024))
                peak_cpu = max(peak_cpu, sum(p.cpu_percent(interval=None) for p in family
                                             if p.is_running()))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if now - last_gpu_sample >= 2:
                used = _process_vram(process.pid)
                if used is not None:
                    peak_vram = max(peak_vram or 0.0, used)
                last_gpu_sample = now
            if heartbeat and now - last_heartbeat >= 5:
                heartbeat()
                last_heartbeat = now
            time.sleep(0.5)
        try:
            code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _kill_group(process.pid)
            code = process.wait(timeout=10)
    return ProcessResult(code, timed_out, cancelled, round(time.monotonic() - started, 3),
                         round(peak_rss, 1), round(peak_cpu, 1), peak_vram,
                         str(stdout_path), str(stderr_path), command,
                         process.pid, pgid, create_time)


def run_capture(command: list[str], *, timeout_s: float,
                heartbeat: Callable[[], None] | None = None,
                should_cancel: Callable[[], bool] | None = None,
                on_start: Callable[[int, int, float | None], None] | None = None,
                metrics_sink: dict | None = None,
                ) -> tuple[int, str, str]:
    """Capture arbitrary output without pipe-buffer deadlocks.

    ffmpeg ``showinfo`` is not small: a several-minute window can fill both OS
    pipe buffers while this loop is doing heartbeat polling. Temporary files
    keep output bounded by disk rather than RAM and let the child write without
    waiting for Sheriff to drain a pipe.
    """
    with tempfile.TemporaryFile(mode="w+b") as stdout_file, \
            tempfile.TemporaryFile(mode="w+b") as stderr_file:
        process = subprocess.Popen(command, stdout=stdout_file, stderr=stderr_file,
                                   shell=False, start_new_session=True)
        ps = psutil.Process(process.pid)
        ps.cpu_percent(interval=None)
        if on_start:
            try:
                create_time = psutil.Process(process.pid).create_time()
            except psutil.Error:
                create_time = None
            on_start(process.pid, os.getpgid(process.pid), create_time)
        started = time.monotonic()
        last_heartbeat = 0.0
        timed_out = False
        cancelled = False
        peak_rss = 0.0
        peak_cpu = 0.0
        peak_vram: float | None = None
        last_gpu_sample = 0.0
        while process.poll() is None:
            now = time.monotonic()
            if now - started > timeout_s:
                timed_out = True
                _terminate_group(process.pid)
                break
            if should_cancel and should_cancel():
                cancelled = True
                _terminate_group(process.pid)
                break
            if heartbeat and now - last_heartbeat >= 5:
                heartbeat()
                last_heartbeat = now
            try:
                family = [ps, *ps.children(recursive=True)]
                peak_rss = max(peak_rss, sum(item.memory_info().rss for item in family
                                             if item.is_running()) / (1024 * 1024))
                peak_cpu = max(peak_cpu, sum(item.cpu_percent(interval=None) for item in family
                                             if item.is_running()))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if now - last_gpu_sample >= 2:
                used = _process_vram(process.pid)
                if used is not None:
                    peak_vram = max(peak_vram or 0.0, used)
                last_gpu_sample = now
            time.sleep(0.25)
        try:
            returncode = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _kill_group(process.pid)
            returncode = process.wait(timeout=10)
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read().decode("utf-8", errors="replace")
        stderr = stderr_file.read().decode("utf-8", errors="replace")
    duration = round(time.monotonic() - started, 3)
    if metrics_sink is not None:
        metrics_sink["duration_s"] = round(
            float(metrics_sink.get("duration_s") or 0.0) + duration, 3)
        metrics_sink["peak_rss_mb"] = max(float(metrics_sink.get("peak_rss_mb") or 0.0),
                                           round(peak_rss, 1))
        metrics_sink["peak_cpu_percent"] = max(
            float(metrics_sink.get("peak_cpu_percent") or 0.0), round(peak_cpu, 1))
        if peak_vram is not None:
            metrics_sink["peak_vram_mb"] = max(
                float(metrics_sink.get("peak_vram_mb") or 0.0), peak_vram)
        metrics_sink.setdefault("subprocesses", []).append({
            "pid": process.pid, "exit_code": returncode, "duration_s": duration,
            "command": command, "timed_out": timed_out, "cancelled": cancelled})
    if timed_out:
        raise subprocess.TimeoutExpired(command, timeout_s, output=stdout, stderr=stderr)
    if cancelled:
        raise RuntimeError("subprocess durduruldu")
    return returncode, stdout, stderr


def _terminate_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not _group_has_live_members(pid):
            return
        time.sleep(0.2)
    _kill_group(pid)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def terminate_recorded_process(pid: int | None, pgid: int | None,
                               expected_create_time: float | None) -> bool:
    """Kill only the exact process recorded for an expired attempt.

    PID reuse is guarded by psutil create_time. Returns True when a matching
    live process was found and its process group was terminated.
    """
    if not pid or not pgid or expected_create_time is None:
        return False
    try:
        try:
            process = psutil.Process(int(pid))
            if abs(process.create_time() - float(expected_create_time)) > 0.01:
                return False
        except psutil.NoSuchProcess:
            # The session leader can die while a model child keeps the group
            # alive. A live group cannot reuse its PGID; still require the
            # recorded timestamp and reject any member older than that leader.
            members = _live_group_processes(int(pgid))
            if not members or any(item.create_time() + 0.01 < float(expected_create_time)
                                  for item in members):
                return False
        try:
            os.killpg(int(pgid), signal.SIGTERM)
        except ProcessLookupError:
            return False
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not _group_has_live_members(int(pgid)):
                return True
            time.sleep(0.2)
        try:
            os.killpg(int(pgid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        return True
    except (psutil.Error, OSError, ValueError):
        return False


def _group_has_live_members(pgid: int) -> bool:
    return bool(_live_group_processes(pgid))


def _live_group_processes(pgid: int) -> list[psutil.Process]:
    members = []
    for process in psutil.process_iter(["status"]):
        try:
            if (os.getpgid(process.pid) == pgid
                    and process.info.get("status") != psutil.STATUS_ZOMBIE):
                members.append(process)
        except (ProcessLookupError, PermissionError, psutil.Error):
            continue
    return members


def _process_vram(root_pid: int) -> float | None:
    try:
        process = psutil.Process(root_pid)
        pids = {root_pid, *(child.pid for child in process.children(recursive=True))}
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory",
             "--format=csv,noheader,nounits"], capture_output=True, text=True,
            timeout=3, shell=False)
        if result.returncode:
            return None
        total = 0.0
        for line in result.stdout.splitlines():
            pid_text, memory_text = (part.strip() for part in line.split(",", 1))
            if int(pid_text) in pids:
                total += float(memory_text)
        return total
    except (OSError, ValueError, psutil.Error, subprocess.SubprocessError):
        return None
