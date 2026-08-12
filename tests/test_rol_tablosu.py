"""core/lexicon/rol_tablosu — betik-farkında rol tanıma (§7 test planı).

Tasarım: docs/superpowers/specs/2026-08-12-betik-farkinda-rol-tanima-design.md

FAZ-2 ilkesi: rol eşleşmesi `get_aktif_dil()` (LLM tahmini) DEĞİL, satırın kendi
unicodedata betiğine bakar. Bu dosya yalnız `core/lexicon/rol_tablosu.py`'yi test
eder — stdlib dışında bağımlılık yok, PaddleOCR/Ollama istemez.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.lexicon.rol_tablosu import TABLO, betik_bul, rol_esles  # noqa: E402


# ── A. Betik tespiti ─────────────────────────────────────────────────────
@pytest.mark.parametrize("satir,beklenen", [
    ("DIRECTED BY JOHN FORD", "LATIN"),
    ("Yönetmen: Nuri Bilge Ceylan", "LATIN"),
    ("Режиссёр Алексей Герман", "KIRIL"),
    ("режиссера", "KIRIL"),
    ("کارگردان مجید مجیدی", "ARAP"),
    ("نویسنده و کارگردان :", "ARAP"),
    ("במאי", "IBRANI"),
    ("עוזרת לבמאית", "IBRANI"),
    ("ΣΚΗΝΟΘΕΤΗΣ", "YUNAN"),
    ("Σκηνοθεσία", "YUNAN"),
    ("감독 박찬욱", "HANGUL"),
    ("연출", "HANGUL"),
    ("导演张艺谋", "CJK"),
    ("監督：是枝裕和", "CJK"),
])
def test_betik_bul_dogru_betigi_secer(satir, beklenen):
    assert betik_bul(satir) == beklenen


def test_betik_bul_karisik_satirda_baskin_betigi_secer():
    # 8 Kiril harfi (ИВАНОВИЧИ) vs 3 Latin harfi (ABC) -> Kiril baskın
    assert betik_bul("ABC ИВАНОВИЧИ") == "KIRIL"
    # 8 Latin harfi (DIRECTOR) vs 3 Kiril harfi (ИВА) -> Latin baskın
    assert betik_bul("DIRECTOR ИВА") == "LATIN"


def test_betik_bul_bos_satirda_bos_doner():
    assert betik_bul("") == "BOS"
    assert betik_bul("   ") == "BOS"
    assert betik_bul("123 -- ...") == "BOS"


# ── B. Pozitif eşleşme (haric_uygula=False, KOBE onset çapası) ──────────
@pytest.mark.parametrize("satir", [
    "Режиссёр Алексей Герман",
    "режиссера",
    "РЕЖИССЕР",
])
def test_kiril_pozitif(satir):
    assert rol_esles(satir, "YONETMEN", haric_uygula=False) is True


def test_arap_pozitif():
    assert rol_esles("کارگردان مجید مجیدی", "YONETMEN", haric_uygula=False) is True


@pytest.mark.parametrize("satir", ["במאי", "בימוי"])
def test_ibrani_pozitif(satir):
    assert rol_esles(satir, "YONETMEN", haric_uygula=False) is True


def test_hangul_pozitif():
    assert rol_esles("감독 박찬욱", "YONETMEN", haric_uygula=False) is True


@pytest.mark.parametrize("satir", [
    "导演张艺谋",       # boşluksuz basit Çince
    "導演",             # geleneksel
    "監督：是枝裕和",    # Japonca
])
def test_cjk_pozitif(satir):
    assert rol_esles(satir, "YONETMEN", haric_uygula=False) is True


def test_yunan_pozitif():
    assert rol_esles("ΣΚΗΝΟΘΕΤΗΣ", "YONETMEN", haric_uygula=False) is True


# ── C. HARIC negatifleri (§6.3 kırmızı çizgi — 9 vektörün tamamı) ───────
_HARIC_VEKTORLER = [
    "촬영감독",              # HANGUL: görüntü yönetmeni
    "조감독",                # HANGUL: yardımcı yönetmen
    "副导演",                # CJK: yardımcı yönetmen
    "助理导演",              # CJK: asistan yönetmen
    "עוזר במאי",             # IBRANI: yardımcı yönetmen
    "دستیار کارگردان",       # ARAP/FARSÇA: yardımcı yönetmen
    "ΒΟΗΘΟΣ ΣΚΗΝΟΘΕΤΗΣ",     # YUNAN: yardımcı yönetmen
    "АССИСТЕНТ РЕЖИССЕРА",   # KIRIL: yönetmen asistanı
    "ПОМОЩНИК РЕЖИССЕРА",    # KIRIL: yönetmen yardımcısı
]


@pytest.mark.parametrize("satir", _HARIC_VEKTORLER)
def test_haric_isim_cikarma_hattinda_dislanir(satir):
    """İsim çıkarma hattı (haric_uygula=True): bunlar YÖNETMEN sayılmamalı."""
    assert rol_esles(satir, "YONETMEN", haric_uygula=True) is False, satir


@pytest.mark.parametrize("satir", _HARIC_VEKTORLER)
def test_haric_kobe_onsetinde_gecerlidir(satir):
    """KOBE onset çapası (haric_uygula=False): 'yardımcı yönetmen' de jeneriktir."""
    assert rol_esles(satir, "YONETMEN", haric_uygula=False) is True, satir


# ── D. Latin regresyonu (en az 10 vektör) ────────────────────────────────
@pytest.mark.parametrize("satir,beklenen", [
    ("DIRECTED BY JOHN FORD", True),
    ("Yönetmen: Nuri Bilge Ceylan", True),
    ("REGIA", True),
    ("UN FILM DE", True),
    ("A FILM BY", True),
    ("GÖRÜNTÜ YÖNETMENİ", False),
    ("ASSISTANT DIRECTOR", False),
    ("DIRECTION ARTISTIQUE", False),
    ("DIRECTOR OF PHOTOGRAPHY", False),
    ("PRODUCED BY JOHN SMITH", False),
])
def test_latin_regresyonu(satir, beklenen):
    assert rol_esles(satir, "YONETMEN", haric_uygula=True) is beklenen, satir


# ── F. Gerçek film vektörleri (§1 — 6 film, ocr_ham.txt'ten kopyalandı) ──
@pytest.mark.parametrize("film,satir,betik", [
    ("MASUMİYET DÜŞLERİ 1994-0238", "ע.במאי 1", "IBRANI"),
    ("DOVLATOV 2018-1036", "режиссер Станислав РУЖЕВИЧ", "KIRIL"),
    ("KOŞUCU 2025-1047", "نویسنده و کارگردان :", "ARAP"),
    ("SERÇELERİN ŞARKISI 2008-1114", "کارگردان", "ARAP"),
    ("MUCİZE 2004-9157", "감독", "HANGUL"),
])
def test_gercek_film_vektorleri_kobe_onsetinde_yakalanir(film, satir, betik):
    assert betik_bul(satir) == betik, f"{film}: beklenmeyen betik"
    assert rol_esles(satir, "YONETMEN", haric_uygula=False) is True, film


def test_seni_seviyorum_frank_latin_isim_cikarma_hattinda_yakalanir():
    """SENİ SEVİYORUM FRANK 1988-0480 — Latin, 'Director-Cameraman' (gerçek OCR satırı).
    credit_parse.py'nin sıra hatası AYRI (adım 5); burada yalnız rol_tablosu'nun
    kelimeyi tanıdığı doğrulanır."""
    satir = "Director-Cameraman, Ron Sandilands"
    assert betik_bul(satir) == "LATIN"
    assert rol_esles(satir, "YONETMEN", haric_uygula=True) is True


# ── Görünürlük (§3.5) — TABLO'da karşılığı olmayan betik loglanır ────────
def test_bilinmeyen_betik_icin_gorunurluk_olayi_loglanir(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="rol_tablosu"):
        sonuc = rol_esles("ทดสอบ ผู้กำกับ", "YONETMEN", haric_uygula=False)
    assert sonuc is False
    assert "rol_tablosu_bosluk" in caplog.text
    assert "THAI" in caplog.text


def test_bos_satir_icin_gorunurluk_olayi_loglanmaz(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="rol_tablosu"):
        sonuc = rol_esles("123", "YONETMEN", haric_uygula=False)
    assert sonuc is False
    assert "rol_tablosu_bosluk" not in caplog.text


# ── TABLO şekli ────────────────────────────────────────────────────────
def test_tablo_yedi_betik_icerir():
    assert set(TABLO.keys()) == {"LATIN", "KIRIL", "ARAP", "IBRANI", "YUNAN", "HANGUL", "CJK"}
    for betik, gruplar in TABLO.items():
        assert "YONETMEN" in gruplar, betik
        assert "HARIC" in gruplar, betik


def test_latin_yonetmen_credit_role_lexicon_director_ile_birebir_ayni():
    """§4.1: LATIN.YONETMEN = credit_role_lexicon.DIRECTOR birebir kopya."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import credit_role_lexicon as crl  # noqa: E402
    assert TABLO["LATIN"]["YONETMEN"] == crl.DIRECTOR


def test_latin_haric_credit_role_lexicon_exclude_ile_birebir_ayni():
    """§4.1: LATIN.HARIC = credit_role_lexicon.EXCLUDE birebir kopya."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import credit_role_lexicon as crl  # noqa: E402
    assert TABLO["LATIN"]["HARIC"] == crl.EXCLUDE
