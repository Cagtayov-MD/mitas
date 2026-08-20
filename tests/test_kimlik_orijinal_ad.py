# -*- coding: utf-8 -*-
"""test_kimlik_orijinal_ad.py — kimlik-doğrulama (credit_validate) orijinal-ad ikinci anahtar testleri.

BAĞLAM (Çağatay 2026-07-31): credit_validate.py'nin DB-araması (_resolve_source) yalnız
Türkçe başlıkla arıyordu; XML sidecar'daki ORİJİNAL AD (a.original) hiç ULAŞMIYORDU. Yabancı
filmde DB'de yalnız İngilizce ad varsa Türkçe arama SIFIR aday buluyor, yönetmen/kimlik
doğrulaması hep "kaynak veri yok" kalıyordu (gerçek film DB'de VAR olsa bile).

FIX: _resolve_source artık opsiyonel `original` alır. Türkçe başlık arama SIFIR aday
döndürürse (ve kill-switch açıksa, orijinal ad Türkçe başlıktan farklıysa) ikinci
deneme orijinal adla yapılır. Kimlik yine cast/yönetmen-örtüşme testinden GEÇMEK ZORUNDA
(_score) — orijinal ad yalnız aday HAVUZUNU genişletir, otomatik kimlik kanıtı DEĞİLDİR.

Bu test DuckDB'ye GERÇEK sorgu ATMAZ — FakeKB ile _resolve_source/validate() saf-mantık
olarak test edilir (hermetik, deterministik).

Çalıştır:  /opt/mitas/venvs/ocr/bin/python -m pytest tests/test_kimlik_orijinal_ad.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import pytest

import credit_validate as cv


class FakeKB:
    """credit_validate._KB arayüzünü taklit eder (duckdb yok, çağrılar KAYDEDİLİR).

    imdb_map / wiki_map: {fold(anahtar): sonuç} — anahtar title VEYA original olabilir.
    Sözlükte olmayan bir anahtar sorgulanırsa boş sonuç döner (gerçek DB'nin "aday yok"
    davranışını taklit eder)."""

    def __init__(self, imdb_map=None, wiki_map=None, directors=None, cast=None):
        self.imdb_map = imdb_map or {}
        self.wiki_map = wiki_map or {}
        self.directors = directors or {}
        self.cast = cast or {}
        self.imdb_calls = []
        self.wiki_calls = []
        self.con = None   # _recover_raw kb.con kontrolü için (bu testlerde ocr_raw kullanılmıyor)

    def imdb_candidates(self, title, limit=8):
        self.imdb_calls.append(title)
        return list(self.imdb_map.get(cv._fold(title), []))

    def imdb_directors(self, tconst):
        return list(self.directors.get(tconst, []))

    def imdb_cast(self, tconst):
        return list(self.cast.get(tconst, []))

    def imdb_category(self, tconst, name):
        return []

    def wiki_candidates(self, title, limit=8):
        self.wiki_calls.append(title)
        return list(self.wiki_map.get(cv._fold(title), []))

    def _names_wiki(self, qids_str):
        return []

    def person_country(self, name):
        return None

    def is_turkish_person(self, name):
        return False


TR_TITLE = "SİYAH İNCİ"
ORIGINAL_TITLE = "Black Beauty"


def _kb_with_original_only(strong=True):
    """Türkçe başlık DB'de YOK (imdb_map'te anahtarı yok → []); orijinal ad İLE aday VAR."""
    ov_cast = ["Alice A", "Bob B"] if strong else ["Alice A"]
    return FakeKB(
        imdb_map={cv._fold(ORIGINAL_TITLE): ["tt_black_beauty"]},
        directors={"tt_black_beauty": ["John Smith"]},
        cast={"tt_black_beauty": ["Alice A", "Bob B", "Carol C"]},
    ), ov_cast


# ───────────────────────── (a) orijinal ad ile aday bulunuyor ─────────────────────────
def test_resolve_source_turkce_bos_orijinal_bulur(monkeypatch):
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    kb, _ = _kb_with_original_only()
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["John Smith"], ["Alice A", "Bob B"],
                              original=ORIGINAL_TITLE)
    assert res["strength"] == "GUCLU"
    assert res["key"] == "tt_black_beauty"
    assert res["arama_anahtari"] == "orijinal_ad"
    # Türkçe başlık ÖNCE denendi (sıra korunuyor), sonra orijinal ad denendi
    assert kb.imdb_calls == [TR_TITLE, ORIGINAL_TITLE]


def test_validate_uctan_uca_orijinal_ad_ile_dogrulanir(monkeypatch):
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    kb, _ = _kb_with_original_only()
    extracted = {"yonetmen": ["John Smith"], "cast": ["Alice A", "Bob B"]}
    out = cv.validate(extracted, title=TR_TITLE, original=ORIGINAL_TITLE, kb=kb)
    assert out["yonetmen"]["status"] == "DOGRULANDI"
    assert out["kaynaklar"]["imdb"]["arama_anahtari"] == "orijinal_ad"
    assert out["kaynaklar"]["imdb"]["key"] == "tt_black_beauty"


def test_kimlik_yine_cast_ortusme_sartina_bagli(monkeypatch):
    """Orijinal ad aday BULUR ama cast/yönetmen HİÇ örtüşmüyorsa (_score eler) kimlik
    KURULMAZ — orijinal ad tek başına kanıt değil, yalnız arama anahtarı."""
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    kb, _ = _kb_with_original_only()
    # OCR yönetmeni de cast'i de DB'dekiyle HİÇ örtüşmüyor → _score best'i hiç kabul etmez
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["Zeki Yanlış"], ["Kimse Yok"],
                              original=ORIGINAL_TITLE)
    assert res["strength"] is None
    assert res["key"] is None
    # aday havuzu orijinal-adla genişledi (arandı) ama kimlik KURULMADI
    assert kb.imdb_calls == [TR_TITLE, ORIGINAL_TITLE]


# ───────────────────────── (b) kill-switch=0 → orijinal ad HİÇ denenmiyor ─────────────────────────
def test_kill_switch_kapaliyken_orijinal_denenmez(monkeypatch):
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "0")
    kb, _ = _kb_with_original_only()
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["John Smith"], ["Alice A", "Bob B"],
                              original=ORIGINAL_TITLE)
    assert res["strength"] is None
    assert res["key"] is None
    assert res["arama_anahtari"] is None
    # SADECE Türkçe başlıkla arandı — orijinal ad HİÇ sorgulanmadı (eski davranış birebir)
    assert kb.imdb_calls == [TR_TITLE]


def test_kill_switch_kapali_validate_uctan_uca(monkeypatch):
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "0")
    kb, _ = _kb_with_original_only()
    extracted = {"yonetmen": ["John Smith"], "cast": ["Alice A", "Bob B"]}
    out = cv.validate(extracted, title=TR_TITLE, original=ORIGINAL_TITLE, kb=kb)
    assert out["yonetmen"]["status"] != "DOGRULANDI"
    assert kb.imdb_calls == [TR_TITLE]
    assert kb.wiki_calls == [TR_TITLE]


# ───────────────────────── (c) orijinal ad boşken davranış AYNI ─────────────────────────
@pytest.mark.parametrize("bos_orijinal", [None, "", "   "])
def test_orijinal_ad_bos_davranis_degismiyor(monkeypatch, bos_orijinal):
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")   # kill-switch açık olsa bile
    kb, _ = _kb_with_original_only()
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["John Smith"], ["Alice A", "Bob B"],
                              original=bos_orijinal)
    assert res["strength"] is None
    assert res["arama_anahtari"] is None
    # original boş/whitespace → ikinci sorgu YOK (eski tek-parametre çağrısıyla birebir)
    assert kb.imdb_calls == [TR_TITLE]


def test_orijinal_parametresi_verilmezse_eski_imza_calisir(monkeypatch):
    """Geriye-uyumluluk: original hiç geçilmeden (eski çağrı imzası) _resolve_source
    ÇÖKMEDEN çalışmalı — yalnız Türkçe başlıkla arar (default original=None)."""
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    kb, _ = _kb_with_original_only()
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["John Smith"], ["Alice A", "Bob B"])
    assert res["strength"] is None
    assert kb.imdb_calls == [TR_TITLE]


def test_orijinal_turkce_ile_ayniysa_ikinci_sorgu_atlanir(monkeypatch):
    """original Türkçe başlıkla (fold-eşit) AYNIYSA ikinci sorgu anlamsız — atlanır."""
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    kb = FakeKB(imdb_map={})   # her iki anahtar da boş döner
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["John Smith"], ["Alice A"], original=TR_TITLE)
    assert res["strength"] is None
    assert kb.imdb_calls == [TR_TITLE]   # ikinci (aynı) sorgu atlandı


# ───────────────────────── wiki tarafı da aynı desende çalışıyor ─────────────────────────
def test_wiki_resolve_source_orijinal_ad_ile_bulur(monkeypatch):
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    kb = FakeKB(wiki_map={cv._fold(ORIGINAL_TITLE): [("Q1", "", "", "Q30", None)]})
    res = cv._resolve_source("wiki", kb, TR_TITLE, [], [], original=ORIGINAL_TITLE)
    # _names_wiki FakeKB'de [] döner → director/cast boş → _score dirm/ov=0 → best kabul edilmez
    assert res["strength"] is None
    assert kb.wiki_calls == [TR_TITLE, ORIGINAL_TITLE]


# ═══════════════════ konsey-incelemesi düzeltmeleri (2026-07-31, commit 799f98cf sonrası) ═══════════════════
# DÜZELTME 1: fallback artık yalnız "TR aday listesi BOŞ" değil, "best None VEYA ZAYIF" iken
# de tetikleniyor (TR adaylar dolu ama hiçbiri skorlamıyor / yalnız zayıf-kilit veriyor olabilir).

def test_a_tr_dolu_skorlamiyor_orijinal_devreye_girer_ve_kilitler(monkeypatch):
    """(a) TR adaylar DOLU ama hiçbiri skorlamıyor (dirm=False, ov=0) → orijinal ad denenir
    ve GÜÇLÜ kilitler. arama_anahtari her iki denemeyi de yansıtır (ikisi de dolu döndü)."""
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    kb = FakeKB(
        imdb_map={
            cv._fold(TR_TITLE): ["tt_mismatch"],
            cv._fold(ORIGINAL_TITLE): ["tt_black_beauty"],
        },
        directors={"tt_mismatch": ["Nobody Match"], "tt_black_beauty": ["John Smith"]},
        cast={"tt_mismatch": ["Nobody X"], "tt_black_beauty": ["Alice A", "Bob B", "Carol C"]},
    )
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["John Smith"], ["Alice A", "Bob B"],
                              original=ORIGINAL_TITLE)
    assert res["strength"] == "GUCLU"
    assert res["key"] == "tt_black_beauty"
    assert res["arama_anahtari"] == "tr_baslik+orijinal_ad"
    assert kb.imdb_calls == [TR_TITLE, ORIGINAL_TITLE]


def test_b_tr_zayif_kilit_orijinal_guclu_kazanir(monkeypatch):
    """(b) TR araması ZAYIF kilit verir (yalnız yönetmen-totoloji, cast örtüşmüyor);
    orijinal ad GÜÇLÜ (yön+cast) bulur → _score en iyisini seçer, GÜÇLÜ kazanır."""
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    kb = FakeKB(
        imdb_map={
            cv._fold(TR_TITLE): ["tt_weak"],
            cv._fold(ORIGINAL_TITLE): ["tt_strong"],
        },
        directors={"tt_weak": ["John Smith"], "tt_strong": ["John Smith"]},
        cast={"tt_weak": [], "tt_strong": ["Alice A", "Bob B"]},
    )
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["John Smith"], ["Alice A", "Bob B"],
                              original=ORIGINAL_TITLE)
    assert res["strength"] == "GUCLU"
    assert res["key"] == "tt_strong"
    assert res["arama_anahtari"] == "tr_baslik+orijinal_ad"
    assert kb.imdb_calls == [TR_TITLE, ORIGINAL_TITLE]


def test_c_tr_guclu_kilit_varken_orijinal_hic_denenmez(monkeypatch):
    """(c) mutlu yol DEĞİŞMEDİ: TR araması zaten GÜÇLÜ kilitlerse orijinal ad hiç sorgulanmaz
    (gereksiz DB çağrısı yok)."""
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    kb = FakeKB(
        imdb_map={cv._fold(TR_TITLE): ["tt_strong_tr"]},
        directors={"tt_strong_tr": ["John Smith"]},
        cast={"tt_strong_tr": ["Alice A", "Bob B"]},
    )
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["John Smith"], ["Alice A", "Bob B"],
                              original=ORIGINAL_TITLE)
    assert res["strength"] == "GUCLU"
    assert res["key"] == "tt_strong_tr"
    assert res["arama_anahtari"] == "tr_baslik"
    assert kb.imdb_calls == [TR_TITLE]   # orijinal ad HİÇ sorgulanmadı


# DÜZELTME 3: MITAS_KIMLIK_ORIJINAL="" (boş string) KAPALI sayılmalı (eski hâlde "not in (...)"
# testinden geçip yanlışlıkla AÇIK sayılıyordu).

def test_d_env_bos_string_kapali_sayilir(monkeypatch):
    """(d) env="" → kill-switch KAPALI (orijinal ad hiç denenmez, eski Türkçe-tek-anahtar
    davranışı)."""
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "")
    kb, _ = _kb_with_original_only()
    res = cv._resolve_source("imdb", kb, TR_TITLE, ["John Smith"], ["Alice A", "Bob B"],
                              original=ORIGINAL_TITLE)
    assert res["strength"] is None
    assert res["key"] is None
    assert res["arama_anahtari"] is None
    assert kb.imdb_calls == [TR_TITLE]


def test_orijinal_ad_acik_dogrudan_bos_ve_whitespace_kapali(monkeypatch):
    """_orijinal_ad_acik() doğrudan: boş / yalnız-boşluk → kapalı; "1" → açık; bilinen
    kapalı-değerler ("0","false","off","no") → kapalı (eski davranış korunur)."""
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "")
    assert cv._orijinal_ad_acik() is False
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "   ")
    assert cv._orijinal_ad_acik() is False
    monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", "1")
    assert cv._orijinal_ad_acik() is True
    for kapali_deger in ("0", "false", "off", "no", "FALSE", "OFF"):
        monkeypatch.setenv("MITAS_KIMLIK_ORIJINAL", kapali_deger)
        assert cv._orijinal_ad_acik() is False
