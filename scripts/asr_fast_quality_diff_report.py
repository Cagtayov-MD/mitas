from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_BENCHMARK_ROOT = Path("outputs") / "asr_archive_all_wav_benchmark"
DEFAULT_OUT_DIR = DEFAULT_BENCHMARK_ROOT / "model_diff_reports"
TR_MAP = str.maketrans(
    {
        "ı": "i",
        "İ": "i",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ş": "s",
        "Ş": "s",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fast-vs-quality ASR word diff reports from archive.json files.")
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--max-rows-per-sample", type=int, default=250)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    samples = discover_samples(args.benchmark_root)
    reports = []
    for sample_dir in samples:
        report = build_sample_report(sample_dir, max_rows=args.max_rows_per_sample)
        reports.append(report)
        write_sample_report(args.out_dir / f"{sample_dir.name}_fast_quality_diff.md", report)
        (args.out_dir / f"{sample_dir.name}_fast_quality_diff.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    write_aggregate_report(args.out_dir / "aggregate_fast_quality_diff.md", reports)
    (args.out_dir / "aggregate_fast_quality_diff.json").write_text(
        json.dumps(summarize_reports(reports), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.out_dir / "aggregate_fast_quality_diff.md")
    return 0


def discover_samples(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.iterdir())
        if path.is_dir() and (path / "fast" / "archive.json").exists() and (path / "quality" / "archive.json").exists()
    ]


def build_sample_report(sample_dir: Path, *, max_rows: int) -> dict[str, Any]:
    fast_archive = json.loads((sample_dir / "fast" / "archive.json").read_text(encoding="utf-8"))
    quality_archive = json.loads((sample_dir / "quality" / "archive.json").read_text(encoding="utf-8"))
    fast_tokens = tokenize_archive(fast_archive)
    quality_tokens = tokenize_archive(quality_archive)
    pairs, distance = align_tokens(fast_tokens, quality_tokens)
    substitutions = [(fast, quality) for op, fast, quality in pairs if op == "S"]
    insertions = [quality for op, _fast, quality in pairs if op == "I"]
    deletions = [fast for op, fast, _quality in pairs if op == "D"]
    sub_counts = Counter((fast["token"], quality["token"]) for fast, quality in substitutions)
    ordered_pairs = sub_counts.most_common()

    selected_pairs = [item for item in ordered_pairs if interesting_pair(item)][:max_rows]
    fast_occurrence: Counter[str] = Counter()
    quality_occurrence: Counter[str] = Counter()
    rows = []
    for (fast_word, quality_word), count in selected_pairs:
        fast_occurrence[norm(fast_word)] += 1
        quality_occurrence[norm(quality_word)] += 1
        fast_item = find_token_occurrence(fast_tokens, fast_word, fast_occurrence[norm(fast_word)])
        quality_item = find_token_occurrence(quality_tokens, quality_word, quality_occurrence[norm(quality_word)])
        rows.append(build_diff_row(fast_word, quality_word, count, fast_item, quality_item, fast_tokens, quality_tokens))

    phrase_differences = collect_phrase_differences(pairs)
    return {
        "sample_id": sample_dir.name,
        "source_name": read_source_name(sample_dir),
        "fast_words": len(fast_tokens),
        "quality_words": len(quality_tokens),
        "edit_distance_fast_vs_quality": distance,
        "substitution_count": len(substitutions),
        "fast_extra_word_count": len(deletions),
        "quality_extra_word_count": len(insertions),
        "diff_rows": rows,
        "phrase_differences": phrase_differences,
    }


def tokenize_archive(archive: dict[str, Any]) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for segment_index, segment in enumerate(archive.get("segments", [])):
        text = str(segment.get("text", ""))
        for match in re.finditer(r"[\w']+", text, flags=re.UNICODE):
            tokens.append(
                {
                    "token": match.group(0),
                    "segment_index": segment_index,
                    "segment": segment,
                }
            )
    return tokens


def align_tokens(fast_tokens: list[dict[str, Any]], quality_tokens: list[dict[str, Any]]) -> tuple[list[tuple[str, Any, Any]], int]:
    fast_norm = [norm(item["token"]) for item in fast_tokens]
    quality_norm = [norm(item["token"]) for item in quality_tokens]
    n = len(fast_norm)
    m = len(quality_norm)
    previous = list(range(m + 1))
    back: list[list[str | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        back[i][0] = "D"
    for j in range(1, m + 1):
        back[0][j] = "I"
    for i in range(1, n + 1):
        current = [i]
        for j in range(1, m + 1):
            substitution_cost = 0 if fast_norm[i - 1] == quality_norm[j - 1] else 1
            choices = [
                (previous[j - 1] + substitution_cost, "M" if substitution_cost == 0 else "S"),
                (current[j - 1] + 1, "I"),
                (previous[j] + 1, "D"),
            ]
            value, op = min(choices, key=lambda item: item[0])
            current.append(value)
            back[i][j] = op
        previous = current
    distance = previous[m]
    pairs: list[tuple[str, Any, Any]] = []
    i = n
    j = m
    while i or j:
        op = back[i][j]
        if op == "M":
            pairs.append(("M", fast_tokens[i - 1], quality_tokens[j - 1]))
            i -= 1
            j -= 1
        elif op == "S":
            pairs.append(("S", fast_tokens[i - 1], quality_tokens[j - 1]))
            i -= 1
            j -= 1
        elif op == "I":
            pairs.append(("I", None, quality_tokens[j - 1]))
            j -= 1
        elif op == "D":
            pairs.append(("D", fast_tokens[i - 1], None))
            i -= 1
        else:
            break
    pairs.reverse()
    return pairs, distance


def build_diff_row(
    fast_word: str,
    quality_word: str,
    count: int,
    fast_item: dict[str, Any] | None,
    quality_item: dict[str, Any] | None,
    fast_tokens: list[dict[str, Any]],
    quality_tokens: list[dict[str, Any]],
) -> dict[str, Any]:
    fast_segment = fast_item.get("segment") if fast_item else None
    quality_segment = quality_item.get("segment") if quality_item else None
    fast_score = combined_score(fast_segment)
    quality_score = combined_score(quality_segment)
    return {
        "fast": fast_word,
        "quality": quality_word,
        "count": count,
        "fast_metrics": segment_metrics(fast_segment),
        "quality_metrics": segment_metrics(quality_segment),
        "combined_delta_fast_minus_quality": round(fast_score - quality_score, 4)
        if fast_score is not None and quality_score is not None
        else None,
        "winner_by_combined": winner(fast_score, quality_score),
        "fast_context": context_for(fast_tokens, fast_item),
        "quality_context": context_for(quality_tokens, quality_item),
    }


def segment_metrics(segment: dict[str, Any] | None) -> dict[str, Any] | None:
    if segment is None:
        return None
    start = float(segment.get("start", 0.0))
    end = float(segment.get("end", 0.0))
    avg_logprob = float(segment.get("avg_logprob", 0.0) or 0.0)
    no_speech_prob = float(segment.get("no_speech_prob", 0.0) or 0.0)
    return {
        "start": start,
        "end": end,
        "duration": round(end - start, 3),
        "avg_logprob": round(avg_logprob, 4),
        "no_speech_prob": round(no_speech_prob, 4),
        "combined": round(avg_logprob - no_speech_prob, 4),
        "flags": list(segment.get("flags", [])),
        "source_chunk_index": segment.get("source_chunk_index"),
    }


def combined_score(segment: dict[str, Any] | None) -> float | None:
    if segment is None:
        return None
    return float(segment.get("avg_logprob", 0.0) or 0.0) - float(segment.get("no_speech_prob", 0.0) or 0.0)


def winner(fast_score: float | None, quality_score: float | None) -> str:
    if fast_score is None or quality_score is None:
        return "missing"
    delta = fast_score - quality_score
    if abs(delta) < 0.05:
        return "near_tie"
    return "fast" if delta > 0 else "quality"


def collect_phrase_differences(pairs: list[tuple[str, Any, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for op, fast, quality in pairs:
        if op in ("I", "D"):
            side = "quality_extra" if op == "I" else "fast_extra"
            token = quality["token"] if op == "I" else fast["token"]
            if current and current["side"] == side:
                current["words"].append(token)
            else:
                if current:
                    chunks.append(current)
                current = {"side": side, "words": [token]}
        else:
            if current:
                chunks.append(current)
                current = None
    if current:
        chunks.append(current)
    chunks = [chunk for chunk in chunks if len(chunk["words"]) >= 2]
    chunks = sorted(chunks, key=lambda item: len(item["words"]), reverse=True)
    return [{"side": chunk["side"], "text": " ".join(chunk["words"]), "word_count": len(chunk["words"])} for chunk in chunks[:80]]


def interesting_pair(item: tuple[tuple[str, str], int]) -> bool:
    (fast_word, quality_word), count = item
    return (
        count >= 2
        or len(fast_word) >= 6
        or len(quality_word) >= 6
        or any(character.isdigit() for character in fast_word + quality_word)
        or fast_word[:1].isupper()
        or quality_word[:1].isupper()
    )


def find_token_occurrence(tokens: list[dict[str, Any]], token: str, occurrence: int) -> dict[str, Any] | None:
    wanted = norm(token)
    seen = 0
    for item in tokens:
        if norm(item["token"]) == wanted:
            seen += 1
            if seen == occurrence:
                return item
    return None


def context_for(tokens: list[dict[str, Any]], item: dict[str, Any] | None, window: int = 7) -> str:
    if item is None:
        return ""
    try:
        index = tokens.index(item)
    except ValueError:
        return ""
    left = max(0, index - window)
    right = min(len(tokens), index + window + 1)
    return " ".join(token["token"] for token in tokens[left:right])


def read_source_name(sample_dir: Path) -> str:
    sample_path = sample_dir / "sample.json"
    if not sample_path.exists():
        return sample_dir.name
    data = json.loads(sample_path.read_text(encoding="utf-8"))
    return Path(data.get("source_path", sample_dir.name)).name


def write_sample_report(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"# Fast vs Quality Diff: {report['sample_id']}",
        "",
        f"- Source: `{report['source_name']}`",
        f"- Fast words: `{report['fast_words']}`",
        f"- Quality words: `{report['quality_words']}`",
        f"- Substitutions: `{report['substitution_count']}`",
        f"- Fast extra words: `{report['fast_extra_word_count']}`",
        f"- Quality extra words: `{report['quality_extra_word_count']}`",
        "",
        "| Fast | Quality | Count | Winner | Fast avg | Quality avg | Fast ns | Quality ns | Fast time | Quality time | Fast context | Quality context |",
        "|---|---|---:|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    for row in report["diff_rows"]:
        fast_metrics = row["fast_metrics"] or {}
        quality_metrics = row["quality_metrics"] or {}
        lines.append(
            "| {fast} | {quality} | {count} | {winner} | {fast_avg} | {quality_avg} | {fast_ns} | {quality_ns} | {fast_time} | {quality_time} | {fast_context} | {quality_context} |".format(
                fast=escape_md(row["fast"]),
                quality=escape_md(row["quality"]),
                count=row["count"],
                winner=row["winner_by_combined"],
                fast_avg=fast_metrics.get("avg_logprob", "-"),
                quality_avg=quality_metrics.get("avg_logprob", "-"),
                fast_ns=fast_metrics.get("no_speech_prob", "-"),
                quality_ns=quality_metrics.get("no_speech_prob", "-"),
                fast_time=format_time(fast_metrics),
                quality_time=format_time(quality_metrics),
                fast_context=escape_md(row["fast_context"]),
                quality_context=escape_md(row["quality_context"]),
            )
        )
    lines += ["", "## Phrase-Level Extra/Missing Chunks", "", "| Side | Words | Count |", "|---|---|---:|"]
    for chunk in report["phrase_differences"]:
        lines.append(f"| {chunk['side']} | {escape_md(chunk['text'])} | {chunk['word_count']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_aggregate_report(path: Path, reports: list[dict[str, Any]]) -> None:
    summary = summarize_reports(reports)
    lines = [
        "# Aggregate Fast vs Quality Diff Report",
        "",
        f"- Samples: `{summary['sample_count']}`",
        f"- Total substitutions: `{summary['total_substitutions']}`",
        f"- Total fast extra words: `{summary['total_fast_extra_words']}`",
        f"- Total quality extra words: `{summary['total_quality_extra_words']}`",
        "",
        "| Sample | Fast words | Quality words | Subs | Fast extra | Quality extra | Fast wins | Quality wins | Near ties | Report |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["samples"]:
        report_name = f"{row['sample_id']}_fast_quality_diff.md"
        lines.append(
            f"| {row['sample_id']} | {row['fast_words']} | {row['quality_words']} | {row['substitutions']} | "
            f"{row['fast_extra_words']} | {row['quality_extra_words']} | {row['fast_wins']} | {row['quality_wins']} | "
            f"{row['near_ties']} | [{report_name}]({report_name}) |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    sample_rows = []
    for report in reports:
        winners = Counter(row["winner_by_combined"] for row in report["diff_rows"])
        sample_rows.append(
            {
                "sample_id": report["sample_id"],
                "source_name": report["source_name"],
                "fast_words": report["fast_words"],
                "quality_words": report["quality_words"],
                "substitutions": report["substitution_count"],
                "fast_extra_words": report["fast_extra_word_count"],
                "quality_extra_words": report["quality_extra_word_count"],
                "fast_wins": winners["fast"],
                "quality_wins": winners["quality"],
                "near_ties": winners["near_tie"],
            }
        )
    return {
        "sample_count": len(reports),
        "total_substitutions": sum(report["substitution_count"] for report in reports),
        "total_fast_extra_words": sum(report["fast_extra_word_count"] for report in reports),
        "total_quality_extra_words": sum(report["quality_extra_word_count"] for report in reports),
        "samples": sample_rows,
    }


def norm(token: str) -> str:
    return token.casefold().translate(TR_MAP).replace("'", "")


def format_time(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "-"
    return f"{metrics.get('start')}-{metrics.get('end')}"


def escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


if __name__ == "__main__":
    raise SystemExit(main())
