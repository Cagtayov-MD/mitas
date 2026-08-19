from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.config import load_config
from src.engine import Engine
from src.resources import ResourceManager
from src.store import Store


def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("SHERIFF_RUN_DIR", str(tmp_path / "runs"))
    cfg = load_config()
    store = Store(tmp_path / "state.sqlite3")
    rm = ResourceManager(cfg, store)
    monkeypatch.setattr(rm, "snapshot", lambda: {
        "cpu_count": 64, "cpu_percent": 0, "ram_total_mb": 121000,
        "ram_available_mb": 100000, "disk_free_gb": 500,
        "vram_total_mb": 24576, "vram_used_mb": 1000,
        "vram_free_mb": 23576, "gpu_util_percent": 0})
    return cfg, store, rm


def test_bir_deepseek_calirken_ikincisi_gecmez(tmp_path, monkeypatch):
    _, store, rm = manager(tmp_path, monkeypatch)
    monkeypatch.setattr(store, "active_reservations", lambda: [
        {"vram_mb": 8192, "ram_mb": 12288, "cpu_threads": 4,
         "exclusive_gpu": 0, "family": "deepseek"},
    ])
    admission = rm.admit("reader_master_default")
    assert not admission.allowed
    assert "DeepSeek" in admission.reason


def test_exclusive_gorev_aktif_gpu_rezervasyonu_varken_acilmaz(tmp_path, monkeypatch):
    _, store, rm = manager(tmp_path, monkeypatch)
    monkeypatch.setattr(store, "active_reservations", lambda: [
        {"vram_mb": 5120, "ram_mb": 8192, "cpu_threads": 4,
         "exclusive_gpu": 0, "family": "kobe"},
    ])
    admission = rm.admit("reader_video_default")
    assert not admission.allowed
    assert "exclusive" in admission.reason


def test_dis_gpu_yuku_canli_vram_kapisinda_reddedilir(tmp_path, monkeypatch):
    _, _, rm = manager(tmp_path, monkeypatch)
    snapshot = rm.snapshot()
    snapshot["vram_free_mb"] = 3500
    monkeypatch.setattr(rm, "snapshot", lambda: snapshot)
    admission = rm.admit("reader_frame_default")
    assert not admission.allowed
    assert "anlik VRAM" in admission.reason


def test_dis_cpu_yuku_canli_kapida_reddedilir(tmp_path, monkeypatch):
    _, _, rm = manager(tmp_path, monkeypatch)
    snapshot = rm.snapshot()
    snapshot["cpu_percent"] = 99
    monkeypatch.setattr(rm, "snapshot", lambda: snapshot)
    admission = rm.admit("cpu_media")
    assert not admission.allowed
    assert "CPU" in admission.reason


def test_gpu_modeli_de_dis_cpu_yukunu_yok_saymaz(tmp_path, monkeypatch):
    _, _, rm = manager(tmp_path, monkeypatch)
    snapshot = rm.snapshot()
    snapshot["cpu_percent"] = 99
    monkeypatch.setattr(rm, "snapshot", lambda: snapshot)
    admission = rm.admit("reader_master_default")
    assert not admission.allowed
    assert "CPU" in admission.reason


def test_oom_exclusive_admission_yukseltilmis_rezervasyonu_kontrol_eder(tmp_path,
                                                                        monkeypatch):
    _, _, rm = manager(tmp_path, monkeypatch)
    snapshot = rm.snapshot()
    snapshot["vram_free_mb"] = 12000
    monkeypatch.setattr(rm, "snapshot", lambda: snapshot)
    admission = rm.admit("reader_master_default", exclusive_override=True)
    assert not admission.allowed
    assert "VRAM" in admission.reason


def test_oom_exclusive_idle_3090da_ulasilabilir_rezervasyondur(tmp_path, monkeypatch):
    _, _, rm = manager(tmp_path, monkeypatch)
    snapshot = rm.snapshot()
    # 24 GiB kartlarda driver payi nedeniyle free, total'dan dusuktur.
    snapshot["vram_free_mb"] = 24125
    snapshot["vram_used_mb"] = 0
    monkeypatch.setattr(rm, "snapshot", lambda: snapshot)
    admission = rm.admit("reader_master_default", exclusive_override=True)
    assert admission.allowed


def test_dis_gpu_yuku_exclusive_beklerken_kucuk_isleri_drain_etmez(tmp_path,
                                                                   monkeypatch):
    cfg, store, _ = manager(tmp_path, monkeypatch)
    engine = Engine(cfg, store)
    old = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    jordan = {"task_id": "j", "kind": "tower", "logical_role": "reader_video",
              "result": None, "updated_at": old}
    aged = engine._aged_exclusive_ids([jordan])
    assert aged == {"j"}
    assert not engine._must_drain_for_exclusive(aged, [])
    assert engine._must_drain_for_exclusive(aged, [{"vram_mb": 8192}])


def test_handoff_hafif_kontrol_profili_kullanir(tmp_path, monkeypatch):
    cfg, store, _ = manager(tmp_path, monkeypatch)
    engine = Engine(cfg, store)
    assert engine._profile({"kind": "handoff"}) == "cpu_light"
    assert cfg.resource_profile("cpu_light")["cpu_threads"] == 1


def test_hazir_gpu_gorevi_cpu_dolumundan_once_degerlendirilir(tmp_path,
                                                               monkeypatch):
    cfg, store, _ = manager(tmp_path, monkeypatch)
    engine = Engine(cfg, store)
    gpu = {"task_id": "gpu", "kind": "tower", "logical_role": "reader_master"}
    cpu = {"task_id": "cpu", "kind": "media_prep"}
    assert engine._ready_rank(
        gpu, yield_to_shared=False, shared_gpu_ids=set(),
        aged_exclusive_ids=set()) < engine._ready_rank(
            cpu, yield_to_shared=False, shared_gpu_ids=set(),
            aged_exclusive_ids=set())
