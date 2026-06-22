# -*- coding: utf-8 -*-
"""test_kunye_suclu_fixes_20260622.py — RED ROCK üç kritik künye suçlusu fix testleri.

Kapsam (hepsi DB/LLM'siz, deterministik):
  • Fix #2 — VL token-kalkanı satır-içi adjacency (_pipe_credit_vl._in_raw):
      'Hans Ebner' Frankenstein-ismi (ayrı satırlardaki HANS-PETER + EBNER'den) DÜŞER;
      gerçek tek-satır isimler KALIR. Flag MITAS_VL_RAW_ADJACENCY=0 eski (substring) davranışı geri getirir.
  • Fix #3 — Latin-dışı erken transliterasyon (credit_text_read + translit_util):
      Arapça isim translit → _fold'dan SAĞ çıkar + _valid_person_name geçer (eskiden boş token → düşerdi);
      read_credits_auto nonlatin_source=True + translit_method sinyali döndürür; Latin film DOKUNULMAZ.

Çalıştır:  python -m pytest tests/test_kunye_suclu_fixes_20260622.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))


# ─────────────────────────────── Fix #2 ───────────────────────────────
import _pipe_credit_vl as vl


# Gerçek MANASLU ham OCR'ını taklit eden satırlar: 'HANS-PETER STAUBER' ve 'HANNELORE EBNER' AYRI satırlar.
_MANASLU_RAW = [
    "hannelore ebner",
    "hans-peter stauber",
    "ignaz gruber",
    "peter habeler",
]


def test_fix2_frankenstein_dusurulur_adjacency_on():
    os.environ["MITAS_VL_RAW_ADJACENCY"] = "1"
    # 'Hans Ebner' hiçbir TEK satırda birlikte yok (hans→stauber satırı, ebner→hannelore satırı) → DÜŞER.
    assert vl._in_raw("Hans Ebner", _MANASLU_RAW) is False


def test_fix2_gercek_isimler_korunur_adjacency_on():
    os.environ["MITAS_VL_RAW_ADJACENCY"] = "1"
    # Her gerçek isim TEK satırda bitişik → KALIR.
    assert vl._in_raw("Hannelore Ebner", _MANASLU_RAW) is True
    assert vl._in_raw("Ignaz Gruber", _MANASLU_RAW) is True
    assert vl._in_raw("Peter Habeler", _MANASLU_RAW) is True


def test_fix2_flag_off_eski_davranis_geri_gelir():
    # Eski (substring) davranış: token'lar AYRI aranır → Frankenstein GEÇER (bug'ı belgeler).
    os.environ["MITAS_VL_RAW_ADJACENCY"] = "0"
    try:
        assert vl._in_raw("Hans Ebner", _MANASLU_RAW) is True
    finally:
        os.environ["MITAS_VL_RAW_ADJACENCY"] = "1"


def test_fix2_raw_yok_failsafe_atla():
    # raw yoksa kalkan atlanır (FAIL-SAFE: veri yok → düşürme yok).
    assert vl._in_raw("Her Hangi Isim", []) is True


# ─────────────────────────────── Fix #3 ───────────────────────────────
import credit_text_read as ctr
from translit_util import detect_script, transliterate, asciify_foreign


# Gerçek NAMUS DÜŞMANI Arapça oyuncu isimleri (Türk oyuncular, Arap-yazısı künye).
_NAMUS_ARABIC = ["زكي آلاسيا", "متين آكبنار", "سومر تلماتش", "رها يورداكول", "أويا بالاي"]


def test_fix3_detect_script_arabic():
    assert detect_script("\n".join(_NAMUS_ARABIC)) == "arabic"
    assert detect_script("JOHN SMITH\nJANE DOE") == "latin"


def test_fix3_translit_fold_dan_sag_cikar():
    # KÖK kanıt: ham Arapça _fold'da ölür; translit SONRASI token SAĞ kalır.
    for ar in _NAMUS_ARABIC:
        ham_toks = [t for t in ctr._fold(ar).split() if t]
        assert ham_toks == [], f"ham Arapça _fold'da token üretmemeli: {ar!r}→{ham_toks}"
        latin, yontem = transliterate(ar, "arabic")
        tr_toks = [t for t in ctr._fold(asciify_foreign(latin)).split() if t]
        assert len(tr_toks) >= 2, f"translit sonrası ≥2 token olmalı: {ar!r}→{latin!r}→{tr_toks}"


def test_fix3_translit_isim_valid_person_gecer():
    # Kaba translit (sesli-harfsiz) garble sayılmaz → _valid_person_name geçer → cast'e ulaşabilir.
    for ar in _NAMUS_ARABIC:
        latin, _ = transliterate(ar, "arabic")
        latin = asciify_foreign(latin)
        assert ctr._valid_person_name(latin) is True, f"translit isim geçerli olmalı: {ar!r}→{latin!r}"


def test_fix3_nonlatin_source_sinyali():
    # read_credits_auto Arapça girdide nonlatin_source=True + translit_method sinyali döndürür.
    _chain, _kb = ctr.model_chain, ctr._get_kb
    ctr.model_chain = lambda: []          # LLM'siz (sinyal LLM'den bağımsız)
    ctr._get_kb = lambda: None
    try:
        res = ctr.read_credits_auto(list(_NAMUS_ARABIC), title="NAMUS DÜŞMANI")
        assert res.get("nonlatin_source") is True
        assert res.get("translit_method")  # unidecode (Arapça)
        # Latin kontrol: dokunulmaz.
        res2 = ctr.read_credits_auto(["JOHN SMITH", "JANE DOE"], title="X")
        assert res2.get("nonlatin_source") is False
        assert res2.get("translit_method") is None
    finally:
        ctr.model_chain, ctr._get_kb = _chain, _kb


def test_fix3_flag_off_translit_yapilmaz():
    # MITAS_NONLATIN_TRANSLIT=0 → erken-translit devre dışı, nonlatin_source False (eski davranış).
    _chain, _kb = ctr.model_chain, ctr._get_kb
    ctr.model_chain = lambda: []
    ctr._get_kb = lambda: None
    os.environ["MITAS_NONLATIN_TRANSLIT"] = "0"
    try:
        res = ctr.read_credits_auto(list(_NAMUS_ARABIC), title="NAMUS DÜŞMANI")
        assert res.get("nonlatin_source") is False
    finally:
        os.environ.pop("MITAS_NONLATIN_TRANSLIT", None)
        ctr.model_chain, ctr._get_kb = _chain, _kb


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
