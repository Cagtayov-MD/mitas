# -*- coding: utf-8 -*-
"""test_qc_c2_ocr_keep.py — C2 MITAS_CAST_OCR_KEEP testi.

Test ettiği: credit_qc_block S6 garble/eleme kapısı + OCR-groundtruth kurtarma baypası.
  • MITAS_CAST_OCR_KEEP=1 + raw_names_groundtruth: S6'nın düşüreceği OCR-okunan isim KORUNUR.
  • MITAS_CAST_OCR_KEEP=0 (default-OFF): isim S6'dan düşer (eski davranış AYNEN).
  • Rol-etiketi (tek-token/junk) → her iki durumda düşer.
  • _cast_cap(): 8/12/bozuk → 8 kısıtlaması.

NOT: S6 eleme; _apply_garble_gate + _only_persons çağrısına bağlı.
     "Sürpriz kurtulan" test için gerçek _looks_garble ile sınır-değer isim seçiyoruz.
     Daha güvenli yol: _apply_garble_gate'i monkeypatch ederek S6'nın "düşürdüğünü" simüle et.
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
    def __init__(self, *, verdict="TEYİT", oyon=None, ocast=None, cast_ov=4,
                 imdb_id="tt1234567"):
        self._d = dict(verdict=verdict, otoriter_yonetmen=list(oyon or []),
                       otoriter_cast=list(ocast or []), cast_ortusme=cast_ov,
                       matched_imdb_id=imdb_id, wikidata_imdb_id=imdb_id, wikidata_tmdb_id=None)
        self.imdb = None

    def crosscheck(self, rd, rc, *, title_tr=None, original=None, year=None):
        return dict(self._d)

    def close(self):
        pass


# S6'nın düşüreceğini garanti etmek için _apply_garble_gate'i monkeypatch ile tam-eleme yapıyoruz.
# OCR_KEEP testi: target KB-otoriter_cast'te OLMAMALI — aksi halde S7 floor-fill geri ekler
# ve flag davranışı gözlemlenemez.
_TARGET_DROP = "Eleonore Vonderschmidt"   # groundtruth'ta var, S6 düşürür (monkeypatch); KB'de YOK
_ROLE_LABEL = "SENARYO"                    # tek-token rol-etiketi → her zaman düşer


def _make_drop_gate(target):
    """target'ı (fold'lı) S6'dan düşüren sahte garble-gate."""
    _fold_target = cc.fold(target)

    def _fake_gate(names, kb=None):
        return [n for n in (names or []) if cc.fold(n) != _fold_target]

    return _fake_gate


def test_c2_ocr_keep_on_kurtarir():
    """MITAS_CAST_OCR_KEEP=1 + raw groundtruth → S6-düşürülen OCR-isim KORUNUR.
    Önemli: KB-otoriter_cast target'ı içermez → S7 floor-fill re-add etmez; yalnız OCR_KEEP etkisi ölçülür."""
    os.environ["MITAS_CAST_OCR_KEEP"] = "1"
    _orig_gate = q._apply_garble_gate
    q._apply_garble_gate = _make_drop_gate(_TARGET_DROP)
    # otoriter_cast: yalnız Ali Veli + Ayse Can (TARGET YOK → floor-fill re-add yok)
    kb = FakeKB(oyon=["Yönetmen Bir"], ocast=["Ali Veli", "Ayse Can"], cast_ov=2)
    # raw_names_groundtruth: TARGET bitişik var (iki ayrı token → bitişiklik için tek satırda)
    raw_gt = ["eleonore vonderschmidt", "ali veli", "ayse can"]
    try:
        r = q.qc_credit_block(["Yönetmen Bir"], ["Ali Veli", "Ayse Can", _TARGET_DROP], [],
                               title="KEDI GOZU", year=1964, ozet=_ozet(), kb=kb,
                               raw_names_groundtruth=raw_gt)
        folds = [cc.fold(n) for n in r["temiz_cast"]]
        assert cc.fold(_TARGET_DROP) in folds, (
            f"OCR_KEEP=1: S6-düşürülen OCR-isim '{_TARGET_DROP}' korunmalıydı, folds={folds}")
    finally:
        q._apply_garble_gate = _orig_gate
        os.environ.pop("MITAS_CAST_OCR_KEEP", None)


