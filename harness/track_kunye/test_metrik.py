# harness/track_kunye/test_metrik.py
import metrik


def test_skorla_fuzzy_toleransi():
    # exact-token tuzağı fix'i: 1-harf OCR hatası eşleşmeli (uganov→ugarov)
    ref = {"ugarov", "archer", "mellor"}
    r = metrik.skorla(["Valeri Uganov", "Neil Archer"], ref, {"ugarov", "archer", "mellor", "valeri", "neil"})
    assert r["eslesen"] == 2 and abs(r["recall"] - 2 / 3) < 1e-6


def test_skorla_precision_yalniz_kb_isimleri():
    # 'SUNG BY' gibi rol satırları precision'ı cezalandırmaz
    ref = {"archer"}
    r = metrik.skorla(["SUNG BY", "Neill Archer"], ref, {"archer", "neill"})
    assert r["precision"] == 1.0


def test_skorla_bos_girdiler():
    r = metrik.skorla([], {"a"}, set())
    assert r["recall"] == 0.0 and r["f1"] == 0.0
