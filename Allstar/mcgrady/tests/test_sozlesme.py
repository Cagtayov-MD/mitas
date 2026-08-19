# -*- coding: utf-8 -*-
"""sozlesme.py sözleşme değişmezleri — kobe test_sozlesme kalıbı."""
import json
import os
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KULE))

import pytest

from sozlesme import (DURUMLAR, GirdiHatasi, ariza, paket_oku)  # noqa: E402
from sozlesme import Cikti  # noqa: E402


def _paket(tmp_path, **uzanti):
    paket = {
        "schema_version": "mcgrady.girdi/v1", "film_id": "test-1", "profile": "film",
        "baslik": {"tr": "AHLAT AĞACI", "orijinal": "The Wild Pear Tree", "yil": 2018},
        "yonetmen": ["Nuri Bilge Ceylan"],
        "cast": ["Doğu Demirkol", "Murat Cemcir"],
        "yapimci": [],
    }
    paket.update(uzanti)
    p = tmp_path / "paket.json"
    p.write_text(json.dumps(paket, ensure_ascii=False), encoding="utf-8")
    return p


# ── paket_oku ────────────────────────────────────────────────────────────────
def test_paket_okunur(tmp_path):
    raw = paket_oku(_paket(tmp_path))
    assert raw["film_id"] == "test-1"
    assert raw["baslik"]["yil"] == 2018


def test_paket_yanlis_sema(tmp_path):
    p = _paket(tmp_path, schema_version="baska/v9")
    with pytest.raises(GirdiHatasi):
        paket_oku(p)


def test_paket_yanlis_profil(tmp_path):
    p = _paket(tmp_path, profile="belgesel")
    with pytest.raises(GirdiHatasi):
        paket_oku(p)


def test_paket_baslik_bos(tmp_path):
    p = _paket(tmp_path, baslik={"tr": "", "orijinal": None})
    with pytest.raises(GirdiHatasi):
        paket_oku(p)


def test_paket_cast_liste_degil(tmp_path):
    p = _paket(tmp_path, cast="Doğu Demirkol")
    with pytest.raises(GirdiHatasi):
        paket_oku(p)


def test_paket_json_degil(tmp_path):
    p = tmp_path / "bozuk.json"
    p.write_text("{", encoding="utf-8")
    with pytest.raises(GirdiHatasi):
        paket_oku(p)


# ── Cikti değişmezleri ───────────────────────────────────────────────────────
def test_ariza_sinif_mesaj_zorunlu():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="ARIZA", sinif=None, mesaj=None)


def test_ariza_disi_sinif_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="KILITLENEMEDI", sinif="X", mesaj="y")


def test_dogrulandi_kimlik_zorunlu():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="DOGRULANDI", kimlik=None)


def test_kilitlenemedi_kimlik_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="KILITLENEMEDI",
              kimlik={"method": "cast-ortusme"})


def test_gecersiz_durum():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="BILINMEYEN")


def test_ariza_fabrikasi():
    c = ariza("f", "DB", "bağlanamadı")
    assert c.durum == "ARIZA" and c.sinif == "DB"


# ── yaz: atomik + _TAMAM + sheriff kimliği ──────────────────────────────────
def test_yaz_tamam_marker(tmp_path):
    c = Cikti(film_id="f1", durum="KILITLENEMEDI")
    yol = c.yaz(tmp_path)
    assert yol == tmp_path / "f1" / "mcgrady.json"
    assert (tmp_path / "f1" / "_TAMAM").exists()
    assert not (tmp_path / "f1" / "mcgrady.json.tmp").exists()
    d = json.loads(yol.read_text(encoding="utf-8"))
    assert d["durum"] == "KILITLENEMEDI"
    assert d["kimlik"] is None


def test_yaz_sheriff_kimligi(tmp_path, monkeypatch):
    for k in ("MITAS_SHERIFF_RUN_ID", "MITAS_SHERIFF_TASK_ID", "MITAS_SHERIFF_ATTEMPT_ID"):
        monkeypatch.setenv(k, "x-" + k)
    c = Cikti(film_id="f2", durum="KILITLENEMEDI")
    yol = c.yaz(tmp_path)
    d = json.loads(yol.read_text(encoding="utf-8"))
    assert d["schema_version"] == "mitas.boundary/v1"
    assert d["identity"]["run_id"] == "x-MITAS_SHERIFF_RUN_ID"


def test_yaz_sheriff_kimligi_yoksa_schema_yok(tmp_path):
    c = Cikti(film_id="f3", durum="KILITLENEMEDI")
    d = json.loads(c.yaz(tmp_path).read_text(encoding="utf-8"))
    assert "schema_version" not in d


def test_dogrulandi_sozluk_alanlari(tmp_path):
    c = Cikti(film_id="f4", durum="DOGRULANDI",
              kimlik={"method": "cast-ortusme", "versiyon_teyitli": True},
              karar_onerileri=["örnek"])
    d = json.loads(c.yaz(tmp_path).read_text(encoding="utf-8"))
    assert d["kimlik"]["method"] == "cast-ortusme"
    assert d["karar_onerileri"] == ["örnek"]
