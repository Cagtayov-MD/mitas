"""Kobe koşu akışı — ffmpeg ve Paddle sahte, gerçek çağrılmaz."""
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))

import main  # noqa: E402
from sozlesme import Girdi  # noqa: E402


# ── film_id türetme: tek kural, tahmin yok ──────────────────────────────
def test_film_id_video_uzantisiz_ad():
    assert main.film_id_uret(Path("/y/2025-1307-1-0000-50-0.mp4"), False) \
        == "2025-1307-1-0000-50-0"


def test_film_id_kareler_dizin_adi():
    assert main.film_id_uret(Path("/y/BEYAZ_BALINA/"), True) == "BEYAZ_BALINA"


# ── scratch yaşam döngüsü: kule kendi yaratmadığını silmez ──────────────
def test_video_yolunda_scratch_silinir(tmp_path, monkeypatch):
    kok, scratch = tmp_path / "out", tmp_path / "scratch"
    monkeypatch.setattr(main, "SCRATCH", scratch)
    monkeypatch.setattr(main, "kare_cikar", _sahte_kare_cikar)
    monkeypatch.setattr(main, "_tespit", lambda d, c: _SahteSonuc(940))
    main.tek(Girdi(film_id="F1", video="/y/F1.mp4"), kok)
    assert not (scratch / "F1").exists()


def test_ariza_da_scratch_silinir(tmp_path, monkeypatch):
    kok, scratch = tmp_path / "out", tmp_path / "scratch"
    monkeypatch.setattr(main, "SCRATCH", scratch)
    monkeypatch.setattr(main, "kare_cikar", _sahte_kare_cikar)
    def _patla(d, c):
        raise RuntimeError("paddle coktu")
    monkeypatch.setattr(main, "_tespit", _patla)
    c = main.tek(Girdi(film_id="F1", video="/y/F1.mp4"), kok)
    assert c.durum == "ARIZA" and not (scratch / "F1").exists()


def test_disaridan_verilen_kare_dizini_SILINMEZ(tmp_path, monkeypatch):
    """Tek-yazar ilkesi: Kobe kendi yaratmadığını silmez."""
    dis = tmp_path / "baskasinin_kareleri"
    dis.mkdir()
    (dis / "c_00001.png").write_bytes(b"x")
    monkeypatch.setattr(main, "_tespit", lambda d, c: _SahteSonuc(12))
    main.tek(Girdi(film_id="F1", kareler=str(dis)), tmp_path / "out")
    assert (dis / "c_00001.png").exists()


# ── arıza asla içerik gerçeğine dönüşmez ────────────────────────────────
def test_motor_cokerse_ARIZA_dondurur_KREDI_YOK_degil(tmp_path, monkeypatch):
    def _patla(d, c):
        raise RuntimeError("OOM")
    monkeypatch.setattr(main, "_tespit", _patla)
    c = main.tek(Girdi(film_id="F1", kareler=str(tmp_path)), tmp_path / "out")
    assert c.durum == "ARIZA" and c.sinif == "MOTOR"


def test_motor_minus_bir_derse_KREDI_YOK(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_tespit", lambda d, c: _SahteSonuc(-1))
    c = main.tek(Girdi(film_id="F1", kareler=str(tmp_path)), tmp_path / "out")
    assert c.durum == "KREDI_YOK"


# ── toplu mod: _TAMAM olanı atlar ───────────────────────────────────────
def test_toplu_tamam_olani_atlar(tmp_path, monkeypatch):
    girdi, kok = tmp_path / "girdi", tmp_path / "out"
    girdi.mkdir()
    for ad in ("A", "B"):
        (girdi / ad).mkdir()
        (girdi / ad / "c_00001.png").write_bytes(b"x")
    (kok / "A" / "cikis").mkdir(parents=True)
    (kok / "A" / "cikis" / "_TAMAM").write_text("")
    islenen = []
    def _izle(d, c):
        islenen.append(Path(d).name)
        return _SahteSonuc(5)
    monkeypatch.setattr(main, "_tespit", _izle)
    main.toplu(girdi, True, kok)
    assert islenen == ["B"]


# ── E1: kanıt telemetrisi motor.Sonuc'u BİREBİR taşır ────────────────────
def test_kanit_telemetrisi_sonucu_birebir_tasir(tmp_path, monkeypatch):
    """E1 (2026-08-17): üretim (scripts/_jenerik_pool.py) manifest'in `v5`
    alt-nesnesini kanıt'taki bu alanlardan besler. Yanlış attribute adı
    getattr'in varsayılanıyla SESSİZCE maskelenirdi (ardisic/ardisik typo'su
    A/B'de yakalandı) — bu test sınıfı kapatır: alan farklı-değerli doldurulur,
    kanıtta AYNI değer görülmeli."""
    import motor
    monkeypatch.setattr(main, "_tespit", lambda d, c: motor.Sonuc(
        start_frame=44, yontem="kutu+scroll", guven=0.77, notlar="not-X",
        tip="scroll", scroll_orani=0.42, ardisik_scroll=7, son_capa=0.81,
        aday_sayisi=3, suphe=["gec_riski"], suphe_geri_kare=123,
        script="ru", ocr_hata=2))
    dis = tmp_path / "kareler"
    dis.mkdir()
    (dis / "c_00044.png").write_bytes(b"x")
    c = main.tek(Girdi(film_id="F1", kareler=str(dis)), tmp_path / "out")
    k = c.kanit
    assert c.durum == "BULUNDU"
    assert k["tip"] == "scroll"
    assert k["scroll_orani"] == 0.42
    assert k["ardisik_scroll"] == 7      # ad yanlışsa getattr varsayılanı (0) gelir
    assert k["son_capa"] == 0.81
    assert k["aday_sayisi"] == 3
    assert k["notlar"] == "not-X"
    assert k["suphe"] == ["gec_riski"]
    assert k["suphe_geri_kare"] == 123
    assert k["ocr_hata"] == 2


# ── yardımcılar ─────────────────────────────────────────────────────────
class _SahteSonuc:
    def __init__(self, kare):
        self.start_frame, self.yontem, self.guven = kare, "tespit_v5", 0.9
        self.script, self.notlar, self.ocr_hata = "en", "", 0


def _sahte_kare_cikar(video, hedef, bolum="cikis"):
    hedef.mkdir(parents=True, exist_ok=True)
    (hedef / "c_00001.png").write_bytes(b"x")
    return hedef, 0
