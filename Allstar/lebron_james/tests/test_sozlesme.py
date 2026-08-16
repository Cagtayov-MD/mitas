"""Sözleşme kilitleri — ARIZA sessizce içerik gerçeğine dönüşemesin.

Bu testler kulenin DIŞ yüzünü kilitler. Buradaki her assert bir üretim
kazasının karşılığıdır; gevşetmeden önce spec 3.3'ü oku.
"""
import json

import pytest

from sozlesme import BOLUMLER, Cikti, Girdi, GirdiHatasi, ariza


# --- Girdi ------------------------------------------------------------------
def test_film_id_bos_olamaz():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="", kareler="/yol")


def test_kareler_zorunlu():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="X", kareler="")


def test_gecersiz_bolum_reddedilir():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="X", kareler="/yol", bolum="ortasi")


def test_iki_bolum_de_gecerli():
    for b in BOLUMLER:
        assert Girdi(film_id="X", kareler="/yol", bolum=b).bolum == b


# --- Cikti: durum üçlüsü ----------------------------------------------------
def test_gecersiz_durum_reddedilir():
    with pytest.raises(ValueError):
        Cikti(film_id="X", durum="TAMAM")


def test_ariza_sinifsiz_olamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="X", durum="ARIZA", sinif="MOTOR")   # mesaj yok


def test_ariza_mesajsiz_olamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="X", durum="ARIZA", mesaj="patladi")  # sinif yok


def test_metin_yok_ariza_alani_tasiyamaz():
    """ARIZA'nın içerik gerçeğine sızmasını engelleyen kapının aynası."""
    with pytest.raises(ValueError):
        Cikti(film_id="X", durum="METIN_YOK", sinif="MOTOR", mesaj="patladi")


def test_okundu_satirsiz_olamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="X", durum="OKUNDU", satirlar=[])


def test_metin_yok_satir_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="X", durum="METIN_YOK", satirlar=["YÖNETMEN"])


def test_ariza_satir_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="X", durum="ARIZA", sinif="MOTOR", mesaj="p", satirlar=["a"])


# --- Cikti: master artefaktı ------------------------------------------------
def test_ariza_master_TASIYABILIR():
    """Kobe'den bilinçli ayrışma (spec 3.2): okuyucu çökse bile master paylaşılır.

    Derlemeye harcanan iş çöpe gitmesin ve arızanın hangi tarafta olduğu
    (derleme mi, okuma mı) gözle görülür kalsın diye.
    """
    c = ariza("X", "OKUYUCU_HAZIR_DEGIL", "okuyucu yok",
              uretilen=[{"tip": "master", "yol": "master.png"}])
    assert c.uretilen[0]["tip"] == "master"


# --- yaz(): dosya düzeni ----------------------------------------------------
def test_yaz_tamam_en_son(tmp_path):
    c = Cikti(film_id="F", bolum="cikis", durum="OKUNDU", satirlar=["YÖNETMEN"])
    c.yaz(tmp_path)
    d = tmp_path / "F" / "cikis"
    assert (d / "lebron.json").is_file()
    assert (d / "_TAMAM").is_file()
    assert not (d / "lebron.json.tmp").exists(), "gecici dosya kalmis"
    assert json.loads((d / "lebron.json").read_text(encoding="utf-8"))["durum"] == "OKUNDU"


def test_txt_yalniz_okundu_da_yazilir(tmp_path):
    """Boş bir lebron.txt, metni okuyan tüketiciye 'yazı yok' gibi görünür ve
    METIN_YOK / ARIZA ayrımını yutar (spec 3.2)."""
    Cikti(film_id="A", durum="OKUNDU", satirlar=["ROL: X"]).yaz(tmp_path)
    assert (tmp_path / "A" / "cikis" / "lebron.txt").read_text(encoding="utf-8").strip() == "ROL: X"

    Cikti(film_id="B", durum="METIN_YOK").yaz(tmp_path)
    assert not (tmp_path / "B" / "cikis" / "lebron.txt").exists()

    ariza("C", "MOTOR", "patladi").yaz(tmp_path)
    assert not (tmp_path / "C" / "cikis" / "lebron.txt").exists()


def test_bayat_txt_silinir(tmp_path):
    """Önceki koşudan kalan txt, bu koşu METIN_YOK dediyse ortada kalmamalı."""
    Cikti(film_id="F", durum="OKUNDU", satirlar=["ESKI"]).yaz(tmp_path)
    txt = tmp_path / "F" / "cikis" / "lebron.txt"
    assert txt.is_file()
    Cikti(film_id="F", durum="METIN_YOK").yaz(tmp_path)
    assert not txt.exists(), "bayat lebron.txt silinmedi"


def test_iki_bolum_birbirini_ezmez(tmp_path):
    Cikti(film_id="F", bolum="giris", durum="OKUNDU", satirlar=["GIRIS"]).yaz(tmp_path)
    Cikti(film_id="F", bolum="cikis", durum="OKUNDU", satirlar=["CIKIS"]).yaz(tmp_path)
    g = (tmp_path / "F" / "giris" / "lebron.txt").read_text(encoding="utf-8").strip()
    c = (tmp_path / "F" / "cikis" / "lebron.txt").read_text(encoding="utf-8").strip()
    assert (g, c) == ("GIRIS", "CIKIS")
