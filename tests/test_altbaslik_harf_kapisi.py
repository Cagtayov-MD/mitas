"""PDF alt başlığı (XML orijinal ad) harf kapısı.

ÇAĞATAY KURALI: "Hiçbir aksan geçmeyecek, hangi dil olduğu önemli değil.
Türkçede Ü Ğ İ Ş Ç Ö büyüyebilir; Latin'de ne aksan var ne Ü Ğ İ Ş Ç Ö."

BULGU: PDF'in kullanıcıya giden metin alanları içinde alt başlık TEK normalize
EDİLMEYEN alandı (cast/crew/title/özet hepsi geçiyordu). TESLİM EDİLMİŞ
PDF'lerde bulundu: 'MADE İN ITALY', 'SERPİCO', 'RED KİT', 'RIYA QEŞAYÊ'.

İKİ YÖNLÜ TEHLİKE — testler ikisini de kilitler:
  • gevşek → yabancı adda Türkçe harf/aksan PDF'e çıkar (kural ihlali)
  • sıkı   → TÜRKÇE başlık bozulur ('AĞAÇ' → 'AGAC'), sağlam çıktı kırılır.
    Ölçüldü: 15 film bu sınıfta, hepsi korunmalı.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("MITAS_PROJECT_ROOT", _KOK)
os.environ.setdefault("MITAS_PDFMITAS_DIR", os.path.join(_KOK, "OCR-worktree", "pdf-mitas"))
sys.path.insert(0, os.path.join(_KOK, "scripts"))

_PP = os.path.join(_KOK, "scripts", "_pipe_pdf.py")
if not os.path.isfile(os.path.join(_KOK, "OCR-worktree", "pdf-mitas", "name_normalize.py")):
    pytest.skip("pdf-mitas yok", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("pp_test", _PP)
pp = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(pp)
except Exception as e:  # noqa: BLE001
    pytest.skip(f"_pipe_pdf import edilemedi: {type(e).__name__}", allow_module_level=True)

kapi = pp._altbaslik_harf_kapisi


# ───────── YABANCI → SAF ASCII ─────────

@pytest.mark.parametrize("orig,baslik,beklenen", [
    # Gerçek üretim vakası: XML <TITLE>='LAND RAİDERS' (İngilizce ad, Türkçe İ ile)
    ("LAND RAİDERS", "YAĞMACILAR", "LAND RAIDERS"),
    # Arapça transliterasyon — Ü ve İ taşıyor, yabancı
    ("EL ADÜVVÜ-L LEZİ FİL MİRA", "AYNADAKİ DÜŞMAN", "EL ADUVVU-L LEZI FIL MIRA"),
    # Teslim edilmiş PDF'te bulundu
    ("MADE İN ITALY", "İTALYAN YAZI", "MADE IN ITALY"),
])
def test_yabanci_ad_ascii_olur(orig, baslik, beklenen):
    assert kapi(orig, baslik) == beklenen


def test_yabanci_aksan_kesin_eler():
    """Ê/é/å Türkçede YOK → dil tahminine gerek kalmadan kesin yabancı."""
    out = kapi("RIYA QEŞAYÊ", "BİR HALK MASALI")
    assert "Ê" not in out and "Ş" not in out


# ───────── TÜRKÇE → DOKUNULMAZ (regresyon kilidi) ─────────

@pytest.mark.parametrize("ad", [
    "AĞAÇ", "MİRAS", "BORÇ", "İMPARATORUN YOLCULUĞU",
    "MEVLANA AŞKIN DANSI", "BÜYÜK SAVAŞTA KÜÇÜK ADAM", "ŞEHİRDE BİR YERLİ",
])
def test_orijinal_baslikla_ayniysa_korunur(ad):
    """TRT 'orijinali de bu' diyorsa Türkçe başlıktır — fold ONU BOZAR."""
    assert kapi(ad, ad) == ad


def test_kesin_turkce_harf_korunur():
    """ı/ş/ğ tr_upper tarafından ÜRETİLEMEZ → gerçek Türkçe kanıtı,
    başlıkla aynı olmasa bile korunur."""
    assert kapi("IŞIK", "BAŞKA BİR AD") == "IŞIK"


# ───────── sınırlar ─────────

def test_zaten_ascii_dokunulmaz():
    assert kapi("SERPICO", "SERPİCO") == "SERPICO"
    assert kapi("THE GODFATHER", "BABA") == "THE GODFATHER"


def test_bos_girdi():
    assert kapi("", "BİR FİLM") == ""
    assert kapi(None, "BİR FİLM") in (None, "")


def test_kapatilabilir():
    """MITAS_ALTBASLIK_KAPISI=0 → eski davranış birebir."""
    eski = os.environ.get("MITAS_ALTBASLIK_KAPISI")
    os.environ["MITAS_ALTBASLIK_KAPISI"] = "0"
    try:
        assert kapi("LAND RAİDERS", "YAĞMACILAR") == "LAND RAİDERS"
    finally:
        if eski is None:
            os.environ.pop("MITAS_ALTBASLIK_KAPISI", None)
        else:
            os.environ["MITAS_ALTBASLIK_KAPISI"] = eski
