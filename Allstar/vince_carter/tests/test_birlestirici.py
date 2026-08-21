"""tests/test_birlestirici.py — Kanıt tartısı, füzyon ve kümeleme testleri."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "src"))

from birlestirici import (
    adaylari_siniflandir,
    birlestir,
    diakritik_hakemligi_uygula,
    fazlari_hizala,
    kanit_capasiyla_kumele,
    konum_tutarliligi_denetle,
)


def test_fazlari_hizala_ve_tutar_isareti():
    faz0 = [
        {"metin": "Yönetmen", "grup_no": 0, "kare_araligi": [1, 8]},
        {"metin": "TEOMAN TARHAN", "grup_no": 0, "kare_araligi": [1, 8]},
        {"metin": "Görüntü Yönetmeni", "grup_no": 1, "kare_araligi": [8, 15]},
    ]
    fazK = [
        {"metin": "Yonetmen", "grup_no": 0, "kare_araligi": [5, 12]},
        {"metin": "TEOMAN TARHAN", "grup_no": 0, "kare_araligi": [5, 12]},
        {"metin": "Kurgu", "grup_no": 1, "kare_araligi": [12, 19]},
    ]
    birlesik = fazlari_hizala(faz0, fazK)
    metinler = [b["metin"] for b in birlesik]
    assert "Yönetmen" in metinler
    assert "TEOMAN TARHAN" in metinler
    assert "Görüntü Yönetmeni" in metinler
    assert "Kurgu" in metinler

    # TEOMAN TARHAN iki fazda da var -> faz_tutar True olmalı
    teoman = next(b for b in birlesik if b["metin"] == "TEOMAN TARHAN")
    assert teoman["faz_tutar"] is True

    # Görüntü Yönetmeni yalnız faz0'da var -> faz_tutar False
    gy = next(b for b in birlesik if b["metin"] == "Görüntü Yönetmeni")
    assert gy["faz_tutar"] is False


def test_konum_tutarliligi_kendall_ihlalinde_skoru_sifirlar():
    adaylar = [
        {"metin": "Satir 1", "grup_no": 0, "y_orani": 0.85, "ocr_skor": 0.95},  # Ekranın en altında ama ilk satır
        {"metin": "Satir 2", "grup_no": 0, "y_orani": 0.20, "ocr_skor": 0.95},
        {"metin": "Satir 3", "grup_no": 0, "y_orani": 0.35, "ocr_skor": 0.95},
    ]
    konum_tutarliligi_denetle(adaylar)
    assert adaylar[0]["konum_uyumlu"] is False
    assert adaylar[0]["ocr_skor_etkin"] == 0.0
    assert adaylar[1]["konum_uyumlu"] is True
    assert adaylar[1]["ocr_skor_etkin"] == 0.95


def test_kanit_capasiyla_kumeleme_marnali_mutasyonunu_cozer():
    # Marnalı vakası: ŞÜKRÜ TİRKİŞ ve varyantları aynı OCR satırına (`ŞÜKRÜ TİRKİŞ`) denk gelir
    adaylar = [
        {"metin": "ŞÜKRÜ TİRKİŞ", "eslesen_metin": "ŞÜKRÜ TİRKİŞ", "ocr_kare_no": 20, "ocr_skor_etkin": 1.0, "faz_tutar": True, "kare_araligi": [18, 24]},
        {"metin": "ŞÜKRÜ TIRKİŞ", "eslesen_metin": "ŞÜKRÜ TİRKİŞ", "ocr_kare_no": 21, "ocr_skor_etkin": 0.91, "faz_tutar": False, "kare_araligi": [20, 26]},
        {"metin": "ŞÜKRÜ TIRKIŞ", "eslesen_metin": "ŞÜKRÜ TİRKİŞ", "ocr_kare_no": 22, "ocr_skor_etkin": 0.88, "faz_tutar": False, "kare_araligi": [22, 28]},
    ]
    kumeli = kanit_capasiyla_kumele(adaylar, kare_payi=4)
    assert len(kumeli) == 1
    temsilci = kumeli[0]
    assert temsilci["metin"] == "ŞÜKRÜ TİRKİŞ"
    assert set(temsilci["varyantlar"]) == {"ŞÜKRÜ TIRKİŞ", "ŞÜKRÜ TIRKIŞ"}
    assert temsilci["kare_araligi"] == [18, 28]


def test_siniflandirma_ve_dejenerasyon_pastane_kanaryasi():
    # Kırmızı Çizgi 1: Pastane uydurması 'Yılmaz Erdoğan' ekranda hiç yok (ocr_skor_etkin = 0)
    adaylar = [
        {"metin": "Yapım Koordinatörü: Yılmaz Erdoğan", "ocr_skor_etkin": 0.0, "faz_tutar": False, "dejenerasyon": True},
        {"metin": "TEOMAN TARHAN", "ocr_skor_etkin": 0.95, "faz_tutar": True, "dejenerasyon": False},
        {"metin": "SERPİL TEZCAN", "ocr_skor_etkin": 0.92, "faz_tutar": False, "dejenerasyon": False},
        {"metin": "Kurgu", "ocr_skor_etkin": 0.0, "faz_tutar": True, "dejenerasyon": False},
        {"metin": "Bilinmeyen Satir", "ocr_skor_etkin": 0.1, "faz_tutar": False, "dejenerasyon": False},
    ]
    adaylari_siniflandir(adaylar, E1=0.75, E2=0.55)

    assert adaylar[0]["sinif"] == "SUPHELI"  # Uydurma karantinaya alındı!
    assert adaylar[1]["sinif"] == "KESIN"
    assert adaylar[2]["sinif"] == "ZAYIF"    # Yalnız OCR kanıtı var
    assert adaylar[3]["sinif"] == "ZAYIF"    # Yalnız faz tutarlılığı var (stilize jenerik kurtarma)
    assert adaylar[4]["sinif"] == "SUPHELI"  # İki olumsuz sinyal


def test_diakritik_hakemligi():
    adaylar = [
        {"metin": "YETIM", "eslesen_metin": "YETİM", "guven": 0.95},
        {"metin": "SERPIL", "eslesen_metin": "SERPİL", "guven": 0.92},
    ]
    degisen = diakritik_hakemligi_uygula(adaylar, mod="ocr_kazanir")
    assert degisen == 2
    assert adaylar[0]["metin"] == "YETİM"
    assert adaylar[0]["hakem"]["onceki"] == "YETIM"
    assert adaylar[1]["metin"] == "SERPİL"


def test_birlestir_tum_akis():
    manifest = {
        "kareler": [
            {"sira": 1, "dosya": "k_00001.jpg", "kaynak_sn": 0.0},
            {"sira": 8, "dosya": "k_00008.jpg", "kaynak_sn": 3.5},
        ]
    }
    ocr_indeksi = {
        "kareler": {
            1: [{"metin": "TEOMAN TARHAN", "kare_no": 1, "y_orani": 0.5, "guven": 0.95, "tip": "kutu"}],
        },
        "kanit": {"toplam_kutu": 1}
    }
    vlm_fazlari = [
        {
            "faz": 0,
            "satirlar": [{"metin": "TEOMAN TARHAN", "grup_no": 0, "kare_araligi": [1, 8], "ilk_sn": 0.0, "son_sn": 3.5}],
            "kanit": {"grup_sayisi": 1}
        },
        {
            "faz": 4,
            "satirlar": [{"metin": "TEOMAN TARHAN", "grup_no": 0, "kare_araligi": [1, 8], "ilk_sn": 0.0, "son_sn": 3.5}],
            "kanit": {"grup_sayisi": 1}
        }
    ]

    sonuc = birlestir(manifest, ocr_indeksi, vlm_fazlari, esikler={"E1": 0.75, "E2": 0.55})
    assert len(sonuc["satirlar"]) == 1
    satir = sonuc["satirlar"][0]
    assert satir["metin"] == "TEOMAN TARHAN"
    assert satir["sinif"] == "KESIN"
    assert satir["ocr_skor"] == 1.0
    assert satir["faz_tutar"] is True
    assert "kanit" in sonuc
