"""Rol-eşleme denetimi — modelin verdiği yönetmeni künye BAĞLAMINA karşı sınar.

ÖLÇÜLEN SORUN (2026-08-01): model, etiketin SAHİBİ OLMAYAN komşu ismi yönetmen
alanına yazıyor. Üç gerçek vaka ölçüldü:
    ÇİNGENE 1998-0435    : satır 20 '2ème assistant réalisateur' → 21 FREDERIC PLANCHON
    KARA GÜNLER 1998-0312: satır 12 'NACH EINER GESCHICHTE VON'  → 13 DOMINIQUE ROULET
                           (DOĞRU yönetmen NIKOLAUS LEYTNER satır 10'da duruyordu)
    YAZ TATİLİ 1963-0035 : koreograf HERBERT ROSS alınmış, doğru isim PETER YATES
                           BİR ALT SATIRDA — ama üstünde etiket YOK

ÇAĞATAY KISITI: "Bu işi modelden ALMAM, en fazla modeli değiştiririz."
Bu yüzden dogrula() ÇIKARIM YAPMAZ — yalnız modelin cevabını DENETLER.
Model ana yol kalır; bu katman hakemdir. (Model değişimi de ölçüldü ve çözüm
değil: gemma4:26b daha iyi nicelemeli ama üç filmde cast=0 verdi.)

İKİ YÖNLÜ TEHLİKE:
  • gevşek → yanlış yönetmen PDF'e çıkar
  • sıkı   → DOĞRU yönetmen reddedilir; alan boşalır, film KONTROL'e düşer.
    Kontrol vakaları (DELİ ORMANLI, KUTSAL HAZİNE) bunu kilitler.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import yonetmen_kurtar as yk  # noqa: E402


# ───────── REDDETMESİ ZORUNLU (gerçek üretim vakaları) ─────────

def test_cingene_ikinci_asistan():
    """ÇİNGENE: 'MISE EN SCENE' etiketi var ama isim asistan satırının ALTINDA."""
    sat = ["et la collaboration de", "MISE EN SCENE",
           "2ème assistant réalisateur", "FREDERIC PLANCHON", "scripte"]
    r = yk.dogrula("FREDERIC PLANCHON", sat)
    assert r and r["sebep"] == "ustunde_rol_etiketi"
    assert "assistan" in r["etiket"].lower()


def test_kara_gunler_hikaye_yazari():
    """KARA GÜNLER: 'NACH EINER GESCHICHTE VON' = hikâyesinden → yazar, yönetmen değil."""
    sat = ["NIKOLAUS LEYTNER", "MAX LINDER", "NACH EINER GESCHICHTE VON",
           "DOMINIQUE ROULET", "GM. 73 HY"]
    r = yk.dogrula("DOMINIQUE ROULET", sat)
    assert r and "geschichte" in r["etiket"].lower()


@pytest.mark.parametrize("etiket", [
    "NACH EINER GESCHICHTE VON", "BASED ON A STORY BY", "SENARYO",
    "SCÉNARIO", "DREHBUCH", "2ème assistant réalisateur",
    "Director of Photography", "Seslendirme Yönetmen", "yönetmen yardımcısı",
])
def test_yonetmen_disi_etiketler_reddedilir(etiket):
    r = yk.dogrula("AHMET YILMAZ", [etiket, "AHMET YILMAZ"])
    assert r is not None, f"{etiket!r} altındaki isim reddedilmedi"


def test_ayni_satirda_rol_etiketi():
    r = yk.dogrula("Mehmet Nazlı", ["Seslendirme Yönetmen  Mehmet Nazlı"])
    assert r and r["sebep"] == "ayni_satirda_rol_etiketi"


# ───────── GEÇMESİ ZORUNLU (regresyon kilidi) ─────────

def test_gercek_yonetmen_etiketi_temiz():
    """'Directed by' ALTINDAKİ isim doğru — reddedilmemeli."""
    assert yk.dogrula("JOHN CONNICK", ["Co-Executive Producers", "Directed by",
                                       "JOHN CONNICK"]) is None


def test_turkce_yonetmen_etiketi_temiz():
    assert yk.dogrula("ZEKİ DEMİRKUBUZ", ["Yönetmen", "ZEKİ DEMİRKUBUZ"]) is None


def test_etiketsiz_isim_temiz():
    """Üstünde hiç etiket yoksa hüküm YOK — uydurma red yapmaz.
    (YAZ TATİLİ sınıfı: bu kural onu yakalayamaz, kayıtlı sınır.)"""
    assert yk.dogrula("HERBERT ROSS", ["Caption:", "Markdown-style Summary:",
                                       "HERBERT ROSS", "PETER YATES"]) is None


def test_arada_baska_isim_varsa_bag_kopar():
    """Etiket ile isim arasına BAŞKA isim girdiyse etiket o isme ait değildir."""
    assert yk.dogrula("CEM YILMAZ", ["Director of Photography", "LUDEK BOGNER",
                                     "CEM YILMAZ"]) is None


def test_kunyede_olmayan_isim_hukumsuz():
    assert yk.dogrula("HİÇ YOKTU", ["Directed by", "BAŞKA BİRİ"]) is None


def test_bos_girdi():
    assert yk.dogrula("", ["Directed by", "X Y"]) is None
    assert yk.dogrula("AHMET YILMAZ", []) is None


# ───────── kurtarıcı ile birlikte çalışma ─────────

def test_denetim_ve_kurtarma_ayni_kunyede():
    """ÇİNGENE deseninde: asistan reddedilir, gerçek etiketli isim kurtarılır."""
    sat = ["MISE EN SCENE", "PHILIPPE DE BROCA",
           "2ème assistant réalisateur", "FREDERIC PLANCHON"]
    assert yk.dogrula("FREDERIC PLANCHON", sat) is not None      # yanlış → red
    assert yk.dogrula("PHILIPPE DE BROCA", sat) is None          # doğru → temiz
    kurt = yk.kurtar(sat)
    assert kurt and kurt["yonetmen"] == "PHILIPPE DE BROCA"      # kurtarıcı doğruyu bulur


# ───────── KONSEY TURU DÜZELTMELERİ (2026-08-01, 4 üye bağımsız buldu) ─────────

def test_isim_kendi_soyadindan_reddedilmez():
    """_DEGIL hedef ismin KENDİ İÇİNDEKİ alt-dizeyi yakalıyordu.
    'AYŞE POSTACI' → 'POST' eşleşti → DOĞRU yönetmen reddedildi.
    Artık isim satırdan MASKELENİP sonra rol etiketi aranıyor."""
    for isim in ("AYŞE POSTACI", "SESLİ KAYA", "SANATKAR DEMİR", "EDITH PIAF"):
        assert yk.dogrula(isim, ["Directed by", isim]) is None, f"{isim} yanlış reddedildi"


def test_cift_rol_auteur_kabul():
    """Aynı kişi hem yazar hem yönetmen olabilir (auteur). Eskiden İLK geçişte
    karar verilip reddediliyordu; artık TÜM geçişler taranıyor, biri temizse kabul."""
    sat = ["Written by", "JANE DOE", "Directed by", "JANE DOE"]
    assert yk.dogrula("JANE DOE", sat) is None


def test_gercek_tuzaklar_hala_reddediliyor():
    """Maskeleme gevşetme DEĞİL — ölçülmüş üç vaka hâlâ reddedilmeli."""
    assert yk.dogrula("FREDERIC PLANCHON",
                      ["MISE EN SCENE", "2ème assistant réalisateur",
                       "FREDERIC PLANCHON"]) is not None
    assert yk.dogrula("DOMINIQUE ROULET",
                      ["NACH EINER GESCHICHTE VON", "DOMINIQUE ROULET"]) is not None
    assert yk.dogrula("Mehmet Nazlı", ["Seslendirme Yönetmen  Mehmet Nazlı"]) is not None


# ───────── ÇOK-YÖNETMEN (P0: ikinci yönetmen sessizce kayboluyordu) ─────────

def test_es_yonetmen_ikisi_de_alinir():
    """'Directed by / JOEL COEN / ETHAN COEN' → ETHAN COEN kaybolmamalı.
    Promptun kural 4'ü de 'HEPSİNİ yaz, TEKE İNDİRME' diyor."""
    r = yk.kurtar(["Directed by", "JOEL COEN", "ETHAN COEN"])
    assert r and r["yonetmenler"] == ["JOEL COEN", "ETHAN COEN"]


