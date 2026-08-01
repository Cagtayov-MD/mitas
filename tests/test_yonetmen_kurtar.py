"""Yönetmen kurtarma — etiket-tabanlı, deterministik. Model/GPU/ağ gerekmez.

NEDEN VAR: ölçüldü (2026-08-01) — yönetmen etiketi olan 145 filmin 35'inde (%24)
etiket künyede VAR ama alan BOŞ → QC1 RED → KONTROL. Kayıp okumada değil,
rol-eşlemede. Bu modül boşluğu deterministik olarak doldurur.

İKİ YÖNLÜ TEHLİKE — testler ikisini de kilitler:
  • Fazla gevşek → YANLIŞ yönetmen yazılır. Bu, boş bırakmaktan BETERDİR
    (Çağatay: "gerisinde halüsinasyon olmasın"). Aşağıdaki tuzakların hepsi
    GERÇEK üretim verisinden geldi ve ilk sürümü çürüttü.
  • Fazla sıkı  → kurtarma hiç çalışmaz, 35 film KONTROL'de çürür.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import yonetmen_kurtar as yk  # noqa: E402


# ───────────────── KURTARMASI ZORUNLU ─────────────────

def test_kutsal_hazine_gercek_vaka():
    """KUTSAL HAZİNE 1998-0325: g_0244.png'de 'Directed by / JOHN CONNICK'
    ekranda görünüyor (gözle doğrulandı), künyeye yazıldı, gemma atladı."""
    r = yk.kurtar(["Co-Executive Producers", "ALAN H. GINSBURG",
                   "MICHAEL WOJCIECHOWSKI", "Directed by", "JOHN CONNICK"])
    assert r and r["yonetmen"] == "JOHN CONNICK"
    assert r["nasil"] == "alt_satir"


def test_ayni_satir_bicimi():
    r = yk.kurtar(["Yönetmen: ZEKİ DEMİRKUBUZ"])
    assert r and r["yonetmen"] == "ZEKİ DEMİRKUBUZ"
    assert r["nasil"] == "ayni_satir"


def test_cok_dilli_etiketler():
    for satirlar, beklenen in (
        (["UN FILM DE", "ALAIN ROBAK"], "ALAIN ROBAK"),
        (["REGIE", "NORA ORTEGA"], "NORA ORTEGA"),
        (["A FILM BY", "TERRY GEORGE"], "TERRY GEORGE"),
        (["Yöneten", "MEMDUH ÜN"], "MEMDUH ÜN"),
    ):
        r = yk.kurtar(satirlar)
        assert r and r["yonetmen"] == beklenen, f"{satirlar} → {r}"


# ───────────────── REDDETMESİ ZORUNLU (hepsi gerçek üretim tuzağı) ─────────────────

def test_gorúntu_yonetmeni_tuzagi():
    """CİNAYET 1974-0213: 'Director of Photography' film yönetmeni DEĞİL."""
    assert yk.kurtar(["Director of Photography", "LUDEK BOGNER"]) is None


def test_ocr_bozulmus_gorüntü_yonetmeni():
    """Kuru koşu bulgusu: OCR 'DIRECTOR OF PHOTOGRAPHY'yi bozunca çıplak
    'DIRECTOR' kalıyordu ve 20 sahte kurtarma üretiyordu."""
    for bozuk in ("OF PHOROGRAPHY", "OF FHOTOGRAPHY", "OH PHOBOGRAGN", "DE FOTOGRAFIA"):
        assert yk.kurtar(["DIRECTOR", bozuk]) is None, bozuk


def test_ikinci_birim_ve_ses_tuzagi():
    assert yk.kurtar(["2nd Unit Director", "MICHAEL BLUNDELL"]) is None
    assert yk.kurtar(["DIRECTORS SOUND", "GLENWOOD AUDIO"]) is None
    assert yk.kurtar(["Seslendirme Yönetmen", "Mehmet NAZLI"]) is None
    assert yk.kurtar(["yönetmen yardımcısı", "LUTZ RABBACH"]) is None


def test_etiket_adaylari_reddedilir():
    """Aday başka bir ETİKET olamaz."""
    assert yk.kurtar(["DIRECTED BY", "PRODUCED BY"]) is None
    assert yk.kurtar(["Directed by", "DIRECTOR OF"]) is None


def test_duzyazi_ve_film_adi_reddedilir():
    """GLORIA KUŞATMASI / FRANK CAPRA vakaları — cümle parçası isim değil."""
    assert yk.kurtar(["DIRECTED BY", "EXPLODED THROUGHOUT AN UNSUSPECTING TOWN"]) is None
    assert yk.kurtar(["DIRECTED BY", "YOU CANT TAKE IT"]) is None


def test_sirket_ve_tek_kelime_reddedilir():
    assert yk.kurtar(["Directed by", "MEGA FILM PRODUCTIONS"]) is None
    assert yk.kurtar(["Directed by", "SMITH"]) is None          # tek kelime isim değil
    assert yk.kurtar(["Directed by", "JOHN 2 SMITH"]) is None    # rakam içeriyor


def test_etiketten_once_metin_varsa_atlanir():
    """Serbest cümle içinde geçen etiket kart değildir."""
    assert yk.kurtar(["Bu film 1998 yılında directed by", "AHMET YILMAZ"]) is None


def test_bulamazsa_none_asla_uydurmaz():
    assert yk.kurtar([]) is None
    assert yk.kurtar(["OYUNCULAR", "AHMET MEHMET", "AYŞE FATMA"]) is None


# ───────────────── adres teyidi ─────────────────

def test_iz_yoksa_teyit_iz_yok_der():
    r = yk.kurtar(["Directed by", "JOHN CONNICK"])
    assert r["kare_teyidi"] == "iz_yok"          # hüküm vermez, işaretler


def test_ayni_satirda_teyit_gerekmez():
    """Etiket ve isim ZATEN aynı satırdaysa adres teyidi anlamsız."""
    r = yk.kurtar(["Yönetmen ZEKİ DEMİRKUBUZ"])
    assert r["kare_teyidi"] == "etiketle_ayni_satir"


def test_ayni_kare_teyidi(tmp_path):
    """Etiket ve isim AYNI kareden geldiyse teyit kare adını döner."""
    iz = tmp_path / "hibrit_iz.jsonl"
    iz.write_text(
        '{"kol":"frame_giris","kaynak":"g_0244.png","text":"Directed by"}\n'
        '{"kol":"frame_giris","kaynak":"g_0244.png","text":"JOHN CONNICK"}\n',
        encoding="utf-8")
    r = yk.kurtar(["Directed by", "JOHN CONNICK"], iz_yolu=str(iz))
    assert r["kare_teyidi"] == "g_0244.png"


def test_ayri_kare_teyitsiz_isaretlenir(tmp_path):
    """HOTEL RWANDA sınıfı: etiket ve isim künyede komşu ama EKRANDA ayrı
    karelerde → teyit YOK → pipeline bunu alana YAZMAZ, aday olarak işaretler."""
    iz = tmp_path / "hibrit_iz.jsonl"
    iz.write_text(
        '{"kol":"frame_cikis","kaynak":"c_0100.png","text":"A FILM BY"}\n'
        '{"kol":"frame_cikis","kaynak":"c_0480.png","text":"FANA MOKOENA"}\n',
        encoding="utf-8")
    r = yk.kurtar(["A FILM BY", "FANA MOKOENA"], iz_yolu=str(iz))
    assert r["kare_teyidi"] == "AYRI_KARE"


# ───────────────── isim_mi birimi ─────────────────

def test_isim_mi_sinirlari():
    assert yk.isim_mi("JOHN CONNICK")
    assert yk.isim_mi("Zeki Demirkubuz")
    assert not yk.isim_mi("SMITH")
    assert not yk.isim_mi("")
    assert not yk.isim_mi("A B C D E F G")        # çok token
    assert not yk.isim_mi("WARNER BROS PICTURES")
