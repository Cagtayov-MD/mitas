"""
asr_backfill_silent_gaps.py — Audit & recover silent-gap holes in historical webui ASR jobs.

Usage:
    python scripts/asr_backfill_silent_gaps.py           # audit only
    python scripts/asr_backfill_silent_gaps.py --apply   # audit + re-run affected clips

The script scans outputs/webui_asr_jobs/asr-*/ jobs, identifies ones that were
processed by pre-fix code (no uncovered_vad_ranges diagnostic), recomputes the
silent-gap signature from the stored normalized.wav + archive segments, classifies
AT_RISK jobs, deduplicates by input media, and writes a report.

With --apply it re-runs the pipeline on each representative non-LONG AT_RISK media
into outputs/asr_backfill/<job_id>/run (never touching the original job dirs).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project root & path resolution
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
JOBS_DIR = PROJECT_ROOT / "outputs" / "webui_asr_jobs"
BACKFILL_DIR = PROJECT_ROOT / "outputs" / "asr_backfill"

# Thresholds matching the spec
AT_RISK_MIN_GAP_SECONDS = 8.0
AT_RISK_MIN_SPEECH_SECONDS = 3.0
LONG_DURATION_THRESHOLD = 1200.0  # >1200s → manual review, never auto-run

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

import io
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace"))],
)
logger = logging.getLogger("backfill")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class JobRecord:
    job_id: str
    job_dir: Path
    input_path: str
    output_dir: str
    profile: str
    channel_mode: str
    job_status: str          # "done" / "partial" / "failed"

    # Computed fields
    code_version: str        # "pre-fix" | "post-fix"
    audio_duration: float
    safety_safe: bool
    fallback_triggered: bool

    # Gap fields (populated by recompute)
    max_gap_range_seconds: float = 0.0
    max_gap_speech_seconds: float = 0.0
    max_gap_start: float = 0.0
    max_gap_end: float = 0.0
    all_gaps: list[dict[str, float]] | None = None

    # Classification
    classification: str = "ok"  # "ok" | "AT_RISK" | "LONG"

    # Dedup key
    media_key: str = ""

    # Error during gap recompute
    recompute_error: str | None = None


# ---------------------------------------------------------------------------
# Job scanning
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except Exception as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None


def _code_version(summary: dict[str, Any]) -> str:
    """post-fix if diagnostics contains uncovered_vad_ranges or max_uncovered_vad_gap_seconds."""
    diag = summary.get("safety", {}).get("diagnostics") or {}
    if "uncovered_vad_ranges" in diag or "max_uncovered_vad_gap_seconds" in diag:
        return "post-fix"
    return "pre-fix"


def scan_jobs() -> list[JobRecord]:
    records: list[JobRecord] = []
    for job_dir in sorted(JOBS_DIR.glob("asr-*")):
        job_json = job_dir / "job.json"
        summary_json = job_dir / "run" / "summary.json"
        archive_json = job_dir / "run" / "archive.json"

        if not job_json.exists() or not summary_json.exists() or not archive_json.exists():
            logger.debug("Skipping %s — missing required files", job_dir.name)
            continue

        job = _load_json(job_json)
        summary = _load_json(summary_json)
        if not job or not summary:
            continue

        job_id = job.get("job_id", job_dir.name)
        safety = summary.get("safety", {}) or {}
        rec = JobRecord(
            job_id=job_id,
            job_dir=job_dir,
            input_path=job.get("input_path", ""),
            output_dir=job.get("output_dir", ""),
            profile=job.get("profile", "fast_with_fallback"),
            channel_mode=job.get("channel_mode", "mono"),
            job_status=job.get("status", "unknown"),
            code_version=_code_version(summary),
            audio_duration=float(summary.get("audio_duration") or 0.0),
            safety_safe=bool(safety.get("safe", False)),
            fallback_triggered=bool(summary.get("fallback_triggered", False)),
        )
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Gap recomputation (CPU-only: just load cached VAD + segments)
# ---------------------------------------------------------------------------

def _segments_from_archive(archive: dict[str, Any]) -> list[Any]:
    """Rebuild TranscriptSegment list from archive.json segments."""
    from core.pipelines.asr.result import TranscriptSegment

    segs = []
    for idx, s in enumerate(archive.get("segments", [])):
        segs.append(
            TranscriptSegment(
                index=idx,
                start=float(s.get("start", 0.0)),
                end=float(s.get("end", 0.0)),
                text=s.get("text", ""),
                language=s.get("language"),
                avg_logprob=float(s.get("avg_logprob", 0.0) or 0.0),
                no_speech_prob=float(s.get("no_speech_prob", 0.0) or 0.0),
                source_chunk_index=int(s.get("source_chunk_index", 0) or 0),
                flags=tuple(s.get("flags", [])),
            )
        )
    return segs


def recompute_gaps(rec: JobRecord) -> None:
    """Run VAD + gap detection on the job's stored normalized.wav.

    Mutates rec in place: sets max_gap_*, all_gaps, classification, media_key.
    CPU-only — silero-vad uses torch but we do NOT load Whisper here.

    Files with audio_duration > LONG_DURATION_THRESHOLD are not VAD-processed:
    even if they had a gap they would go to manual-review only, and running
    Silero VAD on 2-hour+ WAVs takes ~10 min each. They are pre-classified LONG
    (if they would otherwise be AT_RISK) or skipped (if safety_safe=False /
    fallback=True). Gap values are not filled for skipped LONG files.
    """
    from core.pipelines.asr.vad import run_silero_vad
    from core.pipelines.asr.transcribe import _detect_uncovered_vad_ranges

    normalized_wav = rec.job_dir / "run" / "normalized.wav"
    archive_json = rec.job_dir / "run" / "archive.json"

    # Fast-path: if this job could only ever be LONG (audio already > threshold)
    # AND it was safe + no fallback, mark it LONG without running VAD.
    # If safe=False or fallback=True it cannot be AT_RISK regardless.
    if rec.audio_duration > LONG_DURATION_THRESHOLD:
        if rec.safety_safe and not rec.fallback_triggered:
            rec.classification = "LONG"
            rec.recompute_error = "skipped-VAD: LONG file (>1200s), manual-review only"
        else:
            rec.recompute_error = "skipped-VAD: LONG file, not AT_RISK (safe=False or fallback=True)"
        rec.media_key = _fallback_key(rec)
        return

    if not normalized_wav.exists():
        rec.recompute_error = "normalized.wav missing"
        return

    archive = _load_json(archive_json)
    if archive is None:
        rec.recompute_error = "archive.json unreadable"
        return

    try:
        vad_result = run_silero_vad(normalized_wav)
        vad_segs = vad_result.speech_segments
        # Override audio_duration from actual WAV if summary had it wrong
        rec.audio_duration = float(vad_result.audio_duration or rec.audio_duration)
    except Exception as exc:
        rec.recompute_error = f"VAD failed: {exc}"
        return

    try:
        clean_segs = _segments_from_archive(archive)
        gaps = _detect_uncovered_vad_ranges(clean_segs, vad_segs)
    except Exception as exc:
        rec.recompute_error = f"gap detect failed: {exc}"
        return

    rec.all_gaps = gaps
    if gaps:
        best = max(gaps, key=lambda g: g["range_seconds"])
        rec.max_gap_range_seconds = float(best["range_seconds"])
        rec.max_gap_speech_seconds = float(best["speech_seconds"])
        rec.max_gap_start = float(best["start"])
        rec.max_gap_end = float(best["end"])
    else:
        rec.max_gap_range_seconds = 0.0
        rec.max_gap_speech_seconds = 0.0

    # Classify
    is_at_risk = (
        rec.max_gap_range_seconds >= AT_RISK_MIN_GAP_SECONDS
        and rec.max_gap_speech_seconds >= AT_RISK_MIN_SPEECH_SECONDS
        and rec.safety_safe is True
        and not rec.fallback_triggered
    )
    if is_at_risk:
        if rec.audio_duration > LONG_DURATION_THRESHOLD:
            rec.classification = "LONG"
        else:
            rec.classification = "AT_RISK"

    # Build dedup media key
    input_file = Path(rec.input_path)
    if input_file.exists():
        try:
            sha = hashlib.sha256(input_file.read_bytes()).hexdigest()[:16]
            rec.media_key = f"sha:{sha}"
        except Exception:
            rec.media_key = _fallback_key(rec)
    else:
        rec.media_key = _fallback_key(rec)


def _fallback_key(rec: JobRecord) -> str:
    dur = round(rec.audio_duration, 1)
    gs = round(rec.max_gap_start, 0)
    ge = round(rec.max_gap_end, 0)
    return f"dur:{dur}:gap:{gs}-{ge}"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(records: list[JobRecord]) -> dict[str, JobRecord]:
    """For each media_key among AT_RISK/LONG, keep most-recent job (by job_id lex → use created_at if available)."""
    groups: dict[str, list[JobRecord]] = {}
    for rec in records:
        if rec.classification in ("AT_RISK", "LONG"):
            groups.setdefault(rec.media_key, []).append(rec)

    representatives: dict[str, JobRecord] = {}
    for key, group in groups.items():
        # Sort by job_id descending to pick most recent (job IDs are hex — use dir mtime as tiebreak)
        chosen = max(group, key=lambda r: r.job_dir.stat().st_mtime)
        representatives[key] = chosen
    return representatives


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------

def _fmt_gap(rec: JobRecord) -> str:
    if rec.max_gap_range_seconds == 0.0 and not rec.all_gaps:
        return "—"
    return f"{rec.max_gap_start:.1f}–{rec.max_gap_end:.1f}s ({rec.max_gap_range_seconds:.1f}s range, {rec.max_gap_speech_seconds:.1f}s speech)"


def write_report(
    records: list[JobRecord],
    representatives: dict[str, JobRecord],
    report_path: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pre_fix = [r for r in records if r.code_version == "pre-fix"]
    post_fix = [r for r in records if r.code_version == "post-fix"]
    at_risk = [r for r in records if r.classification == "AT_RISK"]
    long_review = [r for r in records if r.classification == "LONG"]
    worklist = [r for r in representatives.values() if r.classification == "AT_RISK"]
    manual = [r for r in representatives.values() if r.classification == "LONG"]

    lines = [
        "# ASR Backfill Silent-Gap Audit Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total jobs scanned | {len(records)} |",
        f"| Pre-fix code (no gap diagnostic) | {len(pre_fix)} |",
        f"| Post-fix code (has gap diagnostic) | {len(post_fix)} |",
        f"| AT_RISK (gap≥8s, speech≥3s, safe=true, no fallback) | {len(at_risk)} |",
        f"| LONG (>1200s audio, manual review only) | {len(long_review)} |",
        f"| Distinct media — auto recovery worklist | {len(worklist)} |",
        f"| Distinct media — manual review (LONG) | {len(manual)} |",
        "",
        "## Full Job Table",
        "",
        "| Job ID | Code Ver | Duration | safety.safe | fallback | Max Gap Region | Gap Range | Gap Speech | Classification |",
        "|--------|----------|----------|------------|----------|----------------|-----------|------------|----------------|",
    ]

    for rec in records:
        err = f" [ERR: {rec.recompute_error}]" if rec.recompute_error else ""
        gap_region = _fmt_gap(rec) + err
        lines.append(
            f"| {rec.job_id} | {rec.code_version} | {rec.audio_duration:.1f}s | "
            f"{rec.safety_safe} | {rec.fallback_triggered} | {gap_region} | "
            f"{rec.max_gap_range_seconds:.1f}s | {rec.max_gap_speech_seconds:.1f}s | "
            f"{rec.classification} |"
        )

    lines += [
        "",
        "## Recovery Worklist (non-LONG AT_RISK, deduplicated)",
        "",
    ]
    if worklist:
        lines += [
            "| Job ID | Input File | Duration | Max Gap Region | Media Key |",
            "|--------|-----------|---------|----------------|-----------|",
        ]
        for rec in sorted(worklist, key=lambda r: r.job_id):
            lines.append(
                f"| {rec.job_id} | {Path(rec.input_path).name} | "
                f"{rec.audio_duration:.1f}s | {_fmt_gap(rec)} | {rec.media_key} |"
            )
    else:
        lines.append("_No non-LONG AT_RISK media found._")

    lines += [
        "",
        "## Manual Review List (LONG clips >1200s)",
        "",
    ]
    if manual:
        lines += [
            "| Job ID | Input File | Duration | Max Gap Region |",
            "|--------|-----------|---------|----------------|",
        ]
        for rec in sorted(manual, key=lambda r: r.job_id):
            lines.append(
                f"| {rec.job_id} | {Path(rec.input_path).name} | "
                f"{rec.audio_duration:.1f}s | {_fmt_gap(rec)} |"
            )
    else:
        lines.append("_No LONG clips found._")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Report written: %s", report_path)


# ---------------------------------------------------------------------------
# Apply: re-run pipeline
# ---------------------------------------------------------------------------

def apply_recovery(
    worklist: list[JobRecord],
    report_path: Path,
) -> None:
    """Re-run each representative non-LONG AT_RISK job into outputs/asr_backfill/<job_id>/run."""
    from core.pipelines.asr.pipeline import run_asr_pipeline

    append_lines: list[str] = [
        "",
        "## Recovery Results (--apply)",
        "",
        "| Job ID | Input | Old Gap | New fallback_triggered | New safety | Recovered Text Snippet |",
        "|--------|-------|---------|----------------------|-----------|----------------------|",
    ]

    for rec in sorted(worklist, key=lambda r: r.job_id):
        logger.info("Re-running pipeline for %s (input: %s)", rec.job_id, rec.input_path)
        old_gap = _fmt_gap(rec)
        new_output_dir = BACKFILL_DIR / rec.job_id / "run"

        try:
            result = run_asr_pipeline(
                rec.input_path,
                profile=rec.profile if rec.profile in ("fast_with_fallback", "quality", "fast") else "fast_with_fallback",
                channel_mode=rec.channel_mode if rec.channel_mode in ("mono", "split", "auto") else "mono",
                output_dir=new_output_dir,
                media_id=rec.job_id,
                job_id=f"backfill-{rec.job_id}",
            )

            tr = result.transcribe_result
            safety = tr.safety
            new_fallback = tr.fallback_triggered
            new_safe = safety.safe if safety else None
            new_failure = (safety.failure_reason or "") if safety else ""

            # Extract recovered text near the old gap
            gap_start = rec.max_gap_start - 2.0
            gap_end = rec.max_gap_end + 2.0
            recovered_segs = [
                s for s in tr.clean_segments
                if s.start >= gap_start and s.start <= gap_end
            ]
            snippet = " | ".join(s.text.strip() for s in recovered_segs[:4])
            if not snippet:
                # Widen search — use all new segments if the gap region produced nothing
                snippet = " | ".join(s.text.strip() for s in tr.clean_segments[:3])
            if not snippet:
                snippet = "[no text recovered]"
            snippet = snippet[:200]  # truncate for table

            status_str = f"fallback={new_fallback} safe={new_safe}"
            if new_failure:
                status_str += f" reason={new_failure[:60]}"

            append_lines.append(
                f"| {rec.job_id} | {Path(rec.input_path).name} | {old_gap} | "
                f"{new_fallback} | {status_str} | {snippet} |"
            )
            logger.info("  Done — fallback=%s safe=%s", new_fallback, new_safe)

        except Exception as exc:
            tb = traceback.format_exc(limit=4)
            logger.error("  FAILED for %s: %s", rec.job_id, exc)
            append_lines.append(
                f"| {rec.job_id} | {Path(rec.input_path).name} | {old_gap} | "
                f"ERROR | ERROR | {str(exc)[:150]} |"
            )
            # Also save traceback to a file
            err_path = BACKFILL_DIR / rec.job_id / "backfill_error.txt"
            err_path.parent.mkdir(parents=True, exist_ok=True)
            err_path.write_text(tb, encoding="utf-8")

    # Append to report
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n".join(append_lines) + "\n")
    logger.info("Recovery results appended to report.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and recover silent-gap holes in historical ASR jobs.")
    parser.add_argument("--apply", action="store_true", help="Re-run pipeline for AT_RISK non-LONG media.")
    args = parser.parse_args()

    # Add project root to sys.path so core imports work
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    logger.info("Scanning jobs under %s", JOBS_DIR)
    records = scan_jobs()
    logger.info("Found %d jobs with run/summary.json + run/archive.json", len(records))

    pre_fix_records = [r for r in records if r.code_version == "pre-fix"]
    logger.info("%d pre-fix jobs to recompute gaps for", len(pre_fix_records))

    # Recompute gaps for ALL records (both pre- and post-fix, so table is complete)
    for i, rec in enumerate(records):
        logger.info("[%d/%d] Recomputing gaps: %s (code=%s)", i + 1, len(records), rec.job_id, rec.code_version)
        recompute_gaps(rec)
        if rec.recompute_error:
            logger.warning("  Error: %s", rec.recompute_error)
        else:
            logger.info(
                "  audio=%.1fs max_gap=%.1fs speech=%.1fs -> %s",
                rec.audio_duration,
                rec.max_gap_range_seconds,
                rec.max_gap_speech_seconds,
                rec.classification,
            )

    representatives = deduplicate(records)
    worklist = [r for r in representatives.values() if r.classification == "AT_RISK"]
    manual = [r for r in representatives.values() if r.classification == "LONG"]

    at_risk_all = [r for r in records if r.classification == "AT_RISK"]
    long_all = [r for r in records if r.classification == "LONG"]

    logger.info(
        "Summary: total=%d pre_fix=%d at_risk=%d (distinct=%d) long=%d (distinct=%d)",
        len(records),
        len(pre_fix_records),
        len(at_risk_all),
        len(worklist),
        len(long_all),
        len(manual),
    )

    report_path = BACKFILL_DIR / "REPORT.md"
    write_report(records, representatives, report_path)

    if args.apply:
        if not worklist:
            logger.info("No non-LONG AT_RISK media to recover.")
        else:
            logger.info("Starting recovery for %d media items (sequential)...", len(worklist))
            apply_recovery(worklist, report_path)
    else:
        logger.info("Audit-only mode. Re-run with --apply to recover affected clips.")
        logger.info("Report: %s", report_path)

    # Print concise console summary
    print("\n" + "=" * 70)
    print("BACKFILL AUDIT SUMMARY")
    print("=" * 70)
    print(f"  Total jobs scanned   : {len(records)}")
    print(f"  Pre-fix code         : {len(pre_fix_records)}")
    print(f"  AT_RISK (all)        : {len(at_risk_all)}")
    print(f"  Distinct media (AT_RISK, non-LONG) : {len(worklist)}")
    print(f"  LONG manual-review   : {len(manual)}")
    print(f"  Report               : {report_path}")
    print("=" * 70)

    for rec in sorted(worklist, key=lambda r: r.job_id):
        print(f"  WORKLIST: {rec.job_id}  gap={rec.max_gap_start:.1f}–{rec.max_gap_end:.1f}s  "
              f"range={rec.max_gap_range_seconds:.1f}s  speech={rec.max_gap_speech_seconds:.1f}s  "
              f"audio={rec.audio_duration:.1f}s  input={Path(rec.input_path).name}")
    for rec in sorted(manual, key=lambda r: r.job_id):
        print(f"  MANUAL  : {rec.job_id}  gap={rec.max_gap_start:.1f}–{rec.max_gap_end:.1f}s  "
              f"audio={rec.audio_duration:.1f}s  input={Path(rec.input_path).name}")
    print()


if __name__ == "__main__":
    main()
