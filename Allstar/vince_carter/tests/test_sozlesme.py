"""sozlesme.py testleri — ARIZA/METIN_YOK degismezi, Girdi disaridan disliligi,
_TAMAM'in en son yazilmasi. bkz. docs/PLAN.md §1."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from sozlesme import (  # noqa: E402
    ARIZA_SINIFLARI,
    BOLUMLER,
    Cikti,
    Girdi,
    GirdiHatasi,
    ariza,
)


# --------------------------------------------------------------------------- Girdi
def test_girdi_film_id_bos_olamaz():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="", video="k.mp4")


def test_girdi_bolum_gecersiz():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="f", video="k.mp4", bolum="ortasi")


@pytest.mark.parametrize("bolum", BOLUMLER)
def test_girdi_gecerli_bolumler_kabul_edilir(bolum):
    g = Girdi(film_id="f", video="k.mp4", bolum=bolum)
    assert g.bolum == bolum


def test_girdi_video_ve_kareler_birlikte_verilemez():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="f", video="k.mp4", kareler="/tmp/kareler")


def test_girdi_ikisi_de_bos_olamaz():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="f")


def test_girdi_yalniz_video_gecerli():
    g = Girdi(film_id="f", video="k.mp4")
    assert g.video == "k.mp4"
    assert g.kareler is None


def test_girdi_yalniz_kareler_gecerli():
    g = Girdi(film_id="f", kareler="/tmp/kareler")
    assert g.kareler == "/tmp/kareler"
    assert g.video is None


def test_girdi_donmus():
    g = Girdi(film_id="f", video="k.mp4")
    with pytest.raises(Exception):  # frozen dataclass -> FrozenInstanceError
        g.film_id = "baska"


# --------------------------------------------------------------------------- Cikti degismezleri
def test_ariza_sinif_mesaj_zorunlu():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="ARIZA")


def test_ariza_sinif_var_mesaj_yok_hala_gecersiz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="ARIZA", sinif="MODEL_HATASI")


def test_ariza_disinda_sinif_mesaj_tasinamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="METIN_YOK", sinif="MODEL_HATASI", mesaj="x")


def test_okundu_bos_satirla_reddedilir():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="OKUNDU", satirlar=[])


def test_metin_yok_satir_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="METIN_YOK",
              satirlar=[{"metin": "A", "sinif": "KESIN"}])


def test_ariza_satir_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="ARIZA", sinif="MODEL_HATASI", mesaj="x",
              satirlar=[{"metin": "A", "sinif": "KESIN"}])


def test_satir_sinifi_gecersizse_reddedilir():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="OKUNDU",
              satirlar=[{"metin": "A", "sinif": "BILINMEYEN"}])


def test_satir_metni_bossa_reddedilir():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="OKUNDU",
              satirlar=[{"metin": "  ", "sinif": "KESIN"}])


def test_gecerli_okundu_kurulur():
    c = Cikti(film_id="f", durum="OKUNDU",
              satirlar=[{"metin": "YÖNETMEN", "sinif": "KESIN"},
                        {"metin": "ADAY İSİM", "sinif": "SUPHELI"}])
    assert c.gorunur_satirlar() == ["YÖNETMEN"]
    assert c.supheli_satirlar() == ["ADAY İSİM"]


# --------------------------------------------------------------------------- ARIZA <-> METIN_YOK asla donusmez
def test_ariza_kurulusta_metin_yoka_esdeger_olamaz():
    """ARIZA'nin sinif/mesaji METIN_YOK uzerine binemez — kurulus anında."""
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="METIN_YOK", sinif="VIDEO_HATASI", mesaj="ffmpeg patladi")


def test_ariza_sonradan_metin_yoka_cevrilemez():
    """Kurulmus bir ARIZA nesnesinin durumu sonradan METIN_YOK'a EZILEMEZ —
    sozlesmenin en kritik degismezi budur (docs/PLAN.md §1)."""
    c = ariza("f", "MODEL_HATASI", "model yuklenemedi")
    with pytest.raises(ValueError):
        c.durum = "METIN_YOK"
    # Basarisiz mutasyon denemesi nesneyi BOZUK birakmamali — eski hale donmeli.
    assert c.durum == "ARIZA"
    assert c.sinif == "MODEL_HATASI"
    assert c.mesaj == "model yuklenemedi"


def test_metin_yok_sonradan_ariza_sinifi_takamaz():
    c = Cikti(film_id="f", durum="METIN_YOK")
    with pytest.raises(ValueError):
        c.sinif = "MODEL_HATASI"
    assert c.durum == "METIN_YOK"
    assert c.sinif is None


