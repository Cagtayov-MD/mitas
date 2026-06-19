import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


pipe_pdf = load_module("pipe_pdf_under_test", ROOT / "scripts" / "_pipe_pdf.py")


def test_video_credits_replace_flattened_parser_cast_and_roles():
    parser_cast = ["PERFORMED BY JONSI", "JASON CLARKE", "ETHAN HAWKE"]
    parser_crew = [
        ("Yönetmen", ["OLD WRONG DIRECTOR"]),
        ("Yapımcı", ["OLD WRONG PRODUCER"]),
        ("Sanat Yönetmeni", ["JASON CLARKE"]),
    ]
    video_credits = {
        "cast": ["ETHAN HAWKE", "WILLIAM HURT"],
        "yonetmen": [],
        "yapimci": ["REAL PRODUCER"],
    }

    cast, crew = pipe_pdf._apply_video_credits_authoritative(
        parser_cast, parser_crew, video_credits, dizi=False
    )

    assert cast == ["ETHAN HAWKE", "WILLIAM HURT"]
    assert ("Yönetmen", ["OLD WRONG DIRECTOR"]) not in crew
    assert ("Yapımcı", ["OLD WRONG PRODUCER"]) not in crew
    assert ("Yapımcı", ["REAL PRODUCER"]) in crew
    assert ("Sanat Yönetmeni", ["JASON CLARKE"]) in crew


def test_video_credits_empty_cast_is_authoritative_blank():
    cast, crew = pipe_pdf._apply_video_credits_authoritative(
        ["PERFORMED BY JONSI", "MIXED BY TOM EIMHIRST"],
        [("Yönetmen", ["OLD WRONG DIRECTOR"])],
        {"cast": [], "yonetmen": [], "yapimci": []},
        dizi=False,
    )

    assert cast == []
    assert crew == []
