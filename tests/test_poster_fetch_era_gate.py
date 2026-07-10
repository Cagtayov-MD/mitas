# -*- coding: utf-8 -*-
"""test_poster_fetch_era_gate.py — _search() ERA-SANITY (kronoloji) kapısı testi.

KANIT (2026-07-09, LAUREL HARDY 1942-0020-1-0000-00-1): TRT katalog başlığı "LAUREL HARDY"
(Fox'un 1942 "A Haunting We Will Go" filmi — Stan Laurel/Oliver Hardy filmde İKİNCİL billing'de,
gerçek üst-kadro Sheila Ryan/John Shelton/vb.) → IMDb suggestion "LAUREL HARDY" sorgusu gerçek
filmi DEĞİL, "Laurel & Hardy: Their Lives and Magic" (tt1698531, 2011 TV-belgeseli, canlı-
doğrulanan gerçek IMDb verisi) döner. Adayın 's' (yıldızlar) alanı tam olarak "Stan Laurel,
Oliver Hardy" — ikisi de GERÇEKTEN bu filmin (ikincil-billing) kadrosunda oldukları için, OCR
kadrosu bu iki ismi doğru biçimde içerdiğinde mevcut KADRO-ZORUNLU KAPI (_cand_has_name)
yanlışlıkla GEÇER: sorgu-metni ZATEN ünlü bir kişi/ikili adı olduğunda, başlık-eşleşmesi VE
kadro-eşleşmesi AYNI kişiden türüyor (bağımsız kanıt değil) → belgeselin "konusu" (subject-of)
ile filmin "oyuncusu" (cast-of) ayırt edilemiyor.

FIX: credit_identity.py'de ZATEN sevkiyatta olan "ERA-SANITY" ilkesiyle AYNI (orada docstring:
"Yıl AYRAÇ değil, TAVAN" — TRT bir filmi kataloglamışsa film o yıldan >2 yıl YENİ olamaz).
_search() artık aynı tavanı adayların (tt listesi) IMDb'nin kendi 'y' alanına uygular.
Kill-switch: MITAS_POSTER_ERA_GATE=0.

Konvansiyon test_c8_ver_gate.py / test_poster_fetch_cast_gate.py ile AYNI: dinamik import +
pf._get monkeypatch (ağ çağrısı yok).
"""
import os
import sys
import json
import importlib.util

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

_PDFMITAS = os.environ.get("MITAS_PDFMITAS_DIR", r"E:\MITAS\OCR-worktree\pdf-mitas")


def _load_poster_fetch():
    spec = importlib.util.spec_from_file_location(
        "poster_fetch", os.path.join(_PDFMITAS, "poster_fetch.py"))
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


pf = _load_poster_fetch()

# 2026-07-09 canlı IMDb suggestion cevabından süzülmüş gerçek veri (uydurulmadı) — tam ham
# cevap 8 aday içeriyordu, burada yalnız _search()'ün loose-prefix aşamasını geçenler tutuldu.
_LAUREL_HARDY_SUGGESTION = {"d": [
    {"id": "nm0491048", "l": "Stan Laurel", "s": "Actor, Block-Heads (1938)",
     "i": {"imageUrl": "https://example/x.jpg"}},
    {"id": "nm0001316", "l": "Oliver Hardy", "s": "Actor, Block-Heads (1938)",
     "i": {"imageUrl": "https://example/x.jpg"}},
    {"id": "tt0021054", "l": "The Laurel-Hardy Murder Case", "q": "short", "y": 1930,
     "s": "Stan Laurel, Oliver Hardy", "i": {"imageUrl": "https://example/x.jpg"}},
    {"id": "tt1698531", "l": "Laurel & Hardy: Their Lives and Magic", "q": "TV movie", "y": 2011,
     "s": "Stan Laurel, Oliver Hardy", "i": {"imageUrl": "https://example/x.jpg"}},
]}


def _skip_if_no_pf():
    if pf is None:
        import pytest
        pytest.skip("poster_fetch yüklenemedi (pdf-mitas yolu yok)")


def _stub_suggestion(payload):
    def _fake_get(url, binary=False):
        assert "suggestion" in url
        return json.dumps(payload)
    return _fake_get


# ──────────── _search(): ERA-SANITY (kronoloji) kapısı ────────────

