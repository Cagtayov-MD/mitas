"""harness/kunye_kiyas/credit_content.cekirdek_rol_bul — betik-farkında rol tanıma
(§1/§2.2 kök-sebep, KOBE onset hattı, adım 2/5).

Arıza (spec §2.2): `cekirdek_rol_bul` FAZ-1 dil TAHMİNİNE (`get_aktif_dil()`) kilitliydi.
DOVLATOV Kiril metin taşıyordu ama tahmin 'en' olduğu için Kiril dalı hiç çalışmadı;
ARŞIN MAL ALAN Kiril metin taşıyordu ama tahmin 'ar' olduğu için Arapça dalı Kiril
metinde koştu (hiç eşleşmedi). Düzeltme: rol eşleşmesi artık satırın kendi
unicodedata betiğine (FAZ-2, %100 kesin) bakar — get_aktif_dil() bu fonksiyonda
HİÇ kullanılmaz.

PaddleOCR/Ollama İSTEMEZ — yalnız cc.cekirdek_rol_bul/genis'e önceden-OCR'lanmış
satır listeleri verilir.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness" / "kunye_kiyas"))

import credit_content as cc  # noqa: E402


@pytest.fixture(autouse=True)
def _dil_sifirla():
    """Her testten önce/sonra FAZ-1 bağlamını varsayılana döndür (testler arası sızıntı yok)."""
    onceki = cc.get_aktif_dil()
    cc.set_aktif_dil("en")
    yield
    cc.set_aktif_dil(onceki)


# ── DOVLATOV vakası (§2.2): tahmin='en', metin Kiril ─────────────────────
def test_dovlatov_kiril_metin_yanlis_tahminde_bile_bulunur():
    cc.set_aktif_dil("en")   # yönlendiricinin YANLIŞ tahmini (gerçek dosya kanıtı)
    kareler = [["режиссер Станислав РУЖЕВИЧ"], ["Ассистент режиссера"]]
    roller = cc.cekirdek_rol_bul(kareler)
    assert roller, "Kiril metin, tahmin='en' iken de bulunmalı (FAZ-2 betik-bazlı)"


# ── ARŞIN MAL ALAN vakası (§2.2): tahmin='ar', metin Kiril ───────────────
def test_arsin_mal_alan_kiril_metin_yanlis_arapca_tahmininde_bile_bulunur():
    cc.set_aktif_dil("ar")   # yönlendiricinin YANLIŞ tahmini (gerçek dosya kanıtı)
    kareler = [["режиссер Станислав РУЖЕВИЧ"]]
    roller = cc.cekirdek_rol_bul(kareler)
    assert roller, "Kiril metin, tahmin='ar' iken de bulunmalı (Arapça dalı Kiril'de koşmamalı)"


# ── get_aktif_dil() ARTIK kullanılmıyor (Faz-2 bağımsızlığı) ─────────────
def test_cekirdek_rol_bul_get_aktif_dil_e_bakmaz(monkeypatch):
    """cekirdek_rol_bul içinde get_aktif_dil() çağrılmamalı — çağrılırsa patlat,
    yine de doğru sonucu vermeli (fonksiyon onu hiç okumuyor demektir)."""
    def _patlat():
        raise AssertionError("get_aktif_dil() KOBE onset hattında ÇAĞRILMAMALI (FAZ-2)")
    monkeypatch.setattr(cc, "get_aktif_dil", _patlat)
    kareler = [["режиссер Станислав РУЖЕВИЧ"]]
    roller = cc.cekirdek_rol_bul(kareler)
    assert roller


# ── Önceden hiç desteklenmeyen betikler (§1 tablosu) ──────────────────────
def test_ibrani_yonetmen_bulunur():
    kareler = [["ע.במאי 1"]]
    assert cc.cekirdek_rol_bul(kareler)


def test_korece_yonetmen_bulunur():
    kareler = [["감독"], ["촬영감독"]]  # MUCİZE gerçek satırları
    assert cc.cekirdek_rol_bul(kareler)


def test_farsca_yonetmen_bulunur():
    kareler = [["نویسنده و کارگردان :"]]  # KOŞUCU gerçek satırı
    assert cc.cekirdek_rol_bul(kareler)


def test_yunanca_yonetmen_bulunur():
    kareler = [["ΣΚΗΝΟΘΕΤΗΣ Θεόδωρος Αγγελόπουλος"]]
    assert cc.cekirdek_rol_bul(kareler)


def test_cjk_yonetmen_bulunur():
    kareler = [["导演张艺谋"]]
    assert cc.cekirdek_rol_bul(kareler)


# ── §6.2 kanonik-rol disiplini: bir betikte YÖNETMEN'in farklı yüzey-formları
# rol çeşitliliğine EN FAZLA +1 katkı yapar (üretim disiplini _PRODUC_GENIS ile
# aynı ilke, şimdi Latin-dışı betiklere de uygulanıyor) ─────────────────────
def test_hangul_iki_farkli_yonetmen_kelimesi_tek_role_katkida_bulunur():
    """'감독' ve '연출' ikisi de HANGUL.YONETMEN'de (aynı rol, farklı kelime).
    Başka HİÇBİR gerçek rol yokken bunlar TEK BAŞINA len>=2 üretmemeli
    (aksi halde kredisiz bir Korece filmde seyrek-yol yanlış açılır — kredi_yok
    kırmızı-çizgisi, §6.2)."""
    kareler = [["감독"], ["연출"], ["감독 연출"]]
    roller = cc.cekirdek_rol_bul(kareler)
    assert len(roller) <= 1, f"tek rol beklenirdi, {roller} bulundu"


def test_kiril_yeni_tablo_esanlamlisi_eski_regexle_ayni_kanonik_role_dusuyor():
    """TABLO KIRIL.YONETMEN'e eklenen 'ПОСТАНОВЩИК' (eski _ROL_KIRIL'de YOK) ile
    'режиссёр' AYNI satırda geçse bile rol çeşitliliğine yalnız +1 katkı yapmalı."""
    kareler = [["Режиссёр-постановщик Иван Петров"]]
    roller = cc.cekirdek_rol_bul(kareler)
    assert len(roller) == 1, f"tek kanonik rol beklenirdi, {roller} bulundu"


# ── Çok-betikli çeşitlilik: farklı KATEGORİ roller hâlâ ayrı sayılmalı ────
def test_farkli_betiklerde_farkli_roller_ayri_sayilir():
    kareler = [["감독 박찬욱"], ["Music by John Williams"]]
    roller = cc.cekirdek_rol_bul(kareler)
    assert len(roller) >= 2, f"iki farklı rol (yönetmen+müzik) beklenirdi: {roller}"


# ── §3.4 KOBE onset HARIC taşımaz — yardımcı yönetmen de çapadır ─────────
def test_yardimci_yonetmen_de_kobe_onsetinde_role_sayilir():
    """'촬영감독' (görüntü yönetmeni, isim-çıkarma hattında YÖNETMEN DEĞİL) KOBE
    onset çapası için geçerli bir rol-işaretidir (haric_uygula=False, §3.4)."""
    kareler = [["촬영감독"]]
    assert cc.cekirdek_rol_bul(kareler), "haric_uygula=False olmalı: yardımcı da çapa"


# ── Latin/Macarca/İskandinav davranışı DEĞİŞMEDİ (§4.2: birebir yol) ─────
def test_latin_davranisi_bozulmadi():
    kareler = [["Directed by John Ford"], ["Regia di Federico Fellini"]]
    assert cc.cekirdek_rol_bul(kareler)


def test_macarca_onek_davranisi_bozulmadi():
    kareler = [["operatőr Sándor Kovács"]]
    assert cc.cekirdek_rol_bul(kareler)


def test_kulubedeki_iskandinav_regresyonu_bozulmadi():
    """test_rol_iskandinav.py ile aynı KULUBEDEKI vakası — burada da doğrulanır."""
    kareler = [
        ["Filmfoto, ljud", "Nina Hedenius"],
        ["Redigering", "Nina Hedenius", "Ulf Neidemar"],
        ["En film av", "NINA HEDENIUS"],
    ]
    roller = cc.cekirdek_rol_bul(kareler)
    assert len(roller) >= 2


# ── cekirdek_rol_bul_genis miras yoluyla düzelir (kendi lang-kapısı hiç yoktu) ──
def test_genis_de_betik_farkinda():
    cc.set_aktif_dil("en")
    kareler = [["режиссер Станислав РУЖЕВИЧ"]]
    assert cc.cekirdek_rol_bul_genis(kareler)


def test_genis_produc_disiplini_bozulmadi():
    """DÖNÜŞÜ_OLMAYAN_NEHİR reg: yalnız produc-ailesi (başka gerçek rol yok) tek
    kanonik role indirgenir — bu davranış rol_tablosu'ndan ETKİLENMEMELİ."""
    kareler = [["A CINEMASCOPE PRODUCTION"], ["Produced and Released by"]]
    roller = cc.cekirdek_rol_bul_genis(kareler)
    assert len(roller) < 2, f"yalnız produc-ailesi tek role inmeli: {roller}"
