"""Kurtarma künyesi çıktıya akar — çöküş artık arıza değil, boy aşımı
hâlâ görünür bir arızadır (devir planı 2026-08-19)."""
import main
import sahte
from sozlesme import Girdi

KURTARMA = {"triggered": True, "strategy": "temporal_chunk_stack",
            "chunk_size": 12, "chunk_count": 10, "original_frames": 120,
            "original_segments": 1, "original_height": 319,
            "recovered_height": 2110}


def _kur(monkeypatch, tmp_path, kanvas, manifest):
    d = sahte.kare_dizini_kur(tmp_path)
    der = sahte.sahte_derleyici(cokmus_mu=False)
    monkeypatch.setattr(main, "_derle", lambda dizin, fid: (der, (kanvas, manifest)))
    monkeypatch.setattr(main, "_oku", lambda yol, bolum, fid, ayar: {
        "satirlar": ["YONETIM AHMET"], "elenen": [], "bant_n": 3,
        "bant_y0": [0, 980, 1960]})
    monkeypatch.delenv("MITAS_OKUMA_V2", raising=False)
    return d


def test_kurtarilan_master_cokme_arizasi_uretmez_kunyeyi_tasir(monkeypatch, tmp_path):
    """10 parçalı kurtarılmış master tek segment değildir: çöküş dedektörü
    sessiz kalır, okuma akar, kurtarma künyesi kanıta çıkar."""
    m = sahte.manifest_ok(kare=120, boy=2110, segment=10)
    m["collapse_recovery"] = dict(KURTARMA)
    d = _kur(monkeypatch, tmp_path, sahte.SahteKanvas(boy=2110), m)

    c = main.tek(Girdi(film_id="F", kareler=str(d)), tmp_path / "out")

    assert c.durum == "OKUNDU"
    assert c.sinif is None
    assert c.kanit["collapse_recovery"] == KURTARMA
    assert c.kanit["segment"] == 10
    assert c.uretilen[0]["boy"] == 2110


def test_h_maks_asimi_kurtarma_kunyesiyle_gorunur_kalir(monkeypatch, tmp_path):
    """Kurtarma sonrası bile H_MAKS aşılırsa arıza görünür kalır ve hangi
    kurtarmanın tavanı aştığını künyesiyle söyler."""
    m = {"slug": "F", "durum": "boy_asimi", "kare": 200, "segment": 17,
         "size": [1920, 3583], "boy": 3583, "sinif_sayimi": {"scroll": 199},
         "collapse_recovery": dict(KURTARMA)}
    d = _kur(monkeypatch, tmp_path, None, m)

    c = main.tek(Girdi(film_id="F", kareler=str(d)), tmp_path / "out")

    assert c.durum == "ARIZA" and c.sinif == "BOY_ASIMI"
    assert "3583" in c.mesaj
    assert c.kanit["collapse_recovery"]["triggered"] is True
    assert c.kanit["collapse_recovery"]["recovered_height"] == 2110
    assert not (tmp_path / "out" / "F" / "cikis" / "master.png").exists()


def test_kurtarma_arizasi_metin_yoka_donusmez(monkeypatch, tmp_path):
    """Kurtarma parçası üretilemedi — derleme arızasıdır; 'metinsiz' içerik
    gerçeği DEĞİLDİR (OkumaCoktu ile aynı ders)."""
    m = {"slug": "F", "durum": "cokme_kurtarma_ariza", "kare": 120,
         "segment": 1, "size": [1920, 319], "sinif_sayimi": {"duraksama": 119},
         "sebep": "Kurtarma parcasi yok",
         "collapse_recovery": {**KURTARMA, "triggered": True}}
    d = _kur(monkeypatch, tmp_path, None, m)

    c = main.tek(Girdi(film_id="F", kareler=str(d)), tmp_path / "out")

    assert c.durum == "ARIZA" and c.sinif == "MOTOR"
    assert "Kurtarma parcasi" in c.mesaj
    assert c.kanit["collapse_recovery"]["triggered"] is True
