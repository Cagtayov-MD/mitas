import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


credit_parse = load_module(
    "credit_parse_under_test", ROOT / "OCR-worktree" / "pdf-mitas" / "credit_parse.py"
)
credit_text_read = load_module(
    "credit_text_read_under_test", ROOT / "scripts" / "credit_text_read.py"
)


def test_cast_editing_assistant_is_not_cast_header():
    assert credit_parse.role_of("CAST") == "CAST"
    assert credit_parse.role_of("CAST/EDITING ASSISTANT") == "Diğer"
    assert credit_parse.role_of("Extras Casting") == "Diğer"


def test_raw_context_gate_drops_crew_names_only():
    raw = [
        "Art Director",
        "GLENN COOLEN",
        "Set Designer",
        "DREW KLASSEN",
        "Draftsman",
        "JASON CLARKE",
        "1st Assistant Art Director",
        "CAPTAIN AHAB",
        "ETHAN HAWKE",
        "CHARLIE COX",
        "Cast/Editing Assistant",
        "EDWARD SAID",
        "Extras Casting",
        "JOSEPH PSAILA",
        "Art Department Buyer",
    ]
    cast = ["JASON CLARKE", "ETHAN HAWKE", "CHARLIE COX", "EDWARD SAID", "JOSEPH PSAILA"]

    assert credit_text_read.filter_cast_by_raw_context(cast, raw) == [
        "ETHAN HAWKE",
        "CHARLIE COX",
    ]


def test_raw_context_gate_keeps_name_with_any_clean_occurrence():
    raw = [
        "Art Director",
        "JASON CLARKE",
        "1st Assistant Art Director",
        "STARRING",
        "JASON CLARKE",
    ]

    assert credit_text_read.filter_cast_by_raw_context(["JASON CLARKE"], raw) == ["JASON CLARKE"]


def test_music_credit_phrase_is_not_a_person(monkeypatch):
    def fake_model_chain():
        return ["fake-qwen"]

    def fake_ollama_json(model, prompt, schema, timeout=180):
        return {
            "yonetmen": [],
            "yapimci": [],
            "oyuncular": ["PERFORMED BY JONSI", "MIXED BY TOM EIMHIRST", "Sally Hawkins"],
        }

    monkeypatch.setattr(credit_text_read, "model_chain", fake_model_chain)
    monkeypatch.setattr(credit_text_read, "_ollama_json", fake_ollama_json)
    monkeypatch.setattr(credit_text_read, "_get_kb", lambda: credit_text_read._NullKB())

    lines = [
        "PERFORMED BY JONSI",
        "MIXED BY TOM EIMHIRST",
        "CAST",
        "MAURA Sally Hawkins",
    ]

    out = credit_text_read.read_credits_auto(lines, "TEST", raw_context_lines=lines)

    assert out["cast"] == ["Sally Hawkins"]