def test_c2_ocr_keep_off_duser():
    """MITAS_CAST_OCR_KEEP=0 (default-OFF) → S6-düşürülen isim korunmaz.
    KB-otoriter_cast target'ı içermez → S7 re-add da yok; net OCR_KEEP=0 davranışı."""
    os.environ.pop("MITAS_CAST_OCR_KEEP", None)
    _orig_gate = q._apply_garble_gate
    q._apply_garble_gate = _make_drop_gate(_TARGET_DROP)
    # otoriter_cast: TARGET YOK
    kb = FakeKB(oyon=["Yönetmen Bir"], ocast=["Ali Veli", "Ayse Can"], cast_ov=2)
    raw_gt = ["eleonore vonderschmidt", "ali veli", "ayse can"]
    try:
        r = q.qc_credit_block(["Yönetmen Bir"], ["Ali Veli", "Ayse Can", _TARGET_DROP], [],
                               title="KEDI GOZU", year=1964, ozet=_ozet(), kb=kb,
                               raw_names_groundtruth=raw_gt)
        folds = [cc.fold(n) for n in r["temiz_cast"]]
        assert cc.fold(_TARGET_DROP) not in folds, (
            f"OCR_KEEP=0 (default): S6-düşürülen '{_TARGET_DROP}' kalmamalıydı, folds={folds}")
    finally:
        q._apply_garble_gate = _orig_gate


def test_c2_rol_etiketi_her_durumda_duser():
    """Rol-etiketi (tek-token, _only_persons) → OCR_KEEP=1'de bile DÜŞER."""
    os.environ["MITAS_CAST_OCR_KEEP"] = "1"
    # "SENARYO" → tek kelime → _valid_person_name False → _only_persons siler
    kb = FakeKB(oyon=["Yön"], ocast=["Ali Veli", "Ayse Can"], cast_ov=2)
    raw_gt = ["senaryo", "ali veli", "ayse can"]
    try:
        r = q.qc_credit_block(["Yön"], ["Ali Veli", "Ayse Can", _ROLE_LABEL], [],
                               title="X", year=2010, ozet=_ozet(), kb=kb,
                               raw_names_groundtruth=raw_gt)
        folds = [cc.fold(n) for n in r["temiz_cast"]]
        assert cc.fold(_ROLE_LABEL) not in folds, (
            f"Rol-etiketi '{_ROLE_LABEL}' OCR_KEEP=1'de bile düşmeli, folds={folds}")
    finally:
        os.environ.pop("MITAS_CAST_OCR_KEEP", None)


def test_c2_cast_cap_8():
    """_cast_cap() = 8 (env'siz default)."""
    os.environ.pop("MITAS_CAST_CAP", None)
    assert q._cast_cap() == 8


def test_c2_cast_cap_12():
    """_cast_cap() = 12 (MITAS_CAST_CAP=12)."""
    os.environ["MITAS_CAST_CAP"] = "12"
    try:
        assert q._cast_cap() == 12
    finally:
        os.environ.pop("MITAS_CAST_CAP", None)


def test_c2_cast_cap_bozuk_8_fallback():
    """_cast_cap() bozuk değer (sıfır/negatif/metin) → 8 fallback."""
    for bad in ("0", "-5", "abc", ""):
        os.environ["MITAS_CAST_CAP"] = bad
        try:
            assert q._cast_cap() == 8, f"MITAS_CAST_CAP={bad!r} → 8 fallback beklendi"
        finally:
            os.environ.pop("MITAS_CAST_CAP", None)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
