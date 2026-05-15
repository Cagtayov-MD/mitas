from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import asdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.pipelines.asr.transcribe import DEFAULT_FFMPEG_EXECUTABLE
from scripts.asr_model_final_benchmark import Sample, prepare_samples, prepared_audio_path, run_one_prediction


DEFAULT_SOURCE_ROOT = r"\\depo01cifs.int.trt.net.tr\sas_h264\testset\wav"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "asr_archive_all_wav_benchmark"
DEFAULT_FFPROBE_EXECUTABLE = str(Path(DEFAULT_FFMPEG_EXECUTABLE).with_name("ffprobe.exe"))
PROFILES = ("fast", "quality")
HIGH_NO_SPEECH_THRESHOLD = 0.10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full archive WAV ASR benchmark with sample-level parallelism.")
    parser.add_argument("--source-root", default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--ffmpeg", default=DEFAULT_FFMPEG_EXECUTABLE)
    parser.add_argument("--ffprobe", default=DEFAULT_FFPROBE_EXECUTABLE)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--worker-sample-id", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--manifest-json", type=Path, default=None, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest_json or args.out_root / "batch_manifest.json"

    if args.worker_sample_id:
        samples = load_manifest(manifest_path)
        sample_by_id = {sample.sample_id: sample for sample in samples}
        if args.worker_sample_id not in sample_by_id:
            raise SystemExit(f"Unknown worker sample id: {args.worker_sample_id}")
        run_worker(sample_by_id[args.worker_sample_id], args.out_root, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, force=args.force)
        return 0

    if args.manifest_json and args.manifest_json.exists():
        samples = json.loads(args.manifest_json.read_text(encoding="utf-8"))["samples"]
    else:
        samples = discover_samples(args.source_root, ffprobe=args.ffprobe)
        write_manifest(manifest_path, samples)

    if args.list_only:
        for sample in samples:
            print(f"{sample['sample_id']}\t{sample['duration_min']:.2f} min\t{sample['size_mb']:.1f} MB\t{Path(sample['source_path']).name}")
        print(f"total\t{sum(sample['duration_min'] for sample in samples):.2f} min\t{sum(sample['size_mb'] for sample in samples):.1f} MB")
        return 0

    return run_parent(samples, args.out_root, manifest_path, jobs=max(args.jobs, 1), ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, force=args.force)


def discover_samples(source_root: str, *, ffprobe: str) -> list[dict[str, Any]]:
    root = Path(source_root)
    wavs = sorted(root.glob("*.wav"), key=lambda path: path.stat().st_size)
    samples: list[dict[str, Any]] = []
    for index, path in enumerate(wavs, start=1):
        duration = probe_duration(path, ffprobe=ffprobe)
        samples.append(
            {
                "sample_id": f"{index:03d}_{slugify(path.stem)}",
                "source_path": str(path),
                "source_name": path.name,
                "size_bytes": path.stat().st_size,
                "size_mb": round(path.stat().st_size / 1_000_000, 3),
                "duration_sec": duration,
                "duration_min": round(duration / 60.0, 3),
            }
        )
    return samples


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text).strip("_").lower()
    return slug[:90] or "sample"


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


