# -*- coding: utf-8 -*-
"""test_c7_ngram_route_union.py — C7 MITAS_GARBLE_NGRAM_ROUTE + _name_ngram_garble testi.

Test ettiği:
  • _name_ngram_garble.looks_garble_ngram: gerçek garble'a True döner (model varsa).
  • MITAS_GARBLE_NGRAM_ROUTE mantığı: şüpheli isim cast_garble_lex'e EKLENIR ama
    d["cast"]'tan SİLİNMEZ (UNION, OCR-otorite invariantı).

  tek_film_kunye.py bu flag'i kullanan asıl kod; izolasyon için o dosyayı import etmeden
  YALNIZ ngram fonksiyonunu + garble-route invariantını (dict üzerinden inline) test ediyoruz.

  Model (_name_ngram_model.json) yoksa looks_garble_ngram False döner (FAIL-SAFE) →
  flag=1 testleri model yokken PASS (regresyon yok). Model varsa gerçek garble yakalanır.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from _name_ngram_garble import looks_garble_ngram, load_model, MODEL_PATH


# ──────────── looks_garble_ngram saf-fonksiyon testleri ─────────────────────

def _model_var():
    """Model dosyası mevcutsa True."""
    return MODEL_PATH.exists()


def test_c7_looks_garble_failsafe_exception():
    """FAIL-SAFE: exception durumunda looks_garble_ngram False döner (try/except).
    _token_scores içinde exception fırlatırsak False beklenir."""
    # looks_garble_ngram try/except ile sarılı: herhangi bir hata → False
    # Özel exception-fırlatıcı model: score_token'da hata tetiklemek için geçersiz counts tipi
    # Ancak kodun kendi try/except'ini test etmek için — looks_garble_ngram'ı doğrudan patch'le.
    import _name_ngram_garble as ngm
    _orig_ts = ngm._token_scores

    def _raise_ts(name, model=None):
        raise RuntimeError("simulated error")

    ngm._token_scores = _raise_ts
    try:
        result = looks_garble_ngram("RDGER MQSTEY")
        assert result is False, "exception durumunda FAIL-SAFE: False beklendi"
    finally:
        ngm._token_scores = _orig_ts


def test_c7_looks_garble_bos_isim_false():
    """Boş/None isim → ts boş → False (FAIL-SAFE)."""
    assert looks_garble_ngram("") is False
    # None için _tokens(None) → hata verebilir ama try/except yakalar
    result = looks_garble_ngram(None)
    assert result is False


def test_c7_looks_garble_gercek_isim_false():
    """Model varsa gerçek isim (JAMES DARREN, GREGORY PECK) garble DEĞİL → False."""
    if not _model_var():
        return   # model yok → FAIL-SAFE her şey False, bu testi atlayamayız ama regresyon yok
    m = load_model()
    for name in ("JAMES DARREN", "GREGORY PECK", "ROBERT REDFORD", "NURI BILGE CEYLAN"):
        result = looks_garble_ngram(name, m)
        assert result is False, f"Gerçek isim '{name}' garble=True olmamalı"


def test_c7_looks_garble_gercek_garble_true():
    """Model varsa gerçek garble (GEORCE STOAD ALRRDED, RDGER MQSTEY) → True."""
    if not _model_var():
        return   # model yok → FAIL-SAFE False, garble testi anlamsız → atla
    m = load_model()
    for name in ("GEORCE STOAD ALRRDED", "RDGER MQSTEY"):
        result = looks_garble_ngram(name, m)
        assert result is True, f"Garble '{name}' → True beklendi (model var)"


def test_c7_looks_garble_kisa_token_false():
    """Kısa tokenlar (MIN_TOKEN_LEN<4: 'J', 'PYL') → puanlanamaz → False."""
    # "J Y" → tüm tokenlar < 4 harf → ts boş → False
    assert looks_garble_ngram("J Y") is False


# ──────────── MITAS_GARBLE_NGRAM_ROUTE mantık union testi ───────────────────
# tek_film_kunye.py kullanamıyoruz; mantığı inline simüle ediyoruz.
# Kaynak kodu (konsept): for nm in d["cast"]: if looks_garble_ngram(nm): d["cast_garble_lex"].append(nm)
# SILME YOK — d["cast"] değişmez.

def _ngram_route_apply(cast_list, *, flag="1", model=None):
    """MITAS_GARBLE_NGRAM_ROUTE mantığını d["cast"] üzerinde uygula.
    Döner (cast_sonra, cast_garble_lex)."""
    _on = flag.strip().lower() in ("1", "true", "on", "yes")
    d = {"cast": list(cast_list), "cast_garble_lex": []}
    if _on:
        for nm in d["cast"]:
            if looks_garble_ngram(nm, model):
                if nm not in d["cast_garble_lex"]:
                    d["cast_garble_lex"].append(nm)
    return d["cast"], d["cast_garble_lex"]


def test_c7_route_union_silme_yok():
    """MITAS_GARBLE_NGRAM_ROUTE: garble şüphelisi cast_garble_lex'e EKLENIR, d["cast"]'tan SİLİNMEZ."""
    if not _model_var():
        # Model yok → looks_garble_ngram False → cast_garble_lex boş; invariant (silme yok) hâlâ geçer
        cast = ["JAMES DARREN", "GEORCE STOAD ALRRDED", "GREGORY PECK"]
        cast_sonra, lex = _ngram_route_apply(cast, flag="1")
        assert set(cast_sonra) == set(cast), "FAIL-SAFE: model yok → cast değişmez"
        return
    m = load_model()
    garble = "GEORCE STOAD ALRRDED"
    real = "JAMES DARREN"
    cast = [real, garble, "GREGORY PECK"]
    cast_sonra, lex = _ngram_route_apply(cast, flag="1", model=m)
    # UNION: cast DEĞİŞMEZ
    assert set(cast_sonra) == set(cast), f"cast değişmemeli; önce={cast}, sonra={cast_sonra}"
    # garble → lex'e eklendi
    assert garble in lex, f"Garble '{garble}' → cast_garble_lex'e eklenmeli"
    # gerçek isim → lex'e EKLENMEMELI
    assert real not in lex, f"Gerçek isim '{real}' garble_lex'e girmemeli"


def test_c7_route_flag_off_bos_lex():
    """MITAS_GARBLE_NGRAM_ROUTE=0 → cast_garble_lex boş (hiç çalışmaz)."""
    if not _model_var():
        cast = ["GEORCE STOAD ALRRDED"]
        cast_sonra, lex = _ngram_route_apply(cast, flag="0")
        assert lex == []
        return
    m = load_model()
    cast = ["GEORCE STOAD ALRRDED"]
    cast_sonra, lex = _ngram_route_apply(cast, flag="0", model=m)
    assert lex == [], f"flag=0 → cast_garble_lex boş olmalı, {lex}"
    assert set(cast_sonra) == set(cast)


def test_c7_route_gercek_isimler_lex_girmez():
    """Gerçek isimler → cast_garble_lex'e GİRMEZ (FP engeli)."""
    if not _model_var():
        return
    m = load_model()
    gercek = ["JAMES DARREN", "GREGORY PECK", "ROBERT REDFORD", "NURI BILGE CEYLAN"]
    cast_sonra, lex = _ngram_route_apply(gercek, flag="1", model=m)
    assert set(cast_sonra) == set(gercek), "Gerçek cast değişmemeli"
    for nm in gercek:
        assert nm not in lex, f"Gerçek isim '{nm}' garble_lex'e girmemeli"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