def test_era_gate_rejects_2011_documentary_for_1942_catalog_entry():
    """LAUREL HARDY (TRT yıl=1942) sorgusu, adayın kendi kadrosu (Stan Laurel/Oliver Hardy)
    OCR-kadrosuyla GERÇEKTEN kesişse bile -- aday 69 yıl UZAK (2011) ise reddedilmeli."""
    _skip_if_no_pf()
    _orig_get = pf._get
    pf._get = _stub_suggestion(_LAUREL_HARDY_SUGGESTION)
    try:
        names_norm = pf._names_norm(["Stan Laurel", "Oliver Hardy"])
        vsig = pf._version_sig("LAUREL HARDY")
        result = pf._search("LAUREL HARDY", 1942, names_norm, vsig)
        assert result is None, (
            f"2011 belgeseli 1942 katalog-yılından 69 yıl uzak -- reddedilmeliydi, {result!r} geldi")
    finally:
        pf._get = _orig_get


def test_era_gate_allows_when_no_year_supplied():
    """year=None (TRT yılı bilinmiyor) -> ERA-kapısı ATIL, eski davranış (byte-identical)
    korunur (regresyon-güvenli varsayılan: veri yoksa yeni kapı hiç devreye girmez)."""
    _skip_if_no_pf()
    _orig_get = pf._get
    pf._get = _stub_suggestion(_LAUREL_HARDY_SUGGESTION)
    try:
        names_norm = pf._names_norm(["Stan Laurel", "Oliver Hardy"])
        vsig = pf._version_sig("LAUREL HARDY")
        result = pf._search("LAUREL HARDY", None, names_norm, vsig)
        assert result is not None and result.get("id") == "tt1698531", (
            "year verilmediğinde ERA-kapısı devre dışı kalmalı (regresyon-güvenli varsayılan)")
    finally:
        pf._get = _orig_get


def test_era_gate_accepts_correct_era_candidate():
    """Aynı sorgu ailesi ama aday KATALOG YILINA yakın (1941, tavan 1944 içinde) ->
    ERA-kapısı bunu ELEMEMELİ (yeni-yanlış-pozitif riski yok, exact-match dalı)."""
    _skip_if_no_pf()
    payload = {"d": [
        {"id": "tt0021054", "l": "LAUREL HARDY", "q": "short", "y": 1941,
         "s": "Stan Laurel, Oliver Hardy", "i": {"imageUrl": "https://example/x.jpg"}},
    ]}
    _orig_get = pf._get
    pf._get = _stub_suggestion(payload)
    try:
        names_norm = pf._names_norm(["Stan Laurel", "Oliver Hardy"])
        vsig = pf._version_sig("LAUREL HARDY")
        result = pf._search("LAUREL HARDY", 1942, names_norm, vsig)
        assert result is not None and result.get("id") == "tt0021054", (
            "1941 aday, 1942 katalog-tavanı (+2) İÇİNDE -- kabul edilmeliydi")
    finally:
        pf._get = _orig_get


def test_era_gate_missing_y_field_not_rejected():
    """Adayda 'y' alanı hiç yoksa (IMDb bazen vermez) ERA-kapısı onu REDDETMEMELİ (fail-open;
    tek kanıt kaynağı değil, ek bir emniyet katmanı)."""
    _skip_if_no_pf()
    payload = {"d": [
        {"id": "tt9999999", "l": "LAUREL HARDY", "s": "Stan Laurel, Oliver Hardy",
         "i": {"imageUrl": "https://example/x.jpg"}},   # y YOK
    ]}
    _orig_get = pf._get
    pf._get = _stub_suggestion(payload)
    try:
        names_norm = pf._names_norm(["Stan Laurel", "Oliver Hardy"])
        vsig = pf._version_sig("LAUREL HARDY")
        result = pf._search("LAUREL HARDY", 1942, names_norm, vsig)
        assert result is not None and result.get("id") == "tt9999999", (
            "'y' alanı yok -- ERA-kapısı veri yokluğunda reddetmemeli")
    finally:
        pf._get = _orig_get


def test_era_gate_kill_switch_env_restores_old_behavior():
    """MITAS_POSTER_ERA_GATE=0 -> kapı devre dışı, eski (hatalı ama byte-identical) davranış."""
    _skip_if_no_pf()
    os.environ["MITAS_POSTER_ERA_GATE"] = "0"
    _orig_get = pf._get
    pf._get = _stub_suggestion(_LAUREL_HARDY_SUGGESTION)
    try:
        names_norm = pf._names_norm(["Stan Laurel", "Oliver Hardy"])
        vsig = pf._version_sig("LAUREL HARDY")
        result = pf._search("LAUREL HARDY", 1942, names_norm, vsig)
        assert result is not None and result.get("id") == "tt1698531", (
            "kill-switch kapalıyken (0) eski davranış (2011 belgeseli kabul) korunmalı")
    finally:
        pf._get = _orig_get
        os.environ.pop("MITAS_POSTER_ERA_GATE", None)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