def test_okundu_satirlari_sonradan_bosaltilamaz():
    c = Cikti(film_id="f", durum="OKUNDU",
              satirlar=[{"metin": "A", "sinif": "KESIN"}])
    with pytest.raises(ValueError):
        c.satirlar = []
    assert c.satirlar == [{"metin": "A", "sinif": "KESIN"}]


def test_ariza_yardimcisi_tek_uretim_noktasi():
    c = ariza("f", "GIRDI_HATASI", "girdi yok")
    assert c.durum == "ARIZA"
    assert c.sinif == "GIRDI_HATASI"
    assert c.mesaj == "girdi yok"
    assert c.sinif in ARIZA_SINIFLARI


# --------------------------------------------------------------------------- sozluk()
def test_sozluk_ariza_alanlari():
    c = ariza("f", "BELLEK_HATASI", "OOM")
    d = c.sozluk()
    assert d["durum"] == "ARIZA"
    assert d["sinif"] == "BELLEK_HATASI"
    assert d["mesaj"] == "OOM"
    assert "satirlar" not in d


def test_sozluk_okundu_alanlari():
    c = Cikti(film_id="f", durum="OKUNDU",
              satirlar=[{"metin": "A", "sinif": "KESIN"}])
    d = c.sozluk()
    assert d["satirlar"] == [{"metin": "A", "sinif": "KESIN"}]
    assert "sinif" not in d
    assert "mesaj" not in d


def test_sozluk_json_serilestirilebilir():
    import json
    c = Cikti(film_id="f", durum="OKUNDU",
              satirlar=[{"metin": "ŞÜKRÜ İĞNELİ", "sinif": "ZAYIF"}])
    json.dumps(c.sozluk(), ensure_ascii=False)  # patlamamali


# --------------------------------------------------------------------------- yaz() / dosya sistemi
def test_yaz_tamam_en_son_yazilir(tmp_path, monkeypatch):
    sira = []
    orijinal_replace = os.replace

    def izlenen_replace(src, dst):
        sira.append(Path(dst).name)
        return orijinal_replace(src, dst)

    monkeypatch.setattr(os, "replace", izlenen_replace)

    orijinal_write_text = Path.write_text

    def izlenen_write_text(self, veri="", *a, **k):
        if self.name == "_TAMAM":
            sira.append("_TAMAM")
        return orijinal_write_text(self, veri, *a, **k)

    monkeypatch.setattr(Path, "write_text", izlenen_write_text)

    c = Cikti(film_id="test_film", bolum="cikis", durum="OKUNDU",
              satirlar=[{"metin": "YÖNETMEN", "sinif": "KESIN"}])
    c.yaz(tmp_path)

    assert sira, "hicbir yazma kaydedilmedi"
    assert sira[-1] == "_TAMAM"
    assert sira.count("_TAMAM") == 1
    assert "vince.json" in sira


def test_yaz_okundu_dosyalari_olusur(tmp_path):
    c = Cikti(film_id="filmA", bolum="cikis", durum="OKUNDU",
              satirlar=[{"metin": "YÖNETMEN", "sinif": "KESIN"},
                        {"metin": "SÜPHELİ AD", "sinif": "SUPHELI"}])
    c.yaz(tmp_path)
    d = tmp_path / "filmA" / "cikis"
    assert (d / "vince.json").exists()
    assert (d / "vince.txt").read_text(encoding="utf-8") == "YÖNETMEN"
    assert (d / "vince_supheli.txt").read_text(encoding="utf-8") == "SÜPHELİ AD"
    assert (d / "_TAMAM").exists()


def test_yaz_metin_yok_dosya_uretmez(tmp_path):
    c = Cikti(film_id="filmB", bolum="cikis", durum="METIN_YOK")
    c.yaz(tmp_path)
    d = tmp_path / "filmB" / "cikis"
    assert not (d / "vince.txt").exists()
    assert not (d / "vince_supheli.txt").exists()
    assert (d / "vince.json").exists()
    assert (d / "_TAMAM").exists()


def test_yaz_ariza_dosya_uretmez(tmp_path):
    c = ariza("filmC", "MODEL_HATASI", "cokme")
    c.yaz(tmp_path)
    d = tmp_path / "filmC" / "cikis"
    assert not (d / "vince.txt").exists()
    assert not (d / "vince_supheli.txt").exists()
    assert (d / "vince.json").exists()
    assert (d / "_TAMAM").exists()


