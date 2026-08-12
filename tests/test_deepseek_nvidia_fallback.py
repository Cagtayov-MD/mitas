"""_deepseek NVIDIA yedek-uç (fallback) testleri.

Gerekçe (2026-07-23): DeepSeek özet zincirinin BİRİNCİL motoru yapıldı
(MITAS_OZET_DEEPSEEK=1). Resmi api.deepseek.com kota/kesinti yaşarsa özet
doğrudan gemma-yerel'e düşüyordu (bake-off: yerel modeller güvenilir Türkçe
özet veremiyor). NVIDIA Build aynı modeli (deepseek-ai/deepseek-v3.2) ücretsiz
uçtan sunuyor → _deepseek birincil uç başarısız olunca oraya düşer.

Modül scripts/ altında paket değil; dosya-yolu ile yüklenir
(test_ozet_kalite.py ile aynı desen). HTTP katmanı mock'lanır — ağ yok.
"""
from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
from pathlib import Path
from unittest import mock

_MOD = Path(__file__).resolve().parents[1] / "scripts" / "_deepseek.py"

PRIMARY_BASE = "https://api.deepseek.com"
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "deepseek-ai/deepseek-v4-pro"  # /models teyidi 2026-07-23: katalogda v3.2 yok


def _load():
    spec = importlib.util.spec_from_file_location("_deepseek_under_test", _MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _ok_response(content="ozet metni"):
    """urlopen'ın döndürdüğü context-manager'ı taklit eder."""
    body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    cm = mock.MagicMock()
    cm.__enter__.return_value = io.BytesIO(body)
    cm.__exit__.return_value = False
    return cm


def _http_error(code, body=b"{}"):
    return urllib.error.HTTPError(
        url="http://x", code=code, msg="err", hdrs=None, fp=io.BytesIO(body)
    )


def _payload_of(req):
    return json.loads(req.data.decode("utf-8"))


def _temiz_env(monkeypatch):
    for k in ("MITAS_DEEPSEEK", "DEEPSEEK_API_KEY", "MITAS_NVIDIA",
              "NVIDIA_API_KEY", "MITAS_DEEPSEEK_BASE",
              "MITAS_DEEPSEEK_NVIDIA_BASE", "MITAS_DEEPSEEK_NVIDIA_MODEL"):
        monkeypatch.delenv(k, raising=False)


def test_birincil_basarili_nvidia_cagirilmaz(monkeypatch):
    _temiz_env(monkeypatch)
    monkeypatch.setenv("MITAS_DEEPSEEK", "sk-test")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    ds = _load()
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        return _ok_response()

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        resp = ds.deepseek_chat(prompt="test")

    assert resp is not None
    assert len(calls) == 1
    assert calls[0].full_url.startswith(PRIMARY_BASE)
    assert _payload_of(calls[0])["model"] == "deepseek-chat"


def test_birincil_402_nvidia_fallback(monkeypatch):
    """Kredi bitti (402) → retry YOK, doğrudan NVIDIA ucuna düşer, model eşlenir."""
    _temiz_env(monkeypatch)
    monkeypatch.setenv("MITAS_DEEPSEEK", "sk-test")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    ds = _load()
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        if req.full_url.startswith(PRIMARY_BASE):
            raise _http_error(402, b'{"error":"insufficient balance"}')
        return _ok_response("nvidia ozeti")

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        resp = ds.deepseek_chat(prompt="test")

    assert resp is not None
    assert resp["choices"][0]["message"]["content"] == "nvidia ozeti"
    assert len(calls) == 2
    assert calls[1].full_url.startswith(NVIDIA_BASE)
    assert _payload_of(calls[1])["model"] == NVIDIA_MODEL
    # Yetki başlığı NVIDIA anahtarıyla gitmeli (birincil anahtar sızmamalı)
    assert calls[1].get_header("Authorization") == "Bearer nvapi-test"


def test_hic_anahtar_yoksa_none_ve_ag_cagrisi_yok(monkeypatch):
    _temiz_env(monkeypatch)
    ds = _load()
    with mock.patch("urllib.request.urlopen") as up:
        assert ds.deepseek_chat(prompt="test") is None
        up.assert_not_called()


def test_sadece_nvidia_anahtari_varsa_dogrudan_nvidia(monkeypatch):
    _temiz_env(monkeypatch)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    ds = _load()
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        return _ok_response()

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        resp = ds.deepseek_chat(prompt="test")

    assert resp is not None
    assert len(calls) == 1
    assert calls[0].full_url.startswith(NVIDIA_BASE)
    assert _payload_of(calls[0])["model"] == NVIDIA_MODEL


def test_birincil_gecici_hatalar_tukenince_fallback(monkeypatch):
    """503 tüm denemelerde → birincil tükenir → NVIDIA devreye girer."""
    _temiz_env(monkeypatch)
    monkeypatch.setenv("MITAS_DEEPSEEK", "sk-test")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setattr("time.sleep", lambda s: None)
    ds = _load()
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        if req.full_url.startswith(PRIMARY_BASE):
            raise _http_error(503)
        return _ok_response()

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        resp = ds.deepseek_chat(prompt="test", retries=2)

    assert resp is not None
    primary_calls = [c for c in calls if c.full_url.startswith(PRIMARY_BASE)]
    nvidia_calls = [c for c in calls if c.full_url.startswith(NVIDIA_BASE)]
    assert len(primary_calls) == 2   # retries=2 → 2 deneme
    assert len(nvidia_calls) == 1


def test_nvidia_da_basarisizsa_none(monkeypatch):
    _temiz_env(monkeypatch)
    monkeypatch.setenv("MITAS_DEEPSEEK", "sk-test")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    ds = _load()

    def fake_urlopen(req, timeout=None):
        raise _http_error(402, b'{"error":"insufficient balance"}')

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert ds.deepseek_chat(prompt="test") is None


def test_deepseek_text_fallback_uzerinden_calisir(monkeypatch):
    _temiz_env(monkeypatch)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    ds = _load()

    with mock.patch("urllib.request.urlopen", side_effect=lambda req, timeout=None: _ok_response("metin")):
        assert ds.deepseek_text(prompt="test") == "metin"
