from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.pipelines.asr.models import clear_model_cache
from core.pipelines.asr.normalize import TARGET_CODEC_NAME, TARGET_SAMPLE_RATE
from core.pipelines.asr.transcribe import DEFAULT_FFMPEG_EXECUTABLE, transcribe
from core.pipelines.asr.vad import read_wav_duration_seconds


MANIFEST_PATH = PROJECT_ROOT / "benchmark_templates" / "asr_model_final_benchmark.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "asr_model_final_benchmark"
DEFAULT_FFPROBE_EXECUTABLE = str(Path(DEFAULT_FFMPEG_EXECUTABLE).with_name("ffprobe.exe"))
PROFILES = ("fast", "quality")
REVIEW_PACKET_DIRNAME = "review_packets"
REVIEW_CANDIDATE_DIRNAME = "review_candidates"
TIMESTAMP_PATTERN = re.compile(r"(?<!\w)\(?\d{1,2}:\d{2}(?::\d{2})?\)?(?!\w)")
PLACEHOLDER_PATTERNS = (
    re.compile(r"\bTODO\b", flags=re.IGNORECASE),
    re.compile(r"paste the manually transcribed reference", flags=re.IGNORECASE),
    re.compile(r"draft reference for", flags=re.IGNORECASE),
    re.compile(r"listen to the source audio", flags=re.IGNORECASE),
)


