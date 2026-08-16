"""Hangi GERÇEK hangi sınıfa gidiyor — spec 3.4 tablosunun kilidi.

Derleyici üç ayrı gerçeği tek kelimeye indiriyor: `durum="kare_yok"` hem
"klasör bulunamadı" hem "2'den az kare" hem "geçerli segment kalmadı" için
dönüyor (lebron_james.py:177,182,310). Kule bunları ayırır. Nash'in
METIN_YOK / ARIZA(KARE_OKUNAMADI) ayrımıyla kapattığı körlüğün aynısı.

Ayrım niye önemli: "bu jenerikte yazı yok" (içerik) ile "PaddleOCR çöktü"
(arıza) aynı kutuya girerse fark bir daha bulunamaz.
"""
from types import SimpleNamespace

import main
import sahte
import yukleyici
from sozlesme import Girdi


def _kos(monkeypatch, tmp_path, dizin, der, kanvas, manifest):
    monkeypatch.setattr(main, "_derle", lambda d, f: (der, (kanvas, manifest)))
    monkeypatch.setattr(main, "_oku", lambda y, b, f, a: {"satirlar": ["X"], "elenen": [], "bant_n": 1, "hata_n": 0, "elenen_n": 0, "kutu_durum": "tam"})
    return main.tek(Girdi(film_id="F", kareler=str(dizin)), tmp_path / "out")


def test_dizin_yok(monkeypatch, tmp_path):
    c = main.tek(Girdi(film_id="F", kareler=str(tmp_path / "yok")), tmp_path / "out")
    assert (c.durum, c.sinif) == ("ARIZA", "GIRDI_HATASI")


def test_dizin_bos(monkeypatch, tmp_path):
    d = tmp_path / "bos"
    d.mkdir()
    der = sahte.sahte_derleyici()
    c = _kos(monkeypatch, tmp_path, d, der, None,
             {"durum": "kare_yok", "kare": 0, "sebep": "Klasor bulunamadi"})
    assert (c.durum, c.sinif) == ("ARIZA", "GIRDI_HATASI")


def test_kareler_var_hicbiri_acilmiyor(monkeypatch, tmp_path):
    """Nash'in kapattığı körlük: içeriksiz mi, yoksa hiç açılamadı mı?"""
    d = sahte.kare_dizini_kur(tmp_path, n=10)
    der = sahte.sahte_derleyici()
    der.kareleri_yukle = lambda dz: ([], len(yukleyici.kareler(dz)))
    c = _kos(monkeypatch, tmp_path, d, der, None, {"durum": "kare_yok", "kare": 0})
    assert (c.durum, c.sinif) == ("ARIZA", "KARE_OKUNAMADI")
    assert "10 dosya" in c.mesaj


def test_tek_kare_girdi_hatasi(monkeypatch, tmp_path):
    """Lebron'un işi BAĞLAMAK; tek kare bağlama işi değildir (spec 3.4).

    Sessizce o kareyi 'master' diye geri vermek bozuk bir beslemeyi gizler.
    """
    d = sahte.kare_dizini_kur(tmp_path, n=1)
    der = sahte.sahte_derleyici()
    c = _kos(monkeypatch, tmp_path, d, der, None, {"durum": "kare_yok", "kare": 1})
    assert (c.durum, c.sinif) == ("ARIZA", "GIRDI_HATASI")
    assert "en az 2 kare" in c.mesaj


def test_gecerli_segment_kalmadi_ICERIK_gercegi(monkeypatch, tmp_path):
    """Kareler açıldı ama bağlanacak yazı yok → ARIZA DEĞİL, içerik gerçeği."""
    d = sahte.kare_dizini_kur(tmp_path, n=30)
    der = sahte.sahte_derleyici()
    c = _kos(monkeypatch, tmp_path, d, der, None,
             {"durum": "kare_yok", "kare": 30, "sebep": "Gecerli segment kalmadi"})
    assert c.durum == "METIN_YOK"
    assert c.sinif is None


def test_boy_asimi(monkeypatch, tmp_path):
    d = sahte.kare_dizini_kur(tmp_path, n=30)
    der = sahte.sahte_derleyici()
    c = _kos(monkeypatch, tmp_path, d, der, None, {"durum": "boy_asimi", "boy": 91000})
    assert (c.durum, c.sinif) == ("ARIZA", "BOY_ASIMI")
    assert "91000" in c.mesaj


def _model_hatasi(monkeypatch, tmp_path, hata):
    """Model yüklenemiyor / OOM — master yazılmış olmalı, arıza açık olmalı."""
    d = sahte.kare_dizini_kur(tmp_path, n=30)
    der = sahte.sahte_derleyici()
    monkeypatch.setattr(main, "_derle",
                        lambda dz, f: (der, (sahte.SahteKanvas(), sahte.manifest_ok())))

    def _patla(yol, bolum, film_id, ayar):
        raise hata
    monkeypatch.setattr(main, "_oku", _patla)
    return main.tek(Girdi(film_id="F", kareler=str(d)), tmp_path / "out")


def test_model_yoksa_acik_ariza(monkeypatch, tmp_path):
    """Model kurulmamışsa sessizce 'metin yok' demek YASAK — o içerik gerçeğidir."""
    from okuyucu import ModelYok
    c = _model_hatasi(monkeypatch, tmp_path,
                      main._ArizaSinyali("MODEL", "model agirligi yok"))
    assert (c.durum, c.sinif) == ("ARIZA", "MODEL")
    assert (tmp_path / "out" / "F" / "cikis" / "master.png").is_file()
    assert ModelYok is not None


def test_beklenmedik_okuyucu_hatasi_sizmaz(monkeypatch, tmp_path):
    c = _model_hatasi(monkeypatch, tmp_path, RuntimeError("bilinmeyen"))
    assert (c.durum, c.sinif) == ("ARIZA", "OKUYUCU")
    assert (tmp_path / "out" / "F" / "cikis" / "master.png").is_file()


def test_master_yazilamadi(monkeypatch, tmp_path):
    d = sahte.kare_dizini_kur(tmp_path, n=30)
    der = sahte.sahte_derleyici()

    def _patla(yol, g):
        raise OSError("disk dolu")
    der.yaz = _patla
    c = _kos(monkeypatch, tmp_path, d, der, sahte.SahteKanvas(), sahte.manifest_ok())
    assert (c.durum, c.sinif) == ("ARIZA", "MOTOR")
    assert "disk dolu" in c.mesaj
