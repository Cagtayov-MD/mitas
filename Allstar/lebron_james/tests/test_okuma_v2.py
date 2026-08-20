"""MITAS_OKUMA_V2 kanıt zinciri — satır-grounding yalnız İLAN EDEN backendte.

Private Ollama görüntü-geneli ``image[[...]]`` döndürür; ona grounding
sormak hem faydasız hem sahte COMPLETE'e açıktı. `_oku` bu yüzden
capability beyanına bakar: beyan yok → ikinci çağrı YOK, kanıt paddle_exact;
beyan var → bant başına bir grounding çağrısı yapılır.
"""
import struct
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import derleyici
import main
import model
import okuyucu


class SahteSor:
    line_grounding_supported = False

    def __init__(self, grounding_yanit=None):
        self.cagrilar = []
        self.grounding_yanit = grounding_yanit

    def __call__(self, path, prompt=None):
        self.cagrilar.append(prompt)
        if prompt is not None and "<|grounding|>" in prompt:
            return self.grounding_yanit or ""
        return "YONETIM AHMET"

    def metrics(self):
        return {"backend": "sahte", "call_count": len(self.cagrilar)}


def _mini_png_yaz(yol, _goruntu):
    """`_png_size`'ın okuyabileceği gerçek başlıklı mini PNG."""
    Path(yol).write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
        + struct.pack(">II", 64, 64) + b"\x00" * 8)


def _kur(monkeypatch, sor):
    monkeypatch.setattr(derleyici, "kare_oku",
                        lambda yol: np.zeros((2400, 1920, 3), np.uint8))
    monkeypatch.setattr(derleyici, "release_ocr_engine", lambda: None)
    monkeypatch.setattr(derleyici, "paddle_satir_kaniti", lambda im: {
        "kutu_n": 1, "width": 64, "height": 64,
        "satirlar": [{"text": "YONETIM AHMET", "confidence": 0.9,
                      "bbox": [1, 2, 40, 12]}]})
    monkeypatch.setattr(derleyici, "yaz", _mini_png_yaz)
    monkeypatch.setattr(okuyucu, "bant_sinirlari",
                        lambda yukseklik, bant_h=None, bindirme=None: [0, 1200])

    gorunen = {}

    def _oku_sahte(yollar, sor_, kutu):
        gorunen.update({
            "yol": [str(p) for p in yollar],
            "kutu": [kutu(str(p)) for p in yollar],
            "satirlar": [sor_(p) for p in yollar]})
        return {"satirlar": ["YONETIM AHMET"], "elenen": []}

    monkeypatch.setattr(okuyucu, "oku", _oku_sahte)
    monkeypatch.setattr(main, "_model_sor", lambda ayar: sor)
    monkeypatch.setattr(main, "_pid_vram_mb", lambda: 0.0)
    return gorunen


def test_private_ollama_satir_grounding_destegini_bildirmez():
    """Sınıf beyanı: bu backend görüntü-geneli yanıt verir, satır kanıtı vermez."""
    assert model.PrivateOllama.line_grounding_supported is False


def test_line_grounding_supported_yalniz_acik_beyanla_gecer():
    assert main._line_grounding_supported(SimpleNamespace()) is False
    assert main._line_grounding_supported(
        SimpleNamespace(line_grounding_supported=True)) is True
    assert main._line_grounding_supported(
        SimpleNamespace(capabilities={"line_grounding": 1})) is True
    assert main._line_grounding_supported(
        SimpleNamespace(capabilities={"grounding": True})) is True


def test_beyan_yoksa_bant_basina_tek_model_cagrisi(monkeypatch, tmp_path):
    """Destek bildirmeyen backendte grounding çağrısı yapılmaz: model
    çağrı sayısı bant sayısına düşer, kanıt paddle_exact stratejisine kalır."""
    monkeypatch.setenv("MITAS_OKUMA_V2", "1")
    sor = SahteSor()
    gorunen = _kur(monkeypatch, sor)

    r = main._oku(tmp_path / "master.png", "cikis", "F_V2_TEST", {})

    assert len(sor.cagrilar) == 2                     # 2 bant × yalnız Free OCR
    assert all(cagr is None for cagr in sor.cagrilar)
    assert r["proof_strategy"] == "paddle_exact"
    assert r["grounding_unsupported"] == "backend_has_no_line_grounding"
    assert "grounding" not in r
    # Paddle satır haritası model yüklenmeden önce önbelleğe alınmış olmalı
    assert r["paddle_satir_haritasi"]["bant_000.png"]["items"][0]["text"] == \
        "YONETIM AHMET"
    assert r["paddle_satir_haritasi"]["bant_001.png"]["width"] == 64
    assert r["bant_y0"] == [0, 1200]
    assert gorunen["kutu"] == [1, 1]


def test_beyan_eden_backendte_grounding_ikinci_cagriyi_alir(monkeypatch, tmp_path):
    monkeypatch.setenv("MITAS_OKUMA_V2", "1")
    sor = SahteSor(grounding_yanit=(
        "<|ref|>YONETIM AHMET<|/ref|><|det|>[[10, 20, 500, 100]]<|/det|>"))
    sor.line_grounding_supported = True
    _kur(monkeypatch, sor)

    r = main._oku(tmp_path / "master.png", "cikis", "F_V2_TEST", {})

    assert len(sor.cagrilar) == 4                     # 2 Free OCR + 2 grounding
    assert sum(1 for c in sor.cagrilar if c and "<|grounding|>" in c) == 2
    assert r["proof_strategy"] == "model_line_grounding"
    assert "grounding_unsupported" not in r
    item = r["grounding"]["bant_000.png"]["items"][0]
    assert item["label"] == "YONETIM AHMET"
    assert item["boxes_999"] == [[10.0, 20.0, 500.0, 100.0]]
    assert r["grounding"]["bant_001.png"]["height"] == 64
