"""Jordan sözleşmesi — kulenin dış yüzü. Model yüklenmez, GPU gerekmez."""
import json
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))

from sozlesme import Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402


# ── Girdi ───────────────────────────────────────────────────────────────
def test_girdi_video_gecerli():
    g = Girdi(film_id="F1", video="/yol/klip.mp4")
    assert g.video == "/yol/klip.mp4" and g.bolum == "cikis"


def test_girdi_kare_havuzu_gecerli():
    g = Girdi(film_id="F1", kareler="/yol/frames")
    assert g.kareler == "/yol/frames" and not g.video


def test_girdi_kaynagi_zorunlu():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="F1")


def test_video_ve_kareler_ayni_anda_reddedilir():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="F1", video="/yol/klip.mp4", kareler="/yol/frames")


def test_girdi_bos_film_id_hata():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="", video="/yol/klip.mp4")


def test_girdi_gecersiz_bolum_hata():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="F1", video="/yol/klip.mp4", bolum="orta")


# ── Cikti: durum degismezi ──────────────────────────────────────────────
def test_ariza_sinif_ve_mesaj_zorunlu():
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="ARIZA")


def test_ariza_yardimcisi_alanlari_doldurur():
    c = ariza("F1", "BELLEK", "CUDA OOM", {"kare": 36})
    assert c.durum == "ARIZA" and c.sinif == "BELLEK"
    assert c.mesaj == "CUDA OOM" and c.kanit == {"kare": 36}


def test_metin_yok_sinif_tasiyamaz():
    """ARIZA asla METIN_YOK'a donusmez — ters yon de kapali."""
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="METIN_YOK", sinif="MODEL")


def test_metin_yok_blok_tasiyamaz():
    """'Metin yok' derken metin tasimak celiskidir."""
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="METIN_YOK",
              bloklar=[{"no": 1, "sn": 0.0, "satirlar": ["YONETMEN"]}])


def test_ariza_blok_tasiyamaz():
    """Ariza aninda okunan yarim metin cikti sayilmaz."""
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="ARIZA", sinif="MODEL", mesaj="coktu",
              bloklar=[{"no": 1, "sn": 0.0, "satirlar": ["X"]}])


def test_okundu_bloksuz_olamaz():
    """OKUNDU demek en az bir blok okundu demektir; bossa METIN_YOK'tur."""
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="OKUNDU", bloklar=[])


def test_cift_bloksuz_olamaz():
    """Ciftler bloklardan tureti­lir; bloksuz cift kaynaksiz veridir."""
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="OKUNDU", bloklar=[],
              ciftler=[{"rol": "YONETMEN", "isim": "A B", "blok": 1}])


def test_bilinmeyen_durum_reddedilir():
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="BELKI")


# ── Yazma: atomik + _TAMAM ──────────────────────────────────────────────
def _ornek(film_id="F1"):
    return Cikti(
        film_id=film_id, durum="OKUNDU",
        bloklar=[{"no": 1, "sn": 12.5, "satirlar": ["YONETMEN", "ALI OZGENTURK"]},
                 {"no": 2, "sn": 18.0, "satirlar": ["MUZIK", "ZULFU LIVANELI"]}],
        ciftler=[{"rol": "YONETMEN", "isim": "ALI OZGENTURK", "blok": 1}])


def test_yaz_jordan_json_ve_tamam_uretir(tmp_path):
    yol = _ornek().yaz(tmp_path)
    assert yol == tmp_path / "F1" / "cikis" / "jordan.json"
    assert (tmp_path / "F1" / "cikis" / "_TAMAM").exists()
    d = json.loads(yol.read_text(encoding="utf-8"))
    assert d["durum"] == "OKUNDU" and len(d["bloklar"]) == 2


def test_yaz_duz_metin_yan_dosyasi_uretir(tmp_path):
    """jordan.txt: satirlar goruldugu sirayla, tek sutun."""
    _ornek().yaz(tmp_path)
    txt = (tmp_path / "F1" / "cikis" / "jordan.txt").read_text(encoding="utf-8")
    assert txt.splitlines() == ["YONETMEN", "ALI OZGENTURK",
                                "MUZIK", "ZULFU LIVANELI"]


def test_yaz_gecici_dosya_birakmaz(tmp_path):
    Cikti(film_id="F1", durum="METIN_YOK").yaz(tmp_path)
    assert list((tmp_path / "F1" / "cikis").glob("*.tmp")) == []


def test_tamam_en_son_yazilir(tmp_path):
    """Tuketici kurali: _TAMAM varsa jordan.json kesin tamdir."""
    _ornek().yaz(tmp_path)
    d = tmp_path / "F1" / "cikis"
    assert (d / "_TAMAM").stat().st_mtime >= (d / "jordan.json").stat().st_mtime
    assert (d / "_TAMAM").stat().st_mtime >= (d / "jordan.txt").stat().st_mtime


def test_bolum_ayri_klasore_yazilir(tmp_path):
    """cikis ve giris birbirini ezmez."""
    Cikti(film_id="F1", durum="METIN_YOK", bolum="cikis").yaz(tmp_path)
    Cikti(film_id="F1", durum="METIN_YOK", bolum="giris").yaz(tmp_path)
    assert (tmp_path / "F1" / "cikis" / "jordan.json").exists()
    assert (tmp_path / "F1" / "giris" / "jordan.json").exists()
