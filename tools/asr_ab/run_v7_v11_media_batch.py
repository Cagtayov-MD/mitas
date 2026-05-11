from __future__ import annotations

from dataclasses import dataclass, asdict
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Sequence

from core.pipelines.asr.normalize import PROJECT_ROOT, TARGET_CODEC_NAME, TARGET_SAMPLE_RATE
from core.pipelines.asr.vad import read_wav_duration_seconds
from tools.asr_ab.common import DEFAULT_FFMPEG_EXE


OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "asr_ab" / "v7_v11_media_batch"
TEST_CLIP_DIR = PROJECT_ROOT / "testklipler"
REQUESTED_WINDOW_START = 180.0
REQUESTED_WINDOW_END = 300.0
BAD_TOKENS = ("É", "I don't know", "Are the days", "Konuklar Türkçe sohbet ediyor")
ARTIFACT_TOKENS = ("Abone olmayı", "Altyazı", "İzlediğiniz için teşekkür ederim")
VARIANTS = {
    "out_v7": "tools.asr_ab.transcribe_v7",
    "out_v11": "tools.asr_ab.transcribe_v11",
}
REQUIRED_VARIANT_FILES = (
    "raw_segments.json",
    "clean_segments.json",
    "clean_transcript.txt",
    "filter_report.json",
    "safety_report.json",
    "timing.json",
)


@dataclass(frozen=True)
class MediaJob:
    slug: str
    source: Path
    requested_start: float | None
    requested_end: float | None
    window_mode: str


@dataclass(frozen=True)
class PreparedAudio:
    job: MediaJob
    output_path: Path
    source_duration: float
    audio_duration: float
    actual_start: float
    actual_end: float
    mode: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--window-mode", choices=("fixed_03_05", "midpoint_2min"), default="fixed_03_05")
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG_EXE)
    parser.add_argument("--ffprobe", type=Path, default=DEFAULT_FFMPEG_EXE.with_name("ffprobe.exe"))
    parser.add_argument("--only-prepare", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    jobs = build_jobs(args.window_mode)
    if args.summarize_only:
        prepared = [resolve_existing_prepared_audio(job, args.out_root, ffprobe=args.ffprobe) for job in jobs]
    else:
        prepared = [prepare_audio(job, args.out_root, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe) for job in jobs]

    write_json(args.out_root / "prepared_manifest.json", [prepared_item_to_dict(item) for item in prepared])

    if args.only_prepare:
        print(args.out_root / "prepared_manifest.json")
        return

    run_warnings: list[dict[str, Any]] = []
    previous_summary: dict[str, Any] | None = None
    if not args.summarize_only:
        for item in prepared:
            job_root = args.out_root / item.job.slug
            for output_name, module in VARIANTS.items():
                warning = run_variant_subprocess(module, item.output_path, job_root, expected_dir=job_root / output_name, ffmpeg=args.ffmpeg)
                if warning is not None:
                    warning["job"] = item.job.slug
                    warning["variant"] = output_name
                    run_warnings.append(warning)
    elif (args.out_root / "batch_summary.json").exists():
        previous_summary = json.loads((args.out_root / "batch_summary.json").read_text(encoding="utf-8"))
        run_warnings = list(previous_summary.get("run_warnings", []))

    elapsed_seconds = round(time.perf_counter() - started, 3)
    if args.summarize_only and previous_summary is not None:
        elapsed_seconds = float(previous_summary.get("elapsed_seconds", elapsed_seconds))
    summary = build_summary(prepared, args.out_root, elapsed_seconds=elapsed_seconds)
    summary["run_warnings"] = run_warnings
    write_json(args.out_root / "batch_summary.json", summary)
    write_markdown(args.out_root / "batch_report.md", summary)
    write_full_transcripts(args.out_root / "full_transcripts.md", summary)
    print(args.out_root / "batch_report.md")


def build_jobs(window_mode: str = "fixed_03_05") -> list[MediaJob]:
    short_clip_names = ["1.mp4", "2.mp4", "3.mp4", "4.mp4", "5.mp4", "beyaz1.mp4"]
    trt_clip_names = ["trt_haber (1).mp4", "trt_haber (2).mp4", "trt_haber (3).mp4"]
    if window_mode == "midpoint_2min":
        return [
            MediaJob(
                slug=f"{slug_from_name(name)}_mid_2min",
                source=TEST_CLIP_DIR / name,
                requested_start=None,
                requested_end=None,
                window_mode=window_mode,
            )
            for name in [*short_clip_names, *trt_clip_names]
        ]

    jobs = [
        MediaJob(
            slug=f"{Path(name).stem}_03_05",
            source=TEST_CLIP_DIR / name,
            requested_start=REQUESTED_WINDOW_START,
            requested_end=REQUESTED_WINDOW_END,
            window_mode=window_mode,
        )
        for name in short_clip_names
    ]
    jobs.extend(
        [
            MediaJob(slug="trt_haber_1_full", source=TEST_CLIP_DIR / "trt_haber (1).mp4", requested_start=None, requested_end=None, window_mode=window_mode),
            MediaJob(slug="trt_haber_2_full", source=TEST_CLIP_DIR / "trt_haber (2).mp4", requested_start=None, requested_end=None, window_mode=window_mode),
            MediaJob(slug="trt_haber_3_full", source=TEST_CLIP_DIR / "trt_haber (3).mp4", requested_start=None, requested_end=None, window_mode=window_mode),
        ]
    )
    return jobs


def slug_from_name(name: str) -> str:
    return Path(name).stem.replace(" ", "_").replace("(", "").replace(")", "")


def prepare_audio(job: MediaJob, output_root: Path, *, ffmpeg: Path, ffprobe: Path) -> PreparedAudio:
    if not job.source.exists():
        raise FileNotFoundError(job.source)

    source_duration = probe_duration(job.source, ffprobe=ffprobe)
    actual_start, actual_end, mode = resolve_window(job, source_duration)
    job_root = output_root / job.slug
    audio_dir = job_root / "normalized"
    audio_dir.mkdir(parents=True, exist_ok=True)
    output_path = audio_dir / f"{job.slug}_16000hz_mono_s16.wav"

    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
    ]
    if actual_start > 0.0:
        command.extend(["-ss", f"{actual_start:.3f}"])
    if actual_end > actual_start:
        command.extend(["-t", f"{actual_end - actual_start:.3f}"])
    command.extend(
        [
            "-i",
            str(job.source),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(TARGET_SAMPLE_RATE),
            "-acodec",
            TARGET_CODEC_NAME,
            str(output_path),
        ]
    )
    subprocess.run(command, check=True)
    audio_duration = read_wav_duration_seconds(output_path)
    return PreparedAudio(
        job=job,
        output_path=output_path,
        source_duration=round(source_duration, 3),
        audio_duration=round(audio_duration, 3),
        actual_start=round(actual_start, 3),
        actual_end=round(actual_end, 3),
        mode=mode,
    )


