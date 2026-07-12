# -*- coding: utf-8 -*-
"""İP-2 extraction_status sözleşmesi testleri (2026-07-11, plan rev.4).
Sahte-arıza enjeksiyonu (şartname kabul kriteri): length/timeout/HTTP kazasında
(1) durum TECHNICAL_FAILURE olarak zincirde taşınır, (2) DEFERANS mekanik sonucu SİLMEZ,
(3) geçerli-boş JSON = ABSTAIN (bilinçli-boş; DEFERANS uygulanır), (4) dolu = OK.
Ağ yok — urlopen/_ollama_json_ex monkeypatch'li."""
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import credit_text_read as ctr  # noqa: E402
import _pipe_pdf as pp  # noqa: E402


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(payload: dict):
    def _f(req, timeout=None):
        return _FakeResp(json.dumps(payload).encode("utf-8"))
    return _f


# ── Katman 1: _ollama_json_ex ────────────────────────────────────────────────
def test_ex_gecerli_json_ok(monkeypatch):
    monkeypatch.setattr(ctr.urllib.request, "urlopen", _fake_urlopen(
        {"response": json.dumps({"yonetmen": ["X Y"]}), "done_reason": "stop",
         "prompt_eval_count": 1200, "eval_count": 88}))
    data, meta = ctr._ollama_json_ex("m", "p", {})
    assert data == {"yonetmen": ["X Y"]}
    assert meta["status"] == "ok"
    assert meta["prompt_eval_count"] == 1200 and meta["eval_count"] == 88


def test_ex_length_kesilmesi_technical_failure(monkeypatch):
    """KARAR KİMİN sınıfı: done_reason=length + yarım-JSON → artık SESSİZ {} değil."""
    monkeypatch.setattr(ctr.urllib.request, "urlopen", _fake_urlopen(
        {"response": '{"_reasoning": "satir satir aciklarken kesil', "done_reason": "length"}))
    data, meta = ctr._ollama_json_ex("m", "p", {})
    assert data == {}
    assert meta["status"] == "technical_failure"
    assert meta["reason"] == "length"


def test_ex_length_parse_edilebilir_json_olsa_da_technical_failure(monkeypatch):
    """Kesilmis cevap sentaktik JSON olabilir; done_reason=length yine tamamlanmamis demektir."""
    monkeypatch.setattr(ctr.urllib.request, "urlopen", _fake_urlopen(
        {"response": json.dumps({"yonetmen": ["Eksik Ama Parse Edilir"]}),
         "done_reason": "length", "prompt_eval_count": 8000, "eval_count": 2048}))
    data, meta = ctr._ollama_json_ex("m", "p", {})
    assert data == {}
    assert meta["status"] == "technical_failure"
    assert meta["reason"] == "length"


def test_ex_baglanti_kazasi_technical_failure(monkeypatch):
    def _boom(req, timeout=None):
        raise OSError("connection refused")
    monkeypatch.setattr(ctr.urllib.request, "urlopen", _boom)
    data, meta = ctr._ollama_json_ex("m", "p", {})
    assert data == {}
    assert meta["status"] == "technical_failure"
    assert meta["reason"] in ("http", "timeout")


def test_eski_sarmalayici_geri_uyum(monkeypatch):
    monkeypatch.setattr(ctr.urllib.request, "urlopen", _fake_urlopen(
        {"response": json.dumps({"satirlar": ["a"]}), "done_reason": "stop"}))
    assert ctr._ollama_json("m", "p", {}) == {"satirlar": ["a"]}


# ── Katman 2: read_credits_auto aggregate ────────────────────────────────────
@pytest.fixture()
def _izole(monkeypatch):
    """KB/rescue/translit kapalı — yalnız aggregate mantığı test edilir."""
    monkeypatch.setattr(ctr, "model_chain", lambda: ["m1"])
    monkeypatch.setattr(ctr, "_get_kb", lambda: None)
    monkeypatch.setenv("MITAS_DIRECTOR_RESCUE", "0")
    monkeypatch.setenv("MITAS_NONLATIN_TRANSLIT", "0")
    monkeypatch.setenv("MITAS_CREDIT_CAST_BLOCK_FAST", "0")


def test_auto_hepsi_kaza_TECHNICAL_FAILURE(monkeypatch, _izole):
    monkeypatch.setattr(ctr, "_ollama_json_ex", lambda m, p, s, timeout=None: (
        {}, {"status": "technical_failure", "reason": "length", "model": m}))
    res = ctr.read_credits_auto(["DIRECTED BY", "JOHN SMITH"], "FILM")
    assert res["extraction_status"] == "TECHNICAL_FAILURE"
    assert res["guven"] == "OKUNAMADI"
    assert res["extraction_detail"]["ok_models"] == []


