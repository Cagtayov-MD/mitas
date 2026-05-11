from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from difflib import SequenceMatcher

from tools.asr_ab.common import DEFAULT_OUTPUT_ROOT, write_json


DEFAULT_REFERENCE = Path(r"C:\Users\TRT03\Downloads\beyaz2 08 11.txt")
BAD_TOKENS = ("É", "I don't know", "Are the days", "Konuklar Türkçe sohbet ediyor")
CODE_SWITCH_TOKENS = ("Dancin", "Dancing", "Beer", "Bear", "Ayılar Dans")
MODEL_ISOLATION_VARIANTS = ("out_v7", "out_v10", "out_v11")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    return parser.parse_args()


def normalize_reference(text: str) -> str:
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith("(Transcribed by TurboScribe")
    ]
    return " ".join(lines)


def variant_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"out_v(\d+)$", path.name)
    if match:
        return (int(match.group(1)), path.name)
    return (9999, path.name)


def main() -> None:
    args = parse_args()
    reference = normalize_reference(args.reference.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []

    for output_dir in sorted(args.out_root.glob("out_v*"), key=variant_sort_key):
        transcript_path = output_dir / "clean_transcript.txt"
        raw_path = output_dir / "raw_segments.json"
        clean_path = output_dir / "clean_segments.json"
        filter_path = output_dir / "filter_report.json"
        safety_path = output_dir / "safety_report.json"
        timing_path = output_dir / "timing.json"
        if not transcript_path.exists():
            continue

        transcript = transcript_path.read_text(encoding="utf-8")
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        clean = json.loads(clean_path.read_text(encoding="utf-8"))
        filter_report = json.loads(filter_path.read_text(encoding="utf-8"))
        safety_report = json.loads(safety_path.read_text(encoding="utf-8")) if safety_path.exists() else None
        timing = json.loads(timing_path.read_text(encoding="utf-8"))
        bad_hits = {token: token.lower() in transcript.lower() for token in BAD_TOKENS}
        code_switch_hits = {token: token.lower() in transcript.lower() for token in CODE_SWITCH_TOKENS}

        rows.append(
            {
                "variant": output_dir.name,
                "name": timing["variant"],
                "model_call_count": timing["model_call_count"],
                "total_seconds": timing["total_seconds"],
                "transcribe_seconds": timing["transcribe_seconds"],
                "raw_segments": len(raw["segments"]),
                "clean_segments": len(clean["segments"]),
                "dropped_segments": filter_report["dropped_segment_count"],
                "drop_reasons": filter_report["drop_reasons"],
                "flags": filter_report.get("flags", {}),
                "languages_clean": filter_report["languages_clean"],
                "safe": safety_report["safe"] if safety_report is not None else None,
                "failure_reason": safety_report["failure_reason"] if safety_report is not None else None,
                "bad_token_hits": bad_hits,
                "bad_token_count": sum(1 for hit in bad_hits.values() if hit),
                "code_switch_hits": code_switch_hits,
                "code_switch_count": sum(1 for hit in code_switch_hits.values() if hit),
                "reference_similarity": round(SequenceMatcher(None, reference.lower(), transcript.lower()).ratio(), 4),
                "word_overlap_f1": round(word_overlap_f1(reference, transcript), 4),
                "char_count": len(transcript),
            }
        )

    comparison = {
        "reference_path": str(args.reference),
        "output_root": str(args.out_root),
        "bad_tokens": BAD_TOKENS,
        "code_switch_tokens": CODE_SWITCH_TOKENS,
        "variants": rows,
    }
    write_json(args.out_root / "comparison_report.json", comparison)
    write_markdown(args.out_root / "comparison_report.md", comparison)
    print(args.out_root / "comparison_report.md")


def write_markdown(path: Path, comparison: dict[str, object]) -> None:
    rows = comparison["variants"]
    lines = [
        "# beyaz2 08:00-11:00 ASR A/B Comparison",
        "",
        f"- Reference: `{comparison['reference_path']}`",
        f"- Output root: `{comparison['output_root']}`",
        "",
        "| Variant | Raw | Clean | Dropped | Safe | Bad hits | Code-switch | Similarity | Word F1 | Calls | Total s | Drop reasons | Flags | Languages |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {variant} | {raw_segments} | {clean_segments} | {dropped_segments} | {safe} | {bad_token_count} | {code_switch_count} | {reference_similarity:.4f} | {word_overlap_f1:.4f} | {model_call_count} | {total_seconds:.3f} | `{drop_reasons}` | `{flags}` | `{languages_clean}` |".format(
                **row
            )
        )
    isolation_rows = [row for row in rows if row["variant"] in MODEL_ISOLATION_VARIANTS]
    if isolation_rows:
        lines.extend(
            [
                "",
                "## Model Isolation Slice",
                "",
                "| Variant | Name | Word F1 | Bad hits | Code-switch | Calls | Total s |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for row in isolation_rows:
            lines.append(
                "| {variant} | {name} | {word_overlap_f1:.4f} | {bad_token_count} | {code_switch_count} | {model_call_count} | {total_seconds:.3f} |".format(
                    **row
                )
            )
    lines.extend(["", "## Token Checks", ""])
    for row in rows:
        lines.append(f"### {row['variant']} - {row['name']}")
        lines.append("")
        lines.append(f"- Bad token hits: `{row['bad_token_hits']}`")
        lines.append(f"- Code-switch hits: `{row['code_switch_hits']}`")
        lines.append(f"- Safety: safe=`{row['safe']}`, failure=`{row['failure_reason']}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def word_overlap_f1(reference: str, candidate: str) -> float:
    reference_words = tokenize(reference)
    candidate_words = tokenize(candidate)
    if not reference_words or not candidate_words:
        return 0.0
    reference_counts = {}
    candidate_counts = {}
    for word in reference_words:
        reference_counts[word] = reference_counts.get(word, 0) + 1
    for word in candidate_words:
        candidate_counts[word] = candidate_counts.get(word, 0) + 1
    overlap = sum(min(reference_counts.get(word, 0), candidate_counts.get(word, 0)) for word in candidate_counts)
    precision = overlap / len(candidate_words)
    recall = overlap / len(reference_words)
    if precision + recall == 0.0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"\w+", text, flags=re.UNICODE)]


if __name__ == "__main__":
    main()
