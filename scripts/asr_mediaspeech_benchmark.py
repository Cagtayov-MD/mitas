"""Run a small ASR benchmark against MediaSpeech Turkish WAV/TXT pairs."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import wave
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.pipelines.asr.transcribe import transcribe  # noqa: E402


TURKISH_SPECIFIC = set("çğıöşüÇĞİÖŞÜ")
TOKEN_RE = re.compile(r"[0-9a-zA-ZçğıöşüÇĞİÖŞÜ]+")


def read_wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / float(wav.getframerate())


def normalize_text(text: str) -> str:
    return " ".join(TOKEN_RE.findall(text.casefold()))


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    return normalized.split() if normalized else []


def edit_distance(left: Iterable[object], right: Iterable[object]) -> int:
    a = list(left)
    b = list(right)
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, a_item in enumerate(a, start=1):
        current = [i]
        for j, b_item in enumerate(b, start=1):
            cost = 0 if a_item == b_item else 1
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + cost,
                )
            )
        previous = current
    return previous[-1]


def error_rate(reference: Iterable[object], hypothesis: Iterable[object]) -> float:
    ref = list(reference)
    if not ref:
        return 0.0 if not list(hypothesis) else 1.0
    return edit_distance(ref, hypothesis) / len(ref)


def collect_candidates(dataset_dir: Path, limit: int, seed: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for txt_path in sorted(dataset_dir.glob("*.txt")):
        wav_path = txt_path.with_suffix(".wav")
        if not wav_path.exists():
            continue
        reference = txt_path.read_text(encoding="utf-8").strip()
        words = tokenize(reference)
        if len(words) < 12 or len(words) > 45:
            continue
        duration = read_wav_duration(wav_path)
        if duration < 8.0 or duration > 15.5:
            continue
        rows.append(
            {
                "id": txt_path.stem,
                "wav": str(wav_path),
                "txt": str(txt_path),
                "duration": round(duration, 3),
                "word_count": len(words),
                "has_turkish_specific": any(char in TURKISH_SPECIFIC for char in reference),
                "reference": reference,
            }
        )

    if len(rows) <= limit:
        return rows

    rng = random.Random(seed)
    return sorted(rng.sample(rows, limit), key=lambda item: str(item["id"]))


def run_benchmark(candidates: list[dict[str, object]], profiles: list[str]) -> dict[str, object]:
    results: list[dict[str, object]] = []
    started = time.perf_counter()

    for profile in profiles:
        for candidate in candidates:
            ref_text = str(candidate["reference"])
            ref_tokens = tokenize(ref_text)
            ref_chars = list(normalize_text(ref_text).replace(" ", ""))

            item_started = time.perf_counter()
            result = transcribe(Path(str(candidate["wav"])), profile=profile)
            elapsed = time.perf_counter() - item_started

            hyp_text = result.clean_transcript
            hyp_tokens = tokenize(hyp_text)
            hyp_chars = list(normalize_text(hyp_text).replace(" ", ""))

            results.append(
                {
                    "id": candidate["id"],
                    "profile": profile,
                    "model_name": result.model_name,
                    "profile_used": result.profile_used,
                    "fallback_triggered": result.fallback_triggered,
                    "wall_seconds": round(elapsed, 3),
                    "decode_seconds": result.timing.decode_seconds,
                    "duration": candidate["duration"],
                    "reference_words": len(ref_tokens),
                    "hypothesis_words": len(hyp_tokens),
                    "wer": round(error_rate(ref_tokens, hyp_tokens), 4),
                    "cer": round(error_rate(ref_chars, hyp_chars), 4),
                    "safety": bool(result.safety.safe) if result.safety else None,
                    "quality_drops": len(result.quality_drops),
                    "raw_segments": len(result.raw_segments),
                    "clean_segments": len(result.clean_segments),
                    "reference": ref_text,
                    "hypothesis": hyp_text,
                }
            )

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in results:
        grouped[str(row["profile"])].append(row)

    by_profile = {}
    for profile, rows in grouped.items():
        by_profile[profile] = {
            "avg_wer": round(sum(float(row["wer"]) for row in rows) / len(rows), 4),
            "avg_cer": round(sum(float(row["cer"]) for row in rows) / len(rows), 4),
            "total_wall_seconds": round(sum(float(row["wall_seconds"]) for row in rows), 3),
            "total_decode_seconds": round(sum(float(row["decode_seconds"]) for row in rows), 3),
            "avg_decode_seconds": round(sum(float(row["decode_seconds"]) for row in rows) / len(rows), 3),
            "count": len(rows),
        }

    return {
        "summary": {
            "candidate_count": len(candidates),
            "profiles": profiles,
            "total_wall_seconds": round(time.perf_counter() - started, 3),
            "by_profile": by_profile,
        },
        "candidates": candidates,
        "results": results,
    }


def render_markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    by_profile = summary["by_profile"]
    lines = [
        "# MediaSpeech Turkish ASR Benchmark",
        "",
        f"Candidate count: `{summary['candidate_count']}`",
        f"Total wall seconds: `{summary['total_wall_seconds']}`",
        "",
        "## Summary",
        "",
        "| Profile | Avg WER | Avg CER | Decode seconds | Avg decode seconds |",
        "|---|---:|---:|---:|---:|",
    ]
    for profile in summary["profiles"]:
        row = by_profile[profile]
        lines.append(
            f"| `{profile}` | `{row['avg_wer']}` | `{row['avg_cer']}` | "
            f"`{row['total_decode_seconds']}` | `{row['avg_decode_seconds']}` |"
        )

    lines.extend(
        [
            "",
            "## Per-Sample",
            "",
            "| ID | Profile | WER | CER | Decode s | Reference words |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload["results"]:
        lines.append(
            f"| `{row['id']}` | `{row['profile']}` | `{row['wer']}` | "
            f"`{row['cer']}` | `{row['decode_seconds']}` | `{row['reference_words']}` |"
        )

    lines.extend(["", "## Notes", ""])
    lines.append(
        "- This benchmark is a temporary external probe. Internal TRT transcripts should remain the final decision source."
    )
    lines.append(
        "- First decode for each model can include model-load overhead in wall time; decode seconds are better for profile comparison."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=ROOT / "cache" / "external_datasets" / "mediaspeech_tr" / "TR",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "external_turkish_transcripts_asr_smoke_20",
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260514)
    parser.add_argument("--profiles", nargs="+", default=["fast", "quality"])
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates = collect_candidates(args.dataset_dir, args.limit, args.seed)
    payload = run_benchmark(candidates, args.profiles)

    json_path = args.output_dir / "benchmark_results.json"
    md_path = args.output_dir / "benchmark_results.md"
    candidates_path = args.output_dir / "candidates.json"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    candidates_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
