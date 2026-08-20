import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "olcum"))
import sheriff_kabul_raporu as rapor  # noqa: E402


def test_fuzzy_esleme_tek_kullanimli_ve_unicode_duyarli():
    matches, only_a, only_b = rapor._eslestir(
        ["Jöhn Smith", "DIRECTED BY"],
        ["John Smith", "Directed by", "Unused Name"])
    assert len(matches) == 2
    assert only_a == []
    assert only_b == [2]


def test_name_like_rol_satirini_isim_sanmaz():
    assert rapor._name_like("Walter Lang") is True
    assert rapor._name_like("Directed by") is False
    assert rapor._name_like("Music by Lionel Newman") is False
