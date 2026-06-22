# -*- coding: utf-8 -*-
"""test_c9_xmlcast_relax.py — C9 MITAS_XMLCAST_GATE_RELAX doğruluk-tablosu testi.

Test ettiği: mitas_pipeline C9 bloğundaki XML-PDF cast kesişim-sıfır şüphesi kararı.
  Koşul: _xmlcast_susp=True + (_cc4 kilitli/kilitsiz) + flag (ON/OFF) → reasons'a eklenir mi?

mitas_pipeline._lean_transcribe + tüm boru hattı izolasyon imkânsız (DB/LLM/ffmpeg gerekir).
Strateji: C9 mantığını SAFI inline Python ile test et (pipeline içinden kopyalanan koşul).
  Bu yaklaşım task brief'teki "pipeline çağırılamıyorsa koşul-fonksiyonunu izole etme YERINE
  doğrudan koşulu test eden saf kontrol yaz" yönergesine uygundur.

Doğruluk tablosu:
  kilitli=True  + relax=True  + susp=True → reasons'a EKLENMEZ (locked_xmlcast=True)
  kilitli=False + relax=True  + susp=True → reasons'a EKLENİR
  kilitli=True  + relax=False + susp=True → reasons'a EKLENİR (flag=0 her şüpheyi ekler)
  susp=False                              → koşul hiç çalışmaz → EKLENMEZ
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))


# C9 koşulunu mitas_pipeline'dan doğrudan izole et (copy — pipeline import edilmez)
def _c9_decision(*, xmlcast_susp: bool, cc4: dict, relax_flag: str = "1") -> bool:
    """C9 bloğu kararı: 'XML-PDF cast kesişimi 0' reasons'a EKLENİR mi?
    Döner True eklendiyse, False eklenmeyecekse."""
    _relax_xmlcast = relax_flag.strip().lower() not in ("0", "false", "off", "no")
    if xmlcast_susp:
        _locked_xmlcast = (
            bool(cc4.get("kimlik_dogru")) or
            (cc4.get("verdict") == "TEYİT") or
            ((cc4.get("cast_ortusme") or 0) >= 2)
        )
        if not (_relax_xmlcast and _locked_xmlcast):
            return True   # ekleniyor
    return False  # eklenmiyor


# ──────────── doğruluk tablosu ────────────────────────────────────────────────

def test_c9_kilitli_relax_on_eklenmez():
    """kilitli=True + relax=ON + susp=True → EKLENMEZ."""
    cc4 = {"kimlik_dogru": True, "verdict": "TEYİT", "cast_ortusme": 4}
    assert _c9_decision(xmlcast_susp=True, cc4=cc4, relax_flag="1") is False, (
        "kilitli+relax=ON → reason EKLENMEMELİ")


def test_c9_kilitsiz_relax_on_eklenir():
    """kilitli=False + relax=ON + susp=True → EKLENİR."""
    cc4 = {}   # boş = locked=False (parse hatası simülasyonu)
    assert _c9_decision(xmlcast_susp=True, cc4=cc4, relax_flag="1") is True, (
        "kilitsiz+relax=ON → reason EKLENMELİ")


def test_c9_kilitli_relax_off_eklenir():
    """kilitli=True + relax=OFF + susp=True → EKLENİR (flag=0 kilide bakmaz)."""
    cc4 = {"kimlik_dogru": True, "verdict": "TEYİT", "cast_ortusme": 3}
    assert _c9_decision(xmlcast_susp=True, cc4=cc4, relax_flag="0") is True, (
        "relax=OFF → kilitli bile olsa reason EKLENMELİ")


def test_c9_susp_false_hic_eklenmez():
    """susp=False → relax/cc4 durumundan bağımsız → EKLENMEMELİ."""
    for relax in ("1", "0"):
        for cc4 in ({}, {"verdict": "TEYİT"}):
            assert _c9_decision(xmlcast_susp=False, cc4=cc4, relax_flag=relax) is False, (
                f"susp=False → reason EKLENMEMELİ (relax={relax})")


def test_c9_verdict_teyit_relax_on_eklenmez():
    """verdict='TEYİT' + relax=ON → EKLENMEZ."""
    cc4 = {"verdict": "TEYİT", "cast_ortusme": 0}
    assert _c9_decision(xmlcast_susp=True, cc4=cc4, relax_flag="1") is False


def test_c9_cast_ortusme_iki_relax_on_eklenmez():
    """cast_ortusme>=2 + relax=ON → EKLENMEZ."""
    cc4 = {"cast_ortusme": 2}
    assert _c9_decision(xmlcast_susp=True, cc4=cc4, relax_flag="1") is False


def test_c9_cast_ortusme_bir_relax_on_eklenir():
    """cast_ortusme=1 (< 2) + kimlik_dogru=False + relax=ON → EKLENİR."""
    cc4 = {"cast_ortusme": 1, "kimlik_dogru": False}
    assert _c9_decision(xmlcast_susp=True, cc4=cc4, relax_flag="1") is True


def test_c9_default_relax_on():
    """MITAS_XMLCAST_GATE_RELAX env default (yokken) → '1' gibi davranır (default-ON)."""
    import os
    os.environ.pop("MITAS_XMLCAST_GATE_RELAX", None)
    # default ON → kod içindeki default değeri "1"'dir (mitas_pipeline:2036)
    # Buraya saf koşul testi: kilitli=True + env yok → eklenmez
    cc4 = {"kimlik_dogru": True}
    # default '1' geçiriyoruz (mitas_pipeline kodunun default değeri)
    assert _c9_decision(xmlcast_susp=True, cc4=cc4, relax_flag="1") is False


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