def test_karakter_adi_es_yonetmen_sayilmaz():
    """KUTSAL HAZİNE: 'Directed by / JOHN CONNICK' sonrası 'Erea Johnson'
    (karakter adı) eş-yönetmen SANILMAMALI. Ayırıcı: KASA DESENİ."""
    r = yk.kurtar(["Directed by", "JOHN CONNICK", "Erea Johnson", "Blakorow"])
    assert r and r["yonetmenler"] == ["JOHN CONNICK"]


@pytest.mark.parametrize("etiket", [
    "Written and Directed by", "Written, Produced and Directed by",
    "Produced and Directed by", "Written, Directed and Edited by",
    "Directed and Produced by",
])
def test_bilesik_etiketler_kabul(etiket):
    """Bileşik yönetmen kartları MEŞRU (promptun kural 4'ü açıkça söylüyor).
    Eski 'etiketten önce metin varsa atla' koruması bunları reddediyordu."""
    r = yk.kurtar([etiket, "ORSON WELLES"])
    assert r and "ORSON WELLES" in (r.get("yonetmenler") or []), f"{etiket!r} reddedildi"


def test_serbest_cumle_hala_reddediliyor():
    """Bileşik-etiket istisnası, serbest cümleyi geçirmemeli."""
    assert yk.kurtar(["Bu film 1998 yılında directed by", "AHMET YILMAZ"]) is None
    assert yk.kurtar(["Set amiri tarafından directed by", "X Y"]) is None
