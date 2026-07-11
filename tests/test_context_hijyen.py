# -*- coding: utf-8 -*-
"""İP-3 context/determinizm hijyeni testleri (2026-07-11, plan rev.4).
(1) ollama options'a seed + num_predict + env'li num_ctx GERÇEKTEN giriyor mu (payload-yakalama);
(2) length'te TEK-seferlik num_ctx-yükseltmeli retry (ikinci kaza → TF kalır, sonsuz döngü yok);
(3) telemetri satırı yazılıyor (best-effort, bozuk girdide çökmez)."""
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import credit_text_read as ctr  # noqa: E402
import run_manifest as rm  # noqa: E402


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_options_seed_num_predict_num_ctx(monkeypatch):
    yakalanan = {}

    def _cap(req, timeout=None):
        yakalanan.update(json.loads(req.data.decode("utf-8")))
        return _FakeResp(json.dumps({"response": "{}", "done_reason": "stop"}).encode())

    monkeypatch.setenv("MITAS_OLLAMA_SEED", "1234")
    monkeypatch.setenv("MITAS_OLLAMA_NUM_PREDICT", "999")
    monkeypatch.setenv("MITAS_OLLAMA_NUM_CTX", "4096")
    monkeypatch.setattr(ctr.urllib.request, "urlopen", _cap)
    _, meta = ctr._ollama_json_ex("m", "p", {})
    o = yakalanan["options"]
    assert o["seed"] == 1234 and o["num_predict"] == 999 and o["num_ctx"] == 4096
    assert meta["num_ctx"] == 4096


def test_length_tek_retry_yukseltilmis_ctx(monkeypatch):
    """1. çağrı length-kazası → 2. çağrı yükseltilmiş num_ctx ile TEK kez; başarılıysa OK."""
    cagrilar = []

    def _fake_ex(m, p, s, timeout=None, num_ctx=None):
        cagrilar.append(num_ctx)
        if len(cagrilar) == 1:
            return {}, {"status": "technical_failure", "reason": "length", "model": m}
        return ({"yonetmen": [], "yapimci": [], "oyuncular": ["John Smith", "Jane Doe"]},
                {"status": "ok", "model": m, "num_ctx": num_ctx})

    monkeypatch.setattr(ctr, "model_chain", lambda: ["m1"])
    monkeypatch.setattr(ctr, "_get_kb", lambda: None)
    monkeypatch.setattr(ctr, "_ollama_json_ex", _fake_ex)
    monkeypatch.setenv("MITAS_DIRECTOR_RESCUE", "0")
    monkeypatch.setenv("MITAS_NONLATIN_TRANSLIT", "0")
    monkeypatch.setenv("MITAS_OLLAMA_NUM_CTX_RETRY", "12288")
    res = ctr.read_credits_auto(["JOHN SMITH", "JANE DOE"], "FILM")
    assert cagrilar == [None, 12288], "ilk normal, ikinci yükseltilmiş, ÜÇÜNCÜ YOK"
    assert res["extraction_status"] == "OK"
    assert res["extraction_detail"]["models"]["m1"].get("length_retry") is True


def test_length_retry_de_kaza_TF_kalir(monkeypatch):
    def _hep_length(m, p, s, timeout=None, num_ctx=None):
        return {}, {"status": "technical_failure", "reason": "length", "model": m}

    monkeypatch.setattr(ctr, "model_chain", lambda: ["m1"])
    monkeypatch.setattr(ctr, "_get_kb", lambda: None)
    monkeypatch.setattr(ctr, "_ollama_json_ex", _hep_length)
    monkeypatch.setenv("MITAS_DIRECTOR_RESCUE", "0")
    monkeypatch.setenv("MITAS_NONLATIN_TRANSLIT", "0")
    res = ctr.read_credits_auto(["X Y"], "FILM")
    assert res["extraction_status"] == "TECHNICAL_FAILURE"


def test_telemetri_yazilir_ve_cokmez(monkeypatch, tmp_path):
    monkeypatch.setattr(rm, "TELEMETRY_PATH", tmp_path / "t.jsonl")
    rm.append_telemetry({"run_id": "r1", "extraction_status": "OK"})
    rm.append_telemetry({"run_id": "r2", "bozuk": object()})  # serileşemez → çökmemeli
    satirlar = (tmp_path / "t.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(satirlar) == 1
    j = json.loads(satirlar[0])
    assert j["run_id"] == "r1" and j["schema_version"] == rm.SCHEMA_VERSION and "ts" in j


# ── _reasoning-kaldırma (2026-07-11, Çağatay onayı; ölçülmüş gerekçe: 13 TF dev-künye) ──
def test_reasoning_default_kaldirilmis(monkeypatch):
    monkeypatch.delenv("MITAS_REASONING", raising=False)
    s = ctr._schema()
    assert "_reasoning" not in s["required"] and "_reasoning" not in s["properties"]
    p = ctr._prompt("SATIR1")
    assert "_reasoning" not in p, "prompt'ta taşma-kaynağı satır-etiketleme talimatı kalmamalı"
    assert '{"yonetmen"' in p


def test_reasoning_rollback_anahtari(monkeypatch):
    """Şartname geri-dönüş anahtarı: MITAS_REASONING=1 eski davranışı AYNEN getirir."""
    monkeypatch.setenv("MITAS_REASONING", "1")
    s = ctr._schema()
    assert s["required"][0] == "_reasoning"
    p = ctr._prompt("SATIR1")
    assert "_reasoning" in p
