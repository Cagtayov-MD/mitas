"""Bölüm ayrımı — çıkış (kapanış) ve giriş jeneriği ayrı klasörlere yazılır.

Giriş jeneriği HENÜZ DESTEKLENMİYOR ve bu bilerek GÖRÜNÜR bir arızadır:
motorun temel ayracı (`SON_ERISIM=0.82` — "krediler pencerenin sonuna kadar
akar") giriş jeneriğinde TERS çalışır. Tahmin etmek yerine arıza döner.
"""
import json
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))

import main  # noqa: E402
from sozlesme import Cikti, Girdi, GirdiHatasi  # noqa: E402


class _SahteSonuc:
    def __init__(self, kare):
        self.start_frame, self.yontem, self.guven = kare, "tespit_v5", 0.9
        self.script, self.notlar, self.ocr_hata = "en", "", 0


def _kare_dizini(p: Path, adet: int = 200) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    for i in range(1, adet + 1):
        (p / f"c_{i:05d}.png").write_bytes(b"x")
    return p


# ── varsayılan bölüm: cikis ─────────────────────────────────────────────
def test_varsayilan_bolum_cikis():
    assert Girdi(film_id="F1", video="/y/f.mp4").bolum == "cikis"


def test_gecersiz_bolum_reddedilir():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="F1", video="/y/f.mp4", bolum="ortasi")


# ── yerleşim: out/<film_id>/<bolum>/ ────────────────────────────────────
def test_cikti_bolum_klasorune_yazilir(tmp_path):
    c = Cikti(film_id="F1", durum="KREDI_YOK", bolum="cikis")
    yol = c.yaz(tmp_path)
    assert yol == tmp_path / "F1" / "cikis" / "kobe.json"
    assert (tmp_path / "F1" / "cikis" / "_TAMAM").exists()


def test_iki_bolum_birbirini_ezmez(tmp_path):
    Cikti(film_id="F1", durum="KREDI_YOK", bolum="cikis").yaz(tmp_path)
    Cikti(film_id="F1", durum="ARIZA", sinif="X", mesaj="y",
          bolum="giris").yaz(tmp_path)
    assert (tmp_path / "F1" / "cikis" / "kobe.json").exists()
    assert (tmp_path / "F1" / "giris" / "kobe.json").exists()
    c = json.loads((tmp_path / "F1" / "cikis" / "kobe.json").read_text(encoding="utf-8"))
    g = json.loads((tmp_path / "F1" / "giris" / "kobe.json").read_text(encoding="utf-8"))
    assert c["durum"] == "KREDI_YOK" and g["durum"] == "ARIZA"


def test_bolum_kobe_jsona_yazilir(tmp_path):
    Cikti(film_id="F1", durum="KREDI_YOK", bolum="cikis").yaz(tmp_path)
    d = json.loads((tmp_path / "F1" / "cikis" / "kobe.json").read_text(encoding="utf-8"))
    assert d["bolum"] == "cikis"


# ── artefaktlar da bölümün altında ──────────────────────────────────────
def test_artefakt_bolum_altina_yazilir(tmp_path, monkeypatch):
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(100))
    main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", uret="kare")
    assert (tmp_path / "out" / "F1" / "cikis" / "kareler").is_dir()


# ── giriş: (a) sinir + (b) havuz çağrılır, çıkışın motoru DEĞİL ─────────
from giris import sinir as giris_sinir  # noqa: E402  (main importu SRC'yi path'e ekledi)


def _sahte_sinir_bulundu(**over):
    d = {"bulundu": True, "baslangic_kare": 10, "baslangic_sn": 5.0,
         "bitis_kare": 200, "bitis_sn": 100.0, "guven": 0.9,
         "kanit": {"sinir_kaynagi": "tespit"}}
    d.update(over)
    return d


def test_giris_motoru_hic_cagirmaz(tmp_path, monkeypatch):
    """Çıkışın motoru (SON_ERISIM=0.82, jenerik sona ulaşmalı) girişte TERS
    çalışır — bu yüzden giriş kendi (a) sinir + (b) havuz yolunu kullanır,
    çıkışın _tespit'i HİÇ koşmamalı."""
    d = _kare_dizini(tmp_path / "kareler")
    cagrildi = []
    monkeypatch.setattr(main, "_tespit",
                        lambda x, c: cagrildi.append(1) or _SahteSonuc(100))
    monkeypatch.setattr(giris_sinir, "bul", lambda dizin, config: _sahte_sinir_bulundu())
    main.tek(Girdi(film_id="F1", kareler=str(d), bolum="giris"), tmp_path / "out")
    assert cagrildi == []


def test_giris_sinir_bulundu_bitis_alanlarini_doldurur(tmp_path, monkeypatch):
    """Girişin sözleşme farkı: bitis_kare/bitis_sn de dolar (çıkışta hep None)."""
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(giris_sinir, "bul", lambda dizin, config: _sahte_sinir_bulundu())
    c = main.tek(Girdi(film_id="F1", kareler=str(d), bolum="giris"), tmp_path / "out")
    assert c.durum == "BULUNDU"
    assert c.baslangic_kare == 10 and c.bitis_kare == 200
    assert c.baslangic_sn == 5.0 and c.bitis_sn == 100.0


def test_giris_sinir_bulunamazsa_kredi_yok(tmp_path, monkeypatch):
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(giris_sinir, "bul", lambda dizin, config: {
        "bulundu": False, "baslangic_kare": None, "baslangic_sn": None,
        "bitis_kare": None, "bitis_sn": None, "guven": 0.0, "kanit": {}})
    c = main.tek(Girdi(film_id="F1", kareler=str(d), bolum="giris"), tmp_path / "out")
    assert c.durum == "KREDI_YOK"


def test_giris_sinir_patlarsa_ariza_GIRIS_SINIR(tmp_path, monkeypatch):
    """Motor patlarsa sessizce sabit pencereye düşmek YASAK — açık ARIZA."""
    d = _kare_dizini(tmp_path / "kareler")

    def _patla(dizin, config):
        raise RuntimeError("jenerik_detector coktu")

    monkeypatch.setattr(giris_sinir, "bul", _patla)
    c = main.tek(Girdi(film_id="F1", kareler=str(d), bolum="giris"), tmp_path / "out")
    assert c.durum == "ARIZA" and c.sinif == "GIRIS_SINIR"
    j = json.loads((tmp_path / "out" / "F1" / "giris" / "kobe.json").read_text(
        encoding="utf-8"))
    assert j["durum"] == "ARIZA" and j["sinif"] == "GIRIS_SINIR"


# ── toplu mod: _TAMAM bölüm bazında ─────────────────────────────────────
def test_toplu_TAMAM_bolum_bazinda_atlar(tmp_path, monkeypatch):
    girdi, kok = tmp_path / "girdi", tmp_path / "out"
    girdi.mkdir()
    for ad in ("A", "B"):
        _kare_dizini(girdi / ad, adet=60)
    (kok / "A" / "cikis").mkdir(parents=True)
    (kok / "A" / "cikis" / "_TAMAM").write_text("")
    islenen = []
    monkeypatch.setattr(main, "_tespit",
                        lambda d, c: islenen.append(Path(d).name) or _SahteSonuc(5))
    main.toplu(girdi, True, kok)
    assert islenen == ["B"]
