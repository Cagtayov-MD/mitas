# -*- coding: utf-8 -*-
"""İP-1 run_manifest testleri (2026-07-11, plan rev.4).
Ağ/duckdb/git'e GERÇEK bağımlılık yok — hepsi monkeypatch; hızlı unit-katman.
Kapsam: (1) preflight ollama-kapalı → PreflightError (36-sahte-KONTROL kapısı);
(2) batch-modda kirli-ağaç → PreflightError, bypass YOK; (3) tek-film MITAS_PREFLIGHT=0 kaçışı;
(4) manifest alan-tamlığı + input_signature kararlılığı; (5) writer-kilidi dolu/bayat davranışı."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_manifest as rm  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("MITAS_PREFLIGHT", raising=False)
    monkeypatch.delenv("MITAS_BATCH_MODE", raising=False)
    monkeypatch.setattr(rm, "LOCK_PATH", tmp_path / ".writer.lock")
    monkeypatch.setattr(rm, "_LOCK_TOKEN", None)
    yield


def test_from_hub_input_signature_degisikligi_yakalar(monkeypatch, tmp_path):
    hub = tmp_path / "hub"
    (hub / "frames" / "cikis").mkdir(parents=True)
    (hub / "clip.json").write_text('{"filename":"x.mp4"}', encoding="utf-8")
    (hub / "frames" / "cikis" / "0001.png").write_bytes(b"frame-a")
    monkeypatch.setenv("MITAS_FROM_HUB_PATH", str(hub))
    a = rm.input_signature(tmp_path / "offline.mp4")
    (hub / "frames" / "cikis" / "0001.png").write_bytes(b"frame-b")
    b = rm.input_signature(tmp_path / "offline.mp4")
    assert a["kind"] == "hub" and a["sig_sha256"] != b["sig_sha256"]


def test_writer_lock_sahiplik_tokeni_olmadan_silinmez(monkeypatch, tmp_path):
    lock = tmp_path / ".writer.lock"
    monkeypatch.setattr(rm, "LOCK_PATH", lock)
    rm.acquire_writer_lock()
    assert lock.exists()
    gercek = rm._LOCK_TOKEN
    rm._LOCK_TOKEN = "baska-sahip"
    rm.release_writer_lock()
    assert lock.exists()
    rm._LOCK_TOKEN = gercek
    rm.release_writer_lock()
    assert not lock.exists()


def test_manifest_secret_env_degerini_sizdirmaz(monkeypatch, tmp_path):
    video = tmp_path / "x.mp4"
    video.write_bytes(b"video")
    monkeypatch.setenv("MITAS_API_KEY", "cok-gizli-deger")
    monkeypatch.setenv("MITAS_NORMAL_FLAG", "1")
    monkeypatch.setattr(rm, "git_state", lambda: {
        "git_sha": "abc", "git_dirty": False, "dirty_patch_sha256": None,
        "dirty_patch_bytes": 0})
    monkeypatch.setattr(rm, "ollama_models", lambda: {})
    m = rm.build_manifest(video, "film", [])
    assert "cok-gizli-deger" not in json.dumps(m)
    assert m["config_snapshot"]["MITAS_API_KEY"].startswith("<redacted:")
    assert m["config_snapshot"]["MITAS_NORMAL_FLAG"] == "1"


def _ok_git(monkeypatch, dirty=False):
    monkeypatch.setattr(rm, "git_state", lambda: {
        "git_sha": "abc123", "git_dirty": dirty,
        "dirty_patch_sha256": "d" * 64 if dirty else None,
        "dirty_patch_bytes": 100 if dirty else 0})


def _ok_infra(monkeypatch):
    monkeypatch.setattr(rm, "ollama_models", lambda: {"gemma-4-31b-it-qat-vision:latest": "sha256:aa"})
    monkeypatch.setattr(rm, "ollama_generate_ping", lambda model, timeout=240.0: 1.2)
    monkeypatch.setattr(rm, "duckdb_check", lambda: [])


def test_preflight_ollama_kapali_hard_fail(monkeypatch):
    _ok_git(monkeypatch)
    monkeypatch.setattr(rm, "ollama_models", lambda: (_ for _ in ()).throw(OSError("baglanti yok")))
    monkeypatch.setattr(rm, "duckdb_check", lambda: [])
    with pytest.raises(rm.PreflightError, match="ollama"):
        rm.run_preflight(batch_mode=False)


def test_preflight_bos_model_deposu_hard_fail(monkeypatch):
    """36-sahte-KONTROL kökü: sunucu ayakta ama depo boş → koşu başlamamalı."""
    _ok_git(monkeypatch)
    monkeypatch.setattr(rm, "ollama_models", lambda: {})
    monkeypatch.setattr(rm, "duckdb_check", lambda: [])
    with pytest.raises(rm.PreflightError, match="BOŞ"):
        rm.run_preflight(batch_mode=False)


def test_batch_kirli_agac_hard_fail_bypass_yok(monkeypatch):
    _ok_infra(monkeypatch)
    _ok_git(monkeypatch, dirty=True)
    monkeypatch.setenv("MITAS_PREFLIGHT", "0")  # kaçış tek-film içindir; batch'te İŞLEMEZ
    with pytest.raises(rm.PreflightError, match="kirli"):
        rm.run_preflight(batch_mode=True)


def test_tek_film_preflight_kacisi(monkeypatch):
    monkeypatch.setenv("MITAS_PREFLIGHT", "0")
    info = rm.run_preflight(batch_mode=False)
    assert info.get("skipped") is True


def test_batch_temiz_agac_kilit_alinir(monkeypatch):
    _ok_infra(monkeypatch)
    _ok_git(monkeypatch, dirty=False)
    info = rm.run_preflight(batch_mode=True)
    assert rm.LOCK_PATH.exists()
    assert info["git"]["git_dirty"] is False
    rm.release_writer_lock()
    assert not rm.LOCK_PATH.exists()


def test_kilit_dolu_canli_pid_fail(monkeypatch):
    rm.LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    rm.LOCK_PATH.write_text(json.dumps({"pid": os.getpid(), "ts": "x"}), encoding="utf-8")
    with pytest.raises(rm.PreflightError, match="kilidi dolu"):
        rm.acquire_writer_lock()


def test_kilit_bayat_olu_pid_devralinir(monkeypatch):
    rm.LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    rm.LOCK_PATH.write_text(json.dumps({"pid": 999999999, "ts": "x"}), encoding="utf-8")
    monkeypatch.setattr(rm, "_pid_alive", lambda pid: False)
    rm.acquire_writer_lock()  # exception YOK — bayat kilit devralındı
    assert json.loads(rm.LOCK_PATH.read_text(encoding="utf-8"))["pid"] == os.getpid()
    rm.release_writer_lock()


def test_manifest_alan_tamligi(monkeypatch, tmp_path):
    _ok_git(monkeypatch, dirty=True)
    monkeypatch.setattr(rm, "ollama_models", lambda: {"m": "d"})
    monkeypatch.setenv("MITAS_ORNEK_FLAG", "42")
    v = tmp_path / "FILM 2000-0001-1-0000-00-1.mp4"
    v.write_bytes(b"x" * 1024)
    m = rm.build_manifest(v, "film", ["--video", str(v)], preflight_info={"ok": 1})
    for alan in ("run_id", "created_at", "git_sha", "git_dirty", "dirty_patch_sha256",
                 "input", "model_digests", "prompt_source_hashes", "config_snapshot",
                 "preflight", "status"):
        assert alan in m, alan
    assert m["config_snapshot"].get("MITAS_ORNEK_FLAG") == "42"
    assert m["input"]["size_bytes"] == 1024
    assert m["status"] == "running"


def test_input_signature_kararli_ve_degisim_yakalar(tmp_path):
    v = tmp_path / "a.bin"
    v.write_bytes(b"A" * (20 * 1024 * 1024))
    s1 = rm.input_signature(v)
    s2 = rm.input_signature(v)
    assert s1 == s2
    with v.open("r+b") as f:  # son bloğa dokun → imza değişmeli
        f.seek(-1, 2)
        f.write(b"B")
    assert rm.input_signature(v)["sig_sha256"] != s1["sig_sha256"]


def test_finalize_bozuk_manifest_kosuyu_bozmaz(tmp_path, capsys):
    (tmp_path / "run_manifest.json").write_text("{bozuk", encoding="utf-8")
    rm.finalize(tmp_path, status="Kontrol")  # exception YOK (best-effort sözleşmesi)
