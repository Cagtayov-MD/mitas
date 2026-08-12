"""scripts/credit_role_lexicon — betik-farkında isim-çıkarma hattı (adım 3/5).

Arıza (spec §2.1): `norm()` Latin-dışı HER karakteri siliyordu (`[^A-Z ]+` →
boşluk), bu yüzden DIRECTOR listesindeki REJISOR/MUHARRIJ/DAOYAN gibi Kiril/
Arapça/Çince translit girdileri hiçbir zaman gerçek üretilemeyen ölü kod idi.

Düzeltme (§4.3): `betik_bul(text)=='LATIN'` ise davranış birebir korunur (§6.1);
değilse `rol_tablosu.rol_esles` + `TABLO`'nun kelime listesi üzerinden isim
çıkarılır (`norm()` DEĞİL — o Latin-dışını siliyor).

Bu testler PaddleOCR istemez — saf string fonksiyonları.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import credit_role_lexicon as crl  # noqa: E402


# ── Latin regresyonu (norm() davranışı DEĞİŞMEDİ) ────────────────────────
def test_norm_latin_disini_hala_siliyor():
    """norm() DEĞİŞTİRİLMEDİ — Latin-dışı hâlâ boşluğa düşer (§4.3)."""
    assert crl.norm("Режиссёр Алексей Герман") == ""
    assert crl.norm("کارگردان مجید مجیدی") == ""


@pytest.mark.parametrize("satir,beklenen_isim", [
    ("DIRECTED BY JOHN FORD", "JOHN FORD"),
    ("Yönetmen: Nuri Bilge Ceylan", "NURI BILGE CEYLAN"),
    ("A NIKI CARO FILM", "NIKI CARO"),
    ("Director of Photography Gregg Toland", ""),   # alt-rol, dışlanır
])
def test_latin_isim_cikarma_bozulmadi(satir, beklenen_isim):
    assert crl.director_name_from_line(satir) == beklenen_isim


# ── Önceden hiç desteklenmeyen betikler (§1/§2.1 ölü-kod bulgusu) ────────
def test_kiril_isim_cikarilir():
    isim = crl.director_name_from_line("Режиссёр Алексей Герман")
    assert isim, "Kiril yönetmen satırından isim çıkmalı"
    assert "Алексей" in isim or "Герман" in isim


def test_ibrani_yonetmen_satiri_taninir():
    assert crl.is_director_line("במאי דני רוזנברג")


def test_korece_yonetmen_satiri_taninir():
    assert crl.is_director_line("감독 박찬욱")


def test_farsca_yonetmen_satiri_taninir():
    assert crl.is_director_line("کارگردان مجید مجیدی")


def test_yunanca_yonetmen_satiri_taninir():
    assert crl.is_director_line("ΣΚΗΝΟΘΕΤΗΣ Θεόδωρος Αγγελόπουλος")


def test_cjk_yonetmen_satiri_taninir():
    assert crl.is_director_line("导演张艺谋")


# ── §6.3 kırmızı çizgi: isim çıkarma hattında alt-roller YÖNETMEN DEĞİL ──
@pytest.mark.parametrize("satir", [
    "촬영감독 이모개",
    "조감독 김민수",
    "副导演 王芳",
    "助理导演 李明",
    "עוזר במאי דני",
    "دستیار کارگردان علی",
    "ΒΟΗΘΟΣ ΣΚΗΝΟΘΕΤΗΣ Γιώργος",
    "АССИСТЕНТ РЕЖИССЕРА Иван Петров",
    "ПОМОЩНИК РЕЖИССЕРА Мария Иванова",
])
def test_alt_roller_isim_cikarma_hattinda_yonetmen_sayilmaz(satir):
    assert crl.is_director_line(satir) is False, satir
    assert crl.director_name_from_line(satir) == "", satir


# ── norm_betik: Latin-dışı karakterleri SİLMEZ (norm()'un tersine) ───────
def test_norm_betik_karakterleri_silmez():
    assert "режиссёр" in crl.norm_betik("  Режиссёр   Алексей Герман  ").lower() \
        or "Режиссёр" in crl.norm_betik("  Режиссёр   Алексей Герман  ")


def test_norm_betik_bosluklari_temizler():
    assert crl.norm_betik("  А    Б  ") == "А Б"


# ── Gerçek film vektörleri (§1, ocr_ham.txt'ten) ─────────────────────────
def test_masumiyet_ibrani_gercek_satir():
    # MASUMİYET DÜŞLERİ 1994-0238 gerçek OCR satırı (ocr_ham.txt): tam sözcük
    # "עוזרת" (yardımcı) ile yazılmış satır isim çıkarma hattında dışlanır.
    assert crl.is_director_line("עוזרת לבמאית") is False


def test_sercelerin_sarkisi_farsca_gercek_satir():
    assert crl.director_name_from_line("کارگردان") == ""  # isim yok, yalnız etiket
    assert crl.is_director_line("کارگردان") is False       # bare head, isim yok — Latin ile TUTARLI
