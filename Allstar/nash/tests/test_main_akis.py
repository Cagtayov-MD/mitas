"""Akış testleri — üç gerçek doğru duruma çevriliyor mu, kuyruk devam ediyor mu?"""
import json

import cv2
import numpy as np
import pytest

import main
import okuyucu
import senaryo
from sozlesme import Girdi


def _kareler(dizin, kareler):
    dizin.mkdir(parents=True, exist_ok=True)
    for i, k in enumerate(kareler):
        cv2.imwrite(str(dizin / f"c_{i:05d}.png"), k)
    return dizin


def _iyi(tmp_path, ad="film"):
    return _kareler(tmp_path / ad,
                    senaryo.kart("BIRINCI KART UZUN METIN", 6) +
                    senaryo.kart("XYZW BAMBASKA ICERIK QQ", 6))


def _sor_iyi(p):
    """Sayfa basina FARKLI icerik — gercek jenerikte oldugu gibi. Ayni metni
    her sayfada dondurmek dedup'i tetikler ve tek kartlik bir film taklit eder."""
    n = p.stem
    return (f"YONETMEN AHMET MEHMET VELI OZTURK {n}\n"
            f"GORUNTU YONETMENI AYSE FATMA KARADENIZ {n}\n"
            f"KURGU MUSTAFA KEMAL YILDIRIM ARSLAN {n}\n"
            f"MUZIK JOHN WILLIAMS SYMPHONY ORCHESTRA {n}\n"
            f"YAPIM TRT TURKIYE RADYO TELEVIZYON KURUMU {n}")


def _cikti_json(kok, fid="F1", bolum="cikis"):
    return json.loads((kok / fid / bolum / "nash.json").read_text("utf-8"))


# ── mutlu yol ────────────────────────────────────────────────────────────────

def test_okundu_diske_yazilir(tmp_path):
    d = _iyi(tmp_path)
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", _sor_iyi)
    assert c.durum == "OKUNDU" and c.satirlar
    j = _cikti_json(tmp_path / "out")
    assert j["durum"] == "OKUNDU"
    assert j["kanit"]["havuz"]["kare"] == 12
    assert j["kanit"]["saglik"] == "ok"
    assert (tmp_path / "out" / "F1" / "cikis" / "_TAMAM").is_file()
    assert (tmp_path / "out" / "F1" / "cikis" / "nash.txt").read_text("utf-8").strip()


def test_motor_surumu_ve_sure_yazilir(tmp_path):
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", _sor_iyi)
    assert c.motor_surumu.startswith("nash@") and c.sure_sn >= 0


# ── üç gerçeğin ayrımı ───────────────────────────────────────────────────────

def test_dizin_yok_ariza_girdi_hatasi(tmp_path):
    c = main.tek(Girdi(film_id="F1", kareler=str(tmp_path / "yok")),
                 tmp_path / "out", _sor_iyi)
    assert c.durum == "ARIZA" and c.sinif == "GIRDI_HATASI"


def test_kareler_acilamiyor_ariza_kare_okunamadi(tmp_path):
    d = tmp_path / "bozuk"
    d.mkdir()
    for i in range(3):
        (d / f"c_{i}.png").write_bytes(b"PNG degil")
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", _sor_iyi)
    assert c.durum == "ARIZA" and c.sinif == "KARE_OKUNAMADI"
    assert c.kanit["acilamayan"] == 3


def test_hepsi_iceriksiz_metin_yok_ariza_degil(tmp_path):
    """Bu bir İÇERİK GERÇEĞİ — arıza değil. Bugün üretimde ikisi aynı kutuda."""
    d = _kareler(tmp_path / "duz",
                 [np.full((160, 200), 128, np.uint8) for _ in range(6)])
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", _sor_iyi)
    assert c.durum == "METIN_YOK"
    assert c.sinif is None and not c.satirlar
    assert _cikti_json(tmp_path / "out")["kanit"]["havuz"]["kare"] == 6


