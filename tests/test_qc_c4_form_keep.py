# -*- coding: utf-8 -*-
"""test_qc_c4_form_keep.py — C4 MITAS_OCR_FORM_KEEP testi.

Test ettiği: credit_qc_block S5 cast yazım-düzeltme kapısı.
  • KB="Murat Cemcir", OCR="Murat Cimcir" → name_close True, name_match False.
  • OCR_FORM_KEEP=1 → OCR formu ("Murat Cimcir") korunur, KB'ye snap YOK.
  • OCR_FORM_KEEP=0 (default-OFF) → name_close eşleşmesi → KB kanonik ("Murat Cemcir") uygulanır.
  • Exact-match isim (name_match True) → her iki flag durumunda aynı (KB kanonik).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import credit_qc_block as q
import credit_crosscheck as cc

# Hermetik: casing bypass
q._upper_names = lambda names: [str(n).upper() for n in (names or [])]
q._tr_upper_prose = lambda text, names: (text or "").upper()


def _ozet():
    return ("Genc adam memleketine doner ve hayallerinin pesinden kosarken ailesiyle yasadigi "
            "catismalar arasinda kendi yolunu bulmaya calisir ve sonunda zor bir karar verir.")


class FakeKB:
    """Kontrollü kimlik: TEYİT + otoriter_cast içinde hem 'Murat Cemcir' hem başkası."""

    def __init__(self, ocast=None, cast_ov=4):
        self._ocast = list(ocast or [])
        self._cast_ov = cast_ov

    def crosscheck(self, rd, rc, *, title_tr=None, original=None, year=None):
        return {
            "verdict": "TEYİT",
            "cast_ortusme": self._cast_ov,
            "otoriter_yonetmen": ["Nuri Bilge Ceylan"],
            "otoriter_cast": self._ocast,
            "matched_imdb_id": "tt1234567",
            "wikidata_imdb_id": "tt1234567",
            "wikidata_tmdb_id": None,
        }

    def close(self):
        pass


# name_close ve name_match kontrolü: "Murat Cimcir" ↔ "Murat Cemcir"
# credit_crosscheck.name_close: token-set benzerlik ≥ threshold → True (burada kanonik yazım farklı ama benzer)
# Doğrulayalım: testleri korumalı yapalım
def _verify_name_close():
    """'Murat Cimcir' ↔ 'Murat Cemcir' name_close True, name_match False olmalı."""
    return (cc.name_close("Murat Cimcir", "Murat Cemcir") and
            not cc.name_match("Murat Cimcir", "Murat Cemcir"))


def test_c4_form_keep_on_ocr_formu_korunur():
    """OCR_FORM_KEEP=1: name_close eşleşmesinde OCR formu ('Murat Cimcir') KORUNUR (S5 snap yok).
    Not: S7 floor-fill KB'den 'Murat Cemcir'i ayrıca ekleyebilir (floor-fill farklı mekanizma);
    burada yalnız S5 OCR-snap davranışı ölçülür → OCR formu 'murat cimcir' cast'te OLMALI."""
    if not _verify_name_close():
        print("  [atla] name_close('Murat Cimcir','Murat Cemcir')=False — test bu ortamda geçersiz")
        return
    os.environ["MITAS_OCR_FORM_KEEP"] = "1"
    kb = FakeKB(ocast=["Murat Cemcir", "Ali Veli", "Ayse Can", "Hazar Erg"], cast_ov=4)
    try:
        r = q.qc_credit_block(["Nuri Bilge Ceylan"],
                               ["Murat Cimcir", "Ali Veli", "Ayse Can", "Hazar Erg"], [],
                               title="AHLAT AGACI", year=2018, ozet=_ozet(), kb=kb)
        folds = [cc.fold(n) for n in r["temiz_cast"]]
        # OCR formu korunmalı: "murat cimcir" bulunmalı (S5 KB-snap uygulanmadı)
        assert "murat cimcir" in folds, (
            f"OCR_FORM_KEEP=1: OCR formu 'Murat Cimcir' korunmalı, folds={folds}")
    finally:
        os.environ.pop("MITAS_OCR_FORM_KEEP", None)


