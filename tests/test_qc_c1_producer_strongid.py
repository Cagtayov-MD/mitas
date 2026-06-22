# -*- coding: utf-8 -*-
"""test_qc_c1_producer_strongid.py — C1 MITAS_QC_PRODUCER_STRONGID testi.

Test ettiği: credit_qc_block._kb_producers + S8 yapımcı-doldurma kapısı.
  • STRONGID=1 (default-ON): zayıf kimlik (cast_ov<3, verdict!=TEYİT) → KB-yapımcı eklenmez.
  • STRONGID=0: zayıf kimlik → KB-yapımcı yine eklenir (eski davranış).
  • TEYİT / cast_ov>=3 → her iki durumda KB-yapımcı eklenir.

NOT: _kb_producers kb.imdb üzerinden DuckDB sorgusu yapar; DB yok olduğundan monkeypatch ile
bypass ediyoruz. FakeKB pattern: test_credit_qc_block.py ile aynı.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import credit_qc_block as q
import credit_crosscheck as cc

# Hermetik: casing'i hızlandır
q._upper_names = lambda names: [str(n).upper() for n in (names or [])]
q._tr_upper_prose = lambda text, names: (text or "").upper()


def _ozet():
    return ("Genc adam memleketine doner ve hayallerinin pesinden kosarken ailesiyle yasadigi "
            "catismalar arasinda kendi yolunu bulmaya calisir ve sonunda zor bir karar verir.")


class FakeKB:
    """CreditKB arayüzünü taklit eder + _kb_producers monkeypatch desteği."""

    def __init__(self, *, verdict="ÇELİŞKİ", cast_ov=2, oyon=None, ocast=None,
                 imdb_id="tt0000099", tmdb_id=None, kb_prods=None):
        self._verdict = verdict
        self._cast_ov = cast_ov
        self._oyon = list(oyon or [])
        self._ocast = list(ocast or [])
        self._imdb_id = imdb_id
        self._tmdb_id = tmdb_id
        # KB-yapımcılar: _kb_producers monkeypatch için dışarıdan verilir
        self._kb_prods = list(kb_prods or [])
        self.imdb = True  # _kb_producers guard: imdb truthy → denemek için gerekli

    def crosscheck(self, rd, rc, *, title_tr=None, original=None, year=None):
        return {
            "verdict": self._verdict,
            "cast_ortusme": self._cast_ov,
            "otoriter_yonetmen": self._oyon,
            "otoriter_cast": self._ocast,
            "matched_imdb_id": self._imdb_id,
            "wikidata_imdb_id": self._imdb_id,
            "wikidata_tmdb_id": self._tmdb_id,
        }

    def close(self):
        pass


def _patch_kb_producers(kb_instance, monkeyval):
    """_kb_producers fonksiyonunu verilen listeyi döndürecek şekilde patch'le."""
    _orig = q._kb_producers
    q._kb_producers = lambda kb, imdb_id, limit=3: list(monkeyval)
    return _orig


def _restore(orig):
    q._kb_producers = orig


# ──────────────────────────── TESTler ────────────────────────────────────────

def test_c1_strongid_on_weak_kimlik_yapimci_eklenmez():
    """STRONGID=1 (default) + zayıf kimlik (cast_ov=2, verdict!=TEYİT) → KB-yapımcı eklenmez."""
    os.environ["MITAS_QC_PRODUCER_STRONGID"] = "1"
    kb = FakeKB(verdict="ÇELİŞKİ", cast_ov=2,
                oyon=["Ali Yönetmen"], ocast=["Ali Veli", "Ayse Can"],
                kb_prods=["Norman Lear", "Ahmet Kaya"])
    orig = _patch_kb_producers(kb, ["Norman Lear", "Ahmet Kaya"])
    try:
        r = q.qc_credit_block(["Ali Yönetmen"], ["Ali Veli", "Ayse Can"], [],
                               title="BEKARLIK SULTAN", year=2005,
                               ozet=_ozet(), kb=kb)
        yap_folds = [cc.fold(n) for n in r["temiz_yap"]]
        assert "norman lear" not in yap_folds, "STRONGID=1 zayıf-kimlikte KB-yapımcı eklememeli"
        assert "ahmet kaya" not in yap_folds, "STRONGID=1 zayıf-kimlikte KB-yapımcı eklememeli"
    finally:
        _restore(orig)
        os.environ.pop("MITAS_QC_PRODUCER_STRONGID", None)


