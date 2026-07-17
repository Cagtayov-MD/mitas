#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent role-block probe for credit OCR output.

This is a diagnostic harness only. It reads existing MITAS OCR artifacts and
does not call or modify the production pipeline.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(r"E:\MITAS")

CASES = [
    {
        "id": "1999-0430-1-0000-00-1",
        "title": "NE TREN VAR NE DE UÇAK",
        "folder": ROOT / "Database" / "NE TREN VAR NE DE UÇAK 1999-0430-1-0000-00-1",
        "watch": ["Hans Heesen", "Jos Stelling"],
    },
    {
        "id": "2017-1057-1-0000-90-1",
        "title": "KAN DAVASININ SONU",
        "folder": ROOT / "Database" / "KAN DAVASININ SONU 2017-1057-1-0000-90-1",
        "watch": ["Les Crutchfield", "James Poe", "John Sturges"],
    },
    {
        "id": "1985-0252-1-0000-00-1",
        "title": "BİR AV PARTİSİ",
        "folder": ROOT / "Database" / "BİR AV PARTİSİ 1985-0252-1-0000-00-1",
        "watch": ["Geoffrey Reeve", "Alan Bridges", "Julian Bond"],
    },
]


DIRECTOR_HEADS = (
    "DIRECTED BY",
    "YONETMEN",
    "YONETEN",
    "DIRECTOR",
    "A FILM BY",
    "FILM BY",
    "REGIE",
    "REALISE PAR",
    "UN FILM DE",
)
PRODUCER_HEADS = (
    "PRODUCED BY",
    "PRODUCER",
    "YAPIMCI",
    "YAPIM",
)
WRITER_HEADS = (
    "SCREENPLAY BY",
    "SCREENPLAY",
    "STORY BY",
    "STORY",
    "SCENARIO",
    "SCRIPT",
    "WRITTEN BY",
    "BASED ON THE NOVEL BY",
    "BASED ON",
)
CAST_HEADS = (
    "STARRING",
    "FEATURING",
    "CAST",
    "OYUNCULAR",
    "OYNAYANLAR",
    "WITH",
)
STOP_HEADS = (
    "DIRECTOR OF PHOTOGRAPHY",
    "DIRECTOF OF PHOTOGZAPHY",
    "ASSISTANT DIRECTOR",
    "ASSOCIATE PRODUCER",
    "EXECUTIVE PRODUCER",
    "PRODUCTION DESIGNER",
    "PRODUCTION CO-ORDINATOR",
    "PRODUCTION COORDINATOR",
    "PRODUCTION MANAGER",
    "MUSIC",
    "MUSIC COMPOSED",
    "ORIGINAL MUSIC",
    "COSTUME",
    "MAKEUP",
    "MAKE-UP",
    "SET DECORATION",
    "ART DIRECTION",
    "SANAT YONETMENI",
    "SANAT YONETMEN",
    "YAPIM TASARIM",
    "YAPIM TASARIMI",
    "YAPIM TASARIMCISI",
    "PRODUCTION DESIGN",
    "PRODUCTION DESIGNER",
    "EDITOR",
    "SOUND",
    "THANKS TO",
    "SPECIAL THANKS",
    "THE END",
)
ROLE_ADJ_LIMITS = {"director": 1, "producer": 2, "writer": 2, "cast": 14}

ROLE_WORDS = {
    "DIRECTOR",
    "DIRECTED",
    "PHOTOGRAPHY",
    "PHOTOGRAPHIC",
    "PRODUCER",
    "PRODUCED",
    "PRODUCTION",
    "PRESENTS",
    "SCREENPLAY",
    "SCENARIO",
    "SCRIPT",
    "STORY",
    "CAST",
    "STARRING",
    "FEATURING",
    "MUSIC",
    "COMPOSED",
    "CONDUCTED",
    "DESIGNER",
    "DESIGN",
    "ASSISTANT",
    "ASSOCIATE",
    "EXECUTIVE",
    "SUPERVISION",
    "SUPERVISOR",
    "EDITOR",
    "EDITORIAL",
    "SOUND",
    "RECORDING",
    "TECHNICOLOR",
    "COLOR",
    "CONSULTANT",
    "DECORATION",
    "DIRECTION",
    "THANKS",
    "COURTESY",
    "PUBLISHING",
    "RECORDED",
    "PERFORMED",
    "COMPANY",
    "PICTURES",
    "FILM",
    "FILMS",
    "TELEVISION",
    "TV",
    "DOLBY",
    "DIGITAL",
}

