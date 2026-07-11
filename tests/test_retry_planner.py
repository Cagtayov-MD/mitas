# -*- coding: utf-8 -*-
"""İP-7 retry_planner testleri (2026-07-11, plan rev.4 + qwen/GLM İP7-turu).
Kapsam: resolver (0/1/AMBIGUOUS) · retry planı candidate-root+delete_existing=False (SİLME YOK) ·
retry_env candidate-mod + köprü-temizliği · stale_downstream LAZY+backlog · circuit-breaker→DLQ ·
deterministik run_id (Math.random yok) · zombie heartbeat."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import retry_planner as rp  # noqa: E402

TRT = "1990-0001-1-0000-00-1"
VIDEO = rf"W:\filmler\evo_{TRT}-TEST_FILM.mp4"


def _hub(db: Path, ad: str) -> Path:
    h = db / ad
    h.mkdir(parents=True)
    (h / "_DURUM.json").write_text("{}", encoding="utf-8")
    (h / "frames").mkdir()
    return h


def test_resolver_0_1_ambiguous(tmp_path):
    db = tmp_path / "Database"
    db.mkdir()
    assert rp.resolve_hub(VIDEO, db) is None                     # 0
    h = _hub(db, f"TEST FILM {TRT}")
    assert rp.resolve_hub(VIDEO, db) == h                        # 1
    _hub(db, f"TEST FILM {TRT} 2")
    with pytest.raises(rp.RetryError, match="AMBIGUOUS_HUB"):    # >1
        rp.resolve_hub(VIDEO, db)


def test_plan_full_candidate_silme_yok(tmp_path):
    db = tmp_path / "Database"
    db.mkdir()
    _hub(db, f"TEST FILM {TRT}")
    p = rp.plan_retry(VIDEO, "FULL", seed="s1", db_root=db)
    assert p["delete_existing"] is False and p["candidate_run"] is True
    assert "--run-root" in p["cmd"] and p["run_root"] in p["cmd"]
    assert p["run_root"].startswith(str(rp.CANDIDATE_ROOT))
    assert p["runner"] == "mitas_pipeline"


def test_plan_stage_hub_gerektirir(tmp_path):
    db = tmp_path / "Database"
    db.mkdir()
    with pytest.raises(rp.RetryError, match="canonical hub gerekli"):
        rp.plan_retry(VIDEO, "OCR", seed="s", db_root=db)   # hub yok
    _hub(db, f"TEST FILM {TRT}")
    p = rp.plan_retry(VIDEO, "OCR", seed="s", db_root=db)
    assert p["runner"] == "stage:OCR" and p["frames_ref"].endswith("frames")


def test_gecersiz_stage(tmp_path):
    db = tmp_path / "Database"; db.mkdir()
    with pytest.raises(rp.RetryError, match="geçersiz stage"):
        rp.plan_retry(VIDEO, "XYZ", seed="s", db_root=db)


def test_run_id_deterministik(tmp_path):
    a = rp.make_run_id("FULL", "seed-x")
    b = rp.make_run_id("FULL", "seed-x")
    c = rp.make_run_id("FULL", "seed-y")
    assert a == b and a != c and a.startswith("retry_full_")


def test_retry_env_candidate_mod_ve_kopru_temizligi():
    base = {"MITAS_WEB_CACHE_DIR": "x", "MITAS_OUTPUTS_DIR": "y", "PATH": "keep"}
    e = rp.retry_env(base, r"E:\MITAS\candidate_runs\r1")
    assert e["MITAS_RUN_ROOT"].endswith("r1")
    assert "MITAS_WEB_CACHE_DIR" not in e and "MITAS_OUTPUTS_DIR" not in e
    assert e["PATH"] == "keep"                              # ilgisiz env korunur


def test_stale_downstream_lazy_yazilir(tmp_path):
    hub = tmp_path / "hub"
    hub.mkdir()
    (hub / "karar.pipeline.json").write_text(json.dumps({"tier": "TEMIZ"}), encoding="utf-8")
    ds = rp.mark_stale_downstream(hub, "OCR")
    assert set(ds) == {"credit", "validation", "pdf", "qc", "karar"}
    obj = json.loads((hub / "karar.pipeline.json").read_text(encoding="utf-8"))
    assert set(obj["stale_downstream"]) == set(ds)
    assert obj["tier"] == "TEMIZ"                           # mevcut alan korunur (merge)


def test_circuit_breaker_dlq(tmp_path):
    cp = tmp_path / "inval.json"
    key = f"{TRT}:OCR"
    for i in range(rp.MAX_INVALIDATION):
        r = rp.bump_invalidation(cp, key)
        assert r["dlq"] is False, f"{i+1}. henüz DLQ değil"
    r = rp.bump_invalidation(cp, key)                       # MAX+1 → DLQ
    assert r["dlq"] is True and r["count"] == rp.MAX_INVALIDATION + 1
    data = json.loads(cp.read_text(encoding="utf-8"))
    assert key in data["_dlq"]


def test_zombie_heartbeat():
    assert rp.is_zombie(last_heartbeat_ts=0.0, now_ts=1000.0, stage="FULL", idle_limit_sn=900) is True
    assert rp.is_zombie(last_heartbeat_ts=500.0, now_ts=1000.0, stage="FULL", idle_limit_sn=900) is False
