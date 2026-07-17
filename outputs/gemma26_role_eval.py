#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gemma4:26B role extraction probe for MITAS credit snippets.

Independent diagnostic. It calls local Ollama only and does not modify the
production pipeline.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import unicodedata
import urllib.request
from pathlib import Path


ROOT = Path(r"E:\MITAS")
OUT_DIR = ROOT / "outputs" / "gemma26_role_eval"
MODEL = "gemma4:26b"
OLLAMA = "http://127.0.0.1:11434"


SCHEMA_CURRENT = {
    "type": "object",
    "properties": {
        "yonetmen": {"type": "array", "items": {"type": "string"}},
        "yapimci": {"type": "array", "items": {"type": "string"}},
        "oyuncular": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["yonetmen", "yapimci", "oyuncular"],
}

SCHEMA_WITH_WRITER = {
    "type": "object",
    "properties": {
        "yonetmen": {"type": "array", "items": {"type": "string"}},
        "yapimci": {"type": "array", "items": {"type": "string"}},
        "senaryo_yazar": {"type": "array", "items": {"type": "string"}},
        "oyuncular": {"type": "array", "items": {"type": "string"}},
        "ignored": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["yonetmen", "yapimci", "senaryo_yazar", "oyuncular", "ignored"],
}


PROMPT_CURRENT = """Aşağıdaki OCR jenerik satırlarından yalnız 3 alan çıkar.

Kurallar:
- DIRECTED BY / YÖNETMEN / DIRECTOR açıkça film yönetmeni ise kişi adını yonetmen'e koy.
- PRODUCED BY / YAPIMCI açıkça asıl yapımcı ise kişi adını yapimci'ye koy.
- STARRING / CAST / FEATURING veya açılış oyuncu billing satırlarında görünen gerçek oyuncuları oyuncular'a koy.
- STORY BY / SCREENPLAY BY / SCENARIO / SCRIPT / WRITTEN BY altındaki kişiler oyuncu değildir; bu 3 alanın hiçbirine koyma.
- DIRECTOR OF PHOTOGRAPHY, ASSISTANT DIRECTOR, ART DIRECTOR, CASTING DIRECTOR, MUSIC DIRECTOR film yönetmeni değildir; yonetmen'e koyma.
- PRESENTS / SUNAR yapımcı etiketi değildir; hemen yanındaki yıldız oyuncu olabilir, yapimci'ye koyma.
- Aynı kişi hem oyuncu hem yönetmen/yazar olabilir; açık rol kanıtı varsa ilgili her alana ayrı ayrı koy.
- Sadece satırlarda görünen isimleri kullan, tahmin etme.

Yalnız geçerli JSON döndür:
{"yonetmen": [], "yapimci": [], "oyuncular": []}

OCR:
%s
"""

PROMPT_WITH_WRITER = """Aşağıdaki OCR jenerik satırlarını role göre ayır.

Kurallar:
- DIRECTED BY / YÖNETMEN / DIRECTOR açıkça film yönetmeni ise kişi adını yonetmen'e koy.
- PRODUCED BY / YAPIMCI açıkça asıl yapımcı ise kişi adını yapimci'ye koy.
- STORY BY / SCREENPLAY BY / SCENARIO / SCRIPT / WRITTEN BY altındaki kişileri senaryo_yazar'a koy.
- STARRING / CAST / FEATURING veya açılış oyuncu billing satırlarında görünen gerçek oyuncuları oyuncular'a koy.
- DIRECTOR OF PHOTOGRAPHY, ASSISTANT DIRECTOR, ART DIRECTOR, CASTING DIRECTOR, MUSIC DIRECTOR film yönetmeni değildir; ignored'a koy veya hiç koyma.
- PRESENTS / SUNAR yapımcı etiketi değildir; hemen yanındaki yıldız oyuncu olabilir, yapimci'ye koyma.
- Aynı kişi hem oyuncu hem yönetmen/yazar olabilir; açık rol kanıtı varsa ilgili her alana ayrı ayrı koy.
- Sadece satırlarda görünen isimleri kullan, tahmin etme.

Yalnız geçerli JSON döndür:
{"yonetmen": [], "yapimci": [], "senaryo_yazar": [], "oyuncular": [], "ignored": []}

OCR:
%s
"""


CASES = [
    {
        "id": "problem_hans_scenario",
        "kind": "problem",
        "source": "NE TREN VAR NE DE UCAK raw OCR",
        "text": """Scenario
Hans Heesen
Jos Stelling
Director of Photography
Goert Giltaij""",
        "expect": {"senaryo_yazar": ["Hans Heesen", "Jos Stelling"]},
        "forbid": {"oyuncular": ["Hans Heesen", "Jos Stelling"], "yonetmen": ["Hans Heesen", "Goert Giltaij"]},
    },
    {
        "id": "problem_les_story",
        "kind": "problem",
        "source": "KAN DAVASININ SONU raw OCR",
        "text": """BRAD DEXTER
BRIAN HUTTON
ZIVA RODANN
VAL AVERY
WALTER SANDE
Screenplay by
JAMES POE
Story by
LES CRUTCHFIELD
Director of Photography
CHARLES LANG, Jr.
Directed by
JOHN STURGES""",
        "expect": {
            "yonetmen": ["John Sturges"],
            "senaryo_yazar": ["James Poe", "Les Crutchfield"],
            "oyuncular": ["Brad Dexter", "Brian Hutton", "Ziva Rodann", "Val Avery", "Walter Sande"],
        },
        "forbid": {"oyuncular": ["Les Crutchfield", "James Poe", "Charles Lang"], "yonetmen": ["Charles Lang"]},
    },
    {
        "id": "problem_geoffrey_produced",
        "kind": "problem",
        "source": "BIR AV PARTISI raw OCR",
        "text": """JAMES MASON
EDWARD FOX
DOROTHY TUTIN
JOHN GIELGUD
ROBERT HARDY
Screenplay by
JULIAN BOND
Produced by
GEOFFREY REEVE
Directed by
ALAN BRIDGES""",
        "expect": {
            "yonetmen": ["Alan Bridges"],
            "yapimci": ["Geoffrey Reeve"],
            "senaryo_yazar": ["Julian Bond"],
            "oyuncular": ["James Mason", "Edward Fox", "Dorothy Tutin", "John Gielgud", "Robert Hardy"],
        },
        "forbid": {"oyuncular": ["Geoffrey Reeve", "Julian Bond"], "yonetmen": ["Geoffrey Reeve"]},
    },
    {
        "id": "trap_assistant_director",
        "kind": "trap",
        "source": "BÜYÜK YARIŞ 2 conflict pattern",
        "text": """BILL COKER
First Assistant Director
TOM CONNORS
Unit Production Manager
BILL COKER""",
        "expect": {},
        "forbid": {"yonetmen": ["Tom Connors"], "oyuncular": ["Tom Connors"], "yapimci": ["Tom Connors"]},
    },
    {
        "id": "trap_director_of_photography",
        "kind": "trap",
        "source": "KAN DAVASININ SONU conflict pattern",
        "text": """Director of Photography
CHARLES LANG, Jr.
Technicolor Color Consultant
RICHARD MUELLER""",
        "expect": {},
        "forbid": {"yonetmen": ["Charles Lang", "Richard Mueller"], "oyuncular": ["Charles Lang", "Richard Mueller"]},
    },
    {
        "id": "trap_presents_billing",
        "kind": "control",
        "source": "classic opening billing",
        "text": """UNIVERSAL INTERNATIONAL PRESENTS
ROCK HUDSON
BARBARA RUSH
MORRIS ANKRUM
Directed by
GEORGE SHERMAN""",
        "expect": {"yonetmen": ["George Sherman"], "oyuncular": ["Rock Hudson", "Barbara Rush", "Morris Ankrum"]},
        "forbid": {"yapimci": ["Rock Hudson", "Barbara Rush", "Universal International"]},
    },
    {
        "id": "clean_directed_by_denzel",
        "kind": "control",
        "source": "synthetic direct label",
        "text": """Directed by
DENZEL WASHINGTON""",
        "expect": {"yonetmen": ["Denzel Washington"]},
        "forbid": {"oyuncular": ["Denzel Washington"], "yapimci": ["Denzel Washington"]},
    },
    {
        "id": "clean_ocr_misspelled_directed",
        "kind": "control",
        "source": "synthetic OCR misspelling",
        "text": """DIRECTED BY
DENZIL WASHINGTOM""",
        "expect": {"yonetmen": ["Denzil Washingtom"]},
        "forbid": {"oyuncular": ["Denzil Washingtom"], "yapimci": ["Denzil Washingtom"]},
    },
    {
        "id": "dual_actor_director",
        "kind": "control",
        "source": "dual role synthetic",
        "text": """STARRING
DENZEL WASHINGTON
VIOLA DAVIS
Directed by
DENZEL WASHINGTON""",
        "expect": {"yonetmen": ["Denzel Washington"], "oyuncular": ["Denzel Washington", "Viola Davis"]},
        "forbid": {"yapimci": ["Denzel Washington"]},
    },
    {
        "id": "dual_actor_writer",
        "kind": "control",
        "source": "dual role synthetic",
        "text": """STARRING
JOHN CLEESE
JAMIE LEE CURTIS
Written by
JOHN CLEESE
Directed by
CHARLES CRICHTON""",
        "expect": {
            "yonetmen": ["Charles Crichton"],
            "senaryo_yazar": ["John Cleese"],
            "oyuncular": ["John Cleese", "Jamie Lee Curtis"],
        },
        "forbid": {"yapimci": ["John Cleese"], "yonetmen": ["John Cleese"]},
    },
    {
        "id": "clean_produced_and_directed",
        "kind": "control",
        "source": "VAHŞİ SEVGİLİ style",
        "text": """Screenplay by
CHRISTOPHER LOGUE
KEN RUSSELL
Produced and Directed by
KEN RUSSELL
DOROTHY TUTIN
SCOTT ANTONY""",
        "expect": {
            "yonetmen": ["Ken Russell"],
            "yapimci": ["Ken Russell"],
            "senaryo_yazar": ["Christopher Logue", "Ken Russell"],
            "oyuncular": ["Dorothy Tutin", "Scott Antony"],
        },
        "forbid": {
            "oyuncular": ["Christopher Logue", "Ken Russell"],
            "yapimci": ["Dorothy Tutin", "Scott Antony"],
        },
    },
    {
        "id": "clean_a_film_by",
        "kind": "control",
        "source": "director idiom",
        "text": """A JOHN MCTIERNAN FILM
BRUCE WILLIS
ALAN RICKMAN
Produced by
LAWRENCE GORDON""",
        "expect": {
            "yonetmen": ["John Mctiernan"],
            "yapimci": ["Lawrence Gordon"],
            "oyuncular": ["Bruce Willis", "Alan Rickman"],
        },
        "forbid": {"oyuncular": ["John Mctiernan"], "yapimci": ["John Mctiernan"]},
    },
]


def fold(text: str) -> str:
    text = (text or "").replace("ı", "i").replace("İ", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def aliases(name: str) -> set[str]:
    base = fold(name)
    out = {base}
    toks = base.split()
    if len(toks) >= 2:
        out.add(" ".join(toks[:2]))
        out.add(" ".join(toks[-2:]))
    return {x for x in out if x}


def contains_name(values: list[str], name: str) -> bool:
    vals = [fold(v) for v in values or []]
    for val in vals:
        for alias in aliases(name):
            if alias and (alias == val or alias in val or val in alias):
                return True
    return False


def ollama_generate(prompt: str, schema: dict, timeout: int) -> tuple[dict, str, float, dict]:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": "10m",
        "options": {
            "temperature": 0,
            "top_p": 1,
            "repeat_penalty": 1.12,
            "num_ctx": 8192,
            "num_predict": 900,
        },
    }
    started = time.perf_counter()
    req = urllib.request.Request(
        OLLAMA + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw_obj = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - started
    raw_text = raw_obj.get("response", "")
    try:
        data = json.loads(raw_text)
    except Exception:
        data = {}
    return data, raw_text, elapsed, raw_obj


def normalize_output(data: dict) -> dict[str, list[str]]:
    return {
        "yonetmen": [str(x).strip() for x in data.get("yonetmen", []) if str(x).strip()],
        "yapimci": [str(x).strip() for x in data.get("yapimci", []) if str(x).strip()],
        "senaryo_yazar": [str(x).strip() for x in data.get("senaryo_yazar", []) if str(x).strip()],
        "oyuncular": [str(x).strip() for x in data.get("oyuncular", []) if str(x).strip()],
        "ignored": [str(x).strip() for x in data.get("ignored", []) if str(x).strip()],
    }


def score(case: dict, output: dict, mode: str) -> dict:
    missing = []
    wrong = []
    expect = case.get("expect", {})
    forbid = case.get("forbid", {})
    for role, names in expect.items():
        if mode == "current_3field" and role == "senaryo_yazar":
            continue
        for name in names:
            if not contains_name(output.get(role, []), name):
                missing.append(f"{role}:{name}")
    for role, names in forbid.items():
        for name in names:
            if contains_name(output.get(role, []), name):
                wrong.append(f"{role}:{name}")
    ok = not missing and not wrong
    return {"ok": ok, "missing": missing, "wrong": wrong}


def run(timeout: int) -> list[dict]:
    modes = [
        ("current_3field", PROMPT_CURRENT, SCHEMA_CURRENT),
        ("with_writer", PROMPT_WITH_WRITER, SCHEMA_WITH_WRITER),
    ]
    rows = []
    for case in CASES:
        for mode, prompt_tmpl, schema in modes:
            prompt = prompt_tmpl % case["text"]
            data, raw_text, elapsed, raw_obj = ollama_generate(prompt, schema, timeout)
            output = normalize_output(data)
            result = score(case, output, mode)
            rows.append(
                {
                    "case_id": case["id"],
                    "kind": case["kind"],
                    "source": case["source"],
                    "mode": mode,
                    "elapsed_sec": round(elapsed, 2),
                    "ok": result["ok"],
                    "missing": result["missing"],
                    "wrong": result["wrong"],
                    "output": output,
                    "raw_response": raw_text,
                    "done_reason": raw_obj.get("done_reason"),
                }
            )
            print(
                f"{case['id']} [{mode}] ok={result['ok']} "
                f"missing={len(result['missing'])} wrong={len(result['wrong'])} "
                f"{round(elapsed, 1)}s",
                flush=True,
            )
    return rows


def write_outputs(rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "gemma26_role_eval_results.json"
    csv_path = OUT_DIR / "gemma26_role_eval_results.csv"
    md_path = OUT_DIR / "gemma26_role_eval_report.md"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "kind",
                "source",
                "mode",
                "elapsed_sec",
                "ok",
                "missing",
                "wrong",
                "yonetmen",
                "yapimci",
                "senaryo_yazar",
                "oyuncular",
                "ignored",
            ],
        )
        writer.writeheader()
        for row in rows:
            out = row["output"]
            writer.writerow(
                {
                    **{k: row[k] for k in ["case_id", "kind", "source", "mode", "elapsed_sec", "ok"]},
                    "missing": "; ".join(row["missing"]),
                    "wrong": "; ".join(row["wrong"]),
                    "yonetmen": "; ".join(out["yonetmen"]),
                    "yapimci": "; ".join(out["yapimci"]),
                    "senaryo_yazar": "; ".join(out["senaryo_yazar"]),
                    "oyuncular": "; ".join(out["oyuncular"]),
                    "ignored": "; ".join(out["ignored"]),
                }
            )
    lines = ["# Gemma4 26B Role Eval", ""]
    for mode in ["current_3field", "with_writer"]:
        subset = [r for r in rows if r["mode"] == mode]
        ok = sum(1 for r in subset if r["ok"])
        lines.append(f"## {mode}")
        lines.append("")
        lines.append(f"- Passed: {ok}/{len(subset)}")
        lines.append(f"- Failed: {len(subset) - ok}/{len(subset)}")
        lines.append("")
        for row in subset:
            mark = "OK" if row["ok"] else "FAIL"
            out = row["output"]
            lines.append(f"### {mark} {row['case_id']}")
            lines.append(f"- Source: {row['source']}")
            lines.append(f"- Time: {row['elapsed_sec']}s")
            lines.append(f"- Director: {', '.join(out['yonetmen']) or '-'}")
            lines.append(f"- Producer: {', '.join(out['yapimci']) or '-'}")
            if mode == "with_writer":
                lines.append(f"- Writer: {', '.join(out['senaryo_yazar']) or '-'}")
            lines.append(f"- Cast: {', '.join(out['oyuncular']) or '-'}")
            if row["missing"]:
                lines.append(f"- Missing: {', '.join(row['missing'])}")
            if row["wrong"]:
                lines.append(f"- Wrong: {', '.join(row['wrong'])}")
            lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"JSON: {json_path}")
    print(f"CSV : {csv_path}")
    print(f"MD  : {md_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--rescore-existing", action="store_true")
    args = parser.parse_args()
    if args.rescore_existing:
        existing = OUT_DIR / "gemma26_role_eval_results.json"
        rows = json.loads(existing.read_text(encoding="utf-8"))
        case_by_id = {case["id"]: case for case in CASES}
        for row in rows:
            result = score(case_by_id[row["case_id"]], row["output"], row["mode"])
            row["ok"] = result["ok"]
            row["missing"] = result["missing"]
            row["wrong"] = result["wrong"]
    else:
        rows = run(args.timeout)
    write_outputs(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
