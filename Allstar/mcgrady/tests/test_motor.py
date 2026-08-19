# -*- coding: utf-8 -*-
"""motor.py orkestrasyon testleri — KB/web modülleri FAKE ile enjekte edilir
(gerçek credit_crosscheck/credit_qc_gates diskte olmasa bile koşar; sys.modules
önceliği sayesinde gerçek dosyalar gelince de aynı fake'lerle koşar — motorun
KARAR mantığı test edilir, KB'nin değil)."""
import sys
import types
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

from garble import _fold  # noqa: E402
import motor  # noqa: E402


def _fold_eq(a, b):
    return _fold(a) == _fold(b)


class _FakeKB:
    def __init__(self, cross):
        self._cross = cross
        self.imdb = object()
    def db_hazir(self):
        return True
    def crosscheck(self, yon, cast, *, title_tr=None, original=None, year=None):
        return self._cross
    def close(self):
        pass


def _cc_fake(cross):
    m = types.ModuleType("credit_crosscheck")
    m.CreditKB = lambda: _FakeKB(cross)
    m.fold = _fold
    m.name_match = lambda a, b: _fold_eq(a, b)
    m.name_close = lambda a, b: False
    m.name_close_window = lambda o, d, thr=0.8: False
    return m


def _gates_fake(web=None):
    m = types.ModuleType("credit_qc_gates")
    def garble_no_signature_gate(read_cast, kb_cast, *, vl_cast=None, identity_locked=True):
        return [{"isim": n, "kb_imza": None, "vl_imza": False,
                 "suspect": bool(identity_locked) and n not in (kb_cast or []),
                 "eski_looks_garble": None} for n in read_cast]
    def web_identity(title, original, year, ocr_director, summary, kb):
        return web or {"locked": False, "method": None, "kaynak_izi": "çapa yok"}
    m.garble_no_signature_gate = garble_no_signature_gate
    m.web_identity = web_identity
    return m


def _paket(profile="film", cast=("Doğu Demirkol", "Murat Cemcir"), yon=("Nuri Bilge Ceylan",)):
    return {
        "schema_version": "mcgrady.girdi/v1", "film_id": "t", "profile": profile,
        "baslik": {"tr": "AHLAT AĞACI", "orijinal": "The Wild Pear Tree", "yil": 2018},
        "yonetmen": list(yon), "cast": list(cast), "yapimci": [],
    }


def test_teyit_dogrulanir(monkeypatch):
    cross = {"verdict": "TEYİT", "kaynak": "wikidata", "eslesen_film": "The Wild Pear Tree",
             "eslesen_yil": 2018, "cast_ortusme": 2,
             "otoriter_yonetmen": ["Nuri Bilge Ceylan"],
             "otoriter_cast": ["Doğu Demirkol", "Murat Cemcir"],
             "matched_imdb_id": "tt8950146", "neden": None}
    monkeypatch.setitem(sys.modules, "credit_crosscheck", _cc_fake(cross))
    monkeypatch.setitem(sys.modules, "credit_qc_gates", _gates_fake())
    r = motor.calistir(_paket(), {})
    assert r["durum"] == "DOGRULANDI"
    assert r["kimlik"]["method"] == "cast-ortusme"
    assert r["kimlik"]["versiyon_teyitli"] is True
    # teyitli yönetmen korunur, kontrol önerisi yok
    assert r["yonetmen"]["karar"] == "Nuri Bilge Ceylan"
    assert r["yonetmen"]["kontrol_onerisi"] is False
    # karar önerisi yok (temiz vaka)
    assert r["karar_onerileri"] == []


def test_kaynak_yok_dizide_web_atlanir(monkeypatch):
    cross = {"verdict": "KAYNAK_YOK", "kaynak": None, "cast_ortusme": 0,
             "otoriter_yonetmen": [], "otoriter_cast": [], "neden": "film bulunamadı"}
    monkeypatch.setitem(sys.modules, "credit_crosscheck", _cc_fake(cross))
    monkeypatch.setitem(sys.modules, "credit_qc_gates", _gates_fake(
        web={"locked": True, "method": "tmdb", "imdb_id": "tt1", "tmdb_id": "2",
             "director": ["X Y"], "cast": ["A B"], "kaynak_izi": "tmdb"}))
    r = motor.calistir(_paket(profile="dizi"), {})
    assert r["durum"] == "KILITLENEMEDI"          # web çağrılmadı — dizi
    assert r["web_oneri"] is None
    assert r["kanit"]["adimlar"]["web"]["neden"].startswith("dizi profili")
    assert any("kimlik kurulamadı" in k for k in r["karar_onerileri"])