def test_c1_strongid_off_weak_kimlik_yapimci_eklenir():
    """STRONGID=0 → zayıf kimlik bile KB-yapımcı ekler (eski davranış)."""
    os.environ["MITAS_QC_PRODUCER_STRONGID"] = "0"
    kb = FakeKB(verdict="ÇELİŞKİ", cast_ov=2,
                oyon=["Ali Yönetmen"], ocast=["Ali Veli", "Ayse Can"],
                kb_prods=["Norman Lear"])
    orig = _patch_kb_producers(kb, ["Norman Lear"])
    try:
        r = q.qc_credit_block(["Ali Yönetmen"], ["Ali Veli", "Ayse Can"], [],
                               title="BEKARLIK SULTAN", year=2005,
                               ozet=_ozet(), kb=kb)
        yap_folds = [cc.fold(n) for n in r["temiz_yap"]]
        assert "norman lear" in yap_folds, "STRONGID=0 zayıf-kimlikte de KB-yapımcı eklemeli"
    finally:
        _restore(orig)
        os.environ.pop("MITAS_QC_PRODUCER_STRONGID", None)


def test_c1_teyit_kimlik_yapimci_her_durumda_eklenir():
    """verdict==TEYİT → STRONGID durumundan bağımsız KB-yapımcı eklenir."""
    for flag in ("1", "0"):
        os.environ["MITAS_QC_PRODUCER_STRONGID"] = flag
        kb = FakeKB(verdict="TEYİT", cast_ov=3,
                    oyon=["Ali Yönetmen"],
                    ocast=["Ali Veli", "Ayse Can", "Mehmet Han", "Hazar Erg"],
                    kb_prods=["Norman Lear"])
        orig = _patch_kb_producers(kb, ["Norman Lear"])
        try:
            r = q.qc_credit_block(["Ali Yönetmen"],
                                   ["Ali Veli", "Ayse Can", "Mehmet Han", "Hazar Erg"], [],
                                   title="TEYIT FILM", year=2005,
                                   ozet=_ozet(), kb=kb)
            yap_folds = [cc.fold(n) for n in r["temiz_yap"]]
            assert "norman lear" in yap_folds, (
                f"STRONGID={flag} TEYİT-kimlikte KB-yapımcı eklemeli (cast_ov=3)")
        finally:
            _restore(orig)
            os.environ.pop("MITAS_QC_PRODUCER_STRONGID", None)


def test_c1_cast_ov3_yapimci_her_durumda_eklenir():
    """cast_ov>=3 (verdict ÇELİŞKİ olsa bile) → STRONGID=1'de de yapımcı eklenir."""
    os.environ["MITAS_QC_PRODUCER_STRONGID"] = "1"
    # "Yapimci Biri" → 'yapimci' junk kelime → _only_persons atar. Gerçek-görünen isim kullan.
    kb = FakeKB(verdict="ÇELİŞKİ", cast_ov=3,
                oyon=["Ali Yönetmen"],
                ocast=["Ali Veli", "Ayse Can", "Mehmet Han", "Hazar Erg"],
                kb_prods=["Luca Miniero"])
    orig = _patch_kb_producers(kb, ["Luca Miniero"])
    try:
        r = q.qc_credit_block(["Ali Yönetmen"],
                               ["Ali Veli", "Ayse Can", "Mehmet Han", "Hazar Erg"], [],
                               title="CAST_OV3 FILM", year=2010,
                               ozet=_ozet(), kb=kb)
        yap_folds = [cc.fold(n) for n in r["temiz_yap"]]
        assert "luca miniero" in yap_folds, "cast_ov=3 → STRONGID=1'de de yapımcı eklemeli"
    finally:
        _restore(orig)
        os.environ.pop("MITAS_QC_PRODUCER_STRONGID", None)


def test_c1_default_on_davranisi():
    """Flag yokken (env silinmiş) → default-ON = STRONGID=1 davranışı (zayıf kimlikte ekleme yok)."""
    os.environ.pop("MITAS_QC_PRODUCER_STRONGID", None)
    kb = FakeKB(verdict="ÇELİŞKİ", cast_ov=2,
                oyon=["Ali Yönetmen"], ocast=["Ali Veli", "Ayse Can"],
                kb_prods=["Norman Lear"])
    orig = _patch_kb_producers(kb, ["Norman Lear"])
    try:
        r = q.qc_credit_block(["Ali Yönetmen"], ["Ali Veli", "Ayse Can"], [],
                               title="VARSAYILAN TEST", year=2005,
                               ozet=_ozet(), kb=kb)
        yap_folds = [cc.fold(n) for n in r["temiz_yap"]]
        # default ON: zayıf kimlikte KB-yapımcı eklememeli
        assert "norman lear" not in yap_folds, "default-ON: zayıf kimlikte KB-yapımcı eklememeli"
    finally:
        _restore(orig)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
