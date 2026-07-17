from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from typing import Any

from .models import DetectionConfig
from .window_detector import WindowClosingCreditOnsetDetector, WindowProtocolConfig


VIDEO_EXTENSIONS = {".mp4", ".mxf", ".mov", ".mkv", ".avi", ".m4v"}
TERMINAL_DETECTOR_STATUSES = {
    "FOUND",
    "REVIEW",
    "LEFT_CENSORED",
    "NOT_FOUND",
    "MODEL_ERROR",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_source_slug(source: Path, index: int) -> str:
    stem = re.sub(r"[^0-9A-Za-z]+", "_", source.stem).strip("_")
    stem = (stem or "video")[:54]
    identity = hashlib.sha256(str(source.resolve()).encode("utf-8")).hexdigest()[:10]
    return f"{index:03d}_{stem}_{identity}"


def discover_videos(root: Path) -> list[Path]:
    if not root.is_dir():
        raise FileNotFoundError(f"input root is not a directory: {root}")
    return sorted(
        (
            path for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def source_fingerprint(path: Path, *, edge_bytes: int = 1024 * 1024) -> dict[str, Any]:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        head = stream.read(edge_bytes)
        digest.update(head)
        if stat.st_size > edge_bytes:
            stream.seek(max(0, stat.st_size - edge_bytes))
            digest.update(stream.read(edge_bytes))
    return {
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "edge_sha256": digest.hexdigest(),
        "edge_bytes_each": edge_bytes,
    }


def probe_video(path: Path, ffprobe: Path, *, timeout_seconds: float = 120.0) -> dict[str, Any]:
    command = [
        str(ffprobe),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "format=duration,format_name:stream=codec_name,width,height,avg_frame_rate,r_frame_rate",
        "-of", "json",
        str(path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed rc={completed.returncode}: {completed.stderr[-1000:]}"
        )
    parsed = json.loads(completed.stdout)
    streams = parsed.get("streams") or []
    if not streams:
        raise RuntimeError("ffprobe returned no video stream")
    stream = streams[0]
    duration = float((parsed.get("format") or {}).get("duration"))
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError(f"invalid video duration: {duration}")
    return {
        "duration_seconds": duration,
        "format_name": (parsed.get("format") or {}).get("format_name"),
        "codec_name": stream.get("codec_name"),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "ffprobe_command": command,
    }


def extraction_contract(
    probe: dict[str, Any],
    *,
    tail_seconds: float,
    fps: float,
) -> dict[str, Any]:
    duration = float(probe["duration_seconds"])
    clip_seconds = min(duration, tail_seconds)
    tail_start = max(0.0, duration - clip_seconds)
    expected_frames = int(round(clip_seconds * fps))
    if expected_frames < 2:
        raise ValueError("tail/fps contract produces fewer than two frames")
    return {
        "duration_seconds": duration,
        "tail_start_seconds": tail_start,
        "clip_seconds": clip_seconds,
        "fps": fps,
        "expected_frames": expected_frames,
        "first_file": "c_0001.png",
        "last_file": f"c_{expected_frames:04d}.png",
    }


def build_ffmpeg_command(
    source: Path,
    stage_dir: Path,
    contract: dict[str, Any],
    ffmpeg: Path,
) -> list[str]:
    return [
        str(ffmpeg),
        "-nostdin",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-ss", f"{float(contract['tail_start_seconds']):.6f}",
        "-i", str(source),
        "-map", "0:v:0",
        "-t", f"{float(contract['clip_seconds']):.6f}",
        "-vf", f"fps={float(contract['fps']):.12g}",
        "-an", "-sn", "-dn",
        "-compression_level", "3",
        "-start_number", "1",
        str(stage_dir / "c_%04d.png"),
    ]


def _frame_sequence(directory: Path) -> list[Path]:
    return sorted(directory.glob("c_*.png"), key=lambda path: path.name)


def validate_frame_sequence(directory: Path, expected_frames: int) -> dict[str, Any]:
    frames = _frame_sequence(directory)
    expected_names = [f"c_{index:04d}.png" for index in range(1, expected_frames + 1)]
    got_names = [path.name for path in frames]
    errors: list[str] = []
    if len(frames) != expected_frames:
        errors.append(f"frame_count={len(frames)} expected={expected_frames}")
    if got_names != expected_names:
        mismatch = next(
            (
                index for index, (got, expected) in enumerate(
                    zip(got_names, expected_names), start=1
                )
                if got != expected
            ),
            min(len(got_names), len(expected_names)) + 1,
        )
        errors.append(f"non-contiguous frame sequence near ordinal={mismatch}")
    if frames and any(path.stat().st_size <= 0 for path in frames):
        errors.append("one or more extracted frames are empty")
    return {
        "ok": not errors,
        "frame_count": len(frames),
        "first_file": frames[0].name if frames else None,
        "last_file": frames[-1].name if frames else None,
        "size_bytes": sum(path.stat().st_size for path in frames),
        "errors": errors,
    }


def _next_numbered_path(parent: Path, prefix: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    for index in range(1, 10_000):
        candidate = parent / f"{prefix}_{index:03d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"no free numbered path under {parent}")


def _reusable_extraction(
    source_root: Path,
    *,
    fingerprint: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[Path, dict[str, Any]] | None:
    if not source_root.is_dir():
        return None
    for attempt in sorted(source_root.glob("extract_*"), reverse=True):
        manifest_path = attempt / "extraction.json"
        frames_dir = attempt / "frames" / "cikis"
        if not manifest_path.is_file() or not frames_dir.is_dir():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            manifest.get("status") != "COMPLETE"
            or manifest.get("source_fingerprint") != fingerprint
            or manifest.get("contract") != contract
        ):
            continue
        validation = validate_frame_sequence(frames_dir, int(contract["expected_frames"]))
        if validation["ok"] and validation == manifest.get("validation"):
            return frames_dir, manifest
    return None


def extract_video_tail(
    source: Path,
    source_root: Path,
    *,
    fingerprint: dict[str, Any],
    probe: dict[str, Any],
    contract: dict[str, Any],
    ffmpeg: Path,
    resume: bool,
    timeout_seconds: float,
) -> tuple[Path, dict[str, Any]]:
    if resume:
        reusable = _reusable_extraction(
            source_root,
            fingerprint=fingerprint,
            contract=contract,
        )
        if reusable is not None:
            return reusable

    attempt = _next_numbered_path(source_root, "extract")
    attempt.mkdir(parents=True, exist_ok=False)
    stage_dir = attempt / f"stage_{uuid.uuid4().hex}"
    stage_dir.mkdir(parents=True, exist_ok=False)
    final_frames = attempt / "frames" / "cikis"
    command = build_ffmpeg_command(source, stage_dir, contract, ffmpeg)
    started = time.perf_counter()
    completed: subprocess.CompletedProcess[str] | None = None
    error: str | None = None
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    stderr = completed.stderr if completed is not None else error or ""
    (attempt / "ffmpeg.stderr.txt").write_text(stderr, encoding="utf-8", newline="\n")
    validation = validate_frame_sequence(stage_dir, int(contract["expected_frames"]))
    return_code = completed.returncode if completed is not None else None
    status = "COMPLETE" if return_code == 0 and validation["ok"] else "ERROR"
    if status == "COMPLETE":
        final_frames.parent.mkdir(parents=True, exist_ok=True)
        stage_dir.replace(final_frames)
        validation = validate_frame_sequence(final_frames, int(contract["expected_frames"]))
    manifest = {
        "schema_version": "closing-credit-video-extraction/1.0",
        "status": status,
        "created_at": _utc_now(),
        "source": str(source.resolve()),
        "source_fingerprint": fingerprint,
        "probe": probe,
        "contract": contract,
        "ffmpeg_command": command,
        "ffmpeg_returncode": return_code,
        "elapsed_seconds": round(elapsed, 3),
        "validation": validation,
        "frames_dir": str(final_frames.resolve()) if status == "COMPLETE" else None,
        "error": error,
    }
    _atomic_write_json(attempt / "extraction.json", manifest)
    if status != "COMPLETE":
        raise RuntimeError(
            "frame extraction contract failed: "
            f"returncode={return_code}, errors={validation['errors']}, error={error}"
        )
    return final_frames, manifest


def _load_latest_rows(progress_path: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    if not progress_path.is_file():
        return latest
    for line in progress_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        source = row.get("source")
        if isinstance(source, str) and source:
            latest[source] = row
    return latest


def _completed_row_is_reusable(row: dict[str, Any], fingerprint: dict[str, Any]) -> bool:
    if row.get("batch_status") != "DONE":
        return False
    if row.get("source_fingerprint") != fingerprint:
        return False
    result_json = row.get("result_json")
    status = row.get("detector_status")
    return (
        status in TERMINAL_DETECTOR_STATUSES
        and isinstance(result_json, str)
        and Path(result_json).is_file()
    )


def _format_hms(seconds: float | None) -> str:
    if seconds is None:
        return ""
    value = max(0.0, float(seconds))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    secs = value % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def write_aggregate_artifacts(
    batch_root: Path,
    rows: list[dict[str, Any]],
    *,
    batch_meta: dict[str, Any],
) -> None:
    ordered = sorted(rows, key=lambda row: int(row.get("source_index") or 0))
    status_counts: dict[str, int] = {}
    for row in ordered:
        status = str(row.get("detector_status") or row.get("batch_status") or "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "schema_version": "closing-credit-video-batch/1.0",
        "updated_at": _utc_now(),
        "batch": batch_meta,
        "processed_count": len(ordered),
        "status_counts": status_counts,
        "results": ordered,
    }
    _atomic_write_json(batch_root / "summary.json", summary)

    fieldnames = [
        "source_index", "source_name", "source", "detector_status", "start_file",
        "start_pos", "tail_onset_seconds", "absolute_onset_seconds",
        "absolute_onset_hms", "video_remaining_seconds", "onset_kind",
        "confidence", "detector_wall_seconds", "extraction_seconds", "result_json",
        "reason", "batch_status",
    ]
    csv_path = batch_root / "results.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ordered)

    lines = [
        "# Closing-credit onset real-film batch",
        "",
        f"Updated: `{summary['updated_at']}`",
        "",
        f"Processed: **{len(ordered)} / {batch_meta['selected_count']}**",
        "",
        "Status counts: " + ", ".join(
            f"`{key}={value}`" for key, value in sorted(status_counts.items())
        ),
        "",
        "| # | Source | Status | Start | Absolute time | Detector s | Reason |",
        "|---:|---|---|---|---|---:|---|",
    ]
    for row in ordered:
        source_name = str(row.get("source_name") or "").replace("|", "\\|")
        reason = str(row.get("reason") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {row.get('source_index', '')} | {source_name} | "
            f"{row.get('detector_status') or row.get('batch_status', '')} | "
            f"{row.get('start_file') or ''} | {row.get('absolute_onset_hms') or ''} | "
            f"{row.get('detector_wall_seconds') or ''} | {reason[:160]} |"
        )
    lines.extend([
        "",
        "All detector decisions are experimental: `publishable=false` and "
        "`pool_may_be_replaced=false`. This table is runtime evidence, not yet "
        "a human-labelled accuracy verdict.",
        "",
    ])
    (batch_root / "REPORT.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def validate_roots(input_root: Path, scratch_root: Path, batch_root: Path, allowed_root: Path) -> None:
    input_resolved = input_root.resolve()
    scratch_resolved = scratch_root.resolve()
    batch_resolved = batch_root.resolve()
    allowed_resolved = allowed_root.resolve()
    if not input_resolved.is_dir():
        raise FileNotFoundError(f"input root is missing: {input_resolved}")
    if _is_relative_to(scratch_resolved, input_resolved):
        raise ValueError("scratch root must not be inside the read-only input root")
    if _is_relative_to(batch_resolved, input_resolved):
        raise ValueError("batch output must not be inside the read-only input root")
    if not _is_relative_to(batch_resolved, allowed_resolved):
        raise ValueError(f"batch output must stay under {allowed_resolved}")


def build_parser() -> argparse.ArgumentParser:
    repository_root = Path(__file__).resolve().parents[2]
    ffmpeg_bin = (
        repository_root / "tools" / "ffmpeg-shared" /
        "ffmpeg-8.1.1-full_build-shared" / "bin"
    )
    parser = argparse.ArgumentParser(
        description="TEST ONLY: extract fixed video tails and run window-boundary-v1 serially."
    )
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, default=ffmpeg_bin / "ffmpeg.exe")
    parser.add_argument("--ffprobe", type=Path, default=ffmpeg_bin / "ffprobe.exe")
    parser.add_argument("--tail-seconds", type=float, default=600.0)
    parser.add_argument("--fps", type=float, default=1.5)
    parser.add_argument("--model", default="qwen3-vl:30b")
    parser.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    parser.add_argument("--max-wall-seconds", type=float, default=120.0)
    parser.add_argument("--extract-timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--match", default=None, help="Unicode regex matched against filename")
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--force-detector",
        action="store_true",
        help="run a new detector attempt even when this source has a completed result",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    args = build_parser().parse_args(argv)
    if args.fps <= 0 or args.tail_seconds <= 0:
        raise ValueError("fps and tail-seconds must be > 0")
    repository_root = Path(__file__).resolve().parents[2]
    allowed_root = (repository_root / "outputs" / "closing_credit_onset_vlm").resolve()
    validate_roots(args.input_root, args.scratch_root, args.batch_root, allowed_root)
    for executable in (args.ffmpeg, args.ffprobe):
        if not executable.is_file():
            raise FileNotFoundError(f"required executable is missing: {executable}")

    discovered = discover_videos(args.input_root)
    indexed = list(enumerate(discovered, start=1))
    if args.match:
        matcher = re.compile(args.match, flags=re.IGNORECASE)
        indexed = [(index, path) for index, path in indexed if matcher.search(path.name)]
    indexed = [(index, path) for index, path in indexed if index >= args.start_index]
    if args.limit:
        indexed = indexed[: args.limit]
    if not indexed:
        raise RuntimeError("no videos selected")

    batch_root = args.batch_root.resolve()
    scratch_root = args.scratch_root.resolve()
    batch_root.mkdir(parents=True, exist_ok=True)
    scratch_root.mkdir(parents=True, exist_ok=True)
    progress_path = batch_root / "progress.jsonl"
    latest = _load_latest_rows(progress_path)
    batch_meta = {
        "schema_version": "closing-credit-video-batch/1.0",
        "created_or_resumed_at": _utc_now(),
        "input_root": str(args.input_root.resolve()),
        "scratch_root": str(scratch_root),
        "batch_root": str(batch_root),
        "discovered_count": len(discovered),
        "selected_count": len(indexed),
        "selected_sources": [str(path.resolve()) for _index, path in indexed],
        "tail_seconds": args.tail_seconds,
        "fps": args.fps,
        "model": args.model,
        "max_wall_seconds": args.max_wall_seconds,
        "ffmpeg": str(args.ffmpeg.resolve()),
        "ffprobe": str(args.ffprobe.resolve()),
        "resume": args.resume,
        "force_detector": args.force_detector,
        "publishable": False,
        "pool_may_be_replaced": False,
    }
    _atomic_write_json(batch_root / "batch_manifest.json", batch_meta)

    detector_config = DetectionConfig(
        fps=args.fps,
        model=args.model,
        ollama_host=args.ollama_host,
        max_wall_seconds=args.max_wall_seconds,
        keep_alive="10m",
        image_width=384,
        mosaic_columns=3,
        jpeg_quality=95,
        batch_size=9,
        fine_overlap=0,
        max_cv_proposals=16,
        proposal_min_distance_seconds=10.0,
        cv_width=320,
        num_ctx=4096,
        num_predict=64,
        seed=42,
        temperature=0.0,
        retry_count=2,
    )
    detector = WindowClosingCreditOnsetDetector(
        detector_config,
        protocol=WindowProtocolConfig(),
        allowed_output_root=allowed_root,
    )

    for selected_ordinal, (source_index, source) in enumerate(indexed, start=1):
        source_key = str(source.resolve())
        slug = safe_source_slug(source, source_index)
        fingerprint = source_fingerprint(source)
        previous = latest.get(source_key)
        if (
            args.resume
            and not args.force_detector
            and previous is not None
            and _completed_row_is_reusable(previous, fingerprint)
        ):
            print(
                json.dumps({
                    "event": "SKIP_COMPLETED",
                    "selected": f"{selected_ordinal}/{len(indexed)}",
                    "source_index": source_index,
                    "source": source.name,
                    "status": previous.get("detector_status"),
                }, ensure_ascii=False),
                flush=True,
            )
            continue

        event_started = time.perf_counter()
        base_row: dict[str, Any] = {
            "event_at": _utc_now(),
            "selected_ordinal": selected_ordinal,
            "selected_count": len(indexed),
            "source_index": source_index,
            "source_name": source.name,
            "source": source_key,
            "source_slug": slug,
            "source_fingerprint": fingerprint,
            "batch_status": "STARTED",
        }
        _append_jsonl(progress_path, base_row)
        print(
            json.dumps({
                "event": "START",
                "selected": f"{selected_ordinal}/{len(indexed)}",
                "source_index": source_index,
                "source": source.name,
            }, ensure_ascii=False),
            flush=True,
        )
        try:
            probe = probe_video(source, args.ffprobe)
            contract = extraction_contract(
                probe,
                tail_seconds=args.tail_seconds,
                fps=args.fps,
            )
            frames_dir, extraction = extract_video_tail(
                source,
                scratch_root / slug,
                fingerprint=fingerprint,
                probe=probe,
                contract=contract,
                ffmpeg=args.ffmpeg,
                resume=args.resume,
                timeout_seconds=args.extract_timeout_seconds,
            )
            film_output_parent = batch_root / "films" / slug
            attempt_dir = _next_numbered_path(film_output_parent, "attempt")
            result = detector.run(frames_dir, attempt_dir)
            result_dict = result.to_dict()
            tail_onset = result.start_time_seconds
            absolute_onset = (
                float(contract["tail_start_seconds"]) + float(tail_onset)
                if tail_onset is not None else None
            )
            remaining = (
                float(probe["duration_seconds"]) - absolute_onset
                if absolute_onset is not None else None
            )
            row = {
                **base_row,
                "event_at": _utc_now(),
                "batch_status": "DONE",
                "probe": probe,
                "contract": contract,
                "extraction_manifest": str(
                    (frames_dir.parents[1] / "extraction.json").resolve()
                ),
                "frames_dir": str(frames_dir.resolve()),
                "extraction_seconds": extraction.get("elapsed_seconds"),
                "detector_status": result.status,
                "start_pos": result.start_pos,
                "start_frame_no": result.start_frame_no,
                "start_file": result.start_file,
                "tail_onset_seconds": tail_onset,
                "absolute_onset_seconds": (
                    round(absolute_onset, 6) if absolute_onset is not None else None
                ),
                "absolute_onset_hms": _format_hms(absolute_onset),
                "video_remaining_seconds": (
                    round(remaining, 6) if remaining is not None else None
                ),
                "onset_kind": result.onset_kind,
                "confidence": result.confidence,
                "reason": result.reason,
                "detector_wall_seconds": result.metrics.get("total_wall_seconds"),
                "result_json": result.artifacts.get("result"),
                "run_output_dir": result.output_dir,
                "publishable": result.publishable,
                "pool_may_be_replaced": result.pool_may_be_replaced,
                "source_drift": result.metrics.get("source_drift"),
                "wall_budget_exhausted": result.metrics.get("wall_budget_exhausted"),
                "result": result_dict,
                "batch_item_wall_seconds": round(time.perf_counter() - event_started, 3),
            }
        except Exception as exc:  # noqa: BLE001
            row = {
                **base_row,
                "event_at": _utc_now(),
                "batch_status": "ERROR",
                "detector_status": None,
                "reason": f"{type(exc).__name__}: {exc}",
                "batch_item_wall_seconds": round(time.perf_counter() - event_started, 3),
            }
        _append_jsonl(progress_path, row)
        latest[source_key] = row
        write_aggregate_artifacts(
            batch_root,
            list(latest.values()),
            batch_meta=batch_meta,
        )
        print(
            json.dumps({
                "event": "DONE" if row["batch_status"] == "DONE" else "ERROR",
                "selected": f"{selected_ordinal}/{len(indexed)}",
                "source_index": source_index,
                "source": source.name,
                "status": row.get("detector_status") or row["batch_status"],
                "start_file": row.get("start_file"),
                "absolute_onset_hms": row.get("absolute_onset_hms"),
                "wall_seconds": row.get("batch_item_wall_seconds"),
                "reason": row.get("reason"),
            }, ensure_ascii=False),
            flush=True,
        )

    write_aggregate_artifacts(
        batch_root,
        list(latest.values()),
        batch_meta=batch_meta,
    )
    errors = sum(1 for row in latest.values() if row.get("batch_status") == "ERROR")
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