def test_model_bos_dondu_metin_yok(tmp_path):
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", lambda p: "")
    assert c.durum == "METIN_YOK"


# ── arıza sınıfları ──────────────────────────────────────────────────────────

def test_garble_ariza_cikti_bozuk_metin_yok_degil(tmp_path):
    """Elimizdeki metin YANLIŞ — aşağı akışa bırakmak künyeyi zehirler (rodeo)."""
    def sor(p):
        return "\n".join(f"A!@#$%^&{i} B!@#$%^&{i} C!@#$%^&{i} D!@#$%^&{i}"
                         for i in range(8))
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", sor)
    assert c.durum == "ARIZA" and c.sinif == "CIKTI_BOZUK"
    assert c.kanit["saglik"] == "garble_yuksek"


def test_cok_kisa_ariza_degil_icerik_korunur(tmp_path):
    """5 satırlık gerçek bir jenerik ARIZA'ya çevrilemez — sağlık bir BAYRAK."""
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", lambda p: "YONETMEN AHMET")
    assert c.durum == "OKUNDU"
    assert c.kanit["saglik"] == "cok_kisa"      # uyari kanitta, hukum degil
    assert [s["text"] for s in c.satirlar] == ["YONETMEN AHMET"]


def test_oom_ariza_bellek(tmp_path):
    def sor(p):
        raise okuyucu.Bellek("CUDA out of memory")
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", sor)
    assert c.durum == "ARIZA" and c.sinif == "BELLEK"


def test_okuyucu_kurulmadiysa_ariza_model(tmp_path):
    """Faz 1'de src/model.py YOK — kule tahmin etmez, açık ARIZA döner."""
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", None)
    assert c.durum == "ARIZA" and c.sinif == "MODEL"
    # Havuz kaniti ARIZA'da da korunur — nerede durdugumuz gorunur.
    assert c.kanit["havuz"]["kare"] == 12


def test_ariza_da_diske_yazilir(tmp_path):
    main.tek(Girdi(film_id="F1", kareler=str(tmp_path / "yok")),
             tmp_path / "out", _sor_iyi)
    assert (tmp_path / "out" / "F1" / "cikis" / "_TAMAM").is_file()
    assert _cikti_json(tmp_path / "out")["sinif"] == "GIRDI_HATASI"


# ── bölüm ────────────────────────────────────────────────────────────────────

def test_giris_bolumu_calisir_ve_ayri_yazar(tmp_path):
    """Kobe'nin aksine Nash'te giriş desteklenir — engeli yok."""
    d = _iyi(tmp_path)
    c = main.tek(Girdi(film_id="F1", kareler=str(d), bolum="giris"),
                 tmp_path / "out", _sor_iyi)
    assert c.durum == "OKUNDU" and c.bolum == "giris"
    assert (tmp_path / "out" / "F1" / "giris" / "nash.json").is_file()
    assert not (tmp_path / "out" / "F1" / "cikis").exists()


# ── toplu kuyruk ─────────────────────────────────────────────────────────────

def test_toplu_tamam_olani_atlar(tmp_path, monkeypatch):
    girdi = tmp_path / "girdi"
    girdi.mkdir()
    for ad in ("A", "B"):
        _iyi(girdi, ad)
    kok = tmp_path / "out"
    monkeypatch.setattr(main, "okuyucu_kur", lambda cfg: _sor_iyi)

    assert len(main.toplu(girdi, kok)) == 2
    # ikinci kosuda ikisi de _TAMAM — hicbiri yeniden islenmez
    assert main.toplu(girdi, kok) == []


def test_toplu_okuyucu_kurulamazsa_her_filme_ariza_yazar(tmp_path):
    girdi = tmp_path / "girdi"
    girdi.mkdir()
    _iyi(girdi, "A")
    sonuc = main.toplu(girdi, tmp_path / "out")
    assert len(sonuc) == 1
    assert sonuc[0].durum == "ARIZA" and sonuc[0].sinif == "MODEL"
