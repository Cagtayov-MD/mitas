"""Frame-based OCR runner for MITAS Tedial jobs.

The OCR environment may have multiple engines installed. This runner prefers a
local OneOCR DLL when present, then Tesseract when the binary exists. If no
engine is usable it still extracts review frames and records a partial result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from time import perf_counter
from typing import Any

from core.schemas.common import JobStatus


OCR_MODULE_VERSION = "0.1"
OCR_PIPELINE_VERSION = "ocr_v0_1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class OcrPipelineRunResult:
    input_path: Path
    output_dir: Path
    frames_dir: Path
    summary_path: Path
    results_path: Path
    review_path: Path
    status: JobStatus
    error_msg: str | None


def run_ocr_pipeline(
    input_path: str | Path,
    *,
    output_dir: str | Path,
    media_id: str,
    job_id: str,
    interval_seconds: float = 10.0,
    max_frames: int = 24,
    engine: str = "auto",
    ffmpeg_executable: str | None = None,
) -> OcrPipelineRunResult:
    source = Path(input_path)
    run_dir = Path(output_dir)
    frames_dir = run_dir / "frames"
    run_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    ffmpeg = ffmpeg_executable or _resolve_ffmpeg()
    frames = _extract_frames(source, frames_dir, interval_seconds=interval_seconds, max_frames=max_frames, ffmpeg_executable=ffmpeg)

    engine_name = "frame_extraction_only"
    engine_error: str | None = None
    frame_results: list[dict[str, Any]] = []
    try:
        recognizer, engine_name = _build_recognizer(engine)
    except Exception as exc:
        recognizer = None
        engine_error = str(exc)

    for index, frame_path in enumerate(frames):
        timestamp = round(index * interval_seconds, 3)
        item: dict[str, Any] = {
            "frame": str(frame_path),
            "timestamp_seconds": timestamp,
            "text": "",
            "lines": [],
            "engine": engine_name,
        }
        if recognizer is not None:
            try:
                recognized = recognizer(frame_path)
                item.update(recognized)
            except Exception as exc:
                item["error"] = str(exc)
        frame_results.append(item)

    text_count = sum(1 for item in frame_results if str(item.get("text") or "").strip())
    completed_at = datetime.now(timezone.utc)
    status = JobStatus.done if recognizer is not None and text_count > 0 else JobStatus.partial
    error_msg = None if status == JobStatus.done else engine_error or "No OCR engine produced text; frames were extracted for review"

    summary = {
        "pipeline_version": OCR_PIPELINE_VERSION,
        "module_version": OCR_MODULE_VERSION,
        "job_id": job_id,
        "media_id": media_id,
        "input_path": str(source),
        "engine": engine_name,
        "status": status.value,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "runtime_sec": round(perf_counter() - started, 3),
        "frames": len(frames),
        "frames_with_text": text_count,
        "error_msg": error_msg,
        "outputs": {
            "summary": "ocr_summary.json",
            "results": "ocr_results.json",
            "review": "ocr_review.md",
            "frames_dir": "frames",
        },
    }
    results = {"summary": summary, "frames": frame_results}

    summary_path = run_dir / "ocr_summary.json"
    results_path = run_dir / "ocr_results.json"
    review_path = run_dir / "ocr_review.md"
    _write_json(summary_path, summary)
    _write_json(results_path, results)
    review_path.write_text(_build_review(summary, frame_results), encoding="utf-8")
    return OcrPipelineRunResult(
        input_path=source,
        output_dir=run_dir,
        frames_dir=frames_dir,
        summary_path=summary_path,
        results_path=results_path,
        review_path=review_path,
        status=status,
        error_msg=error_msg,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MITAS OCR on a video file")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--media-id", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--interval-seconds", type=float, default=10.0)
    parser.add_argument("--max-frames", type=int, default=24)
    parser.add_argument("--engine", default="auto")
    args = parser.parse_args(argv)

    result = run_ocr_pipeline(
        args.input,
        output_dir=args.output_dir,
        media_id=args.media_id,
        job_id=args.job_id,
        interval_seconds=args.interval_seconds,
        max_frames=args.max_frames,
        engine=args.engine,
    )
    print(json.dumps({"status": result.status.value, "summary_path": str(result.summary_path)}, ensure_ascii=False))
    return 0


def _extract_frames(
    input_path: Path,
    frames_dir: Path,
    *,
    interval_seconds: float,
    max_frames: int,
    ffmpeg_executable: str,
) -> list[Path]:
    for existing in frames_dir.glob("frame_*.png"):
        existing.unlink()
    fps_expr = f"fps=1/{max(interval_seconds, 0.1)}"
    pattern = frames_dir / "frame_%04d.png"
    command = [
        ffmpeg_executable,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-vf",
        fps_expr,
        "-frames:v",
        str(max(1, max_frames)),
        str(pattern),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "ffmpeg frame extraction failed").strip())
    return sorted(frames_dir.glob("frame_*.png"))


def _build_recognizer(engine: str):
    normalized = engine.strip().lower()
    if normalized in {"auto", "oneocr"}:
        try:
            import oneocr

            config_dir = Path(os.path.expanduser("~")) / ".config" / "oneocr"
            if not (config_dir / "oneocr.dll").exists():
                raise RuntimeError("OneOCR DLL is not configured")
            ocr = oneocr.OcrEngine()

            def recognize_oneocr(path: Path) -> dict[str, Any]:
                from PIL import Image

                result = ocr.recognize_pil(Image.open(path))
                return {
                    "text": result.get("text") or "",
                    "lines": result.get("lines") or [],
                    "engine": "oneocr",
                }

            return recognize_oneocr, "oneocr"
        except Exception:
            if normalized == "oneocr":
                raise

    if normalized in {"auto", "tesseract"}:
        try:
            if shutil.which("tesseract") is None:
                raise RuntimeError("tesseract binary is not on PATH")
            import pytesseract
            from PIL import Image

            def recognize_tesseract(path: Path) -> dict[str, Any]:
                text = pytesseract.image_to_string(Image.open(path), lang=os.environ.get("MITAS_TESSERACT_LANG", "tur+eng"))
                return {"text": text.strip(), "lines": [], "engine": "tesseract"}

            return recognize_tesseract, "tesseract"
        except Exception:
            if normalized == "tesseract":
                raise

    raise RuntimeError("No configured OCR engine is available")


def _resolve_ffmpeg() -> str:
    configured = os.environ.get("MITAS_FFMPEG", "").strip()
    if configured:
        return configured

    candidates = [
        PROJECT_ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe",
    ]
    for parent in PROJECT_ROOT.parents:
        candidates.append(parent / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe")
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "ffmpeg"


def _build_review(summary: dict[str, Any], frames: list[dict[str, Any]]) -> str:
    lines = [
        "# OCR Module Run Review",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Frame Text",
        "",
    ]
    for item in frames:
        text = str(item.get("text") or "").strip() or "[no text]"
        lines.append(f"- {item.get('timestamp_seconds')}s: {text}")
    lines.append("")
    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
