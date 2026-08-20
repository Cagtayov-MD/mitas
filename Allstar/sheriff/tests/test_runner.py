from __future__ import annotations

import os
import sys
import subprocess

import psutil
import pytest

from src.runner import run_capture, terminate_recorded_process


def test_run_capture_pipe_tamponundan_buyuk_stderrde_kilitlenmez():
    size = 1024 * 1024
    metrics = {}
    code, stdout, stderr = run_capture(
        [sys.executable, "-c",
         f"import sys; sys.stderr.write('x' * {size}); print('tamam')"],
        timeout_s=10, metrics_sink=metrics)
    assert code == 0
    assert stdout.strip() == "tamam"
    assert len(stderr) == size
    assert metrics["subprocesses"][0]["exit_code"] == 0
    assert metrics["duration_s"] >= 0


def test_timeout_butun_process_grubunu_sonlandirir():
    code = ("import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            "print(p.pid, flush=True); time.sleep(60)")
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        run_capture([sys.executable, "-c", code], timeout_s=0.5)
    child_pid = int((caught.value.output or "").strip())
    if psutil.pid_exists(child_pid):
        assert psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE


def test_olmus_liderin_yasayan_process_grubu_recoveryde_sonlandirilir(tmp_path):
    pid_path = tmp_path / "child.pid"
    code = ("import subprocess,sys; from pathlib import Path; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            "Path(sys.argv[1]).write_text(str(p.pid))")
    leader = subprocess.Popen(
        [sys.executable, "-c", code, str(pid_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    process = psutil.Process(leader.pid)
    create_time = process.create_time()
    pgid = os.getpgid(leader.pid)
    leader.wait(timeout=10)
    child_pid = int(pid_path.read_text(encoding="utf-8"))
    assert psutil.pid_exists(child_pid)
    assert terminate_recorded_process(leader.pid, pgid, create_time)
    if psutil.pid_exists(child_pid):
        assert psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE
