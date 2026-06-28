# -*- coding: utf-8 -*-
"""test_qc_role_filter_20260628.py — KAPI1 karakter-rol/tarif çöp filtresi.

Test ettiği: credit_text_read._looks_character_role + _valid_person_name (flag MITAS_QC_ROLE_FILTER).
  • Çöp düşer: yapısal-kesin karakter-tarifi (edat / ordinal / tam-ifade).
  • Gerçek ad KORUNUR — özellikle rol-kelimesi = SOYAD olan TEHLİKELİ vakalar
    (Adam Driver, Mike Judge, Pat Priest, Gerard Butler) ASLA düşmez.
  • Flag OFF (modül-default) → davranış birebir eski (regresyon yok).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from credit_text_read import _looks_character_role, _valid_person_name, _only_persons  # noqa: E402


# ────────────────── _looks_character_role: ÇÖP yakalanır ──────────────────

CHARACTER_ROLE_GARBAGE = [
    "IMMIGRATION OFFICER",   # tam-ifade
    "FRENCH MAID",           # tam-ifade
    "POLICE OFFICER",        # tam-ifade
    "PRISON GUARD",          # tam-ifade
    "NIGHT WATCHMAN",        # tam-ifade
    "HIMSELF", "HERSELF", "NARRATOR",  # kredi-konvansiyonu
    "GIRL AT DANCE",         # edat (at) + girl
    "SECOND GIRL AT DANCE",  # ordinal-önek
    "MAN IN BAR",            # edat (in) + man
    "WOMAN ON TRAIN",        # edat (on) + woman
    "VOICE OF GOD",          # edat (of) + voice
    "FIRST POLICEMAN",       # ordinal-önek
    "SECOND MAN",            # ordinal-önek
]

def test_role_garbage_caught():
    for g in CHARACTER_ROLE_GARBAGE:
        assert _looks_character_role(g) is True, f"ÇÖP yakalanmalı: {g!r}"


# ────────────────── _looks_character_role: GERÇEK AD korunur ──────────────────
# TEHLİKE: rol-kelimesi = gerçek soyadı olan ünlü oyuncular. ASLA düşmemeli.

REAL_NAMES_KEEP = [
    "ADAM DRIVER",      # driver = soyad (ambig rol-ismi ama edat YOK)
    "MINNIE DRIVER",
    "MIKE JUDGE",
    "PAT PRIEST",       # priest = soyad (ambig ama edat YOK)
    "GERARD BUTLER",
    "CHARLES BRONSON", "KEVIN COSTNER", "GENE HACKMAN", "KIM NOVAK",
    "NISA SEREZLI", "SEMIH KAPLANOGLU", "JOHN FORD",
    "MAN HO",           # Asya verilen-adı (man tek başına → korunur)
    "BOY GEORGE",       # boy tek başına + edat yok → korunur
    "JOAN OF ARC",      # 'of' var ama ambig rol-ismi YOK → korunur
    "VINCENT VAN GOGH",
]

def test_real_names_kept():
    for n in REAL_NAMES_KEEP:
        assert _looks_character_role(n) is False, f"GERÇEK AD düşmemeli: {n!r}"


# ────────────────── _valid_person_name: flag ON → çöp red, ad geçer ──────────────────

def test_valid_person_flag_on():
    os.environ["MITAS_QC_ROLE_FILTER"] = "1"
    try:
        assert _valid_person_name("IMMIGRATION OFFICER") is False
        assert _valid_person_name("GIRL AT DANCE") is False
        assert _valid_person_name("SECOND GIRL AT DANCE") is False
        # gerçek ad — özellikle tehlikeli soyad-rol vakaları
        assert _valid_person_name("ADAM DRIVER") is True
        assert _valid_person_name("MIKE JUDGE") is True
        assert _valid_person_name("CHARLES BRONSON") is True
        assert _valid_person_name("NISA SEREZLI") is True
    finally:
        os.environ.pop("MITAS_QC_ROLE_FILTER", None)


# ────────────────── flag OFF (default) → REGRESYON YOK ──────────────────

def test_valid_person_flag_off_no_regression():
    """Flag OFF iken karakter-rol çöpü ESKİSİ GİBİ geçer (davranış değişmedi)."""
    os.environ.pop("MITAS_QC_ROLE_FILTER", None)
    # Bu girdiler flag-öncesi _valid_person_name'den GEÇİYORDU; flag OFF → hâlâ geçer.
    assert _valid_person_name("IMMIGRATION OFFICER") is True
    assert _valid_person_name("GIRL AT DANCE") is True
    # gerçek ad her durumda geçer
    assert _valid_person_name("ADAM DRIVER") is True


# ────────────────── _only_persons uçtan-uca (flag ON) ──────────────────

def test_only_persons_end_to_end():
    os.environ["MITAS_QC_ROLE_FILTER"] = "1"
    try:
        cast = ["CHARLES BRONSON", "IMMIGRATION OFFICER", "ADAM DRIVER",
                "GIRL AT DANCE", "KIM NOVAK", "SECOND MAN", "MIKE JUDGE"]
        kept = _only_persons(cast)
        assert kept == ["CHARLES BRONSON", "ADAM DRIVER", "KIM NOVAK", "MIKE JUDGE"], kept
    finally:
        os.environ.pop("MITAS_QC_ROLE_FILTER", None)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
