import glob
import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = r"E:\MITAS\Database"


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


# ─────────── BAĞIMSIZ-KANIT KAPISI (2026-07-10, task_61e2ea2d) — gerçek-film kanıtı ───────────
# test_raw_context_gate_drops_crew_names_only (yukarıda) ETHAN HAWKE desenini (etiketle arasına
# cast-listesiyle ilgisiz bir dolgu satırı giren isim) senkron olarak sabitliyor. Aşağıdaki 2 test
# aynı fix'in GERÇEK filmlerde regresyona yol AÇMADIĞINI ve gerçekten bir isim KURTARDIĞINI
# donduruyor -- bkz filter_cast_by_raw_context docstring'i. Database/ repo-dışı/gitignored
# olduğundan klasör yoksa atlanır.

def _ocr_kunye(film_dir):
    hits = glob.glob(os.path.join(film_dir, "ocr", "ocr-*", "kunye.txt"))
    return hits[0] if hits else None


def test_kabakcigin_morgan_navarro_stays_dropped_real_data():
    """DONMUS KANIT: Bağımsız-kanıt kapısının basit ilk denemesi (yalnız "i-1 bağlantılı mı") bu
    filmde REGRESE OLUYORDU -- MORGAN NAVARRO 13 ham-tekrarın 10'unda "Collaborateurs au scénario"
    etiketiyle arasına bağımsız bir yönetmen-kredisi (CLAUDE BARRAS, scroll-OCR kart-geçiş gürültüsü)
    giriyor, ETHAN HAWKE/CAPTAIN AHAB deseniyle şekilce ayırt edilemez hale geliyordu. Uygulanan
    2-geçişli çözüm (bu ADIN başka bir tekrarda BAĞIMSIZ doğrudan kanıtı var mı) onu doğru şekilde
    crew saymaya devam ediyor -- bu test gelecekte biri yalnız sentetik testi geçirmek için pencereyi
    yeniden gevşetirse fark ettirsin."""
    film_dir = os.path.join(DATABASE, "KABAKÇIĞIN HAYATI 2016-1084-1-0000-90-1")
    ocr = _ocr_kunye(film_dir)
    if not ocr:
        print("  SKIP  test_kabakcigin_morgan_navarro_stays_dropped_real_data (Database/KABAKCIGIN bulunamadi)")
        return
    raw = credit_text_read.load_raw_context_for_ocr(ocr)
    result = credit_text_read.filter_cast_by_raw_context(
        ["MORGAN NAVARRO", "NATACHA VARGA-KOUTCHOUMOV"], raw
    )
    assert "MORGAN NAVARRO" not in result, "KABAKCIGIN: MORGAN NAVARRO (gercek senaryo-ortagi) crew sayilip DUSMELI"
    assert "NATACHA VARGA-KOUTCHOUMOV" in result, "KABAKCIGIN: kontrol ismi yeni-DUSMEMELI"


def test_saskin_reklamci_pierre_richard_rescued_real_data():
    """DONMUS KANIT: PIERRE RICHARD'ın ham OCR'daki tek 2 görünümü de bir yazar-kredisine
    ("Scenario et adaptation de ANDRE RUELLAN ET PIERRE RICHARD") 2-satır-geriden bağlanıyor;
    fix-öncesi kod onu tamamen düşürüyordu (ratio=1.0). Bağımsız-kanıt kapısı onu artık kurtarıyor
    çünkü hiçbir tekrarında doğrudan/gürültüsüz crew-kanıtı YOK -- ve bu bağımsız olarak DOĞRU: ham
    OCR'da AYRI bir "AVEC / P ERRE / RICHARD" (starring-kart, MARIE CHRISTINE BARRAULT'la birlikte)
    kanıtı var (mevcut ad-eşleştirme OCR'ın "PIERRE"yi "P ERRE" diye bölmesi yüzünden bunu ayrıca
    yakalayamıyor -- ayrı, bu fix'in kapsamı dışı bir ad-eşleştirme kısıtı)."""
    film_dir = os.path.join(DATABASE, "ŞAŞKIN REKLAMCI 1970-0076-1-0000-00-1")
    ocr = _ocr_kunye(film_dir)
    if not ocr:
        print("  SKIP  test_saskin_reklamci_pierre_richard_rescued_real_data (Database/SASKIN REKLAMCI bulunamadi)")
        return
    raw = credit_text_read.load_raw_context_for_ocr(ocr)
    result = credit_text_read.filter_cast_by_raw_context(["PIERRE RICHARD"], raw)
    assert "PIERRE RICHARD" in result, "SASKIN REKLAMCI: PIERRE RICHARD fix-sonrasi hayatta kalmali"
