"""WhisperX word-level alignment wrapper for ASR pipeline artifacts."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any, Literal

from core.pipelines.asr.normalize import PROJECT_ROOT
from core.pipelines.asr.result import ProductionTranscribeResult, TranscriptSegment
from core.pipelines.asr.word_timing import (
    WORD_TIMING_METHOD,
    WORD_TIMING_OK_THRESHOLD,
    attach_word_timestamps,
    build_interpolated_word_timestamps,
    segment_words,
)


AlignmentMode = Literal["whisperx", "interpolated", "off"]

ALIGNMENT_STATUS_OK = "ok"
ALIGNMENT_STATUS_DEGRADED = "degraded"
ALIGNMENT_STATUS_FAILED = "failed"
ALIGNMENT_STATUS_SKIPPED = "skipped"
ALIGNMENT_STATUS_NOT_APPLICABLE = "not_applicable"
WHISPERX_WORD_TIMING_METHOD = "whisperx"

DEFAULT_ALIGNMENT_PYTHON = PROJECT_ROOT / "venvs" / "alignment" / "Scripts" / "python.exe"
DEFAULT_ALIGNMENT_SCRIPT = PROJECT_ROOT / "scripts" / "alignment_subprocess.py"
DEFAULT_ALIGNMENT_MODEL_DIR = PROJECT_ROOT / "models" / "alignment" / "whisperx"


@dataclass(frozen=True)
class AlignmentOutcome:
    """Summary of the word-level alignment stage."""

    status: str
    method: str
    expected_words: int
    aligned_words: int
    coverage: float | None
    runtime_sec: float
    success: bool | None
    reason: str | None = None
    fallback_method: str | None = None
    artifacts: tuple[str, ...] = ()
    details: tuple[dict[str, Any], ...] = ()


class AudioAlignmentError(RuntimeError):
    """Raised when the WhisperX subprocess cannot complete."""


def align_word_timestamps(
    result: ProductionTranscribeResult,
    *,
    normalized_outputs: dict[str, Path],
    run_dir: Path,
    mode: AlignmentMode = "whisperx",
    language: str = "tr",
    device: str = "cuda",
    python_executable: Path = DEFAULT_ALIGNMENT_PYTHON,
    script_path: Path = DEFAULT_ALIGNMENT_SCRIPT,
    model_dir: Path = DEFAULT_ALIGNMENT_MODEL_DIR,
    timeout_seconds: int = 1800,
) -> tuple[ProductionTranscribeResult, AlignmentOutcome]:
    """Attach word timestamps using WhisperX, with an explicit fallback report."""
    expected_words = _expected_word_count(result.clean_segments)
    if expected_words == 0:
        return result, AlignmentOutcome(
            status=ALIGNMENT_STATUS_NOT_APPLICABLE,
            method=mode,
            expected_words=0,
            aligned_words=0,
            coverage=None,
            runtime_sec=0.0,
            success=None,
            reason="no_transcript_words",
        )

    if mode == "off":
        return result, AlignmentOutcome(
            status=ALIGNMENT_STATUS_SKIPPED,
            method="off",
            expected_words=expected_words,
            aligned_words=0,
            coverage=0.0,
            runtime_sec=0.0,
            success=False,
            reason="word_alignment_disabled",
        )

    if mode == "interpolated":
        started = perf_counter()
        updated = attach_word_timestamps(result)
        aligned_words = _timestamp_word_count(updated.clean_segments)
        coverage = _coverage(aligned_words, expected_words)
        status = ALIGNMENT_STATUS_OK if coverage is not None and coverage >= WORD_TIMING_OK_THRESHOLD else ALIGNMENT_STATUS_DEGRADED
        return updated, AlignmentOutcome(
            status=status,
            method=WORD_TIMING_METHOD,
            expected_words=expected_words,
            aligned_words=aligned_words,
            coverage=coverage,
            runtime_sec=perf_counter() - started,
            success=status == ALIGNMENT_STATUS_OK,
            reason=None if status == ALIGNMENT_STATUS_OK else "interpolated_word_coverage_below_threshold",
        )

    started = perf_counter()
    try:
        updated, aligned_words, artifacts, details = _run_whisperx_alignment(
            result,
            normalized_outputs=normalized_outputs,
            run_dir=run_dir,
            language=language,
            device=device,
            python_executable=python_executable,
            script_path=script_path,
            model_dir=model_dir,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        fallback = attach_word_timestamps(result)
        return fallback, AlignmentOutcome(
            status=ALIGNMENT_STATUS_FAILED,
            method=WHISPERX_WORD_TIMING_METHOD,
            expected_words=expected_words,
            aligned_words=0,
            coverage=0.0,
            runtime_sec=perf_counter() - started,
            success=False,
            reason=str(exc) or type(exc).__name__,
            fallback_method=WORD_TIMING_METHOD,
        )

    coverage = _coverage(aligned_words, expected_words)
    status = ALIGNMENT_STATUS_OK if coverage is not None and coverage >= WORD_TIMING_OK_THRESHOLD else ALIGNMENT_STATUS_DEGRADED
    return updated, AlignmentOutcome(
        status=status,
        method=WHISPERX_WORD_TIMING_METHOD,
        expected_words=expected_words,
        aligned_words=aligned_words,
        coverage=coverage,
        runtime_sec=perf_counter() - started,
        success=status == ALIGNMENT_STATUS_OK,
        reason=None if status == ALIGNMENT_STATUS_OK else "whisperx_word_coverage_below_threshold",
        fallback_method=WORD_TIMING_METHOD if aligned_words < expected_words else None,
        artifacts=tuple(artifacts),
        details=tuple(details),
    )


def _run_whisperx_alignment(
    result: ProductionTranscribeResult,
    *,
    normalized_outputs: dict[str, Path],
    run_dir: Path,
    language: str,
    device: str,
    python_executable: Path,
    script_path: Path,
    model_dir: Path,
    timeout_seconds: int,
) -> tuple[ProductionTranscribeResult, int, list[str], list[dict[str, Any]]]:
    if not python_executable.exists():
        raise AudioAlignmentError(f"alignment_python_missing:{python_executable}")
    if not script_path.exists():
        raise AudioAlignmentError(f"alignment_script_missing:{script_path}")

    groups = _alignment_groups(result.clean_segments, normalized_outputs)
    if not groups:
        raise AudioAlignmentError("no_alignment_audio_for_segments")

    alignment_dir = run_dir / "alignment"
    alignment_dir.mkdir(parents=True, exist_ok=True)

    word_timestamps_by_index: dict[int, tuple[dict[str, Any], ...]] = {}
    artifacts: list[str] = []
    details: list[dict[str, Any]] = []
    aligned_word_count = 0

    for group_name, wav_path, segment_refs in groups:
        if not segment_refs:
            continue
        segments_path = alignment_dir / f"{group_name}_segments.json"
        output_path = alignment_dir / f"{group_name}_whisperx.json"
        _write_alignment_segments(segments_path, segment_refs)
        _run_alignment_subprocess(
            python_executable=python_executable,
            script_path=script_path,
            wav_path=wav_path,
            segments_path=segments_path,
            output_path=output_path,
            language=language,
            device=device,
            model_dir=model_dir,
            timeout_seconds=timeout_seconds,
        )
        payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
        result_payload = payload.get("result") or {}
        aligned_segments = result_payload.get("segments") or []
        raw_word_segments = result_payload.get("word_segments") or _flatten_segment_words(aligned_segments)
        artifacts.extend([str(segments_path), str(output_path)])
        details.append(
            {
                "group": group_name,
                "audio_path": str(wav_path),
                "input_segments": len(segment_refs),
                "aligned_segments": len(aligned_segments),
                "word_segments": len(raw_word_segments),
                "runtime_sec": payload.get("runtime_sec"),
            }
        )
        group_words = _collect_word_timestamps(raw_word_segments, segment_refs)
        retry_refs = _segments_needing_alignment_retry(group_words, segment_refs)
        if retry_refs:
            retry_segments_path = alignment_dir / f"{group_name}_retry_segments.json"
            retry_output_path = alignment_dir / f"{group_name}_retry_whisperx.json"
            _write_alignment_segments(retry_segments_path, retry_refs)
            try:
                _run_alignment_subprocess(
                    python_executable=python_executable,
                    script_path=script_path,
                    wav_path=wav_path,
                    segments_path=retry_segments_path,
                    output_path=retry_output_path,
                    language=language,
                    device=device,
                    model_dir=model_dir,
                    timeout_seconds=timeout_seconds,
                )
                retry_payload = json.loads(retry_output_path.read_text(encoding="utf-8-sig"))
                retry_result_payload = retry_payload.get("result") or {}
                retry_aligned_segments = retry_result_payload.get("segments") or []
                retry_raw_words = retry_result_payload.get("word_segments") or _flatten_segment_words(retry_aligned_segments)
                retry_words = _collect_word_timestamps(retry_raw_words, retry_refs)
                for segment_index, words in retry_words.items():
                    if len(words) > len(group_words.get(segment_index, ())):
                        group_words[segment_index] = words
                artifacts.extend([str(retry_segments_path), str(retry_output_path)])
                details.append(
                    {
                        "group": group_name,
                        "retry": True,
                        "input_segments": len(retry_refs),
                        "word_segments": len(retry_raw_words),
                        "runtime_sec": retry_payload.get("runtime_sec"),
                    }
                )
            except Exception as exc:
                artifacts.append(str(retry_segments_path))
                details.append(
                    {
                        "group": group_name,
                        "retry": True,
                        "input_segments": len(retry_refs),
                        "error": str(exc) or type(exc).__name__,
                    }
                )
        for segment_index, segment in segment_refs:
            words = tuple(group_words.get(segment_index) or ())
            aligned_word_count += min(len(words), len(segment_words(segment.text)))
            if not words:
                words = build_interpolated_word_timestamps(segment)
            word_timestamps_by_index[segment_index] = words

    updated_segments: list[TranscriptSegment] = []
    for index, segment in enumerate(result.clean_segments):
        words = word_timestamps_by_index.get(index)
        if words is None:
            words = build_interpolated_word_timestamps(segment)
        updated_segments.append(replace(segment, word_timestamps=words))

    return replace(result, clean_segments=updated_segments), aligned_word_count, artifacts, details


def _alignment_groups(
    segments: list[TranscriptSegment],
    normalized_outputs: dict[str, Path],
) -> list[tuple[str, Path, list[tuple[int, TranscriptSegment]]]]:
    has_split_channels = any(segment.channel in {"L", "R"} for segment in segments)
    groups: list[tuple[str, Path, list[tuple[int, TranscriptSegment]]]] = []

    if has_split_channels and {"L", "R"}.issubset(normalized_outputs):
        for channel in ("L", "R"):
            refs = [(index, segment) for index, segment in enumerate(segments) if segment.channel == channel]
            groups.append((channel, normalized_outputs[channel], refs))
        unchannelled = [(index, segment) for index, segment in enumerate(segments) if segment.channel not in {"L", "R"}]
        if unchannelled and "mono" in normalized_outputs:
            groups.append(("mono", normalized_outputs["mono"], unchannelled))
        return groups

    wav_path = normalized_outputs.get("mono") or next(iter(normalized_outputs.values()), None)
    if wav_path is None:
        return []
    return [("mono", wav_path, list(enumerate(segments)))]


def _write_alignment_segments(path: Path, segment_refs: list[tuple[int, TranscriptSegment]]) -> None:
    payload = {
        "segments": [
            {
                "index": index,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
            }
            for index, segment in segment_refs
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_alignment_subprocess(
    *,
    python_executable: Path,
    script_path: Path,
    wav_path: Path,
    segments_path: Path,
    output_path: Path,
    language: str,
    device: str,
    model_dir: Path,
    timeout_seconds: int,
) -> None:
    command = [
        str(python_executable),
        str(script_path),
        "--wav",
        str(wav_path),
        "--segments",
        str(segments_path),
        "--output",
        str(output_path),
        "--language",
        language,
        "--device",
        device,
        "--model-dir",
        str(model_dir),
        "--local-files-only",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or f"exit_code={completed.returncode}").strip()
        raise AudioAlignmentError(f"whisperx_alignment_failed:{stderr[-1200:]}")
    if not output_path.exists():
        raise AudioAlignmentError(f"whisperx_alignment_output_missing:{output_path}")


def _flatten_segment_words(aligned_segments: Any) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    if not isinstance(aligned_segments, list):
        return words
    for segment in aligned_segments:
        if not isinstance(segment, dict):
            continue
        raw_words = segment.get("words")
        if isinstance(raw_words, list):
            words.extend(word for word in raw_words if isinstance(word, dict))
    return words


def _collect_word_timestamps(
    raw_word_segments: Any,
    segment_refs: list[tuple[int, TranscriptSegment]],
) -> dict[int, list[dict[str, Any]]]:
    group_words: dict[int, list[dict[str, Any]]] = {segment_index: [] for segment_index, _ in segment_refs}
    if not isinstance(raw_word_segments, list):
        return group_words
    for raw_word in raw_word_segments:
        if not isinstance(raw_word, dict):
            continue
        target = _segment_ref_for_word(raw_word, segment_refs)
        if target is None:
            continue
        segment_index, segment = target
        word = _word_timestamp_from_raw_word(raw_word, segment)
        if word is None:
            continue
        group_words[segment_index].append(word)
    return group_words


def _segments_needing_alignment_retry(
    group_words: dict[int, list[dict[str, Any]]],
    segment_refs: list[tuple[int, TranscriptSegment]],
) -> list[tuple[int, TranscriptSegment]]:
    retry_refs: list[tuple[int, TranscriptSegment]] = []
    for segment_index, segment in segment_refs:
        expected_words = len(segment_words(segment.text))
        if expected_words > 0 and len(group_words.get(segment_index, ())) < expected_words:
            retry_refs.append((segment_index, segment))
    return retry_refs


def _segment_ref_for_word(
    raw_word: dict[str, Any],
    segment_refs: list[tuple[int, TranscriptSegment]],
) -> tuple[int, TranscriptSegment] | None:
    if not segment_refs:
        return None
    try:
        start = float(raw_word.get("start"))
        end = float(raw_word.get("end"))
    except (TypeError, ValueError):
        return None
    midpoint = (start + end) / 2.0
    for segment_ref in segment_refs:
        _, segment = segment_ref
        if segment.start <= midpoint <= segment.end:
            return segment_ref

    def overlap_seconds(segment: TranscriptSegment) -> float:
        return max(0.0, min(end, segment.end) - max(start, segment.start))

    best = max(segment_refs, key=lambda ref: overlap_seconds(ref[1]))
    if overlap_seconds(best[1]) > 0.0:
        return best
    return min(segment_refs, key=lambda ref: min(abs(midpoint - ref[1].start), abs(midpoint - ref[1].end)))


def _word_timestamp_from_raw_word(raw_word: dict[str, Any], source_segment: TranscriptSegment) -> dict[str, Any] | None:
    word = str(raw_word.get("word") or "").strip()
    if not word:
        return None
    start = _bounded_time(raw_word.get("start"), lower=source_segment.start, upper=source_segment.end)
    end = _bounded_time(raw_word.get("end"), lower=start, upper=source_segment.end)
    item: dict[str, Any] = {
        "word": word,
        "start": round(start, 3),
        "end": round(max(start, end), 3),
        "source": WHISPERX_WORD_TIMING_METHOD,
    }
    score = raw_word.get("score")
    if isinstance(score, (int, float)):
        item["score"] = round(float(score), 3)
    return item


def _bounded_time(value: Any, *, lower: float, upper: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(lower)
    return max(float(lower), min(float(upper), parsed))


def _expected_word_count(segments: list[TranscriptSegment]) -> int:
    return sum(len(segment_words(segment.text)) for segment in segments)


def _timestamp_word_count(segments: list[TranscriptSegment]) -> int:
    return sum(len(segment.word_timestamps) for segment in segments)


def _coverage(aligned_words: int, expected_words: int) -> float | None:
    if expected_words <= 0:
        return None
    return round(aligned_words / expected_words, 6)
