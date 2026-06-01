"""Word timing helpers for ASR artifacts."""

from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from core.pipelines.asr.result import ProductionTranscribeResult, TranscriptSegment


WORD_TIMING_METHOD = "segment_interpolated"
WORD_TIMING_OK_THRESHOLD = 0.95

_TOKEN_RE = re.compile(r"\S+")
_EDGE_PUNCTUATION = " \t\r\n\"'.,!?;:()[]{}<>"


def attach_word_timestamps(result: ProductionTranscribeResult) -> ProductionTranscribeResult:
    """Attach word-level timing metadata without changing transcript text."""
    updated_segments: list[TranscriptSegment] = []
    changed = False
    for segment in result.clean_segments:
        word_timestamps = segment.word_timestamps or build_interpolated_word_timestamps(segment)
        if word_timestamps != segment.word_timestamps:
            changed = True
        updated_segments.append(replace(segment, word_timestamps=word_timestamps))

    if not changed:
        return result
    return replace(result, clean_segments=updated_segments)


def build_interpolated_word_timestamps(segment: TranscriptSegment) -> tuple[dict[str, Any], ...]:
    """Spread segment words across the segment timebox when forced alignment is absent."""
    words = segment_words(segment.text)
    duration = max(0.0, float(segment.end) - float(segment.start))
    if not words or duration <= 0.0:
        return ()

    step = duration / len(words)
    timestamps: list[dict[str, Any]] = []
    for index, word in enumerate(words):
        start = round(float(segment.start) + (step * index), 3)
        if index == len(words) - 1:
            end = round(float(segment.end), 3)
        else:
            end = round(float(segment.start) + (step * (index + 1)), 3)
        timestamps.append(
            {
                "word": word,
                "start": start,
                "end": max(start, end),
                "source": WORD_TIMING_METHOD,
            }
        )
    return tuple(timestamps)


def summarize_word_timestamps(segments: list[TranscriptSegment]) -> dict[str, Any]:
    """Return coverage metrics for summary.quality_report."""
    expected_words = sum(len(segment_words(segment.text)) for segment in segments)
    aligned_words = sum(len(segment.word_timestamps) for segment in segments)

    if expected_words == 0:
        return {
            "method": WORD_TIMING_METHOD,
            "expected_words": 0,
            "aligned_words": aligned_words,
            "coverage": None,
            "status": "not_applicable",
            "reason": "no_transcript_words",
            "success": None,
        }

    coverage = round(aligned_words / expected_words, 6)
    if aligned_words == 0:
        status = "missing"
        reason = "word_timestamps_missing"
    elif coverage >= WORD_TIMING_OK_THRESHOLD:
        status = "ok"
        reason = None
    else:
        status = "degraded"
        reason = "word_timestamp_coverage_below_threshold"

    return {
        "method": WORD_TIMING_METHOD,
        "expected_words": expected_words,
        "aligned_words": aligned_words,
        "coverage": coverage,
        "status": status,
        "reason": reason,
        "success": status == "ok",
    }


def segment_words(text: str) -> tuple[str, ...]:
    """Tokenize enough for timing coverage without rewriting transcript text."""
    words: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        word = match.group(0).strip(_EDGE_PUNCTUATION)
        if word:
            words.append(word)
    return tuple(words)