def resolve_existing_prepared_audio(job: MediaJob, output_root: Path, *, ffprobe: Path) -> PreparedAudio:
    source_duration = probe_duration(job.source, ffprobe=ffprobe)
    actual_start, actual_end, mode = resolve_window(job, source_duration)
    output_path = output_root / job.slug / "normalized" / f"{job.slug}_16000hz_mono_s16.wav"
    audio_duration = read_wav_duration_seconds(output_path)
    return PreparedAudio(
        job=job,
        output_path=output_path,
        source_duration=round(source_duration, 3),
        audio_duration=round(audio_duration, 3),
        actual_start=round(actual_start, 3),
        actual_end=round(actual_end, 3),
        mode=mode,
    )


def prepared_item_to_dict(item: PreparedAudio) -> dict[str, Any]:
    return {
        "slug": item.job.slug,
        "source": str(item.job.source),
        "requested_start": item.job.requested_start,
        "requested_end": item.job.requested_end,
        "window_mode": item.job.window_mode,
        "output_path": str(item.output_path),
        "source_duration": item.source_duration,
        "audio_duration": item.audio_duration,
        "actual_start": item.actual_start,
        "actual_end": item.actual_end,
        "mode": item.mode,
    }


def run_variant_subprocess(module: str, audio_path: Path, output_root: Path, *, expected_dir: Path, ffmpeg: Path) -> dict[str, Any] | None:
    expected_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_VARIANT_FILES:
        path = expected_dir / name
        if path.exists():
            path.unlink()
    command = [
        sys.executable,
        "-m",
        module,
        "--audio",
        str(audio_path),
        "--out-root",
        str(output_root),
        "--ffmpeg",
        str(ffmpeg),
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode == 0:
        return None
    missing = [name for name in REQUIRED_VARIANT_FILES if not (expected_dir / name).exists()]
    if missing:
        raise RuntimeError(
            f"{module} failed before writing required outputs: exit={completed.returncode}, missing={missing}, stderr={completed.stderr.strip()}"
        )
    return {
        "module": module,
        "exit_code": completed.returncode,
        "warning": "nonzero_exit_after_required_outputs_written",
        "stderr_tail": completed.stderr.strip()[-2000:],
    }


def resolve_window(job: MediaJob, source_duration: float) -> tuple[float, float, str]:
    if job.window_mode == "midpoint_2min":
        start = max(0.0, source_duration / 2.0)
        end = min(source_duration, start + 120.0)
        mode = "midpoint_2min" if end - start >= 119.9 else "midpoint_2min_partial_to_end"
        return start, end, mode
    if job.requested_start is None or job.requested_end is None:
        return 0.0, source_duration, "full_requested"
    if source_duration <= job.requested_start:
        return 0.0, source_duration, "full_fallback_shorter_than_3min"
    actual_end = min(job.requested_end, source_duration)
    mode = "requested_03_05" if actual_end >= job.requested_end else "partial_fallback_source_ends_before_5min"
    return job.requested_start, actual_end, mode


def build_summary(prepared: Sequence[PreparedAudio], output_root: Path, *, elapsed_seconds: float) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    for item in prepared:
        job_root = output_root / item.job.slug
        variants = {
            "out_v7": read_variant_result(job_root / "out_v7"),
            "out_v11": read_variant_result(job_root / "out_v11"),
        }
        jobs.append(
            {
                "slug": item.job.slug,
                "source": str(item.job.source),
                "requested_start": item.job.requested_start,
                "requested_end": item.job.requested_end,
                "actual_start": item.actual_start,
                "actual_end": item.actual_end,
                "source_duration": item.source_duration,
                "audio_duration": item.audio_duration,
                "mode": item.mode,
                "variants": variants,
                "v7_v11_word_f1": round(word_overlap_f1(variants["out_v7"]["transcript"], variants["out_v11"]["transcript"]), 4),
                "v11_speedup": round(variants["out_v7"]["timing"]["total_seconds"] / variants["out_v11"]["timing"]["total_seconds"], 3)
                if variants["out_v11"]["timing"]["total_seconds"]
                else None,
            }
        )
    return {
        "output_root": str(output_root),
        "elapsed_seconds": elapsed_seconds,
        "jobs": jobs,
    }


def read_variant_result(output_dir: Path) -> dict[str, Any]:
    transcript = (output_dir / "clean_transcript.txt").read_text(encoding="utf-8")
    timing = json.loads((output_dir / "timing.json").read_text(encoding="utf-8"))
    filter_report = json.loads((output_dir / "filter_report.json").read_text(encoding="utf-8"))
    safety_report = json.loads((output_dir / "safety_report.json").read_text(encoding="utf-8"))
    clean_segments = json.loads((output_dir / "clean_segments.json").read_text(encoding="utf-8"))["segments"]
    bad_hits = {token: token.lower() in transcript.lower() for token in BAD_TOKENS}
    artifact_hits = {token: token.lower() in transcript.lower() for token in ARTIFACT_TOKENS}
    tokens = tokenize(transcript)
    return {
        "output_dir": str(output_dir),
        "transcript": transcript,
        "timing": timing,
        "filter_report": filter_report,
        "safety_report": safety_report,
        "word_count": len(tokenize(transcript)),
        "char_count": len(transcript),
        "segment_count": len(clean_segments),
        "bad_token_hits": bad_hits,
        "bad_token_count": sum(1 for hit in bad_hits.values() if hit),
        "artifact_token_hits": artifact_hits,
        "artifact_token_count": sum(1 for hit in artifact_hits.values() if hit),
        "max_consecutive_token_run": max_consecutive_token_run(tokens),
        "max_token_length": max((len(token) for token in tokens), default=0),
    }


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# v7 vs v11 Media Batch Report",
        "",
        f"- Output root: `{summary['output_root']}`",
        f"- Elapsed seconds: `{summary['elapsed_seconds']}`",
        f"- Nonzero exits after complete outputs: `{len(summary.get('run_warnings', []))}`",
        "",
        "| Job | Mode | Window | v7 words | v11 words | v7 total | v11 total | Speedup | Pair F1 | v7 bad | v11 bad |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for job in summary["jobs"]:
        v7 = job["variants"]["out_v7"]
        v11 = job["variants"]["out_v11"]
        lines.append(
            "| {slug} | {mode} | {actual_start:.3f}-{actual_end:.3f}s | {v7_words} | {v11_words} | {v7_total:.3f}s | {v11_total:.3f}s | {speedup:.3f}x | {pair_f1:.4f} | {v7_bad} | {v11_bad} |".format(
                slug=job["slug"],
                mode=job["mode"],
                actual_start=job["actual_start"],
                actual_end=job["actual_end"],
                v7_words=v7["word_count"],
                v11_words=v11["word_count"],
                v7_total=v7["timing"]["total_seconds"],
                v11_total=v11["timing"]["total_seconds"],
                speedup=job["v11_speedup"],
                pair_f1=job["v7_v11_word_f1"],
                v7_bad=v7["bad_token_count"],
                v11_bad=v11["bad_token_count"],
            )
        )

    lines.extend(["", "## Per Job Files", ""])
    for job in summary["jobs"]:
        lines.append(f"### {job['slug']}")
        lines.append("")
        lines.append(f"- Source: `{job['source']}`")
        lines.append(f"- Mode: `{job['mode']}`")
        lines.append(f"- Audio: `{job['actual_start']:.3f}-{job['actual_end']:.3f}s`")
        lines.append(f"- v7 transcript: `{job['variants']['out_v7']['output_dir']}\\clean_transcript.txt`")
        lines.append(f"- v11 transcript: `{job['variants']['out_v11']['output_dir']}\\clean_transcript.txt`")
        lines.append("")

    lines.extend(["", "## Artifact And Repetition Flags", ""])
    flagged = False
    for job in summary["jobs"]:
        for variant in ("out_v7", "out_v11"):
            result = job["variants"][variant]
            active_artifacts = [token for token, hit in result["artifact_token_hits"].items() if hit]
            if active_artifacts or result["max_consecutive_token_run"] >= 8 or result["max_token_length"] >= 40:
                flagged = True
                lines.append(
                    f"- `{job['slug']}` / `{variant}`: artifacts={active_artifacts}, "
                    f"max_token_run={result['max_consecutive_token_run']}, max_token_length={result['max_token_length']}"
                )
    if not flagged:
        lines.append("- No artifact/repetition flags.")

    lines.extend(["", "## Safety Decisions", ""])
    for job in summary["jobs"]:
        for variant in ("out_v7", "out_v11"):
            safety = job["variants"][variant]["safety_report"]
            lines.append(
                f"- `{job['slug']}` / `{variant}`: safe=`{safety['safe']}`, "
                f"failure=`{safety['failure_reason']}` diagnostics=`{safety['diagnostics']}`"
            )

    if summary.get("run_warnings"):
        lines.extend(["", "## Run Warnings", ""])
        for warning in summary["run_warnings"]:
            lines.append(
                f"- `{warning['job']}` / `{warning['variant']}`: exit `{warning['exit_code']}` after all required outputs were written."
            )
        lines.append("")

    lines.extend(
        [
            "## Decision Notes",
            "",
            "- Bu raporda referans transcript yok; `Pair F1`, v7 ve v11'in birbirine ne kadar benzediğini gösterir, doğruluk skoru değildir.",
            "- Nihai karar için tam transcriptler `full_transcripts.md` içinde yan yana okunmalıdır.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_full_transcripts(path: Path, summary: dict[str, Any]) -> None:
    lines = ["# v7 vs v11 Full Transcripts", ""]
    for job in summary["jobs"]:
        lines.append(f"## {job['slug']}")
        lines.append("")
        lines.append(f"- Source: `{job['source']}`")
        lines.append(f"- Mode: `{job['mode']}`")
        lines.append(f"- Window: `{job['actual_start']:.3f}-{job['actual_end']:.3f}s`")
        for variant in ("out_v7", "out_v11"):
            result = job["variants"][variant]
            lines.append("")
            lines.append(f"### {variant}")
            lines.append("")
            lines.append("```text")
            lines.append(result["transcript"].strip())
            lines.append("```")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def probe_duration(path: Path, *, ffprobe: Path) -> float:
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return float(completed.stdout.strip())


def word_overlap_f1(reference: str, candidate: str) -> float:
    reference_words = tokenize(reference)
    candidate_words = tokenize(candidate)
    if not reference_words or not candidate_words:
        return 0.0
    reference_counts: dict[str, int] = {}
    candidate_counts: dict[str, int] = {}
    for word in reference_words:
        reference_counts[word] = reference_counts.get(word, 0) + 1
    for word in candidate_words:
        candidate_counts[word] = candidate_counts.get(word, 0) + 1
    overlap = sum(min(reference_counts.get(word, 0), candidate_counts.get(word, 0)) for word in candidate_counts)
    precision = overlap / len(candidate_words)
    recall = overlap / len(reference_words)
    return 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"\w+", text, flags=re.UNICODE)]


def max_consecutive_token_run(tokens: Sequence[str]) -> int:
    best = 0
    current = 0
    previous: str | None = None
    for token in tokens:
        if token == previous:
            current += 1
        else:
            current = 1
            previous = token
        best = max(best, current)
    return best


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=asdict), encoding="utf-8")


if __name__ == "__main__":
    main()