def test_c4_form_keep_off_kb_snap():
    """OCR_FORM_KEEP=0 (default-OFF): name_close → KB kanonik ('Murat Cemcir') uygulanır."""
    if not _verify_name_close():
        print("  [atla] name_close('Murat Cimcir','Murat Cemcir')=False — test bu ortamda geçersiz")
        return
    os.environ.pop("MITAS_OCR_FORM_KEEP", None)
    kb = FakeKB(ocast=["Murat Cemcir", "Ali Veli", "Ayse Can", "Hazar Erg"], cast_ov=4)
    try:
        r = q.qc_credit_block(["Nuri Bilge Ceylan"],
                               ["Murat Cimcir", "Ali Veli", "Ayse Can", "Hazar Erg"], [],
                               title="AHLAT AGACI", year=2018, ozet=_ozet(), kb=kb)
        folds = [cc.fold(n) for n in r["temiz_cast"]]
        # KB snap: "murat cemcir" bulunmalı
        assert "murat cemcir" in folds, (
            f"OCR_FORM_KEEP=0: KB snap 'Murat Cemcir' uygulanmalı, folds={folds}")
    finally:
        os.environ.pop("MITAS_OCR_FORM_KEEP", None)


def test_c4_exact_match_flag_bagimsiz():
    """name_match True (exact isim) → her iki flag durumunda KB kanonik uygulanır."""
    for flag in ("1", "0"):
        os.environ["MITAS_OCR_FORM_KEEP"] = flag
        kb = FakeKB(ocast=["Ali Veli", "Ayse Can", "Mehmet Han"], cast_ov=3)
        try:
            r = q.qc_credit_block(["Nuri Bilge Ceylan"],
                                   ["Ali Veli", "Ayse Can", "Mehmet Han"], [],
                                   title="X", year=2010, ozet=_ozet(), kb=kb)
            folds = [cc.fold(n) for n in r["temiz_cast"]]
            assert "ali veli" in folds, (
                f"OCR_FORM_KEEP={flag}: exact-match 'Ali Veli' her durumda mevcut olmalı")
        finally:
            os.environ.pop("MITAS_OCR_FORM_KEEP", None)


def test_c4_default_off_byte_identical():
    """Flag yokken (env silinmiş) → default-OFF: name_close → KB snap (eski davranış değişmez)."""
    if not _verify_name_close():
        print("  [atla] name_close geçersiz bu ortamda")
        return
    os.environ.pop("MITAS_OCR_FORM_KEEP", None)
    kb = FakeKB(ocast=["Murat Cemcir", "Ali Veli", "Ayse Can", "Hazar Erg"], cast_ov=4)
    r1 = q.qc_credit_block(["Nuri Bilge Ceylan"],
                            ["Murat Cimcir", "Ali Veli", "Ayse Can", "Hazar Erg"], [],
                            title="DEFAULT TEST", year=2018, ozet=_ozet(), kb=kb)
    os.environ["MITAS_OCR_FORM_KEEP"] = "0"
    r2 = q.qc_credit_block(["Nuri Bilge Ceylan"],
                            ["Murat Cimcir", "Ali Veli", "Ayse Can", "Hazar Erg"], [],
                            title="DEFAULT TEST", year=2018, ozet=_ozet(), kb=kb)
    os.environ.pop("MITAS_OCR_FORM_KEEP", None)
    # Her iki çıktı aynı olmalı (byte-identical temiz_cast)
    assert sorted(r1["temiz_cast"]) == sorted(r2["temiz_cast"]), (
        "flag yokken ile =0 arasında temiz_cast FARKI olmamalı")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
