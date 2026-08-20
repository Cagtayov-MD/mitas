# -*- coding: utf-8 -*-
"""garble.py — _looks_garble / _only_persons söküm doğrulaması (bilinen vakalar)."""
import os
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KULE / "src"))

from garble import _fold, _looks_garble, _only_persons, _valid_person_name  # noqa: E402


def test_fold_turkce():
    assert _fold("Ahmet CİMCİR") == "ahmet cimcir"


def test_garble_rol_token():
    # "CRAFT SERVICES" — SERVICES departman token'ı (CRAFT bilinçli dışarıda)
    assert _looks_garble("CRAFT SERVICES") is not None


def test_garble_fiil_eki():
    assert _looks_garble("YAPILDIGI") is not None


def test_garble_temiz_isim_none():
    assert _looks_garble("George Segal") is None
    assert _looks_garble("Murat Cemcir") is None


def test_garble_gecerli_harf_garble_kor_nokta():
    # _looks_garble'ın bilinen kör noktası: geçerli-harf garble ("GEORCE STOAD")
    # imza-yokluğu kapısının işi (KB crosscheck) — burada sinyal YOK olması BEKLENİR.
    assert _looks_garble("GEORCE STOAD") is None


def test_only_persons_gecerli_ad_kalir():
    assert "Doğu Demirkol" in _only_persons(["Doğu Demirkol", "CRAFT SERVICES"])


def test_only_persons_sirket_duser():
    # "Warner Bros Pictures": pictures NONPERSON token → RED.
    assert _only_persons(["Warner Bros Pictures"]) == []
    # "COMPANYCAAN PRODLICTONS": geçerli-harf garble — _only_persons TEK BAŞINA
    # yakalamaz (tasarım böyle: KB imza-yokluğu kapısının işi, bkz credit_qc_gates).
    assert _only_persons(["COMPANYCAAN PRODLICTONS"]) == ["COMPANYCAAN PRODLICTONS"]


def test_only_persons_tek_token_red():
    assert _only_persons(["Segal"]) == []


def test_valid_person_bas_harf_istisnasi():
    # "E. B. CLUCHER" — iki ön-ad da baş-harfe inmiş; istisna KORUNUR
    assert _valid_person_name("E. B. Clucher") is True


def test_valid_person_karakter_rol_flagli(monkeypatch):
    monkeypatch.setenv("MITAS_QC_ROLE_FILTER", "1")
    assert _valid_person_name("GIRL AT DANCE") is False
    # "Man Ho" tek başına ambiguous token ama edatsız — KORUNUR
    assert _valid_person_name("Man Ho") is True
    monkeypatch.setenv("MITAS_QC_ROLE_FILTER", "0")