@dataclass(frozen=True)
class Sample:
    sample_id: str
    category: str
    source_path: Path
    start_sec: float | None
    end_sec: float | None
    reference_path: Path
    review_priority: str
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ASR model finalization mini benchmark.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--ffmpeg", default=DEFAULT_FFMPEG_EXECUTABLE)
    parser.add_argument("--ffprobe", default=DEFAULT_FFPROBE_EXECUTABLE)
    parser.add_argument("--prepare", action="store_true", help="Prepare normalized benchmark WAV files.")
    parser.add_argument("--run", action="store_true", help="Run fast and quality ASR profiles.")
    parser.add_argument("--review", action="store_true", help="Build candidate gold text and suspect lists for human review.")
    parser.add_argument("--score", action="store_true", help="Score existing transcripts against references.")
    parser.add_argument("--all", action="store_true", help="Prepare, run, and score.")
    parser.add_argument("--max-review-items", type=int, default=15, help="Maximum suspect items per review packet.")
    parser.add_argument("--sample", action="append", default=None, help="Run only the given sample_id. Can be repeated.")
    parser.add_argument("--run-one-sample", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--run-one-profile", choices=PROFILES, default=None, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    samples = load_samples(args.manifest)
    if args.sample:
        requested = set(args.sample)
        samples = [sample for sample in samples if sample.sample_id in requested]
        missing = requested - {sample.sample_id for sample in samples}
        if missing:
            raise SystemExit(f"Unknown sample id(s): {sorted(missing)}")

    if args.run_one_sample or args.run_one_profile:
        if not args.run_one_sample or not args.run_one_profile:
            raise SystemExit("--run-one-sample and --run-one-profile must be used together")
        sample_by_id = {sample.sample_id: sample for sample in samples}
        if args.run_one_sample not in sample_by_id:
            raise SystemExit(f"Unknown sample id: {args.run_one_sample}")
        run_one_prediction(sample_by_id[args.run_one_sample], args.run_one_profile, args.out_root, ffprobe=args.ffprobe)
        return 0

    if not (args.prepare or args.run or args.review or args.score or args.all):
        args.all = True

    args.out_root.mkdir(parents=True, exist_ok=True)
    if args.prepare or args.all:
        prepare_samples(samples, args.out_root, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    if args.run or args.all:
        run_predictions(samples, args.out_root, manifest_path=args.manifest, ffprobe=args.ffprobe)
    if args.review:
        write_review_packets(samples, args.out_root, max_items=args.max_review_items)
        print(args.out_root / REVIEW_PACKET_DIRNAME / "README.md")
    if args.score or args.all:
        manifest_meta = load_manifest_metadata(args.manifest)
        report = score_predictions(
            samples,
            args.out_root,
            benchmark_id=manifest_meta.get("benchmark_id", "asr_model_final_v0_1"),
            benchmark_name=manifest_meta.get("benchmark_name", "ASR Model Finalization Mini Benchmark"),
        )
        write_report(report, args.out_root)
        print(args.out_root / "report.md")
    return 0


def load_manifest_metadata(manifest_path: Path) -> dict[str, str]:
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return {
        "benchmark_id": str(data.get("benchmark_id", "")),
        "benchmark_name": str(data.get("benchmark_name", "")),
    }


def load_samples(manifest_path: Path) -> list[Sample]:
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    samples: list[Sample] = []
    for item in data["samples"]:
        samples.append(
            Sample(
                sample_id=item["sample_id"],
                category=item["category"],
                source_path=PROJECT_ROOT / item["source_path"],
                start_sec=item["start_sec"],
                end_sec=item["end_sec"],
                reference_path=PROJECT_ROOT / item["reference_path"],
                review_priority=item["review_priority"],
                notes=item["notes"],
            )
        )
    return samples


def prepare_samples(samples: list[Sample], output_root: Path, *, ffmpeg: str, ffprobe: str) -> None:
    for sample in samples:
        sample_dir = output_root / sample.sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        audio_path = prepared_audio_path(output_root, sample)
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
        ]
        if sample.start_sec is not None:
            command.extend(["-ss", f"{sample.start_sec:.3f}"])
        if sample.start_sec is not None and sample.end_sec is not None:
            command.extend(["-t", f"{sample.end_sec - sample.start_sec:.3f}"])
        command.extend(
            [
                "-i",
                str(sample.source_path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(TARGET_SAMPLE_RATE),
                "-acodec",
                TARGET_CODEC_NAME,
                str(audio_path),
            ]
        )
        subprocess.run(command, check=True)
        metadata = {
            "sample_id": sample.sample_id,
            "category": sample.category,
            "source_path": str(sample.source_path),
            "prepared_audio_path": str(audio_path),
            "start_sec": sample.start_sec,
            "end_sec": sample.end_sec,
            "audio_duration": read_wav_duration_seconds(audio_path),
            "source_duration": probe_duration(sample.source_path, ffprobe=ffprobe),
            "reference_path": str(sample.reference_path),
            "review_priority": sample.review_priority,
            "notes": sample.notes,
        }
        write_json(sample_dir / "sample.json", metadata)


def run_predictions(samples: list[Sample], output_root: Path, *, manifest_path: Path, ffprobe: str) -> None:
    for sample in samples:
        audio_path = prepared_audio_path(output_root, sample)
        if not audio_path.exists():
            raise FileNotFoundError(f"Prepared audio missing for {sample.sample_id}: {audio_path}")
        for profile in PROFILES:
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--manifest",
                str(manifest_path),
                "--out-root",
                str(output_root),
                "--ffprobe",
                ffprobe,
                "--run-one-sample",
                sample.sample_id,
                "--run-one-profile",
                profile,
            ]
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            summary_path = output_root / sample.sample_id / profile / "summary.json"
            if completed.returncode != 0 and not summary_path.exists():
                raise RuntimeError(
                    f"ASR subprocess failed for {sample.sample_id}/{profile}: "
                    f"exit={completed.returncode}, stderr={completed.stderr.strip()[-2000:]}"
                )
        write_draft_reference(sample, output_root)


def run_one_prediction(sample: Sample, profile: str, output_root: Path, *, ffprobe: str) -> None:
    audio_path = prepared_audio_path(output_root, sample)
    if not audio_path.exists():
        raise FileNotFoundError(f"Prepared audio missing for {sample.sample_id}: {audio_path}")
    clear_model_cache()
    started = time.perf_counter()
    result = transcribe(audio_path, profile=profile, ffprobe_executable=ffprobe)
    elapsed = time.perf_counter() - started
    profile_dir = output_root / sample.sample_id / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "transcript.txt").write_text(result.clean_transcript + "\n", encoding="utf-8")
    write_json(profile_dir / "archive.json", result.to_archive_dict())
    write_json(
        profile_dir / "summary.json",
        {
            "sample_id": sample.sample_id,
            "profile": profile,
            "model_name": result.model_name,
            "audio_duration": result.audio_duration,
            "runtime_seconds_wall": round(elapsed, 3),
            "runtime_seconds_reported": result.timing.total_seconds if result.timing else None,
            "runtime_per_audio_minute": round(elapsed / max(result.audio_duration / 60.0, 0.001), 3),
            "clean_word_count": len(result.clean_transcript.split()),
            "clean_segment_count": len(result.clean_segments),
            "quality_drop_count": len(result.quality_drops),
            "safety_passed": result.safety.safe if result.safety else None,
            "safety_failure": result.safety.failure_reason if result.safety else None,
            "safety_diagnostics": result.safety.diagnostics if result.safety else None,
        },
    )


