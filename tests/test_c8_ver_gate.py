# -*- coding: utf-8 -*-
"""test_c8_ver_gate.py — C8 MITAS_POSTER_VER_GATE + _version_ok testi.

Test ettiği: poster_fetch._version_sig + _version_ok + _fetch_tmdb_poster'ın versiyon-kapısı.
  • vsig.active=True + uyumsuz sekel → _version_ok False → poster None (elendi).
  • vsig.active=False → _version_ok daima True → byte-identical davranış.
  • _fetch_tmdb_poster monkeypatch _get: ağ çağrısı yok, JSON stub döner.
  • _version_ok'u gerçek çağır (saf fonksiyon, DB/ağ yok).

NOT: _fetch_tmdb_poster MITAS_TMDB/TMDB_API_KEY env YOK olduğunda doğrudan None döner;
     Dolayısıyla poster_fetch._get'i monkeypatch etsek de key yoksa çalışmaz.
     Bu testte MITAS_TMDB="fakekey" koyup _get'i stub'luyoruz.
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

# poster_fetch pdf-mitas altında; dinamik yükle
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


def _skip_if_no_pf():
    if pf is None:
        import pytest
        pytest.skip("poster_fetch yüklenemedi (pdf-mitas yolu yok)")


# ──────────── _version_sig + _version_ok saf-fonksiyon testleri ─────────────

def test_c8_version_sig_sekel_aktif():
    """'ROCKY II' → seq=2, active=True."""
    _skip_if_no_pf()
    vsig = pf._version_sig("ROCKY II")
    assert vsig["active"] is True
    assert vsig["seq"] == 2


def test_c8_version_sig_sekel_yok_inactive():
    """Sekel imzası olmayan başlık → active=False."""
    _skip_if_no_pf()
    vsig = pf._version_sig("AHLAT AGACI")
    assert vsig["active"] is False


def test_c8_version_ok_uyumlu_baslik():
    """vsig.seq=2 + 'Rocky II' aday → True (tutarlı)."""
    _skip_if_no_pf()
    vsig = pf._version_sig("ROCKY II")
    assert pf._version_ok(vsig, "Rocky II") is True


def test_c8_version_ok_uyumsuz_baslik():
    """vsig.seq=2 + 'Rocky' (I — sekel yok) aday → False (tutarsız)."""
    _skip_if_no_pf()
    vsig = pf._version_sig("ROCKY II")
    assert pf._version_ok(vsig, "Rocky") is False


def test_c8_version_ok_inactive_daima_true():
    """vsig.active=False → _version_ok daima True (byte-identical)."""
    _skip_if_no_pf()
    vsig = pf._version_sig("AHLAT AGACI")   # active=False
    assert pf._version_ok(vsig, "Ahlat Agaci") is True
    assert pf._version_ok(vsig, "Herhangi Baslik") is True
    assert pf._version_ok(vsig, "Rocky II") is True


def test_c8_version_ok_none_sig_daima_true():
    """vsig=None → daima True (fail-safe)."""
    _skip_if_no_pf()
    assert pf._version_ok(None, "Rocky II") is True


# ──────────── _fetch_tmdb_poster versiyon-kapısı (monkeypatch _get) ──────────

def test_c8_fetch_tmdb_uyumsuz_sekel_none():
    """vsig.active=True + uyumsuz sekel adayı → _fetch_tmdb_poster None döner."""
    _skip_if_no_pf()
    os.environ["MITAS_TMDB"] = "fakekey"
    os.environ["MITAS_POSTER_VER_GATE"] = "1"

    _orig_get = pf._get
    # tmdb_id path: meta = {title: "Rocky", poster_path: "/abc.jpg"} → seq=2 ama "Rocky" seq yok → elenir
    call_count = [0]

    def _fake_get(url, binary=False):
        call_count[0] += 1
        if "themoviedb.org/3/movie" in url:
            # tmdb_id direct → meta title "Rocky" (sekel 1, uyumsuz vsig seq=2)
            return json.dumps({"title": "Rocky", "original_title": "Rocky", "poster_path": "/abc.jpg"})
        if "image.tmdb.org" in url:
            return b"FAKEDATA"
        # find/search → boş
        return json.dumps({"movie_results": [], "tv_results": [], "results": []})

    pf._get = _fake_get
    try:
        vsig = pf._version_sig("ROCKY II")   # seq=2, active=True
        result = pf._fetch_tmdb_poster(tmdb_id="12345", title="ROCKY II", vsig=vsig)
        # "Rocky" (I) uyumsuz sekel=2 → elenmeli → None
        assert result is None, f"uyumsuz sekel → None beklendi, {result!r} geldi"
    finally:
        pf._get = _orig_get
        os.environ.pop("MITAS_TMDB", None)
        os.environ.pop("MITAS_POSTER_VER_GATE", None)


def test_c8_fetch_tmdb_vsig_inactive_kabul():
    """vsig.active=False → versiyon kapısı ATIL → poster kabul edilir (byte-identical)."""
    _skip_if_no_pf()
    os.environ["MITAS_TMDB"] = "fakekey"
    os.environ["MITAS_POSTER_VER_GATE"] = "1"

    _orig_get = pf._get
    _poster_data = b"FAKEPOSTER" * 100  # >5000 bayt

    def _fake_get(url, binary=False):
        if "themoviedb.org/3/movie" in url:
            return json.dumps({"title": "Ahlat Agaci", "poster_path": "/abc.jpg"})
        if "image.tmdb.org" in url:
            return _poster_data
        return json.dumps({"movie_results": [], "tv_results": [], "results": []})

    pf._get = _fake_get
    try:
        vsig = pf._version_sig("AHLAT AGACI")   # active=False
        result = pf._fetch_tmdb_poster(tmdb_id="54321", title="AHLAT AGACI", vsig=vsig)
        assert result == _poster_data, "vsig.active=False → poster kabul edilmeli"
    finally:
        pf._get = _orig_get
        os.environ.pop("MITAS_TMDB", None)
        os.environ.pop("MITAS_POSTER_VER_GATE", None)


def test_c8_fetch_tmdb_key_yok_none():
    """TMDB key yok → _fetch_tmdb_poster hemen None (erken çıkış)."""
    _skip_if_no_pf()
    os.environ.pop("MITAS_TMDB", None)
    os.environ.pop("TMDB_API_KEY", None)
    vsig = pf._version_sig("ROCKY II") if pf else {"seq": 2, "subs": [], "active": True}
    result = pf._fetch_tmdb_poster(tmdb_id="12345", title="ROCKY II", vsig=vsig)
    assert result is None, "TMDB key yok → None beklendi"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