def test_tmdb_capesi_kilitler_versiyon_teyitsiz(monkeypatch):
    cross = {"verdict": "KAYNAK_YOK", "kaynak": None, "cast_ortusme": 0,
             "otoriter_yonetmen": [], "otoriter_cast": [], "neden": "film bulunamadı"}
    monkeypatch.setitem(sys.modules, "credit_crosscheck", _cc_fake(cross))
    monkeypatch.setitem(sys.modules, "credit_qc_gates", _gates_fake(
        web={"locked": True, "method": "tmdb", "imdb_id": "tt1", "tmdb_id": "2",
             "director": ["X Y"], "cast": ["A B", "C D"], "kaynak_izi": "tmdb-çapası"}))
    r = motor.calistir(_paket(cast=["Okunamayan İsim"]), {})
    assert r["durum"] == "DOGRULANDI"
    assert r["kimlik"]["method"] == "tmdb"
    assert r["kimlik"]["versiyon_teyitli"] is False
    # OCR cast doluyken web cast YALNIZ ÖNERİ (OCR-otorite: ezme yok)
    assert r["web_oneri"]["cast_oneri"] == ["A B", "C D"]
    assert any("versiyon cast-teyitsiz" in k for k in r["karar_onerileri"])


def test_garble_suspekt_kontrol_onerisi(monkeypatch):
    cross = {"verdict": "TEYİT", "cast_ortusme": 2,
             "otoriter_yonetmen": ["Nuri Bilge Ceylan"],
             "otoriter_cast": ["Doğu Demirkol", "Murat Cemcir"],
             "matched_imdb_id": "tt8950146", "neden": None}
    monkeypatch.setitem(sys.modules, "credit_crosscheck", _cc_fake(cross))
    monkeypatch.setitem(sys.modules, "credit_qc_gates", _gates_fake())
    r = motor.calistir(_paket(cast=["Doğu Demirkol", "GEORCE STOAD"]), {})
    assert r["durum"] == "DOGRULANDI"
    assert any("garble şüphesi" in k for k in r["karar_onerileri"])


def test_yonetmen_celiski_kontrol_onerisi(monkeypatch):
    cross = {"verdict": "ÇELİŞKİ", "cast_ortusme": 3,
             "otoriter_yonetmen": ["Bertrand Tavernier"],
             "otoriter_cast": ["Dexter Gordon"], "matched_imdb_id": "tt9", "neden": None}
    monkeypatch.setitem(sys.modules, "credit_crosscheck", _cc_fake(cross))
    monkeypatch.setitem(sys.modules, "credit_qc_gates", _gates_fake())
    r = motor.calistir(_paket(cast=["Dexter Gordon", "François Cluzet"],
                              yon=("Martin Scorsese",)), {})
    # ÇELİŞKİ → TEYİT değil → kimlik cast_ov>=2 ile kilitlenir
    assert r["durum"] == "DOGRULANDI"
    assert r["yonetmen"]["karar"] == "Bertrand Tavernier"
    assert r["yonetmen"]["kontrol_onerisi"] is True
    assert any("yönetmen kararı insan teyidi" in k for k in r["karar_onerileri"])


def test_db_yoksa_motor_arizasi(monkeypatch):
    fake = _cc_fake({"verdict": "KAYNAK_YOK"})
    fake.CreditKB = lambda: types.SimpleNamespace(db_hazir=lambda: False, close=lambda: None)
    monkeypatch.setitem(sys.modules, "credit_crosscheck", fake)
    monkeypatch.setitem(sys.modules, "credit_qc_gates", _gates_fake())
    try:
        motor.calistir(_paket(), {})
        assert False, "MotorArizasi beklenmişti"
    except motor.MotorArizasi as e:
        assert e.sinif == "DB"
