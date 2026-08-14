"""Seçim testleri — üç gerçeğin ayrımı + üretimden taşınan iki sigorta."""
import cv2
import numpy as np
import pytest

import secim
import senaryo


def _yaz(dizin, kareler, on="c_"):
    dizin.mkdir(parents=True, exist_ok=True)
    for i, k in enumerate(kareler):
        cv2.imwrite(str(dizin / f"{on}{i:05d}.png"), k)
    return dizin


AYAR = {"tavan": 100, "son_kare_zorla": True, "ham_kuyruk": 0}


# ── üç gerçeğin ayrımı (spec §3.1) ───────────────────────────────────────────

def test_dizin_yoksa_dizin_bos(tmp_path):
    s = secim.sec(tmp_path / "olmayan", AYAR)
    assert s.hata == "dizin_bos" and not s.yollar


def test_desene_uyan_dosya_yoksa_dizin_bos(tmp_path):
    (tmp_path / "bos").mkdir()
    (tmp_path / "bos" / "not.txt").write_text("x")
    assert secim.sec(tmp_path / "bos", AYAR).hata == "dizin_bos"


def test_hicbiri_acilamiyorsa_kare_okunamadi(tmp_path):
    """Dosya VAR ama açılamıyor → ARIZA gerçeği, içerik gerçeği DEĞİL."""
    d = tmp_path / "bozuk"
    d.mkdir()
    for i in range(4):
        (d / f"c_{i:05d}.png").write_bytes(b"bu bir PNG degil")
    s = secim.sec(d, AYAR)
    assert s.hata == "kare_okunamadi"
    assert s.kanit["acilamayan"] == 4


def test_hepsi_iceriksizse_havuz_bos(tmp_path):
    """Kareler okundu ama hepsi düz → METIN_YOK'a çevrilecek içerik gerçeği."""
    duz = [np.full((160, 200), 128, np.uint8) for _ in range(6)]
    s = secim.sec(_yaz(tmp_path / "duz", duz), AYAR)
    assert s.hata == "havuz_bos"
    assert s.kanit["havuz"]["kare"] == 6


def test_gercek_kartlar_secilir(tmp_path):
    kareler = senaryo.kart("BIRINCI KART UZUN METIN", 6) + \
              senaryo.kart("XYZW BAMBASKA ICERIK QQ", 6)
    s = secim.sec(_yaz(tmp_path / "iyi", kareler), AYAR)
    assert s.hata is None and s.yollar
    assert s.kanit["havuz"]["kare"] == 12
    assert s.kanit["secilen_kare"] == len(s.yollar)


def test_bozuk_kare_karisikta_sayilir_ama_durdurmaz(tmp_path):
    d = _yaz(tmp_path / "karisik", senaryo.kart("GERCEK KART METNI", 4))
    (d / "c_09999.png").write_bytes(b"bozuk")
    s = secim.sec(d, AYAR)
    assert s.hata is None
    assert s.kanit["acilamayan"] == 1
    assert s.kanit["havuz"]["kare"] == 4


# ── örnekleme ────────────────────────────────────────────────────────────────

def _p(n):
    from pathlib import Path
    return [Path(f"{i:04d}.png") for i in range(n)]


def test_tavan_altinda_degismez():
    y = _p(10)
    secilen, dusen = secim.ornekle(y, 100, True)
    assert secilen == y and dusen == 0


def test_tavan_ustunde_duzgun_adim_ve_dusen_dogru():
    secilen, dusen = secim.ornekle(_p(500), 100, False)
    assert len(secilen) == 100
    assert dusen == 400
    assert secilen == sorted(secilen)


def test_son_kare_zorla_son_indeksi_ekler():
    """© / 'SON' kartı tam sonda; düzgün-adım onu hiç seçmeyebilir."""
    y = _p(303)
    ile, _ = secim.ornekle(y, 100, True)
    haric, _ = secim.ornekle(y, 100, False)
    assert ile[-1] == y[-1]
    assert haric[-1] != y[-1]          # sigorta olmadan son kare KAYIP
    assert len(ile) == len(haric) + 1


def test_tavan_sifir_kirpmaz():
    y = _p(7)
    assert secim.ornekle(y, 0, False) == (y, 0)


# ── giriş kuyruk sigortası (ALİE vakası) ─────────────────────────────────────

def test_ham_kuyruk_son_kareleri_ekler():
    tum = _p(300)
    secilen = tum[:5]
    yeni, ek = secim.ham_kuyruk_ekle(secilen, tum, 12)
    assert ek == 12
    assert yeni[-12:] == tum[-12:]
    assert len(yeni) == 17


def test_ham_kuyruk_zaten_secilmisi_tekrarlamaz():
    tum = _p(20)
    yeni, ek = secim.ham_kuyruk_ekle(list(tum), tum, 12)
    assert ek == 0 and len(yeni) == 20


def test_ham_kuyruk_sifirsa_dokunmaz():
    tum = _p(20)
    yeni, ek = secim.ham_kuyruk_ekle(tum[:3], tum, 0)
    assert ek == 0 and yeni == tum[:3]


def test_giris_ayari_kuyrugu_uygular(tmp_path):
    kareler = senaryo.kart("GIRIS KARTI UZUN METIN", 30) + \
              senaryo.kart("YONETMEN AHMET MEHMET", 6)
    d = _yaz(tmp_path / "giris", kareler)
    s = secim.sec(d, {"tavan": 3, "son_kare_zorla": False, "ham_kuyruk": 12})
    assert s.hata is None
    assert s.kanit["kuyruk_ek"] > 0
    # Ham dizinin SON karesi, tavan 3 olmasina ragmen secimde.
    assert any(p.name == "c_00035.png" for p in s.yollar)
