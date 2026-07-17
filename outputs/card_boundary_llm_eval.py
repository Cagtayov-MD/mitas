#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Card-boundary role extraction probe for local LLMs.

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
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(r"E:\MITAS")
OUT_DIR = ROOT / "outputs" / "card_boundary_llm_eval"
OLLAMA = "http://127.0.0.1:11434"
DEFAULT_MODELS = ["gemma4:26b", "qwen3.6:35b-a3b"]


SCHEMA = {
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


PROMPT_FLAT = """Aşağıdaki OCR jenerik satırlarından rol çıkar.

Kurallar:
- DIRECTED BY / YÖNETMEN / DIRECTOR açıkça film yönetmeni ise kişi adını yonetmen'e koy.
- PRODUCED BY / YAPIMCI açıkça asıl yapımcı ise kişi adını yapimci'ye koy.
- PRODUCED AND DIRECTED BY aynı kişi için hem yapimci hem yonetmen demektir.
- STORY BY / SCREENPLAY BY / SCENARIO / SCRIPT / WRITTEN BY altındaki kişileri senaryo_yazar'a koy.
- STARRING / CAST / FEATURING veya oyuncu billing satırlarında görünen gerçek oyuncuları oyuncular'a koy.
- Büyük harfli kişi adı ve altında karakter/rol adı varsa büyük harfli kişi adını oyuncular'a koy, altındaki karakter/rol adını koyma.
- DIRECTOR OF PHOTOGRAPHY, ASSISTANT DIRECTOR, ART DIRECTOR, CASTING DIRECTOR, MUSIC DIRECTOR film yönetmeni değildir.
- PRESENTS / SUNAR yapımcı etiketi değildir.
- PRESENTS / SUNAR kartından hemen sonra gelen kişi-adı kartları açılış oyuncu billing'i sayılır; yapımcı değildir.
- Aynı kişi farklı kartlarda/rollerde tekrar görünürse açık kanıt olan her role konabilir.
- Kişi adlarını OCR'da göründüğü gibi aynen kopyala; harf değiştirme, çeviri/canonicalize etme.
- Sadece OCR'da görünen isimleri kullan, tahmin etme.

Yalnız geçerli JSON döndür:
{"yonetmen": [], "yapimci": [], "senaryo_yazar": [], "oyuncular": [], "ignored": []}

OCR:
%s
"""


PROMPT_CARD = """Aşağıdaki OCR jeneriği frame/kart sınırları korunarak verilmiştir.

ÇOK ÖNEMLİ KURALLAR:
- CARD_BEGIN ile CARD_END arası tek kredi kartıdır. CARD_END sonrası yeni kart başlar.
- Bir rol etiketi sadece kendi kartındaki isimlere uygulanır. Asla sonraki karta taşma.
- Aynı arka plan veya benzer frame aynı kart demek değildir; yazı değiştiyse yeni karttır.
- frame_id sadece kanıt izidir; model görüntü görmüyor ama kart sınırına uymalıdır.
- PRODUCED AND DIRECTED BY kartında görünen kişi hem yapimci hem yonetmen olur.
- SCREENPLAY BY / STORY BY / WRITTEN BY kartındaki kişiler senaryo_yazar olur.
- Büyük harfli kişi adı ve altında karakter/rol adı varsa büyük harfli kişi adını oyuncular'a koy, altındaki karakter/rol adını koyma.
- Bir kartta açık crew rol etiketi yoksa ve kişi/karakter billing düzeni varsa kişi adları oyuncular'dır.
- DIRECTOR OF PHOTOGRAPHY, ASSISTANT DIRECTOR, ART DIRECTOR, CASTING DIRECTOR, MUSIC DIRECTOR film yönetmeni değildir.
- PRESENTS / SUNAR yapımcı etiketi değildir.
- PRESENTS / SUNAR kartından hemen sonra gelen kişi-adı kartları açılış oyuncu billing'i sayılır; yapımcı değildir.
- Aynı kişi farklı kartlarda/rollerde tekrar görünürse açık kanıt olan her role konabilir.
- Kişi adlarını OCR'da göründüğü gibi aynen kopyala; harf değiştirme, çeviri/canonicalize etme.
- Sadece OCR'da görünen isimleri kullan, tahmin etme.

Yalnız geçerli JSON döndür:
{"yonetmen": [], "yapimci": [], "senaryo_yazar": [], "oyuncular": [], "ignored": []}

OCR_CARDS:
%s
"""


CASES = [
    {
        "id": "vahsi_sevgili_boundary_leak",
        "kind": "real_boundary",
        "source": "VAHŞİ SEVGİLİ cikis_fb c_0221/c_0235/c_0255",
        "flat": """Produced and Directed by
KEN RUSSELL
Screenplay by
CHRISTOPHER LOGUE
Based on the book by
H.S. EDE
DOROTHY TUTIN
Sophie Brzeska
SCOTT ANTONY
Henri Gaudier
and
HELEN MIRREN
Gosh Boyle""",
        "card": """CARD_BEGIN frame_id=c_0221
Produced and Directed by
KEN RUSSELL
CARD_END

CARD_BEGIN frame_id=c_0235
Screenplay by
CHRISTOPHER LOGUE
Based on the book by
H.S. EDE
CARD_END

CARD_BEGIN frame_id=c_0255
DOROTHY TUTIN
Sophie Brzeska
CARD_END

CARD_BEGIN frame_id=c_0265
SCOTT ANTONY
Henri Gaudier
and
HELEN MIRREN
Gosh Boyle
CARD_END""",
        "expect": {
            "yonetmen": ["Ken Russell"],
            "yapimci": ["Ken Russell"],
            "senaryo_yazar": ["Christopher Logue"],
            "oyuncular": ["Dorothy Tutin", "Scott Antony", "Helen Mirren"],
        },
        "forbid": {
            "yapimci": ["Dorothy Tutin", "Scott Antony", "Helen Mirren", "Christopher Logue"],
            "yonetmen": ["Dorothy Tutin", "Scott Antony", "Helen Mirren", "Christopher Logue"],
            "senaryo_yazar": ["H.S. Ede"],
            "oyuncular": [
                "Ken Russell",
                "Christopher Logue",
                "H.S. Ede",
                "Sophie Brzeska",
                "Henri Gaudier",
                "Gosh Boyle",
            ],
        },
    },
    {
        "id": "vahsi_sevgili_grid_cast",
        "kind": "real_cast_grid",
        "source": "VAHŞİ SEVGİLİ cikis_fb c_0286",
        "flat": """LINDSAY KEMP
Angus Corky
MICHAEL GOUGH
M. Gaudier
JOHN JUSTIN
Lionel Shaw
AUBREY RICHARDS
Mayor
PETER VAUGHAN
Museum Attendant""",
        "card": """CARD_BEGIN frame_id=c_0286
LINDSAY KEMP
Angus Corky
MICHAEL GOUGH
M. Gaudier
JOHN JUSTIN
Lionel Shaw
AUBREY RICHARDS
Mayor
PETER VAUGHAN
Museum Attendant
CARD_END""",
        "expect": {
            "oyuncular": ["Lindsay Kemp", "Michael Gough", "John Justin", "Aubrey Richards", "Peter Vaughan"],
        },
        "forbid": {
            "oyuncular": ["Angus Corky", "M. Gaudier", "Lionel Shaw", "Mayor", "Museum Attendant"],
            "yonetmen": ["Lindsay Kemp", "Michael Gough", "John Justin", "Aubrey Richards", "Peter Vaughan"],
            "yapimci": ["Lindsay Kemp", "Michael Gough", "John Justin", "Aubrey Richards", "Peter Vaughan"],
        },
    },
    {
        "id": "assistant_director_trap",
        "kind": "trap",
        "source": "Assistant Director should not become director/cast/producer",
        "flat": """First Assistant Director
TOM CONNORS
Unit Production Manager
BILL COKER""",
        "card": """CARD_BEGIN frame_id=test_001
First Assistant Director
TOM CONNORS
Unit Production Manager
BILL COKER
CARD_END""",
        "expect": {},
        "forbid": {
            "yonetmen": ["Tom Connors", "Bill Coker"],
            "oyuncular": ["Tom Connors", "Bill Coker"],
            "yapimci": ["Tom Connors", "Bill Coker"],
        },
    },
    {
        "id": "presents_not_producer",
        "kind": "opening_billing",
        "source": "PRESENTS plus actor cards",
        "flat": """UNIVERSAL INTERNATIONAL PRESENTS
ROCK HUDSON
BARBARA RUSH
MORRIS ANKRUM
Directed by
GEORGE SHERMAN""",
        "card": """CARD_BEGIN frame_id=test_010
UNIVERSAL INTERNATIONAL PRESENTS
CARD_END

CARD_BEGIN frame_id=test_011
ROCK HUDSON
BARBARA RUSH
MORRIS ANKRUM
CARD_END

CARD_BEGIN frame_id=test_012
Directed by
GEORGE SHERMAN
CARD_END""",
        "expect": {
            "yonetmen": ["George Sherman"],
            "oyuncular": ["Rock Hudson", "Barbara Rush", "Morris Ankrum"],
        },
        "forbid": {
            "yapimci": ["Universal International", "Rock Hudson", "Barbara Rush", "Morris Ankrum"],
        },
    },
    {
        "id": "dual_role_across_cards",
        "kind": "dual_role",
        "source": "Actor and director in separate cards",
        "flat": """STARRING
DENZEL WASHINGTON
VIOLA DAVIS
Directed by
DENZEL WASHINGTON""",
        "card": """CARD_BEGIN frame_id=test_020
STARRING
DENZEL WASHINGTON
VIOLA DAVIS
CARD_END

CARD_BEGIN frame_id=test_021
Directed by
DENZEL WASHINGTON
CARD_END""",
        "expect": {
            "yonetmen": ["Denzel Washington"],
            "oyuncular": ["Denzel Washington", "Viola Davis"],
        },
        "forbid": {"yapimci": ["Denzel Washington", "Viola Davis"]},
    },
    {
        "id": "director_of_photography_trap",
        "kind": "trap",
        "source": "Director of Photography should not become director",
        "flat": """Director of Photography
CHARLES LANG, Jr.
Technicolor Color Consultant
RICHARD MUELLER""",
        "card": """CARD_BEGIN frame_id=test_030
Director of Photography
CHARLES LANG, Jr.
Technicolor Color Consultant
RICHARD MUELLER
CARD_END""",
        "expect": {},
        "forbid": {
            "yonetmen": ["Charles Lang", "Richard Mueller"],
            "oyuncular": ["Charles Lang", "Richard Mueller"],
            "yapimci": ["Charles Lang", "Richard Mueller"],
        },
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


def normalize_output(data: dict) -> dict[str, list[str]]:
    return {
        role: [str(x).strip() for x in data.get(role, []) if str(x).strip()]
        for role in ["yonetmen", "yapimci", "senaryo_yazar", "oyuncular", "ignored"]
    }


def score(case: dict, output: dict) -> dict:
    missing: list[str] = []
    wrong: list[str] = []
    for role, names in case.get("expect", {}).items():
        for name in names:
            if not contains_name(output.get(role, []), name):
                missing.append(f"{role}:{name}")
    for role, names in case.get("forbid", {}).items():
        for name in names:
            if contains_name(output.get(role, []), name):
                wrong.append(f"{role}:{name}")
    return {"ok": not missing and not wrong, "missing": missing, "wrong": wrong}


def ollama_generate(model: str, prompt: str, timeout: int) -> tuple[dict, str, float, str]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": SCHEMA,
        "keep_alive": "10m",
        "options": {
            "temperature": 0,
            "top_p": 1,
            "repeat_penalty": 1.12,
            "num_ctx": 8192,
            "num_predict": 1000,
        },
    }
    req = urllib.request.Request(
        OLLAMA + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_obj = json.loads(resp.read().decode("utf-8"))
        elapsed = time.perf_counter() - started
        raw_text = raw_obj.get("response", "")
        try:
            data = json.loads(raw_text)
        except Exception:
            data = {}
        return data, raw_text, elapsed, str(raw_obj.get("done_reason") or "")
    except (TimeoutError, urllib.error.URLError) as exc:
        elapsed = time.perf_counter() - started
        return {}, "", elapsed, f"ERROR:{type(exc).__name__}:{exc}"
    except Exception as exc:  # noqa: BLE001 - diagnostic harness should report model failures.
        elapsed = time.perf_counter() - started
        return {}, "", elapsed, f"ERROR:{type(exc).__name__}:{exc}"


def run(models: list[str], variants: list[str], cases: list[dict], timeout: int) -> list[dict]:
    rows: list[dict] = []
    for case in cases:
        for variant in variants:
            prompt = (PROMPT_CARD if variant == "card" else PROMPT_FLAT) % case[variant]
            for model in models:
                data, raw_text, elapsed, done_reason = ollama_generate(model, prompt, timeout)
                output = normalize_output(data)
                result = score(case, output)
                row = {
                    "model": model,
                    "case_id": case["id"],
                    "kind": case["kind"],
                    "source": case["source"],
                    "variant": variant,
                    "elapsed_sec": round(elapsed, 2),
                    "ok": result["ok"],
                    "missing": result["missing"],
                    "wrong": result["wrong"],
                    "output": output,
                    "raw_response": raw_text,
                    "done_reason": done_reason,
                }
                rows.append(row)
                print(
                    f"{model} {case['id']} [{variant}] ok={row['ok']} "
                    f"missing={len(row['missing'])} wrong={len(row['wrong'])} "
                    f"{row['elapsed_sec']}s",
                    flush=True,
                )
    return rows


def write_outputs(rows: list[dict], out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "card_boundary_llm_eval_results.json"
    csv_path = out_dir / "card_boundary_llm_eval_results.csv"
    md_path = out_dir / "card_boundary_llm_eval_report.md"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "variant",
                "case_id",
                "kind",
                "source",
                "elapsed_sec",
                "ok",
                "missing",
                "wrong",
                "yonetmen",
                "yapimci",
                "senaryo_yazar",
                "oyuncular",
                "ignored",
                "done_reason",
            ],
        )
        writer.writeheader()
        for row in rows:
            out = row["output"]
            writer.writerow(
                {
                    **{k: row[k] for k in ["model", "variant", "case_id", "kind", "source", "elapsed_sec", "ok", "done_reason"]},
                    "missing": "; ".join(row["missing"]),
                    "wrong": "; ".join(row["wrong"]),
                    "yonetmen": "; ".join(out["yonetmen"]),
                    "yapimci": "; ".join(out["yapimci"]),
                    "senaryo_yazar": "; ".join(out["senaryo_yazar"]),
                    "oyuncular": "; ".join(out["oyuncular"]),
                    "ignored": "; ".join(out["ignored"]),
                }
            )

    lines = ["# Card Boundary LLM Eval", ""]
    models = sorted({r["model"] for r in rows})
    variants = ["flat", "card"]
    for model in models:
        lines.append(f"## {model}")
        lines.append("")
        for variant in variants:
            subset = [r for r in rows if r["model"] == model and r["variant"] == variant]
            if not subset:
                continue
            ok = sum(1 for r in subset if r["ok"])
            avg = sum(r["elapsed_sec"] for r in subset) / max(1, len(subset))
            lines.append(f"### {variant}")
            lines.append(f"- Passed: {ok}/{len(subset)}")
            lines.append(f"- Failed: {len(subset) - ok}/{len(subset)}")
            lines.append(f"- Avg time: {avg:.2f}s")
            lines.append("")
            for row in subset:
                mark = "OK" if row["ok"] else "FAIL"
                out = row["output"]
                lines.append(f"#### {mark} {row['case_id']}")
                lines.append(f"- Director: {', '.join(out['yonetmen']) or '-'}")
                lines.append(f"- Producer: {', '.join(out['yapimci']) or '-'}")
                lines.append(f"- Writer: {', '.join(out['senaryo_yazar']) or '-'}")
                lines.append(f"- Cast: {', '.join(out['oyuncular']) or '-'}")
                if row["missing"]:
                    lines.append(f"- Missing: {', '.join(row['missing'])}")
                if row["wrong"]:
                    lines.append(f"- Wrong: {', '.join(row['wrong'])}")
                if row["done_reason"].startswith("ERROR:"):
                    lines.append(f"- Error: {row['done_reason']}")
                lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"JSON: {json_path}")
    print(f"CSV : {csv_path}")
    print(f"MD  : {md_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--variants", default="flat,card")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--case", action="append", dest="case_ids", default=[])
    parser.add_argument("--quick", action="store_true", help="Run a short representative subset.")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args()

    models = [x.strip() for x in args.models.split(",") if x.strip()]
    variants = [x.strip() for x in args.variants.split(",") if x.strip()]
    cases = CASES
    if args.quick:
        quick_ids = {
            "vahsi_sevgili_boundary_leak",
            "vahsi_sevgili_grid_cast",
            "assistant_director_trap",
            "dual_role_across_cards",
        }
        cases = [c for c in cases if c["id"] in quick_ids]
    if args.case_ids:
        wanted = set(args.case_ids)
        cases = [c for c in cases if c["id"] in wanted]
    rows = run(models, variants, cases, args.timeout)
    write_outputs(rows, Path(args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
