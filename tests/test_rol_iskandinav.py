"""İskandinav (sv/no/da) rol kelimeleri — KULÜBEDEKİ_YAŞLI_ADAM arızası.

Arıza (2026-08-12): SVERIGES TELEVISION belgeselinde kutu sinyali jeneriği DOĞRU
buldu (kare 649-719, son_ok=True) ama kare başına 1-3 isim düşüyordu (seyrek kart
düzeni) → kredi_skoru_coklu'nun varsayılan yogun_esik=4'ü geçilemedi, kb=0.00.
Seyrek-kredi yolu (eşiği 4→2 indirir) ≥2 ÇEKİRDEK-ROL ister; 'Filmfoto' /
'Redigering' 7 dilin regex'ine uymadığı için hiç tetiklenmedi.

PaddleOCR İSTEMEZ — credit_content'te Paddle tembel yükleniyor, bu testler yalnız
regex'e dokunuyor.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness" / "kunye_kiyas"))

import credit_content as cc  # noqa: E402


# KULÜBEDEKİ'nin gerçek OCR çıktısı (üretim karelerinden alındı, uydurma değil)
KULUBEDEKI_KARELER = [
    ["Filmfoto, ljud", "Nina Hedenius"],
    ["Redigering", "Nina Hedenius", "Ulf Neidemar"],
    ["En film av", "NINA HEDENIUS"],
    ["For", "SVERIGES TELEVISION", "Kanal 1 Dokumentär"],
    ["SVERIGESTELEVISION", "DOKUMENTÄRFILM", "STOCKHOLM"],
]


def test_kulubedeki_karelerinde_iki_cekirdek_rol_bulunur():
    """Seyrek-kredi yolunun tetiklenmesi için ≥2 FARKLI çekirdek-rol şart.
    Arıza anında 0 bulunuyordu."""
    roller = cc.cekirdek_rol_bul(KULUBEDEKI_KARELER)
    assert len(roller) >= 2, f"çekirdek-rol yetersiz: {roller}"


@pytest.mark.parametrize("satir,beklenen", [
    ("Filmfoto, ljud", True),
    ("Redigering", True),
    ("Regi Nina Hedenius", True),
    ("Manus", True),
    ("Klippning", True),
    ("Medverkande", True),
    ("Instruktion", True),          # Danca
    ("Produsent", True),            # Norveççe ('produc\\w*' bunu YAKALAMAZ)
    ("Musikk", True),               # Norveççe ('musik' \\b yüzünden yakalamaz)
    ("Skuespillere", True),
])
def test_iskandinav_rol_kelimeleri_taniniyor(satir, beklenen):
    assert bool(cc._ROL_CEKIRDEK.search(satir)) is beklenen


@pytest.mark.parametrize("satir", [
    "Roller Skating Champion",   # 'roller' EN kelimesi — 'roller'(sv) ALINMADI
    "Photo by the roller crew",
    "Lyd Studios Incorporated",  # 'lyd' 3 harf — ALINMADI
])
def test_carpisma_riskli_kelimeler_alinmadi(satir):
    """SEÇİM DİSİPLİNİ: kısa/çarpışan kelimeler bilerek dışarıda bırakıldı
    (kodun kendi 'vágó' içtihadı). Bu test o kararı kilitler."""
    assert not cc._ROL_CEKIRDEK.search(satir), f"çarpışma: {satir!r}"


def test_mevcut_diller_bozulmadi():
    """Yedi dilin (EN/TR/IT/FR/DE/ES/HU) örnekleri aynen tutmaya devam etmeli."""
    for satir in ("Directed by", "Yönetmen", "Regia", "Réalisation",
                  "Drehbuch", "Dirección", "Rendezte"):
        assert cc._ROL_CEKIRDEK.search(satir), f"regresyon: {satir!r}"
