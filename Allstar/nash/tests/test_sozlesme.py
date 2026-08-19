"""Sözleşme testleri — kulenin DIŞ yüzü. Değişmezler kodla zorlanıyor mu?"""
import json

import pytest

from sozlesme import Cikti, Girdi, GirdiHatasi, ariza


# ── Girdi ────────────────────────────────────────────────────────────────────

def test_girdi_film_id_zorunlu():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="", kareler="/yol")


def test_girdi_kareler_zorunlu_video_alinmaz():
    with pytest.raises(GirdiHatasi, match="kareler"):
        Girdi(film_id="X", kareler="")


def test_girdi_bolum_gecersiz():
    with pytest.raises(GirdiHatasi, match="bolum"):
        Girdi(film_id="X", kareler="/yol", bolum="orta")


def test_girdi_gecerli():
    g = Girdi(film_id="X", kareler="/yol", bolum="giris")
    assert g.bolum == "giris"


# ── Cikti değişmezleri ───────────────────────────────────────────────────────

def test_okundu_satirsiz_olamaz():
    """Okunduysa bir şey okunmuştur; boşsa o METIN_YOK'tur."""
    with pytest.raises(ValueError, match="satirsiz"):
        Cikti(film_id="X", durum="OKUNDU")


def test_metin_yok_satir_tasiyamaz():
    with pytest.raises(ValueError, match="satir tasiyamaz"):
        Cikti(film_id="X", durum="METIN_YOK", satirlar=[{"text": "A"}])


def test_ariza_satir_tasiyamaz():
    with pytest.raises(ValueError, match="satir tasiyamaz"):
        Cikti(film_id="X", durum="ARIZA", sinif="MODEL", mesaj="m",
              satirlar=[{"text": "A"}])


def test_ariza_sinif_ve_mesaj_zorunlu():
    with pytest.raises(ValueError, match="sinif ve mesaj"):
        Cikti(film_id="X", durum="ARIZA")
    with pytest.raises(ValueError, match="sinif ve mesaj"):
        Cikti(film_id="X", durum="ARIZA", sinif="MODEL")


def test_ariza_sinifi_listede_olmali():
    with pytest.raises(ValueError, match="gecersiz"):
        Cikti(film_id="X", durum="ARIZA", sinif="UYDURMA", mesaj="m")


def test_ariza_disi_durum_sinif_tasiyamaz():
    """ARIZA alanlarını içerik gerçeğine iliştirmek yasak."""
    with pytest.raises(ValueError, match="tasiyamaz"):
        Cikti(film_id="X", durum="METIN_YOK", sinif="MODEL", mesaj="m")


def test_durum_gecersiz():
    with pytest.raises(ValueError, match="durum"):
        Cikti(film_id="X", durum="BELKI")


# ── yazım ────────────────────────────────────────────────────────────────────

def _ornek(**k):
    return Cikti(film_id="F1", durum="OKUNDU",
                 satirlar=[{"kaynak": "a.png", "sayfa_sira": 1,
                            "satir_sira": 0, "text": "YONETMEN AHMET"},
                           {"kaynak": "a.png", "sayfa_sira": 1,
                            "satir_sira": 1, "text": "KURGU AYSE"}], **k)


def test_yaz_uc_dosya_ve_tamam_en_son(tmp_path):
    c = _ornek()
    yol = c.yaz(tmp_path)
    d = tmp_path / "F1" / "cikis"
    assert yol == d / "nash.json"
    assert (d / "nash.txt").is_file() and (d / "_TAMAM").is_file()
    # _TAMAM EN SON yazilir: isaret varsa ikisi de hazirdir.
    assert (d / "_TAMAM").stat().st_mtime >= (d / "nash.json").stat().st_mtime
    assert (d / "_TAMAM").stat().st_mtime >= (d / "nash.txt").stat().st_mtime


def test_yaz_gecici_dosya_birakmaz(tmp_path):
    _ornek().yaz(tmp_path)
    assert not list((tmp_path / "F1" / "cikis").glob("*.tmp"))


def test_okundu_disinda_nash_txt_YAZILMAZ(tmp_path):
    """Boş nash.txt, ARIZA ile METIN_YOK ayrımını yutar. Dosya yoksa tüketici
    nash.json'a bakmak zorunda kalır."""
    ariza("F1", "MODEL", "model yok").yaz(tmp_path)
    Cikti(film_id="F2", durum="METIN_YOK").yaz(tmp_path)
    for fid in ("F1", "F2"):
        d = tmp_path / fid / "cikis"
        assert (d / "nash.json").is_file() and (d / "_TAMAM").is_file()
        assert not (d / "nash.txt").exists()


def test_yeniden_kosuda_eski_metin_ve_kanit_paketi_kalmaz(tmp_path):
    d = tmp_path / "F1" / "cikis"
    _ornek().yaz(tmp_path, {"nash.okuma.json": {"eski": True}})
    assert (d / "nash.txt").exists() and (d / "nash.okuma.json").exists()
    ariza("F1", "MODEL", "model yok").yaz(tmp_path)
    assert (d / "_TAMAM").exists() and (d / "nash.json").exists()
    assert not (d / "nash.txt").exists()
    assert not (d / "nash.okuma.json").exists()


def test_yaz_bolum_ayri_klasor(tmp_path):
    _ornek().yaz(tmp_path)
    Cikti(film_id="F1", bolum="giris", durum="METIN_YOK").yaz(tmp_path)
    assert (tmp_path / "F1" / "cikis" / "nash.json").is_file()
    assert (tmp_path / "F1" / "giris" / "nash.json").is_file()
    g = json.loads((tmp_path / "F1" / "giris" / "nash.json").read_text("utf-8"))
    assert g["durum"] == "METIN_YOK" and "satirlar" not in g


def test_metin_satirlari_sirasiyla_verir():
    assert _ornek().metin() == "YONETMEN AHMET\nKURGU AYSE"


def test_sozluk_ariza_alanlarini_yalniz_arizada_tasir():
    d = ariza("F1", "BELLEK", "OOM").sozluk()
    assert d["sinif"] == "BELLEK" and "satirlar" not in d
    assert "sinif" not in _ornek().sozluk()


def test_uretim_zamani_otomatik():
    assert _ornek().uretim_zamani
