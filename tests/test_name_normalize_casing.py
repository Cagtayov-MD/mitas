import importlib.util
from pathlib import Path


def _load_name_normalize():
    path = Path(r"E:\MITAS\OCR-worktree\pdf-mitas\name_normalize.py")
    spec = importlib.util.spec_from_file_location("name_normalize_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod._mitas_people_set = lambda names: (False, {})
    mod._TR_GIVEN = set()
    mod._TR_SUR = set()
    return mod


def test_upper_names_repairs_synthetic_dotted_i_in_foreign_names():
    nn = _load_name_normalize()

    assert nn.upper_names([
        "JEAN-PİERRE DARROUSSİN",
        "ANDRÉ WİLMS",
        "MASSİMO GİROTTİ",
        "MARTİN RİTT",
        "MİCHAEL PATAKİ",
    ]) == [
        "JEAN-PIERRE DARROUSSIN",
        "ANDRE WILMS",
        "MASSIMO GIROTTI",
        "MARTIN RITT",
        "MICHAEL PATAKI",
    ]


def test_upper_names_keeps_turkish_dotted_i_when_not_foreign_marked():
    nn = _load_name_normalize()

    assert nn.upper_names([
        "ALİ ATAY",
        "İPEK FİLİZ YAZICI",
        "NURİ BİLGE CEYLAN",
    ]) == [
        "ALİ ATAY",
        "İPEK FİLİZ YAZICI",
        "NURİ BİLGE CEYLAN",
    ]


def test_upper_names_still_folds_clean_foreign_names():
    nn = _load_name_normalize()

    assert nn.upper_names([
        "Jean-Pierre Darroussin",
        "André Wilms",
        "Aki Kaurismäki",
    ]) == [
        "JEAN-PIERRE DARROUSSIN",
        "ANDRE WILMS",
        "AKI KAURISMAKI",
    ]


def test_tr_upper_prose_repairs_foreign_character_name_roots():
    nn = _load_name_normalize()

    out = nn.tr_upper_prose(
        "Freddie Butler, Sophie ile evlenir. Sophie'nin kararı finalde değişir.",
        names=[],
    )

    assert "FREDDIE BUTLER" in out
    assert "SOPHIE İLE" in out
    assert "SOPHIE'NİN" in out
    assert "FİNALDE" in out
    assert "SOPHİE" not in out
    assert "FREDDİE" not in out
