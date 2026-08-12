"""Kobe sözleşmesi — kulenin dış yüzü. Motor koşmaz, Paddle gerekmez."""
import json
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))

from sozlesme import Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402


# ── Girdi: video/kareler XOR ────────────────────────────────────────────
def test_girdi_video_tek_basina_gecerli():
    g = Girdi(film_id="F1", video="/yol/f.mp4")
    assert g.video == "/yol/f.mp4" and g.kareler is None


def test_girdi_kareler_tek_basina_gecerli():
    g = Girdi(film_id="F1", kareler="/yol/kareler")
    assert g.kareler == "/yol/kareler" and g.video is None


def test_girdi_ikisi_birden_hata():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="F1", video="/yol/f.mp4", kareler="/yol/kareler")


def test_girdi_hicbiri_hata():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="F1")


def test_girdi_bos_film_id_hata():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="", video="/yol/f.mp4")


# ── Cikti: durum değişmezi ──────────────────────────────────────────────
def test_ariza_sinif_ve_mesaj_zorunlu():
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="ARIZA")


def test_ariza_yardimcisi_alanlari_doldurur():
    c = ariza("F1", "FFMPEG", "kare cikarilamadi", {"kod": 1})
    assert c.durum == "ARIZA" and c.sinif == "FFMPEG"
    assert c.mesaj == "kare cikarilamadi" and c.kanit == {"kod": 1}


def test_kredi_yok_sinif_tasiyamaz():
    """ARIZA asla KREDI_YOK'a dönüşmez — ters yön de kapalı."""
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="KREDI_YOK", sinif="FFMPEG")


def test_bilinmeyen_durum_reddedilir():
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="BELKI")


# ── Yazma: atomik + _TAMAM ──────────────────────────────────────────────
def test_yaz_kobe_json_ve_tamam_uretir(tmp_path):
    c = Cikti(film_id="F1", durum="BULUNDU", baslangic_kare=940,
              baslangic_sn=470.0, guven=0.87, script="ar")
    yol = c.yaz(tmp_path)
    assert yol == tmp_path / "F1" / "kobe.json"
    assert (tmp_path / "F1" / "_TAMAM").exists()
    d = json.loads(yol.read_text(encoding="utf-8"))
    assert d["durum"] == "BULUNDU" and d["baslangic_kare"] == 940


def test_yaz_gecici_dosya_birakmaz(tmp_path):
    Cikti(film_id="F1", durum="KREDI_YOK").yaz(tmp_path)
    assert list((tmp_path / "F1").glob("*.tmp")) == []


def test_tamam_kobe_jsondan_SONRA_yazilir(tmp_path):
    """Tüketici kuralı: _TAMAM varsa kobe.json kesin tamdır."""
    c = Cikti(film_id="F1", durum="BULUNDU", baslangic_kare=1)
    c.yaz(tmp_path)
    d = tmp_path / "F1"
    assert (d / "_TAMAM").stat().st_mtime >= (d / "kobe.json").stat().st_mtime