def write_manifest(path: Path, samples: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_manifest(path: Path) -> list[Sample]:
    data = json.loads(path.read_text(encoding="utf-8"))
    samples: list[Sample] = []
    for item in data["samples"]:
        samples.append(
            Sample(
                sample_id=item["sample_id"],
                category="archive_all_wav",
                source_path=Path(item["source_path"]),
                start_sec=None,
                end_sec=None,
                reference_path=PROJECT_ROOT / "references" / "asr_archive_all_wav" / f"{item['sample_id']}.txt",
                review_priority="medium",
                notes=item["source_name"],
            )
        )
    return samples


def run_parent(
    samples: list[dict[str, Any]],
    out_root: Path,
    manifest_path: Path,
    *,
    jobs: int,
    ffmpeg: str,
    ffprobe: str,
    force: bool,
) -> int:
    logs_dir = out_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    running: dict[str, subprocess.Popen[Any]] = {}
    pending = [sample for sample in samples if force or not sample_done(out_root, sample["sample_id"])]
    completed_skips = [sample["sample_id"] for sample in samples if sample not in pending]
    failures: dict[str, int] = {}
    started_at = time.time()
    write_progress(out_root, samples, running=running, pending=pending, failures=failures, started_at=started_at, completed_skips=completed_skips)

    while pending or running:
        while pending and len(running) < jobs:
            sample = pending.pop(0)
            sample_id = sample["sample_id"]
            log_path = logs_dir / f"{sample_id}.log"
            log_file = log_path.open("a", encoding="utf-8")
            log_file.write(f"\n=== START {timestamp()} {sample_id} ===\n")
            log_file.flush()
            command = [
                sys.executable,
                "-u",
                str(Path(__file__).resolve()),
                "--manifest-json",
                str(manifest_path),
                "--out-root",
                str(out_root),
                "--ffmpeg",
                ffmpeg,
                "--ffprobe",
                ffprobe,
                "--worker-sample-id",
                sample_id,
            ]
            if force:
                command.append("--force")
            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
            process._mitas_log_file = log_file  # type: ignore[attr-defined]
            running[sample_id] = process
        time.sleep(5)
        finished: list[str] = []
        for sample_id, process in running.items():
            code = process.poll()
            if code is None:
                continue
            log_file = getattr(process, "_mitas_log_file", None)
            if log_file:
                log_file.write(f"=== END {timestamp()} {sample_id} exit={code} ===\n")
                log_file.close()
            if code != 0:
                failures[sample_id] = code
            finished.append(sample_id)
        for sample_id in finished:
            del running[sample_id]
        if finished:
            write_progress(
                out_root,
                samples,
                running=running,
                pending=pending,
                failures=failures,
                started_at=started_at,
                completed_skips=completed_skips,
            )

    write_progress(out_root, samples, running=running, pending=pending, failures=failures, started_at=started_at, completed_skips=completed_skips)
    return 1 if failures else 0


def run_worker(sample: Sample, out_root: Path, *, ffmpeg: str, ffprobe: str, force: bool) -> None:
    print(f"sample={sample.sample_id}")
    audio_path = prepared_audio_path(out_root, sample)
    if force or not audio_path.exists():
        print("prepare=start")
        prepare_samples([sample], out_root, ffmpeg=ffmpeg, ffprobe=ffprobe)
        print("prepare=done")
    else:
        print("prepare=skip")
    for profile in PROFILES:
        transcript_path = out_root / sample.sample_id / profile / "transcript.txt"
        summary_path = out_root / sample.sample_id / profile / "summary.json"
        archive_path = out_root / sample.sample_id / profile / "archive.json"
        if not force and transcript_path.exists() and summary_path.exists() and archive_path.exists():
            print(f"profile={profile} skip")
            continue
        print(f"profile={profile} start")
        run_one_prediction(sample, profile, out_root, ffprobe=ffprobe)
        print(f"profile={profile} done")


def sample_done(out_root: Path, sample_id: str) -> bool:
    for profile in PROFILES:
        profile_dir = out_root / sample_id / profile
        if not (profile_dir / "transcript.txt").exists():
            return False
        if not (profile_dir / "summary.json").exists():
            return False
        if not (profile_dir / "archive.json").exists():
            return False
    return True


def write_progress(
    out_root: Path,
    samples: list[dict[str, Any]],
    *,
    running: dict[str, subprocess.Popen[Any]],
    pending: list[dict[str, Any]],
    failures: dict[str, int],
    started_at: float,
    completed_skips: list[str],
) -> None:
    sample_rows = [sample_status(out_root, sample, failures=failures, running=running, pending=pending) for sample in samples]
    payload = {
        "started_at": timestamp(started_at),
        "updated_at": timestamp(),
        "total_samples": len(samples),
        "completed": sum(1 for row in sample_rows if row["status"] == "complete"),
        "running": list(running),
        "pending": [sample["sample_id"] for sample in pending],
        "failed": failures,
        "completed_before_start": completed_skips,
        "samples": sample_rows,
    }
    (out_root / "batch_progress.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_batch_report(out_root / "batch_report.md", payload)


def sample_status(
    out_root: Path,
    sample: dict[str, Any],
    *,
    failures: dict[str, int],
    running: dict[str, subprocess.Popen[Any]],
    pending: list[dict[str, Any]],
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    row: dict[str, Any] = {
        "sample_id": sample_id,
        "source_name": sample["source_name"],
        "duration_min": sample["duration_min"],
        "size_mb": sample["size_mb"],
        "status": "pending",
        "profiles": {},
    }
    if sample_id in failures:
        row["status"] = "failed"
        row["exit_code"] = failures[sample_id]
    elif sample_id in running:
        row["status"] = "running"
    elif not any(item["sample_id"] == sample_id for item in pending):
        row["status"] = "complete" if sample_done(out_root, sample_id) else "partial"

    for profile in PROFILES:
        summary_path = out_root / sample_id / profile / "summary.json"
        archive_path = out_root / sample_id / profile / "archive.json"
        profile_row: dict[str, Any] = {"status": "missing"}
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            profile_row = {
                "status": "done",
                "runtime_seconds_wall": summary.get("runtime_seconds_wall"),
                "runtime_per_audio_minute": summary.get("runtime_per_audio_minute"),
                "clean_word_count": summary.get("clean_word_count"),
                "quality_drop_count": summary.get("quality_drop_count"),
                "safety_passed": summary.get("safety_passed"),
            }
        if archive_path.exists():
            archive = json.loads(archive_path.read_text(encoding="utf-8"))
            high_segments = [
                segment
                for segment in archive.get("segments", [])
                if float(segment.get("no_speech_prob") or 0.0) > HIGH_NO_SPEECH_THRESHOLD
            ]
            profile_row["high_no_speech_segments"] = len(high_segments)
            profile_row["high_no_speech_duration"] = round(
                sum(float(segment.get("end", 0.0)) - float(segment.get("start", 0.0)) for segment in high_segments),
                3,
            )
        row["profiles"][profile] = profile_row
    return row


def write_batch_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# ASR Archive All WAV Batch",
        "",
        f"- Updated: `{payload['updated_at']}`",
        f"- Completed: `{payload['completed']}/{payload['total_samples']}`",
        f"- Running: `{', '.join(payload['running']) or '-'}`",
        f"- Failed: `{', '.join(payload['failed']) or '-'}`",
        "",
        "| Sample | Min | MB | Status | Fast | Quality | Fast hi-ns | Quality hi-ns | Source |",
        "|---|---:|---:|---|---|---|---:|---:|---|",
    ]
    for row in payload["samples"]:
        fast = row["profiles"]["fast"]
        quality = row["profiles"]["quality"]
        lines.append(
            "| {sample} | {mins:.2f} | {mb:.1f} | {status} | {fast_status} | {quality_status} | {fast_hi} | {quality_hi} | {source} |".format(
                sample=row["sample_id"],
                mins=row["duration_min"],
                mb=row["size_mb"],
                status=row["status"],
                fast_status=format_profile(fast),
                quality_status=format_profile(quality),
                fast_hi=fast.get("high_no_speech_segments", "-"),
                quality_hi=quality.get("high_no_speech_segments", "-"),
                source=row["source_name"].replace("|", "\\|"),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_profile(profile: dict[str, Any]) -> str:
    if profile.get("status") != "done":
        return profile.get("status", "missing")
    runtime = profile.get("runtime_seconds_wall")
    rtf = profile.get("runtime_per_audio_minute")
    safe = profile.get("safety_passed")
    return f"done {runtime}s / {rtf} spm / safe={safe}"


def timestamp(value: float | None = None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value or time.time()))


if __name__ == "__main__":
    raise SystemExit(main())