CORP_WORDS = {
    "PICTURES",
    "PRODUCTION",
    "PRODUCTIONS",
    "FILMPRODUKTION",
    "TELEVISION",
    "TELEVISIE",
    "STUDIO",
    "STUDIOS",
    "WARNER",
    "BROS",
    "PARAMOUNT",
    "TECHNICOLOR",
    "DOLBY",
    "INC",
    "LTD",
    "LLC",
    "BV",
    "GMBH",
    "SRL",
    "NDR",
    "VPRO",
}


def fold(text: str) -> str:
    text = (text or "").replace("ı", "i").replace("İ", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9']+", " ", text).upper()
    return re.sub(r"\s+", " ", text).strip()


def display_name(text: str) -> str:
    parts = []
    for tok in re.findall(r"[A-Za-zÀ-ÿİıŞşĞğÇçÖöÜü'.-]+", text or ""):
        if len(tok) == 1 and tok.isupper():
            parts.append(tok)
        elif tok.isupper():
            parts.append(tok.title())
        else:
            parts.append(tok[:1].upper() + tok[1:])
    return " ".join(parts).strip()


def is_role_line(line: str) -> bool:
    nf = fold(line)
    heads = DIRECTOR_HEADS + PRODUCER_HEADS + WRITER_HEADS + CAST_HEADS + STOP_HEADS
    return any(nf == h or nf.startswith(h + " ") or h in nf for h in heads)


def is_name_like(line: str) -> bool:
    nf = fold(line)
    if not nf:
        return False
    toks = nf.split()
    if not (2 <= len(toks) <= 5):
        return False
    if any(tok.isdigit() for tok in toks):
        return False
    if any(tok in ROLE_WORDS for tok in toks):
        return False
    if any(tok in CORP_WORDS for tok in toks):
        return False
    alpha_chars = sum(ch.isalpha() for ch in nf)
    if alpha_chars < 5:
        return False
    return True


def role_for_line(line: str) -> tuple[str | None, str | None]:
    nf = fold(line)
    toks = set(nf.split())
    if ("DIRECTOR" in toks or "DIRECTOF" in toks or "DIRECTER" in toks or "DIRECT" in toks) and any(
        t.startswith("PHOTOG") or t.startswith("PHET") for t in toks
    ):
        return "stop", "NOISY_DIRECTOR_OF_PHOTOGRAPHY"
    if any(t.startswith("ASSIST") or t.startswith("ASAIS") or t.startswith("AMINT") for t in toks) and any(
        t.startswith("DIRECT") for t in toks
    ):
        return "stop", "NOISY_ASSISTANT_DIRECTOR"
    if "YAPIM" in toks and any(t in toks for t in {"TASARIM", "TASARIMI", "TASARIMCISI"}):
        return "stop", "NOISY_PRODUCTION_DESIGN"
    if "SANAT" in toks and any(t.startswith("YONET") or t.startswith("YON") for t in toks):
        return "stop", "NOISY_ART_DIRECTOR_TR"
    if "ART" in toks and any(t.startswith("DIR") for t in toks):
        return "stop", "NOISY_ART_DIRECTION"
    if "CASTING" in toks and any(t.startswith("DIR") for t in toks):
        return "stop", "NOISY_CASTING_DIRECTOR"
    for head in STOP_HEADS:
        if nf == head or nf.startswith(head + " ") or head in nf:
            return "stop", head
    for role, heads in (
        ("director", DIRECTOR_HEADS),
        ("producer", PRODUCER_HEADS),
        ("writer", WRITER_HEADS),
        ("cast", CAST_HEADS),
    ):
        for head in heads:
            if nf == head or nf.startswith(head + " ") or nf.endswith(" " + head) or head in nf:
                return role, head
    return None, None


def inline_name(line: str, head: str) -> str | None:
    nf = fold(line)
    raw_tokens = line.strip().split()
    head_tokens = head.split()
    if nf == head:
        return None
    if nf.startswith(head + " ") and len(raw_tokens) > len(head_tokens):
        cand = " ".join(raw_tokens[len(head_tokens) :])
    elif nf.endswith(" " + head) and len(raw_tokens) > len(head_tokens):
        cand = " ".join(raw_tokens[: -len(head_tokens)])
    else:
        # Last resort for noisy OCR: remove a case-insensitive head phrase.
        cand = re.sub(re.escape(head), "", nf, count=1).strip()
    cand = cand.strip(" :-,.;")
    return display_name(cand) if is_name_like(cand) else None


def dedup(names: list[str]) -> list[str]:
    out = []
    seen = set()
    for name in names:
        key = fold(name)
        if key and key not in seen:
            out.append(name)
            seen.add(key)
    return out


def most_common_display(counter: Counter[str]) -> list[str]:
    by_key: dict[str, Counter[str]] = defaultdict(Counter)
    for name, count in counter.items():
        by_key[fold(name)][display_name(name)] += count
    ranked = []
    for key, displays in by_key.items():
        if key:
            display, count = displays.most_common(1)[0]
            ranked.append((count, display))
    ranked.sort(reverse=True)
    return [name for _, name in ranked]


def find_ocr_files(folder: Path) -> tuple[Path, Path | None]:
    raw_files = sorted(folder.glob("ocr/ocr*/ocr_raw_all.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    kunye_files = sorted(folder.glob("ocr/ocr*/kunye.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not raw_files:
        raise FileNotFoundError(f"ocr_raw_all.txt not found under {folder}")
    return raw_files[0], (kunye_files[0] if kunye_files else None)


def case_from_folder(folder: Path) -> dict | None:
    if not (folder / "ocr").exists():
        return None
    try:
        find_ocr_files(folder)
    except FileNotFoundError:
        return None
    match = re.search(r"(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)", folder.name)
    item_id = match.group(1) if match else folder.name
    title = folder.name
    if match:
        title = (folder.name[: match.start()] + folder.name[match.end() :]).strip(" -_")
    return {"id": item_id, "title": title, "folder": folder, "watch": []}


def scan_cases(limit: int | None = None) -> list[dict]:
    folders = sorted((ROOT / "Database").iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    cases = []
    for folder in folders:
        if not folder.is_dir():
            continue
        case = case_from_folder(folder)
        if case:
            cases.append(case)
            if limit and len(cases) >= limit:
                break
    return cases


def find_pdf(folder: Path) -> Path | None:
    pdfs = sorted(folder.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    return pdfs[0] if pdfs else None


def extract_pdf_cast(folder: Path) -> list[str]:
    pdf = find_pdf(folder)
    if not pdf:
        return []
    try:
        import fitz  # type: ignore
    except Exception:
        return []
    try:
        with fitz.open(pdf) as doc:
            lines = []
            for page in doc:
                lines.extend(page.get_text().splitlines())
    except Exception:
        return []
    out = []
    in_cast = False
    for raw in lines:
        line = raw.strip()
        compact = fold(line).replace(" ", "")
        if compact == "OYUNCULAR":
            in_cast = True
            continue
        if in_cast and compact in {"YAPIMEKIBI", "OZET", "SESEALTYAZI", "ANAHATARSZCUKLER", "ANAHTARSOZCUKLER"}:
            break
        if in_cast and is_name_like(line):
            out.append(display_name(line))
    return dedup(out)


def parse_role_blocks(lines: list[str]) -> dict:
    evidence: dict[str, dict[str, list[dict]]] = {
        "director": defaultdict(list),
        "producer": defaultdict(list),
        "writer": defaultdict(list),
        "cast": defaultdict(list),
        "protected_noncast": defaultdict(list),
    }
    billing_counter: Counter[str] = Counter()
    current_role: str | None = None
    current_ttl = 0

    def add(role: str, name: str, idx: int, reason: str, context: list[str]) -> None:
        name = display_name(name)
        if not is_name_like(name):
            return
        key = fold(name)
        evidence[role][key].append({"name": name, "line": idx + 1, "reason": reason, "context": context})
        if role in {"director", "producer", "writer"}:
            evidence["protected_noncast"][key].append(
                {"name": name, "line": idx + 1, "reason": role, "context": context}
            )

    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        role, head = role_for_line(line)
        context = [x.strip() for x in lines[max(0, idx - 2) : min(len(lines), idx + 3)] if x.strip()]

        if role == "stop":
            current_role = None
            current_ttl = 0
            continue

        if role:
            current_role = role
            current_ttl = ROLE_ADJ_LIMITS.get(role, 1)
            if head:
                nm = inline_name(line, head)
                if nm:
                    add(role, nm, idx, f"inline:{head}", context)
            continue

        if current_role and current_ttl > 0:
            if is_role_line(line):
                current_role = None
                current_ttl = 0
                continue
            if is_name_like(line):
                add(current_role, line, idx, "adjacent-role-block", context)
                current_ttl -= 1
                if current_ttl <= 0:
                    current_role = None
                continue
            if current_role != "cast":
                current_role = None
                current_ttl = 0
            else:
                current_ttl -= 1

        # Billing/opening names are only weak cast candidates; protected roles remove them later.
        if idx < 420 and is_name_like(line) and not is_role_line(line):
            billing_counter[display_name(line)] += 1

    protected = {key: vals for key, vals in evidence["protected_noncast"].items()}
    protected_list = []
    for key, vals in protected.items():
        protected_list.append(
            {
                "name": vals[0]["name"],
                "roles": sorted({v["reason"] for v in vals}),
                "evidence": vals[:3],
            }
        )
    cast_names = most_common_display(billing_counter)
    cast_names.extend(entry["name"] for vals in evidence["cast"].values() for entry in vals)
    cast_names = dedup(cast_names)

    blocked = []
    cast_after = []
    for name in cast_names:
        key = fold(name)
        if key in protected:
            blocked.append(
                {
                    "name": name,
                    "blocked_by": sorted({e["reason"] for e in protected[key]}),
                    "evidence": protected[key][:3],
                }
            )
        else:
            cast_after.append(name)

    return {
        "director": dedup([e["name"] for vals in evidence["director"].values() for e in vals]),
        "producer": dedup([e["name"] for vals in evidence["producer"].values() for e in vals]),
        "writer": dedup([e["name"] for vals in evidence["writer"].values() for e in vals]),
        "cast_candidates_before": cast_names,
        "cast_after_role_block": cast_after,
        "blocked_from_cast": blocked,
        "protected_noncast": protected_list,
        "protected_noncast_count": len(protected),
    }


def collect_name_candidates(lines: list[str]) -> list[str]:
    names = []
    for line in lines:
        line = line.strip()
        if is_name_like(line) and not is_role_line(line):
            names.append(display_name(line))
    return dedup(names)


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def run_case(case: dict) -> dict:
    raw_path, kunye_path = find_ocr_files(case["folder"])
    raw_lines = read_lines(raw_path)
    parsed = parse_role_blocks(raw_lines)
    protected_keys_all = {fold(item["name"]): item for item in parsed["protected_noncast"]}
    kunye_candidates = []
    kunye_after = []
    blocked_from_kunye = []
    if kunye_path:
        kunye_candidates = collect_name_candidates(read_lines(kunye_path))
        for name in kunye_candidates:
            key = fold(name)
            if key in protected_keys_all:
                blocked_from_kunye.append(
                    {
                        "name": name,
                        "blocked_by": protected_keys_all[key]["roles"],
                        "evidence": protected_keys_all[key]["evidence"][:3],
                    }
                )
            else:
                kunye_after.append(name)
    pdf_cast = extract_pdf_cast(case["folder"])
    pdf_cast_keys = {fold(name) for name in pdf_cast}
    blocked_pdf_cast_conflicts = [
        item for item in blocked_from_kunye if fold(item["name"]) in pdf_cast_keys
    ]
    watch = []
    blocked_keys = {fold(item["name"]): item for item in parsed["blocked_from_cast"]}
    kunye_block_keys = {fold(item["name"]): item for item in blocked_from_kunye}
    protected_keys = protected_keys_all
    cast_after_keys = {fold(n) for n in parsed["cast_after_role_block"]}
    kunye_after_keys = {fold(n) for n in kunye_after}
    for name in case.get("watch", []):
        key = fold(name)
        watch.append(
            {
                "name": name,
                "protected_noncast": key in protected_keys,
                "blocked_from_cast": key in blocked_keys,
                "blocked_from_kunye": key in kunye_block_keys,
                "still_in_cast_after": key in cast_after_keys,
                "still_in_kunye_after": key in kunye_after_keys,
                "protected_reason": protected_keys.get(key, {}).get("roles", []),
                "block_reason": (blocked_keys.get(key, {}) or kunye_block_keys.get(key, {})).get("blocked_by", []),
            }
        )
    return {
        "id": case["id"],
        "title": case["title"],
        "folder": str(case["folder"]),
        "raw_ocr": str(raw_path),
        "kunye": str(kunye_path) if kunye_path else None,
        "kunye_candidates_before": kunye_candidates,
        "kunye_after_role_block": kunye_after,
        "blocked_from_kunye": blocked_from_kunye,
        "pdf_cast": pdf_cast,
        "blocked_pdf_cast_conflicts": blocked_pdf_cast_conflicts,
        "watch": watch,
        **parsed,
    }


def write_markdown(results: list[dict], path: Path) -> None:
    lines = [
        "# Role Block Probe",
        "",
        "Ana pipeline'a dokunmadan, mevcut `ocr_raw_all.txt` uzerinde role-block deneyi.",
        "",
    ]
    for res in results:
        lines.append(f"## {res['id']} {res['title']}")
        lines.append("")
        lines.append(f"- Raw OCR: `{res['raw_ocr']}`")
        lines.append(f"- Director: {', '.join(res['director'][:5]) or '-'}")
        lines.append(f"- Producer: {', '.join(res['producer'][:5]) or '-'}")
        lines.append(f"- Writer/Scenario: {', '.join(res['writer'][:8]) or '-'}")
        lines.append(f"- Cast before block gate: {', '.join(res['cast_candidates_before'][:12]) or '-'}")
        lines.append(f"- Cast after block gate: {', '.join(res['cast_after_role_block'][:12]) or '-'}")
        lines.append(f"- Künye candidates before: {', '.join(res['kunye_candidates_before'][:12]) or '-'}")
        lines.append(f"- Künye candidates after: {', '.join(res['kunye_after_role_block'][:12]) or '-'}")
        lines.append(f"- Final PDF cast: {', '.join(res.get('pdf_cast', [])[:12]) or '-'}")
        lines.append(f"- Block/PDF cast conflicts: {len(res.get('blocked_pdf_cast_conflicts', []))}")
        lines.append("")
        lines.append(
            "| Watch name | Protected non-cast | Blocked from künye | "
            "Still in künye after | Blocked from raw cast | Reason |"
        )
        lines.append("|---|---:|---:|---:|---:|---|")
        for item in res["watch"]:
            lines.append(
                f"| {item['name']} | {item['protected_noncast']} | {item['blocked_from_kunye']} | "
                f"{item['still_in_kunye_after']} | {item['blocked_from_cast']} | "
                f"{', '.join(item['block_reason'] or item['protected_reason']) or '-'} |"
            )
        lines.append("")
        if res["blocked_from_cast"]:
            lines.append("Blocked evidence:")
            for block in res["blocked_from_cast"][:10]:
                ev = block["evidence"][0] if block.get("evidence") else {}
                ctx = " / ".join(ev.get("context") or [])
                lines.append(f"- {block['name']} -> {', '.join(block['blocked_by'])}; line {ev.get('line')}: {ctx}")
            lines.append("")
        if res.get("blocked_pdf_cast_conflicts"):
            lines.append("Potential false positives against final PDF cast:")
            for item in res["blocked_pdf_cast_conflicts"][:20]:
                lines.append(f"- {item['name']} -> {', '.join(item['blocked_by'])}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(results: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "title",
                "name",
                "protected_noncast",
                "blocked_from_kunye",
                "still_in_kunye_after",
                "blocked_from_cast",
                "still_in_cast_after",
                "reason",
            ],
        )
        writer.writeheader()
        for res in results:
            for item in res["watch"]:
                writer.writerow(
                    {
                        "id": res["id"],
                        "title": res["title"],
                        "name": item["name"],
                        "protected_noncast": item["protected_noncast"],
                        "blocked_from_kunye": item["blocked_from_kunye"],
                        "still_in_kunye_after": item["still_in_kunye_after"],
                        "blocked_from_cast": item["blocked_from_cast"],
                        "still_in_cast_after": item["still_in_cast_after"],
                        "reason": ",".join(item["block_reason"] or item["protected_reason"]),
                    }
                )


def write_batch_summary(results: list[dict], path: Path) -> None:
    rows = []
    for res in results:
        rows.append(
            {
                "id": res["id"],
                "title": res["title"],
                "kunye_candidates": len(res.get("kunye_candidates_before", [])),
                "blocked_from_kunye": len(res.get("blocked_from_kunye", [])),
                "pdf_cast": len(res.get("pdf_cast", [])),
                "blocked_pdf_cast_conflicts": len(res.get("blocked_pdf_cast_conflicts", [])),
                "blocked_names": "; ".join(
                    f"{x['name']}({','.join(x['blocked_by'])})"
                    for x in res.get("blocked_from_kunye", [])[:20]
                ),
                "conflict_names": "; ".join(
                    f"{x['name']}({','.join(x['blocked_by'])})"
                    for x in res.get("blocked_pdf_cast_conflicts", [])[:20]
                ),
            }
        )
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "title",
                "kunye_candidates",
                "blocked_from_kunye",
                "pdf_cast",
                "blocked_pdf_cast_conflicts",
                "blocked_names",
                "conflict_names",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_batch_markdown(results: list[dict], path: Path) -> None:
    total = len(results)
    blocked_films = sum(1 for r in results if r.get("blocked_from_kunye"))
    blocked_names = sum(len(r.get("blocked_from_kunye", [])) for r in results)
    conflict_films = sum(1 for r in results if r.get("blocked_pdf_cast_conflicts"))
    conflict_names = sum(len(r.get("blocked_pdf_cast_conflicts", [])) for r in results)
    lines = [
        "# Role Block Batch Probe",
        "",
        f"- Films scanned: {total}",
        f"- Films with at least one künye candidate blocked: {blocked_films}",
        f"- Names blocked from künye candidates: {blocked_names}",
        f"- Films with blocked name still present in final PDF cast: {conflict_films}",
        f"- Block/PDF-cast conflict names: {conflict_names}",
        "",
        "## Conflicts",
        "",
    ]
    conflicts = [r for r in results if r.get("blocked_pdf_cast_conflicts")]
    if not conflicts:
        lines.append("- None")
    for res in conflicts:
        lines.append(f"### {res['id']} {res['title']}")
        for item in res["blocked_pdf_cast_conflicts"]:
            lines.append(f"- {item['name']} -> {', '.join(item['blocked_by'])}")
        lines.append("")
    lines.extend(["", "## Largest Block Sets", ""])
    for res in sorted(results, key=lambda r: len(r.get("blocked_from_kunye", [])), reverse=True)[:25]:
        if not res.get("blocked_from_kunye"):
            continue
        names = "; ".join(
            f"{x['name']}({','.join(x['blocked_by'])})" for x in res["blocked_from_kunye"][:12]
        )
        lines.append(f"- {res['id']} {res['title']}: {len(res['blocked_from_kunye'])} blocked -> {names}")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "role_block_probe"))
    parser.add_argument("--scan", action="store_true", help="scan recent Database folders instead of the fixed cases")
    parser.add_argument("--limit", type=int, default=0, help="max folders for --scan; 0 means all")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = scan_cases(args.limit or None) if args.scan else CASES
    results = [run_case(case) for case in cases]
    json_path = out_dir / "role_block_probe_results.json"
    md_path = out_dir / "role_block_probe_report.md"
    csv_path = out_dir / "role_block_probe_watch.csv"
    batch_csv_path = out_dir / "role_block_probe_batch_summary.csv"
    batch_md_path = out_dir / "role_block_probe_batch_summary.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(results, md_path)
    write_csv(results, csv_path)
    write_batch_summary(results, batch_csv_path)
    write_batch_markdown(results, batch_md_path)

    print(f"JSON: {json_path}")
    print(f"MD  : {md_path}")
    print(f"CSV : {csv_path}")
    print(f"SUM : {batch_md_path}")
    print(f"SUMCSV: {batch_csv_path}")
    for res in results[:30]:
        verdict = []
        for item in res["watch"]:
            if item["blocked_from_kunye"] and not item["still_in_kunye_after"]:
                verdict.append(f"{item['name']}: KUNYE_BLOCK_OK")
            elif item["protected_noncast"] and not item["still_in_cast_after"]:
                verdict.append(f"{item['name']}: PROTECT_OK")
            elif item["blocked_from_cast"] and not item["still_in_cast_after"]:
                verdict.append(f"{item['name']}: BLOCK_OK")
            elif item["still_in_cast_after"]:
                verdict.append(f"{item['name']}: LEAK")
            else:
                verdict.append(f"{item['name']}: NO_BLOCK")
        print(f"{res['id']} {res['title']} -> " + "; ".join(verdict))
    conflict_count = sum(len(r.get("blocked_pdf_cast_conflicts", [])) for r in results)
    print(
        f"Scanned={len(results)} blocked_names="
        f"{sum(len(r.get('blocked_from_kunye', [])) for r in results)} "
        f"pdf_cast_conflicts={conflict_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
