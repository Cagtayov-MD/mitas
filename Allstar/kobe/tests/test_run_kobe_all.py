from __future__ import annotations

import argparse
import json
import threading
import time

import pytest

import run_kobe_all as batch


def test_isci_sayisi_dortle_sinirlidir():
    assert batch._isci_sayisi("1") == 1
    assert batch._isci_sayisi("4") == 4
    with pytest.raises(argparse.ArgumentTypeError):
        batch._isci_sayisi("0")
    with pytest.raises(argparse.ArgumentTypeError):
        batch._isci_sayisi("5")


def test_toplu_kosu_en_cok_dort_alt_proses_acar(tmp_path, monkeypatch):
    sheriff = tmp_path / "sheriff"
    out = tmp_path / "out"
    for index in range(6):
        for bolum in ("giris", "cikis"):
            (sheriff / f"film-{index}" / bolum).mkdir(parents=True)

    active = 0
    peak = 0
    lock = threading.Lock()

    def fake_run(cmd, **_kwargs):
        nonlocal active, peak
        film_id = cmd[cmd.index("--film-id") + 1]
        bolum = cmd[cmd.index("--bolum") + 1]
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.02)
            result_dir = out / film_id / bolum
            result_dir.mkdir(parents=True)
            (result_dir / "kobe.json").write_text(
                json.dumps({"durum": "BULUNDU", "baslangic_kare": 1,
                            "guven": 1.0}), encoding="utf-8")
            return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(batch, "KOBE_OUT", out)
    monkeypatch.setattr(batch.subprocess, "run", fake_run)
    batch.main(["--sheriff-output", str(sheriff), "--force", "--isci", "4"])

    assert peak == 4
    assert len(list(out.glob("*/*/kobe.json"))) == 12
