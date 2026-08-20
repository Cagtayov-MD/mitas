import importlib.util
from pathlib import Path


YOL = Path(__file__).parents[1] / "olcum/okunmalik_toplu.py"
SPEC = importlib.util.spec_from_file_location("okunmalik_toplu", YOL)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_bolum_dosya_adindan_bulunur():
    assert MOD.bolum_bul(Path("güneş_ilk_02m18s.mp4")) == "giris"
    assert MOD.bolum_bul(Path("suç_dosyası_bitiş.mp4")) == "cikis"


def test_film_id_yol_ayirici_uretmez():
    assert MOD.film_id(3, Path("FRANNY'NİN AYAKLARI.mxf")) == (
        "03_franny_nin_ayaklari")