def test_auto_gecerli_bos_ABSTAIN(monkeypatch, _izole):
    monkeypatch.setattr(ctr, "_ollama_json_ex", lambda m, p, s, timeout=None: (
        {"yonetmen": [], "yapimci": [], "oyuncular": []}, {"status": "ok", "model": m}))
    res = ctr.read_credits_auto(["METIN VAR AMA ISIM YOK"], "FILM")
    assert res["extraction_status"] == "ABSTAIN"


def test_auto_dolu_OK(monkeypatch, _izole):
    # NOT: yönetmen tek-model+KB'siz bilinçli düşer ("dolu≠doğru" kanunu) — OK'yi cast taşır.
    monkeypatch.setattr(ctr, "_ollama_json_ex", lambda m, p, s, timeout=None: (
        {"yonetmen": [], "yapimci": [], "oyuncular": ["John Smith", "Jane Doe"]},
        {"status": "ok", "model": m}))
    res = ctr.read_credits_auto(["JOHN SMITH", "JANE DOE"], "FILM")
    assert res["extraction_status"] == "OK"
    assert "John Smith" in res["cast"]


def test_auto_kismi_model_kazasi_DEGRADED_olarak_gorunur(monkeypatch, _izole):
    monkeypatch.setattr(ctr, "model_chain", lambda: ["m_ok", "m_fail"])

    def _mixed(model, prompt, schema, timeout=None, num_ctx=None):
        if model == "m_ok":
            return ({"yonetmen": [], "yapimci": [],
                     "oyuncular": ["John Smith", "Jane Doe"]},
                    {"status": "ok", "model": model})
        return {}, {"status": "technical_failure", "reason": "timeout", "model": model}

    monkeypatch.setattr(ctr, "_ollama_json_ex", _mixed)
    res = ctr.read_credits_auto(["JOHN SMITH", "JANE DOE"], "FILM")
    assert res["extraction_status"] == "DEGRADED"
    assert res["degraded"] is True
    assert res["extraction_detail"]["ok_models"] == ["m_ok"]
    assert res["extraction_detail"]["failed_models"] == ["m_fail"]
    assert any("m_fail:timeout" in r for r in res["degraded_reasons"])


def test_auto_rescue_teknik_kazayi_MASKELEMEZ(monkeypatch, _izole):
    """Şartname: LLM-kaza + deterministik-rescue dolu → rescue KORUNUR ama status TF kalır."""
    monkeypatch.setenv("MITAS_DIRECTOR_RESCUE", "1")
    monkeypatch.setattr(ctr, "_ollama_json_ex", lambda m, p, s, timeout=None: (
        {}, {"status": "technical_failure", "reason": "timeout", "model": m}))
    res = ctr.read_credits_auto(["JOHN SMITH", "directed by"], "FILM")
    assert res["extraction_status"] == "TECHNICAL_FAILURE"
    if res["yonetmen"]:  # rescue bulduysa kanıt korunmuş VE maskelenmemiş olmalı
        assert res["extraction_detail"]["rescue_filled"] is True


# ── Katman 4→PDF: DEFERANS ön-koşulu ─────────────────────────────────────────
_MEKANIK_CREW = [("Yönetmen", ["Gercek Yonetmen"]), ("Müzik", ["Besteci Kisi"])]


def test_deferans_teknik_kazada_mekanik_KORUNUR():
    cast, crew = pp._apply_video_credits_authoritative(
        ["A B"], list(_MEKANIK_CREW),
        {"yonetmen": [], "yapimci": [], "extraction_status": "TECHNICAL_FAILURE"}, dizi=False)
    assert ("Yönetmen", ["Gercek Yonetmen"]) in crew, "kaza mekanik sonucu SILEMEZ (dar pencere kapandi)"


def test_deferans_abstain_bilincli_bos_SILER():
    """ABSTAIN = bilinçli-boş → DEFERANS politikası AYNEN işler (okunamadı>yanlış-oku)."""
    cast, crew = pp._apply_video_credits_authoritative(
        ["A B"], list(_MEKANIK_CREW),
        {"yonetmen": [], "yapimci": [], "extraction_status": "ABSTAIN"}, dizi=False)
    assert not any(r == "Yönetmen" for r, _ in crew), "bilinçli-boşta deference eski davranış"


def test_deferans_ok_dolu_otorite():
    cast, crew = pp._apply_video_credits_authoritative(
        ["A B"], list(_MEKANIK_CREW),
        {"yonetmen": ["Yeni Yonetmen"], "yapimci": [], "extraction_status": "OK"}, dizi=False)
    assert ("Yönetmen", ["Yeni Yonetmen"]) in crew
