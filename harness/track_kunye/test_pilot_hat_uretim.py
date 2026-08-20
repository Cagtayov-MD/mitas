"""pilot_hat üretim uyarlamaları: env-aware yollar + dizin-parametreli havuz."""
import importlib
import os
import sys
from pathlib import Path

import numpy as np
import cv2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _yeniden_yukle():
    import pilot_hat
    return importlib.reload(pilot_hat)


def test_ollama_url_env_ile_degisir(monkeypatch):
    monkeypatch.setenv("MITAS_OLLAMA_URL", "http://ornek:9999")
    ph = _yeniden_yukle()
    assert ph.OLLAMA == "http://ornek:9999/api/generate"
    monkeypatch.delenv("MITAS_OLLAMA_URL")
    ph = _yeniden_yukle()
    assert ph.OLLAMA == "http://127.0.0.1:11434/api/generate"


def test_kb_yolu_env_ile_degisir(monkeypatch):
    monkeypatch.setenv("MITAS_KB_DUCKDB", "/tmp/olmayan.duckdb")
    ph = _yeniden_yukle()
    assert ph.KB_DUCKDB == "/tmp/olmayan.duckdb"


def test_havuz_derle_dizin_istatistigi_donuste(tmp_path):
    ph = _yeniden_yukle()
    # 6 sentetik kare: 3 farklı "sayfa" (içerikli, std>=3), aralarda tekrar
    rng = np.random.default_rng(7)
    desenler = [rng.integers(0, 255, (120, 160), dtype=np.uint8) for _ in range(3)]
    sira = [0, 0, 1, 1, 2, 2]
    for i, d in enumerate(sira):
        cv2.imwrite(str(tmp_path / f"c_{i:04d}.png"), desenler[d])
    secim, ist = ph.havuz_derle_dizin(tmp_path, "*.png")
    assert isinstance(secim, list) and isinstance(ist, dict)
    assert ist["kare"] == 6
    assert ist["sayfa"] >= 1
    assert all(p.parent == tmp_path for p in secim)


def test_havuz_derle_dizin_bos_dizin(tmp_path):
    ph = _yeniden_yukle()
    secim, ist = ph.havuz_derle_dizin(tmp_path, "*.png")
    assert secim == []
    assert ist == {"kare": 0, "sayfa": 0}


def test_havuz_derle_eski_imza_calisiyor(tmp_path, monkeypatch):
    # geriye-uyum: havuz_derle(slug) EX kökünden okur ve SON_HAVUZ_ISTATISTIK doldurur
    ph = _yeniden_yukle()
    monkeypatch.setattr(ph, "EX", tmp_path)
    kok = tmp_path / "deneme-exit_frames"
    kok.mkdir()
    rng = np.random.default_rng(3)
    for i in range(3):
        cv2.imwrite(str(kok / f"exit_{i:06d}.png"),
                    rng.integers(0, 255, (100, 140), dtype=np.uint8))
    secim = ph.havuz_derle("deneme")
    assert isinstance(secim, list)
    assert ph.SON_HAVUZ_ISTATISTIK.get("sayfa") is not None


def test_oku_deepseek_cagri_timeout_parametresi(monkeypatch, tmp_path):
    ph = _yeniden_yukle()
    gorulen = {}
    def sahte_iste(model, prompt, imgs=None, num_predict=2048, num_ctx=8192, timeout=900):
        gorulen["timeout"] = timeout
        return "SATIR BIR"
    monkeypatch.setattr(ph, "ollama_iste", sahte_iste)
    p = tmp_path / "a.png"
    cv2.imwrite(str(p), np.zeros((10, 10), dtype=np.uint8))
    ph.oku_deepseek([p], cagri_timeout=42)
    assert gorulen["timeout"] == 42
