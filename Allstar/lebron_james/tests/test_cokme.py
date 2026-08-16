"""Çöküş dedektörü — master_png_monitor._lebron_cokmus'ün kule içindeki hali.

Motor bazen 20+ kareyi tek ekrana çökertiyor: segment=1 ve boy kare
yüksekliğinin iki katını geçmiyor. Üretimde bu çıktı REDDEDİLİR ("kötü master
yerine hiç"). Kural kule içinde yaşar ki her tüketici aynı testi yeniden
yazmak zorunda kalmasın — ve biri unutmasın.
"""
import main
import sahte
from kural import cokmus
from sozlesme import Girdi


def test_cokme_tetiklenir():
    assert cokmus({"segment": 1, "size": [1920, 2000]}, 30, 1080) is True


def test_cok_segment_cokme_degil():
    assert cokmus({"segment": 7, "size": [1920, 2000]}, 30, 1080) is False


def test_az_karede_hukum_verilmez():
    """19 kare tek ekrana sığabilir — gerçekten tek karttır, çöküş değil."""
    assert cokmus({"segment": 1, "size": [1920, 2000]}, 19, 1080) is False


def test_uzun_master_cokme_degil():
    assert cokmus({"segment": 1, "size": [1920, 9000]}, 30, 1080) is False


def test_sinir_degeri_dahil():
    """boy == 2*h → çöküş (üretimdeki `<=` korunur)."""
    assert cokmus({"segment": 1, "size": [1920, 2160]}, 30, 1080) is True
    assert cokmus({"segment": 1, "size": [1920, 2161]}, 30, 1080) is False


def test_boy_yoksa_hukum_yok():
    assert cokmus({"segment": 1, "size": None}, 30, 1080) is False


def test_akista_ariza_uretir_ama_master_kalir(monkeypatch, tmp_path):
    """Çöküşte bile master diskte durur: 'neden çökmüş' sorusu kanıtsız kalmasın."""
    d = sahte.kare_dizini_kur(tmp_path, n=30)
    der = sahte.sahte_derleyici(cokmus_mu=True)
    monkeypatch.setattr(main, "_derle",
                        lambda dz, f: (der, (sahte.SahteKanvas(boy=2000),
                                             sahte.manifest_ok(boy=2000, segment=1))))
    monkeypatch.setattr(main, "_oku", lambda y, b, f, a: {"satirlar": ["X"], "elenen": [], "bant_n": 1, "hata_n": 0, "elenen_n": 0, "kutu_durum": "tam"})
    c = main.tek(Girdi(film_id="F", kareler=str(d)), tmp_path / "out")
    assert (c.durum, c.sinif) == ("ARIZA", "COKME")
    assert (tmp_path / "out" / "F" / "cikis" / "master.png").is_file()
    assert c.uretilen[0]["tip"] == "master"
