"""isim_normalize golden testleri.

Vakalarin TAMAMI gercek veriden: Katman A sentez raporunun tespit ettigi
biçim çakismalari (wf_aa9a936e-5bb, 2026-07-20) + TRT XML yazim hatalari.
Uydurma vaka YOK — her satir sahada gorulmus bir carpismadir.
"""
from __future__ import annotations

import pytest

from isim_normalize import ayni_kisi, normalize, tr_lower

# ── Turkce buyuk/kucuk harf tuzagi ───────────────────────────────────────
# Python'un str.lower() metodu Turkce'de BOZUK: "I".lower() -> "i" (dogrusu "ı"),
# "İ".lower() -> "i̇" (kombine nokta, 2 kod noktasi!). Kunye tamamen BUYUK HARF
# geldigi icin bu her Turkce isimde tetiklenir.
TR_LOWER = [
    ("FAHRİYE", "fahriye"),
    ("MURAT YILDIRIM", "murat yıldırım"),
    ("IŞIL", "ışıl"),
    ("İNCİ", "inci"),
    ("KIŞ KÖRFEZİ", "kış körfezi"),
]


@pytest.mark.parametrize("giris,beklenen", TR_LOWER)
def test_turkce_lower(giris, beklenen):
    assert tr_lower(giris) == beklenen


def test_python_lower_bozuk_biz_degiliz():
    """Regresyon bekcisi: standart lower()'in bozuk oldugunu belgeler."""
    assert "İ".lower() != "i"          # kombine nokta uretir
    assert len("İ".lower()) == 2       # tek karakter degil!
    assert tr_lower("İ") == "i"        # bizimki dogru
    assert len(tr_lower("İ")) == 1


# ── AYNI kisi sayilmali ──────────────────────────────────────────────────
AYNI = [
    # diakritik dusurme (Cekce, Hollandaca, Fransizca)
    ("Vladimir Dlouhy", "Vladimír Dlouhý"),
    ("Zdena Hadrbolcova", "Zdena Hadrbolcová"),
    ("Victor Low", "Victor Löw"),
    ("Rene van Asten", "René van Asten"),
    ("Philippe de Cherisey", "Philippe de Chérisey"),
    # TRT XML yazim hatalari (gercek, olculmus)
    ("ERROL FLYN", "Errol Flynn"),
    ("MARILYN MONREO", "Marilyn Monroe"),
    ("PIERRE BRASSUER", "Pierre Brasseur"),
    ("ASYLKHAN TOLYPOV", "Asylkhan Tolepov"),
    # bosluk/birlesme varyanti
    ("ALEC MC COWEN", "Alec McCowen"),
    ("Le Febvre", "Lefebvre"),
    # orta ad / inisyal — jenerik biçimi vs veritabani biçimi
    ("Keith Robinson", "Keith D. Robinson"),
    ("Dennis Lewiston", "Dennis C. Lewiston"),
    ("Hans F. Koenekamp", "H. F. Koenekamp"),
    ("Clifford Parrish", "Clifford Parish"),
    # tek-ad sanatci adi
    ("Vangelis", "Vangelis Papathanassiou"),
    # ad-soyad SIRASI ters (CJK, TRT listesinde ters geliyor)
    ("LUNG TI", "Ti Lung"),
    ("HUA YUEH", "Yueh Hua"),
    # transliterasyon (Kirgiz/Rus)
    ("BOLOTBEK SAMSIYEV", "Bolotbek Shamshiyev"),
    # buyuk harf + Turkce
    ("FAHRİYE EVCEN", "Fahriye Evcen"),
    ("MURAT YILDIRIM", "Murat Yıldırım"),
    # noktalama / unvan gurultusu
    ("Mitchum, Robert", "Robert Mitchum"),
    ("Sean  Bean", "Sean Bean"),
]


@pytest.mark.parametrize("a,b", AYNI)
def test_ayni_kisi(a, b):
    assert ayni_kisi(a, b), f"AYNI sayilmaliydi: {a!r} vs {b!r} (norm: {normalize(a)!r} / {normalize(b)!r})"


# ── FARKLI kisi sayilmali (yanlis birlestirme sonucu iyimser gosterir) ───
FARKLI = [
    ("Robert Mitchum", "Robert Mitchell"),
    ("Andy Lau", "Andy Lee"),
    ("Kadir Savun", "Kadir Savaş"),
    ("John Smith", "Jane Smith"),
    ("Sean Bean", "Sean Penn"),
    ("Alfred Molina", "Alfred Hitchcock"),
    ("Maggie Q", "Maggie Cheung"),
    ("David Gwillim", "David Gwilym Jones"),
    # ayni soyad, farkli ad — kardes/akraba tuzagi
    ("Olivia de Havilland", "Joan de Havilland"),
    # kisa isimlerde fuzzy patlamasi olmamali
    ("Ti Lung", "Ti Long"),
]


@pytest.mark.parametrize("a,b", FARKLI)
def test_farkli_kisi(a, b):
    assert not ayni_kisi(a, b), f"FARKLI sayilmaliydi: {a!r} vs {b!r} (norm: {normalize(a)!r} / {normalize(b)!r})"


# ── isim olmayanlar elenmeli ─────────────────────────────────────────────
@pytest.mark.parametrize("metin", [
    "YERLİ SİNEMA", "YABANCI SİNEMA", "[okunamadı]", "[yazı yok]",
    "", "   ", "---", "1994", "...",
])
def test_isim_degil(metin):
    from isim_normalize import isim_gibi_mi
    assert not isim_gibi_mi(metin), f"isim sayilmamaliydi: {metin!r}"


@pytest.mark.parametrize("metin", [
    "Sophie Marceau", "FAHRİYE EVCEN", "Ti Lung", "Vangelis", "H. F. Koenekamp",
])
def test_isim_evet(metin):
    from isim_normalize import isim_gibi_mi
    assert isim_gibi_mi(metin), f"isim sayilmaliydi: {metin!r}"


# ── liste eslestirme ─────────────────────────────────────────────────────
def test_liste_eslestirme_temel():
    from isim_normalize import listeyi_esle
    okunan = ["ERROL FLYN", "OLIVIA DE HAVILLAND", "RAYMOND MASSEY", "[okunamadı]"]
    referans = ["Errol Flynn", "Olivia de Havilland", "Ronald Reagan"]
    s = listeyi_esle(okunan, referans)
    assert {e["okunan"] for e in s["eslesen"]} == {"ERROL FLYN", "OLIVIA DE HAVILLAND"}
    assert s["referansta_yok"] == ["RAYMOND MASSEY"]      # NOTR kova — uydurma DEGIL
    assert s["kacirilan"] == ["Ronald Reagan"]
    assert s["elenen"] == ["[okunamadı]"]


def test_bir_referans_iki_kez_eslesmez():
    """Ayni referans ismi iki farkli okumaya atanirsa precision sisirilir."""
    from isim_normalize import listeyi_esle
    s = listeyi_esle(["Sean Bean", "Sean Bean"], ["Sean Bean"])
    assert len(s["eslesen"]) == 1
    assert len(s["referansta_yok"]) == 1
