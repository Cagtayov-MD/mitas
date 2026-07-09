# -*- coding: utf-8 -*-
"""test_poster_fetch_cast_gate.py — ID-güvenilir zincirin (TMDB/OMDb) kör title-search
fallback'ine KADRO-ZORUNLU KAPI testi.

KANIT (2026-07-09, REKABET 1983-0234): imdb_id doğru çözüldü (tt2033995, "Geel Trui vir 'n
Wenner") ama TMDB'de o filmin posteri YOK (poster_path=None, canlı doğrulandı) →
_fetch_tmdb_poster() kör bir `search/movie?query=REKABET`'e düşüyordu; TMDB'nin kendi arama
indeksi "Rekabet"i Challengers'ın (2024, alakasız tenis filmi) bir AKA'sıyla çakıştırıyor
(canlı doğrulandı) → hiçbir başlık/kadro kontrolü olmadan Challengers'ın posteri indirilip
teslim edilen PDF'e giriyordu (E:\\MITAS\\_102_afis_cache\\1983-0234-1-0000-00-1.jpg'de kanıt
olarak duruyor). Bu test, o kör dala mevcut _search()'ün KADRO-ZORUNLU KAPI (_cand_has_name)
desenini mirror eden bir cast-crosscheck kapısı ekler: adayın KENDİ cast'i (TMDB credits /
OMDb Actors) bilinen OCR-cast ile kesişmiyorsa REDDET (None); doğrulanmış tmdb_id/imdb_id
DOĞRUDAN-lookup dalları (zaten kimlik-doğrulanmış) bu kapıya tabi DEĞİL.

Konvansiyon test_c8_ver_gate.py ile AYNI: dinamik import + pf._get monkeypatch (ağ çağrısı yok).
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import importlib.util

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

_OCR_CAST = ["Ray Storm", "Deon Van Zyl", "Claudia Turgas", "Bobbette Fouche"]
_CORRECT_TMDB_ID = 242480   # Geel Trui vir 'n Wenner (gerçek REKABET; TMDB'de posterless)
_WRONG_TMDB_ID = 937287     # Challengers (TMDB AKA-çakışması "Rekabet")


def _skip_if_no_pf():
    if pf is None:
        import pytest
        pytest.skip("poster_fetch yüklenemedi (pdf-mitas yolu yok)")


# ──────────── _fetch_tmdb_poster: title-search fallback kadro kapısı ────────────

def test_tmdb_title_fallback_rejects_uncorroborated_candidate():
    """imdb_id doğru + posterless → title-search'e düşer; adayın (Challengers) KENDİ cast'i
    OCR-cast ile kesişmiyor → None (REKABET/Challengers bug'ının doğrudan reprosu)."""
    _skip_if_no_pf()
    os.environ["MITAS_TMDB"] = "fakekey"
    _orig_get = pf._get

    def _fake_get(url, binary=False):
        if "themoviedb.org/3/find/" in url:
            return json.dumps({"movie_results": [
                {"id": _CORRECT_TMDB_ID, "poster_path": None, "title": "Geel Trui vir 'n Wenner"}],
                "tv_results": []})
        if "themoviedb.org/3/search/movie" in url:
            return json.dumps({"results": [
                {"id": _WRONG_TMDB_ID, "poster_path": "/wrong.jpg", "title": "Challengers",
                 "release_date": "2024-04-18"}]})
        if "themoviedb.org/3/search/tv" in url:
            return json.dumps({"results": []})
        if f"themoviedb.org/3/movie/{_WRONG_TMDB_ID}/credits" in url:
            return json.dumps({"cast": [{"name": "Zendaya"}, {"name": "Josh O'Connor"}],
                               "crew": [{"name": "Luca Guadagnino", "job": "Director"}]})
        if "image.tmdb.org" in url:
            return b"WRONGPOSTERDATA" * 400
        return json.dumps({"results": []})

    pf._get = _fake_get
    try:
        result = pf._fetch_tmdb_poster(imdb_id="tt2033995", title="REKABET",
                                        names_norm=pf._names_norm(_OCR_CAST))
        assert result is None, "kadro kesişmiyor → None beklenir (Challengers kabul edilmemeli)"
    finally:
        pf._get = _orig_get
        os.environ.pop("MITAS_TMDB", None)


def test_tmdb_title_fallback_accepts_corroborated_candidate():
    """Aynı senaryo ama adayın (gerçek film) cast'i OCR-cast ile GERÇEKTEN kesişiyor → kabul edilmeli
    (kapı yanlış-pozitif ELEMİYOR — yalnız kesişmeyeni eler)."""
    _skip_if_no_pf()
    os.environ["MITAS_TMDB"] = "fakekey"
    _orig_get = pf._get
    _poster_data = b"RIGHTPOSTERDATA" * 400

    def _fake_get(url, binary=False):
        if "themoviedb.org/3/find/" in url:
            return json.dumps({"movie_results": [
                {"id": _CORRECT_TMDB_ID, "poster_path": None, "title": "Geel Trui vir 'n Wenner"}],
                "tv_results": []})
        if "themoviedb.org/3/search/movie" in url:
            return json.dumps({"results": [
                {"id": _CORRECT_TMDB_ID, "poster_path": "/right.jpg",
                 "title": "Geel Trui vir 'n Wenner", "release_date": "1983-12-01"}]})
        if "themoviedb.org/3/search/tv" in url:
            return json.dumps({"results": []})
        if f"themoviedb.org/3/movie/{_CORRECT_TMDB_ID}/credits" in url:
            return json.dumps({"cast": [{"name": "Ray Storm"}, {"name": "Deon van Zyl"}], "crew": []})
        if "image.tmdb.org" in url:
            return _poster_data
        return json.dumps({"results": []})

    pf._get = _fake_get
    try:
        result = pf._fetch_tmdb_poster(imdb_id="tt2033995", title="REKABET",
                                        names_norm=pf._names_norm(_OCR_CAST))
        assert result == _poster_data, "kadro kesişiyor → gerçek afiş dönmeli"
    finally:
        pf._get = _orig_get
        os.environ.pop("MITAS_TMDB", None)


def test_tmdb_title_fallback_rejects_when_no_cast_known():
    """Kadro HİÇ bilinmiyorsa (names_norm boş) → title-search fallback körlemesine kabul ETMEMELİ
    (_search()'ün KADRO-ZORUNLU KAPI ilkesiyle aynı: doğrulayacak isim yoksa afiş YOK)."""
    _skip_if_no_pf()
    os.environ["MITAS_TMDB"] = "fakekey"
    _orig_get = pf._get

    def _fake_get(url, binary=False):
        if "themoviedb.org/3/find/" in url:
            return json.dumps({"movie_results": [
                {"id": _CORRECT_TMDB_ID, "poster_path": None, "title": "Geel Trui vir 'n Wenner"}],
                "tv_results": []})
        if "themoviedb.org/3/search/movie" in url:
            return json.dumps({"results": [
                {"id": _WRONG_TMDB_ID, "poster_path": "/wrong.jpg", "title": "Challengers",
                 "release_date": "2024-04-18"}]})
        if "themoviedb.org/3/search/tv" in url:
            return json.dumps({"results": []})
        if "image.tmdb.org" in url:
            return b"WRONGPOSTERDATA" * 400
        return json.dumps({"results": []})

    pf._get = _fake_get
    try:
        result = pf._fetch_tmdb_poster(imdb_id="tt2033995", title="REKABET", names_norm=None)
        assert result is None, "kadro bilinmiyorsa title-search fallback hiç kabul etmemeli"
    finally:
        pf._get = _orig_get
        os.environ.pop("MITAS_TMDB", None)


# ──────────── _fetch_omdb_poster: title (t=) fallback kadro kapısı ────────────

def test_omdb_title_search_rejects_uncorroborated_actors():
    """OMDb t= (title) araması: dönen 'Actors' alanı OCR-cast ile kesişmiyorsa REDDEDİLMELİ."""
    _skip_if_no_pf()
    os.environ["MITAS_OMDB"] = "fakekey"
    _orig_get = pf._get

    def _fake_get(url, binary=False):
        if "omdbapi.com" in url and "t=" in url:
            return json.dumps({"Poster": "http://example.com/wrong.jpg",
                               "Actors": "Zendaya, Josh O'Connor", "Director": "Luca Guadagnino"})
        if "example.com" in url:
            return b"WRONGDATA" * 700
        return json.dumps({})

    pf._get = _fake_get
    try:
        result = pf._fetch_omdb_poster(title="REKABET", names_norm=pf._names_norm(_OCR_CAST))
        assert result is None, "Actors kesişmiyor → None beklenir"
    finally:
        pf._get = _orig_get
        os.environ.pop("MITAS_OMDB", None)


def test_omdb_title_search_accepts_corroborated_actors():
    """OMDb t= araması: 'Actors' alanı OCR-cast ile GERÇEKTEN kesişiyorsa kabul edilmeli."""
    _skip_if_no_pf()
    os.environ["MITAS_OMDB"] = "fakekey"
    _orig_get = pf._get
    _poster_data = b"RIGHTDATA" * 700

    def _fake_get(url, binary=False):
        if "omdbapi.com" in url and "t=" in url:
            return json.dumps({"Poster": "http://example.com/right.jpg",
                               "Actors": "Ray Storm, Deon van Zyl", "Director": "Franz Marx"})
        if "example.com" in url:
            return _poster_data
        return json.dumps({})

    pf._get = _fake_get
    try:
        result = pf._fetch_omdb_poster(title="REKABET", names_norm=pf._names_norm(_OCR_CAST))
        assert result == _poster_data, "Actors kesişiyor → gerçek afiş dönmeli"
    finally:
        pf._get = _orig_get
        os.environ.pop("MITAS_OMDB", None)


def test_omdb_imdb_id_direct_lookup_unaffected_by_gate():
    """i= (imdb_id) DOĞRUDAN lookup zaten kimlik-doğrulanmış → KADRO-ZORUNLU KAPI'ye tabi DEĞİL
    (names_norm verilmese bile poster kabul edilir)."""
    _skip_if_no_pf()
    os.environ["MITAS_OMDB"] = "fakekey"
    _orig_get = pf._get
    _poster_data = b"CORRECTDATA" * 600

    def _fake_get(url, binary=False):
        if "omdbapi.com" in url and "i=" in url:
            return json.dumps({"Poster": "http://example.com/right.jpg", "Actors": "Nobody Known"})
        if "example.com" in url:
            return _poster_data
        return json.dumps({})

    pf._get = _fake_get
    try:
        result = pf._fetch_omdb_poster(imdb_id="tt2033995")   # names_norm verilmedi
        assert result == _poster_data, "imdb_id doğrudan lookup kapıdan etkilenmemeli"
    finally:
        pf._get = _orig_get
        os.environ.pop("MITAS_OMDB", None)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