def test_yaz_bos_dosya_yazilmaz_nash_dersi(tmp_path):
    """Tum satirlar SUPHELI ise vince.txt HIC yazilmamali (bos dosya yasak)."""
    c = Cikti(film_id="filmD", bolum="cikis", durum="OKUNDU",
              satirlar=[{"metin": "BELIRSIZ AD", "sinif": "SUPHELI"}])
    c.yaz(tmp_path)
    d = tmp_path / "filmD" / "cikis"
    assert not (d / "vince.txt").exists()
    assert (d / "vince_supheli.txt").read_text(encoding="utf-8") == "BELIRSIZ AD"


def test_yaz_bolum_klasorune_gider(tmp_path):
    c = Cikti(film_id="filmE", bolum="giris", durum="METIN_YOK")
    c.yaz(tmp_path)
    assert (tmp_path / "filmE" / "giris" / "_TAMAM").exists()


def test_yaz_bayat_dosyayi_temizler(tmp_path):
    """Koordinator bulgusu: OKUNDU -> ARIZA gecisinde eski vince.txt
    SILINMELI, yoksa tuketici bayat satirlari gecerli okuma sanir (ARIZA'nin
    icerik gercegine donusmesiyle ayni sonuc, dolambacli yoldan)."""
    c1 = Cikti(film_id="filmF", bolum="cikis", durum="OKUNDU",
               satirlar=[{"metin": "ESKI SATIR 1", "sinif": "KESIN"},
                         {"metin": "ESKI SUPHELI", "sinif": "SUPHELI"}])
    c1.yaz(tmp_path)
    d = tmp_path / "filmF" / "cikis"
    assert (d / "vince.txt").exists()
    assert (d / "vince_supheli.txt").exists()

    c2 = ariza("filmF", "BELLEK_HATASI", "GPU dustu", bolum="cikis")
    c2.yaz(tmp_path)

    assert not (d / "vince.txt").exists(), "bayat vince.txt silinmeden kalmis"
    assert not (d / "vince_supheli.txt").exists(), "bayat supheli dosyasi kalmis"
    assert (d / "_TAMAM").exists()
    import json
    kayitli = json.loads((d / "vince.json").read_text(encoding="utf-8"))
    assert kayitli["durum"] == "ARIZA"
    assert kayitli["sinif"] == "BELLEK_HATASI"
    assert "satirlar" not in kayitli


def test_yaz_ikinci_okundu_kosusu_ilkinin_supheli_dosyasini_temizler(tmp_path):
    """Once supheli satirli bir OKUNDU, sonra supheli'siz bir OKUNDU: eski
    vince_supheli.txt yeni kosuda kalmamali."""
    c1 = Cikti(film_id="filmG", bolum="cikis", durum="OKUNDU",
               satirlar=[{"metin": "A", "sinif": "KESIN"},
                         {"metin": "B SUPHELI", "sinif": "SUPHELI"}])
    c1.yaz(tmp_path)
    d = tmp_path / "filmG" / "cikis"
    assert (d / "vince_supheli.txt").exists()

    c2 = Cikti(film_id="filmG", bolum="cikis", durum="OKUNDU",
               satirlar=[{"metin": "A", "sinif": "KESIN"}])
    c2.yaz(tmp_path)
    assert not (d / "vince_supheli.txt").exists()
    assert (d / "vince.txt").read_text(encoding="utf-8") == "A"


# --------------------------------------------------------------------------- film_id yol guvenligi
@pytest.mark.parametrize("kotu_id", ["../kacis", "a/b", "a\\b", ".", "..",
                                     "/mutlak/yol", "../../etc"])
def test_girdi_film_id_yol_kacisi_reddedilir(kotu_id):
    with pytest.raises(GirdiHatasi):
        Girdi(film_id=kotu_id, video="k.mp4")


@pytest.mark.parametrize("kotu_id", ["../kacis", "a/b", "a\\b", ".", ".."])
def test_cikti_film_id_yol_kacisi_reddedilir(kotu_id):
    with pytest.raises(ValueError):
        Cikti(film_id=kotu_id, durum="METIN_YOK")


@pytest.mark.parametrize("kotu_id", ["../kacis", "a/b"])
def test_ariza_film_id_yol_kacisi_reddedilir(kotu_id):
    with pytest.raises(ValueError):
        ariza(kotu_id, "MODEL_HATASI", "x")


def test_cikti_film_id_sonradan_yol_kacisina_cevrilemez():
    c = Cikti(film_id="guvenli_ad", durum="METIN_YOK")
    with pytest.raises(ValueError):
        c.film_id = "../kacis"
    assert c.film_id == "guvenli_ad"


def test_gecerli_film_id_alt_cizgi_ve_rakam_kabul_eder():
    g = Girdi(film_id="film_123", video="k.mp4")
    assert g.film_id == "film_123"
