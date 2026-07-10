import importlib.util
from pathlib import Path


def _load_tek_film_kunye():
    path = Path(r"E:\MITAS\scripts\tek_film_kunye.py")
    spec = importlib.util.spec_from_file_location("tek_film_kunye_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod._GLOBAL_PERSON_GATE_ON = True  # kapı production'da varsayılan OFF; opt-in özelliği izole test et
    return mod


class FakeKB:
    _known = {
        "Sally Hawkins": "Sally Hawkins",
        "Sinead Maguire": "Sinead Maguire",
        "Tina Kellegher": "Tina Kellegher",
    }

    imdb = object()
    wd = None

    def global_person_match(self, name, role="cast", max_edits=1):
        if role != "cast":
            return None
        out = self._known.get(name)
        if not out:
            return None
        return {"source": "fake-global", "name": out, "distance": 0}


class EmptyKB:
    imdb = object()
    wd = None

    def global_person_match(self, name, role="cast", max_edits=1):
        return None


def test_global_person_gate_strips_character_prefix_from_cast_names():
    mod = _load_tek_film_kunye()

    out, report = mod._gate_role_names(
        ["Maura Sally Hawkins", "Molly Sinead Maguire", "Karen Tina Kellegher"],
        "cast",
        xml_roles={},
        film_pool=[],
        kb=FakeKB(),
    )

    assert out == ["Sally Hawkins", "Sinead Maguire", "Tina Kellegher"]
    assert [x["action"] for x in report["kept"]] == [
        "KARAKTER_ADI_ATILDI",
        "KARAKTER_ADI_ATILDI",
        "KARAKTER_ADI_ATILDI",
    ]
    assert report["dropped"] == []


def test_global_person_gate_keeps_suffix_when_external_kb_has_no_hit():
    mod = _load_tek_film_kunye()

    out, report = mod._gate_role_names(
        ["Maura Sally Hawkins"],
        "cast",
        xml_roles={},
        film_pool=[],
        kb=EmptyKB(),
    )

    assert out == ["Sally Hawkins"]
    assert report["kept"][0]["source"] == "ocr_suffix"
    assert report["kept"][0]["action"] == "KARAKTER_ADI_ATILDI"
    assert report["dropped"] == []


def test_global_person_gate_uses_role_pool_for_small_ocr_name_errors():
    mod = _load_tek_film_kunye()

    out, report = mod._gate_role_names(
        ["Doirdro Molloy"],
        "cast",
        xml_roles={},
        film_pool=["Deirdre Molloy"],
        kb=EmptyKB(),
    )

    assert out == ["Deirdre Molloy"]
    assert report["kept"][0]["match"] == "fuzzy2"
    assert report["dropped"] == []


def test_read_producer_names_are_canonicalized_without_global_drop():
    mod = _load_tek_film_kunye()

    class FakeCreditKB:
        def global_person_match(self, name, role="producer", max_edits=1):
            if name == "Jerpy Wald" and role == "producer":
                return {"source": "fake-global", "name": "Jerry Wald", "distance": 1}
            return None

        def close(self):
            pass

    class FakeCC:
        CreditKB = FakeCreditKB

        @staticmethod
        def name_match(a, b):
            return str(a).lower() == str(b).lower()

        @staticmethod
        def strict_name_close(a, b):
            return str(a).lower() == str(b).lower()

    old_cc = mod._cc
    try:
        mod._cc = FakeCC
        out, changes = mod._canonicalize_read_producers(["Jerpy Wald", "Unknown Producer"])
    finally:
        mod._cc = old_cc

    assert out == ["Jerry Wald", "Unknown Producer"]
    assert changes == [{"in": "Jerpy Wald", "out": "Jerry Wald", "source": "fake-global", "distance": 1}]


def test_read_producer_names_preserve_kb_diacritics():
    mod = _load_tek_film_kunye()

    class FakeCreditKB:
        def global_person_match(self, name, role="producer", max_edits=1):
            if name == "Memduh Un" and role == "producer":
                return {"source": "fake-global", "name": "Memduh Ün", "distance": 0}
            return None

        def close(self):
            pass

    class FakeCC:
        CreditKB = FakeCreditKB

        @staticmethod
        def name_match(a, b):
            return str(a).lower().replace("ü", "u") == str(b).lower().replace("ü", "u")

        @staticmethod
        def strict_name_close(a, b):
            return FakeCC.name_match(a, b)

    old_cc = mod._cc
    try:
        mod._cc = FakeCC
        out, changes = mod._canonicalize_read_producers(["Memduh Un"])
    finally:
        mod._cc = old_cc

    assert out == ["Memduh Ün"]
    assert changes == [{"in": "Memduh Un", "out": "Memduh Ün", "source": "fake-global", "distance": 0}]