def score_predictions(
    samples: list[Sample],
    output_root: Path,
    *,
    benchmark_id: str = "asr_model_final_v0_1",
    benchmark_name: str = "ASR Model Finalization Mini Benchmark",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        reference = read_reference(sample.reference_path)
        reference_issues = reference_hygiene_issues(reference)
        reference_ready = not reference_issues
        profile_results: dict[str, Any] = {}
        for profile in PROFILES:
            transcript_path = output_root / sample.sample_id / profile / "transcript.txt"
            summary_path = output_root / sample.sample_id / profile / "summary.json"
            if not transcript_path.exists() or not summary_path.exists():
                profile_results[profile] = {"status": "missing_prediction"}
                continue
            transcript = transcript_path.read_text(encoding="utf-8")
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            metrics = {
                "wer": None,
                "cer": None,
                "reference_ready": reference_ready,
            }
            if reference_ready:
                metrics["wer"] = round(word_error_rate(reference, transcript), 4)
                metrics["cer"] = round(char_error_rate(reference, transcript), 4)
            profile_results[profile] = {
                "status": "scored" if reference_ready else "awaiting_reference",
                **metrics,
                **summary,
            }
        speedup = None
        fast_runtime = profile_results.get("fast", {}).get("runtime_seconds_wall")
        quality_runtime = profile_results.get("quality", {}).get("runtime_seconds_wall")
        if fast_runtime and quality_runtime:
            speedup = round(quality_runtime / fast_runtime, 3)
        rows.append(
            {
                "sample_id": sample.sample_id,
                "category": sample.category,
                "reference_ready": reference_ready,
                "reference_issues": reference_issues,
                "reference_path": str(sample.reference_path),
                "draft_reference_path": str(output_root / "draft_references" / f"{sample.sample_id}.txt"),
                "review_packet_path": str(output_root / REVIEW_PACKET_DIRNAME / f"{sample.sample_id}.md"),
                "review_candidate_path": str(output_root / REVIEW_CANDIDATE_DIRNAME / f"{sample.sample_id}.txt"),
                "speedup_quality_vs_fast": speedup,
                "profiles": profile_results,
            }
        )
    return {
        "benchmark_id": benchmark_id,
        "benchmark_name": benchmark_name,
        "profiles": list(PROFILES),
        "rows": rows,
        "decision_hint": build_decision_hint(rows),
    }


def build_decision_hint(rows: list[dict[str, Any]]) -> str:
    if any(not row["reference_ready"] for row in rows):
        return "awaiting_reference_transcripts"
    fast_failures = [
        row["sample_id"]
        for row in rows
        if row["profiles"].get("fast", {}).get("safety_passed") is False
    ]
    if fast_failures:
        return f"not_final_fast_safety_failures:{','.join(fast_failures)}"
    return "ready_for_manual_decision_review"


def write_draft_reference(sample: Sample, output_root: Path) -> None:
    draft_dir = output_root / "draft_references"
    draft_dir.mkdir(parents=True, exist_ok=True)
    quality_path = output_root / sample.sample_id / "quality" / "transcript.txt"
    fast_path = output_root / sample.sample_id / "fast" / "transcript.txt"
    source_path = quality_path if quality_path.exists() else fast_path
    if not source_path.exists():
        return
    header = (
        f"# Draft reference for {sample.sample_id}\n"
        "# Listen to the source audio/video and manually correct this text.\n"
        "# Delete these comment lines before copying into references/asr_model_final/.\n\n"
    )
    (draft_dir / f"{sample.sample_id}.txt").write_text(
        header + source_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def write_review_packets(samples: list[Sample], output_root: Path, *, max_items: int = 15) -> None:
    packet_dir = output_root / REVIEW_PACKET_DIRNAME
    candidate_dir = output_root / REVIEW_CANDIDATE_DIRNAME
    packet_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)

    index_lines = [
        "# ASR Gold Probe Review Packets",
        "",
        "Bu klasor, gold referans isini bastan transcript yazmaya cevirmeden yapmak icindir.",
        "Her sample icin once `review_candidates/*.txt` aday metnini dinle; sadece hatali kelime/ifadeleri bildir.",
        "",
        "Geri bildirim formati:",
        "",
        "```text",
        "sample_id:",
        "02:30 \"yanlis ifade\" degil, \"dogru ifade\"",
        "```",
        "",
        "| Sample | Candidate | Packet | Ref status |",
        "|---|---|---|---|",
    ]

    for sample in samples:
        packet = build_review_packet(sample, output_root, max_items=max_items)
        candidate_path = candidate_dir / f"{sample.sample_id}.txt"
        packet_path = packet_dir / f"{sample.sample_id}.md"
        candidate_path.write_text(packet["candidate_text"] + "\n", encoding="utf-8")
        packet_path.write_text(packet["packet_markdown"], encoding="utf-8")
        index_lines.append(
            "| {sample} | {candidate} | {packet_path} | {status} |".format(
                sample=sample.sample_id,
                candidate=relative_display(candidate_path),
                packet_path=relative_display(packet_path),
                status=packet["reference_status"],
            )
        )

    (packet_dir / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")


def build_review_packet(sample: Sample, output_root: Path, *, max_items: int = 15) -> dict[str, Any]:
    candidate_source, candidate_text = select_candidate_text(sample, output_root)
    candidate_text = clean_review_text(candidate_text)
    reference_text = read_reference(sample.reference_path)
    reference_issues = reference_hygiene_issues(reference_text)
    suspect_items = build_suspect_items(sample, output_root, max_items=max_items)

    lines = [
        f"# {sample.sample_id}",
        "",
        f"- Category: `{sample.category}`",
        f"- Candidate source: `{candidate_source}`",
        f"- Prepared audio: `{relative_display(prepared_audio_path(output_root, sample))}`",
        f"- Reference target: `{relative_display(sample.reference_path)}`",
        f"- Reference status: `{format_reference_status(reference_issues)}`",
        "",
        "## Aday Gold Metin",
        "",
        candidate_text or "_Aday metin bulunamadi._",
        "",
        "## Supheli Noktalar",
        "",
    ]
    if suspect_items:
        for item in suspect_items:
            lines.extend(
                [
                    "- {source_time} (clip {clip_time}) [{reasons}]".format(
                        source_time=item["source_time"],
                        clip_time=item["clip_time"],
                        reasons=", ".join(item["reasons"]),
                    ),
                    f"  fast: {item['fast_text'] or '-'}",
                    f"  quality: {item['quality_text'] or '-'}",
                ]
            )
    else:
        lines.append("- Fast/quality arasinda belirgin fark bulunamadi; aday metni hizli dinleme yeterli.")

    lines.extend(
        [
            "",
            "## Kullanici Geri Bildirim Formati",
            "",
            "```text",
            f"{sample.sample_id}:",
            "02:30 \"yanlis ifade\" degil, \"dogru ifade\"",
            "```",
            "",
        ]
    )
    return {
        "candidate_text": candidate_text,
        "packet_markdown": "\n".join(lines),
        "reference_status": format_reference_status(reference_issues),
        "suspect_count": len(suspect_items),
    }


def select_candidate_text(sample: Sample, output_root: Path) -> tuple[str, str]:
    reference_text = read_reference(sample.reference_path)
    if reference_text.strip() and not has_placeholder_text(reference_text):
        return "current_reference_cleaned", reference_text

    draft_path = output_root / "draft_references" / f"{sample.sample_id}.txt"
    if draft_path.exists():
        return "draft_reference_cleaned", draft_path.read_text(encoding="utf-8")

    quality_path = output_root / sample.sample_id / "quality" / "transcript.txt"
    if quality_path.exists():
        return "quality_transcript", quality_path.read_text(encoding="utf-8")

    fast_path = output_root / sample.sample_id / "fast" / "transcript.txt"
    if fast_path.exists():
        return "fast_transcript", fast_path.read_text(encoding="utf-8")

    return "missing", ""


def clean_review_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        cleaned_lines.append(TIMESTAMP_PATTERN.sub("", line).strip())
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_suspect_items(sample: Sample, output_root: Path, *, max_items: int = 15) -> list[dict[str, Any]]:
    fast_segments = read_archive_segments(output_root / sample.sample_id / "fast" / "archive.json")
    quality_segments = read_archive_segments(output_root / sample.sample_id / "quality" / "archive.json")
    if not fast_segments or not quality_segments:
        return []

    items: list[dict[str, Any]] = []
    used_quality: set[int] = set()
    for fast_segment in fast_segments:
        match_index, quality_segment = best_overlap_segment(fast_segment, quality_segments)
        if quality_segment is None:
            items.append(review_item(sample, fast_segment, None, ["missing_quality_overlap"]))
            continue
        used_quality.add(match_index)
        reasons = segment_review_reasons(fast_segment, quality_segment)
        if reasons:
            items.append(review_item(sample, fast_segment, quality_segment, reasons))

    for index, quality_segment in enumerate(quality_segments):
        if index in used_quality:
            continue
        if high_risk_segment(quality_segment):
            items.append(review_item(sample, None, quality_segment, ["quality_unmatched_high_risk"]))

    items.sort(key=lambda item: item["sort_start"])
    if max_items > 0:
        return items[:max_items]
    return items


def read_archive_segments(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    return segments if isinstance(segments, list) else []


def best_overlap_segment(segment: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[int, dict[str, Any] | None]:
    best_index = -1
    best_segment: dict[str, Any] | None = None
    best_overlap = 0.0
    for index, candidate in enumerate(candidates):
        overlap = time_overlap(segment, candidate)
        if overlap > best_overlap:
            best_overlap = overlap
            best_index = index
            best_segment = candidate
    return best_index, best_segment


def segment_review_reasons(fast_segment: dict[str, Any], quality_segment: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    fast_text = str(fast_segment.get("text") or "")
    quality_text = str(quality_segment.get("text") or "")
    if normalize_words(fast_text) != normalize_words(quality_text):
        reasons.append("fast_quality_diff")
    if high_risk_segment(fast_segment):
        reasons.append("fast_low_confidence")
    if high_risk_segment(quality_segment):
        reasons.append("quality_low_confidence")
    return reasons


def high_risk_segment(segment: dict[str, Any]) -> bool:
    flags = segment.get("flags") or []
    if "high_no_speech_prob" in flags or "low_confidence" in flags:
        return True
    try:
        no_speech_prob = float(segment.get("no_speech_prob") or 0.0)
        avg_logprob = float(segment.get("avg_logprob") or 0.0)
    except (TypeError, ValueError):
        return False
    return no_speech_prob > 0.4 or avg_logprob < -0.8


def review_item(
    sample: Sample,
    fast_segment: dict[str, Any] | None,
    quality_segment: dict[str, Any] | None,
    reasons: list[str],
) -> dict[str, Any]:
    anchor = fast_segment or quality_segment or {}
    start = float(anchor.get("start") or 0.0)
    end = float(anchor.get("end") or start)
    source_start = (sample.start_sec or 0.0) + start
    return {
        "sort_start": start,
        "clip_time": f"{format_time(start)}-{format_time(end)}",
        "source_time": format_time(source_start),
        "fast_text": str((fast_segment or {}).get("text") or ""),
        "quality_text": str((quality_segment or {}).get("text") or ""),
        "reasons": reasons,
    }


def time_overlap(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_start = float(left.get("start") or 0.0)
    left_end = float(left.get("end") or left_start)
    right_start = float(right.get("start") or 0.0)
    right_end = float(right.get("end") or right_start)
    return max(0.0, min(left_end, right_end) - max(left_start, right_start))


def write_report(report: dict[str, Any], output_root: Path) -> None:
    write_json(output_root / "report.json", report)
    lines = [
        f"# {report.get('benchmark_name') or 'ASR Benchmark Report'}",
        "",
        f"- Decision hint: `{report['decision_hint']}`",
        f"- Benchmark id: `{report['benchmark_id']}`",
        f"- Profiles: `{', '.join(report['profiles'])}`",
        "",
        "| Sample | Ref | Fast model | Fast WER | Quality model | Quality WER | Speedup | Fast safety | Quality safety |",
        "|---|---|---|---:|---|---:|---:|---|---|",
    ]
    for row in report["rows"]:
        fast = row["profiles"].get("fast", {})
        quality = row["profiles"].get("quality", {})
        lines.append(
            "| {sample} | {ref} | {fast_model} | {fast_wer} | {quality_model} | {quality_wer} | {speedup} | {fast_safe} | {quality_safe} |".format(
                sample=row["sample_id"],
                ref=format_reference_status(row.get("reference_issues", [])),
                fast_model=fast.get("model_name", "-"),
                fast_wer=format_metric(fast.get("wer")),
                quality_model=quality.get("model_name", "-"),
                quality_wer=format_metric(quality.get("wer")),
                speedup=format_metric(row.get("speedup_quality_vs_fast")),
                fast_safe=fast.get("safety_passed", "-"),
                quality_safe=quality.get("safety_passed", "-"),
            )
        )
    lines.extend(
        [
            "",
            "## Next Manual Step",
            "",
            "Run `--review` to generate candidate ASR text and suspect points.",
            "Listen only for wrong words/phrases, apply those corrections to the configured `reference_path` files, then rerun with `--score`.",
            "",
        ]
    )
    issue_rows = [row for row in report["rows"] if row.get("reference_issues")]
    if issue_rows:
        lines.extend(["## Reference Hygiene", ""])
        for row in issue_rows:
            lines.append(
                "- `{sample}`: {issues} (`{path}`)".format(
                    sample=row["sample_id"],
                    issues=", ".join(row["reference_issues"]),
                    path=row["reference_path"],
                )
            )
        lines.append("")
    (output_root / "report.md").write_text("\n".join(lines), encoding="utf-8")


def prepared_audio_path(output_root: Path, sample: Sample) -> Path:
    return output_root / sample.sample_id / "audio_16000hz_mono_s16.wav"


def probe_duration(path: Path, *, ffprobe: str) -> float:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return round(float(completed.stdout.strip()), 3)


def read_reference(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def is_reference_ready(text: str) -> bool:
    return not reference_hygiene_issues(text)


def reference_hygiene_issues(text: str) -> list[str]:
    stripped = text.strip()
    issues: list[str] = []
    if not stripped:
        issues.append("empty")
        return issues
    if has_placeholder_text(stripped):
        issues.append("placeholder_or_draft_text")
    if TIMESTAMP_PATTERN.search(stripped):
        issues.append("timestamp_markers_present")
    return issues


def has_placeholder_text(text: str) -> bool:
    return any(pattern.search(text) for pattern in PLACEHOLDER_PATTERNS)


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref_tokens = normalize_words(reference)
    hyp_tokens = normalize_words(hypothesis)
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0
    return levenshtein_distance(ref_tokens, hyp_tokens) / len(ref_tokens)


def char_error_rate(reference: str, hypothesis: str) -> float:
    ref_chars = list(normalize_text(reference).replace(" ", ""))
    hyp_chars = list(normalize_text(hypothesis).replace(" ", ""))
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    return levenshtein_distance(ref_chars, hyp_chars) / len(ref_chars)


def normalize_words(text: str) -> list[str]:
    return re.findall(r"\w+", normalize_text(text), flags=re.UNICODE)


def normalize_text(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"#.*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def levenshtein_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, ref_item in enumerate(reference, start=1):
        current = [i]
        for j, hyp_item in enumerate(hypothesis, start=1):
            substitution = previous[j - 1] + (0 if ref_item == hyp_item else 1)
            insertion = current[j - 1] + 1
            deletion = previous[j] + 1
            current.append(min(substitution, insertion, deletion))
        previous = current
    return previous[-1]


def format_metric(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def format_reference_status(issues: list[str]) -> str:
    if not issues:
        return "yes"
    if issues == ["empty"]:
        return "no"
    return "needs_cleanup"


def format_time(seconds: float) -> str:
    seconds_int = max(0, int(round(seconds)))
    minutes, secs = divmod(seconds_int, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def relative_display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=asdict) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
