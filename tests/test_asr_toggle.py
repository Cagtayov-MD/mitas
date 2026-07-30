# -*- coding: utf-8 -*-
"""test_asr_toggle.py — global ASR + Özet anahtarı (Çağatay 2026-07-30).

Tek anahtar: kuyruk state'inde üst-düzey `asrEnabled` (default AÇIK). Kapalıyken
worker ve tek-dosya yolu pipeline'a `--no-asr` ekler. DİKKAT: put_flow_queue
state'i SIFIRDAN kurar — alan rebuild'e açıkça eklenmezse sessizce düşer
(bu tuzak 2026-07-30 denetiminde kanıtlandı, 'force' yalnız öğe-düzeyi yaşıyor).

Çalıştır: /opt/mitas/venvs/asr/bin/python -m pytest tests/test_asr_toggle.py -q
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from core.api import asr_server  # noqa: E402


@pytest.fixture()
def istemci(monkeypatch, tmp_path):
    monkeypatch.setenv("MITAS_ACCESS_SECRET", "test-secret")
    monkeypatch.setattr(asr_server, "FLOW_QUEUE_STATE_PATH", tmp_path / "queue.json")
    client = TestClient(asr_server.app)
    login = client.post("/api/auth/login", json={"username": "mitas", "pwId": "test_61"})
    assert login.status_code == 200
    return client


def test_put_flow_queue_asr_alanini_korur(istemci):
    r = istemci.put("/api/flow-queue", json={"bulkProfile": "film_dizi",
                                             "asrEnabled": False, "items": []})
    assert r.status_code == 200
    assert r.json().get("asrEnabled") is False
    diskte = json.loads(Path(asr_server.FLOW_QUEUE_STATE_PATH).read_text(encoding="utf-8"))
    assert diskte.get("asrEnabled") is False


def test_put_flow_queue_alan_yoksa_acik(istemci):
    """Eski UI payload'ı (alansız) → varsayılan AÇIK; eski kuyruklar kırılmaz."""
    r = istemci.put("/api/flow-queue", json={"bulkProfile": "film_dizi", "items": []})
    assert r.status_code == 200
    assert r.json().get("asrEnabled") is True


def test_flow_asr_enabled_yardimcisi(monkeypatch, tmp_path):
    q = tmp_path / "queue.json"
    monkeypatch.setattr(asr_server, "FLOW_QUEUE_STATE_PATH", q)

    assert asr_server._flow_asr_enabled() is True          # dosya yok → AÇIK
    q.write_text(json.dumps({"id": "main", "asrEnabled": False}), encoding="utf-8")
    assert asr_server._flow_asr_enabled() is False
    q.write_text(json.dumps({"id": "main"}), encoding="utf-8")
    assert asr_server._flow_asr_enabled() is True          # alan yok → AÇIK
    q.write_text("BOZUK JSON", encoding="utf-8")
    assert asr_server._flow_asr_enabled() is True          # fail-safe → AÇIK


def test_iki_spawn_yolu_da_anahtari_okur():
    """Worker VE tek-dosya (_run_pipeline_job) cmd bloğu anahtara bağlı olmalı."""
    src = (Path(asr_server.__file__)).read_text(encoding="utf-8", errors="replace")
    assert src.count("_flow_asr_enabled()") >= 2, (
        "en az iki çağrı yeri bekleniyor (worker + _run_pipeline_job)")
    assert '"--no-asr"' in src
