import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


credit_text_read = load_module(
    "credit_text_read_qwen_source_under_test", ROOT / "scripts" / "credit_text_read.py"
)


def test_llm_input_prefers_raw_ham_over_flattened_kunye():
    temp_base = ROOT / ".pytest_tmp_credit_text_qwen_source"
    temp_base.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_base) as td:
        ocr_dir = Path(td) / "ocr-1"
        ocr_dir.mkdir()
        kunye = ocr_dir / "kunye.txt"
        kunye.write_text("MAURA SALLY HAWKINS\nMOLLY SINEAD MAGUIRE\n", encoding="utf-8")
        (ocr_dir / "ocr_ham.txt").write_text(
            "CAST\n(IN ORDER OF APPEARANCE)\nMAURA Sally Hawkins\nMOLLY Sinead Maguire\n",
            encoding="utf-8",
        )

        lines, source = credit_text_read.load_llm_lines_for_ocr(kunye)

    assert source == "ocr_ham.txt"
    assert "MAURA Sally Hawkins" in lines
    assert "MAURA SALLY HAWKINS" not in lines


def test_read_credits_auto_uses_raw_lines_for_qwen_and_raw_context_for_guard(monkeypatch):
    sent_prompts = []

    def fake_model_chain():
        return ["fake-qwen"]

    def fake_ollama_json(model, prompt, schema, timeout=180):
        sent_prompts.append(prompt)
        return {
            "yonetmen": [],
            "yapimci": [],
            "oyuncular": [
                "Sally Hawkins",
                "Sinead Maguire",
                "Tom Riley",
                "Tina Kellegher",
                "Deirdre Molloy",
                "Jill Murphy",
                "Simon Delaney",
                "Leroy Harris",
            ],
        }

    monkeypatch.setattr(credit_text_read, "model_chain", fake_model_chain)
    monkeypatch.setattr(credit_text_read, "_ollama_json", fake_ollama_json)
    monkeypatch.setattr(credit_text_read, "_get_kb", lambda: credit_text_read._NullKB())

    llm_lines = [
        "CAST",
        "(IN ORDER OF APPEARANCE)",
        "MAURA Sally Hawkins",
        "MOLLY Sinead Maguire",
        "Tom Riley",
        "KAREN Tina Kellegher",
        "Doirdro Molloy",
        "Jill Murphy",
        "Simon Delaney",
        "Leroy Harris",
    ]
    raw_context = llm_lines + ["NIAMH Deirdre Molloy"]

    out = credit_text_read.read_credits_auto(
        llm_lines,
        "SONSUZA KADAR MUTLULAR",
        raw_context_lines=raw_context,
    )

    assert "MAURA Sally Hawkins" in sent_prompts[0]
    assert out["cast"] == [
        "Sally Hawkins",
        "Sinead Maguire",
        "Tom Riley",
        "Tina Kellegher",
        "Deirdre Molloy",
        "Jill Murphy",
        "Simon Delaney",
        "Leroy Harris",
    ]


def test_cast_block_fallback_handles_role_actor_suffix_when_qwen_times_out(monkeypatch):
    def fake_model_chain():
        return ["fake-qwen"]

    def fake_ollama_json(model, prompt, schema, timeout=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr(credit_text_read, "model_chain", fake_model_chain)
    monkeypatch.setattr(credit_text_read, "_ollama_json", fake_ollama_json)
    monkeypatch.setattr(credit_text_read, "_get_kb", lambda: credit_text_read._NullKB())

    lines = [
        "CAST",
        "(IN ORDER OF APPEARANCE)",
        "MAURA Sally Hawkins",
        "MOLLY Sinead Maguire",
        "FREDDIE Tom Riley",
        "KAREN Tina Kellegher",
    ]

    out = credit_text_read.read_credits_auto(lines, "SONSUZA KADAR MUTLULAR", raw_context_lines=lines)

    assert out["cast"][:4] == ["Sally Hawkins", "Sinead Maguire", "Tom Riley", "Tina Kellegher"]


def test_cast_block_fallback_drops_character_and_crew_rows(monkeypatch):
    def fake_model_chain():
        return ["fake-qwen"]

    def fake_ollama_json(model, prompt, schema, timeout=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr(credit_text_read, "model_chain", fake_model_chain)
    monkeypatch.setattr(credit_text_read, "_ollama_json", fake_ollama_json)
    monkeypatch.setattr(credit_text_read, "_get_kb", lambda: credit_text_read._NullKB())

    lines = [
        "CAST",
        "CAPTAIN AHAB",
        "bana uzak John",
        "ETHAN HAWKE",
        "STARBUCK",
        "CHARLIE COX",
        "ISHMAEL",
        "WILLIAM HURT",
        "Draftsman",
        "JASON CLARKE",
        "1st Assistant Art Director",
    ]

    out = credit_text_read.read_credits_auto(lines, "MOBY DICK 2", raw_context_lines=lines)

    assert out["cast"] == ["ETHAN HAWKE", "CHARLIE COX", "WILLIAM HURT"]
