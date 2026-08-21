"""tests/test_kanal_ocr.py — OCR tanık kanalı birim testleri.

GPU/Paddle İSTEMEZ — Sahte modeller ve yapay kutularla çalışır.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "src"))

from kanal_ocr import (
    BANT_ORANI,
    CATISMA_ALT,
    CATISMA_UST,
    Tanik,
    ara,
    benzer,
    kanit_indeksi,
    norm,
    satir_adaylari,
    yuvarla,
)


def test_norm_turkce_ve_diakritik():
    assert norm("İSTANBUL") == "istanbul"
    assert norm("IŞIK", katla=False) == "ışık"
    assert norm("IŞIK", katla=True) == "isik"
    assert norm("SER PİL", bosluksuz=True) == "serpil"


def test_benzer_bosluk_ve_yazim():
    assert benzer("SERPİL TEZCAN", "SER PİL TEZCAN") >= 0.95
    assert benzer("TEOMAN TARHAN", "TEOMAN TARHAN") == 1.0
    assert benzer("TEOMAN TARHAN", "XYZ QWE 123") < 0.30


def test_satir_adaylari_bant_ve_kutu():
    # 2 kutu: "Yapım" ve "TEOMAN TARHAN" aynı yatay bantta
    kutular = [
        {"kare_no": 1, "metin": "Yapım", "guven": 0.95, "x1": 100, "y1": 200, "x2": 180, "y2": 230, "y_orani": 0.43},
        {"kare_no": 1, "metin": "TEOMAN TARHAN", "guven": 0.92, "x1": 200, "y1": 202, "x2": 450, "y2": 232, "y_orani": 0.434},
    ]
    adaylar = satir_adaylari(kutular, kare_yuksekligi=500, min_guven=0.80)
    metinler = [a["metin"] for a in adaylar]
    assert "Yapım TEOMAN TARHAN" in metinler
    assert "Yapım" in metinler
    assert "TEOMAN TARHAN" in metinler


def test_ara_zaman_penceresi_ve_pay():
    indeks = {
        "kareler": {
            1: [{"metin": "ÖNCEKİ METİN", "kare_no": 1, "y_orani": 0.2, "guven": 0.9, "tip": "kutu"}],
            10: [{"metin": "TEOMAN TARHAN", "kare_no": 10, "y_orani": 0.5, "guven": 0.95, "tip": "kutu"}],
            50: [{"metin": "SONRAKİ METİN", "kare_no": 50, "y_orani": 0.8, "guven": 0.9, "tip": "kutu"}],
        }
    }

    # kare_araligi [8, 12], pay 2 -> kareler 6..14 taranır -> kare 10 bulunur
    res = ara(indeks, "TEOMAN TARHAN", [8, 12], pay=2)
    assert res["ocr_skor"] == 1.0
    assert res["kare_no"] == 10

    # kare_araligi [30, 35], pay 2 -> kareler 28..37 taranır -> bulunamaz
    res_yok = ara(indeks, "TEOMAN TARHAN", [30, 35], pay=2)
    assert res_yok["ocr_skor"] < 0.3
    assert res_yok["kare_no"] is None


def test_ara_catisma_tespiti():
    # Kare 10'da aynı Y bandında farklı bir metin var (rol kayması)
    indeks = {
        "kareler": {
            10: [
                {"metin": "Kostüm EDWARD STEVENSON", "kare_no": 10, "y_orani": 0.50, "guven": 0.92, "tip": "bant_guclu"},
            ]
        }
    }
    # VLM yanlışlıkla EDITH HEAD okumuş olsun
    res = ara(indeks, "Kostüm EDITH HEAD", [10, 10], pay=2)
    # Benzerlik ~0.50 - 0.70 aralığında olmalı ve çatışma yakalanmalı
    assert res["catisma"] is not None
    assert res["catisma"]["metin"] == "Kostüm EDWARD STEVENSON"


def test_yuvarla_dosya_boyutunu_optimize_eder():
    indeks = {
        "kareler": {
            1: [{"metin": "TEST", "x1": 10.12345, "y1": 20.6789, "x2": 30.111, "y2": 40.222,
                 "y_orani": 0.12345678, "guven": 0.987654}]
        }
    }
    yuv = yuvarla(indeks, koordinat_ondalik=1)
    kutu = yuv["kareler"][1][0]
    assert kutu["x1"] == 10.1
    assert kutu["y1"] == 20.7
    assert kutu["y_orani"] == 0.1235
    assert kutu["guven"] == 0.9877


def test_kanit_indeksi_sahte_tanikla():
    class SahteTanik:
        def __init__(self):
            self.ayarlar = {"det_thresh": 0.2, "box_thresh": 0.45, "unclip_ratio": 1.4, "min_guven": 0.8}

        def oku(self, yol, kare_no=1):
            return [{"kare_no": kare_no, "metin": "Kurgu", "guven": 0.95,
                     "x1": 50, "y1": 50, "x2": 100, "y2": 80, "y_orani": 0.13}]

        def kanit(self):
            return {"det": {"ad": "sahte"}, "rec": {"ad": "sahte"}}

        def kapat(self):
            pass

    manifest = {
        "kareler": [{"sira": 1, "dosya": "k_00001.jpg", "yukseklik": 500, "genislik": 720, "kaynak_sn": 0.0}]
    }
    res = kanit_indeksi(manifest, "/tmp", tanik=SahteTanik())
    assert 1 in res["kareler"]
    assert len(res["kareler"][1]) > 0
    assert res["kanit"]["toplam_kutu"] == 1
