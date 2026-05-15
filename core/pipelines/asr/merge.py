"""Merge ASR transcript segments with pyannote speaker turns.

Paket 2 of the v0.1.x ASR maturation track wires the diarization output into
each transcript segment. Each `TranscriptSegment` is annotated with the
speaker turn that overlaps it the most; when the best overlap falls below the
configured ratio (Karar 15 graceful degradation), the segment gets
`speaker_id=None` instead of an unsafe guess.

This module only does the temporal merge. The actual diarization call lives
in `core.pipelines.asr.diarize` and the pipeline-level wiring (including the
`diarize_required` strict mode and Karar 16 partial-success behavior) lives
in `core.pipelines.asr.pipeline`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from core.pipelines.asr.diarize import DiarizationResult, DiarizationSegment
from core.pipelines.asr.result import TranscriptSegment


@dataclass(frozen=True)
class SpeakerMergeConfig:
    """Configuration knobs for the segment-speaker merge.

    `min_speaker_overlap_ratio` is the share of the transcript segment that
    must be covered by the best-matching diarization turn before we attach
    the speaker label. The default (0.5) implements the Karar 15 "düşük
    güven → speaker_id=null" rule directly.
    """

    min_speaker_overlap_ratio: float = 0.5


@dataclass(frozen=True)
class SpeakerMergeResult:
    """Outcome of merging diarization into a transcript.

    `low_confidence_count` is the number of transcript segments left with
    `speaker_id=None` because the best overlap was below the threshold (or
    there were no diarization turns at all). Used by the pipeline to decide
    whether the diarization run is "ok" vs "degraded".
    """

    segments: list[TranscriptSegment]
    speaker_count: int
    speakers: list[str]
    low_confidence_count: int


def merge_speakers_into_segments(
    transcript_segments: Sequence[TranscriptSegment],
    diarization: DiarizationResult,
    *,
    config: SpeakerMergeConfig | None = None,
) -> SpeakerMergeResult:
    """Attach the best-overlapping speaker label to each transcript segment.

    Returns the segments with `speaker_id` populated (or left None for
    low-confidence cases) plus aggregate diagnostics for the quality report.
    The diarization label set surfaced via `speakers` is the actual labels
    that ended up *attached* to at least one segment, not the raw pyannote
    label list — segments below threshold do not contribute speakers.
    """
    cfg = config or SpeakerMergeConfig()
    turns = list(diarization.segments)

    merged: list[TranscriptSegment] = []
    used_speakers: set[str] = set()
    low_confidence = 0

    for segment in transcript_segments:
        speaker_id = _pick_best_speaker(segment, turns, cfg.min_speaker_overlap_ratio)
        if speaker_id is None:
            low_confidence += 1
        else:
            used_speakers.add(speaker_id)
        merged.append(replace(segment, speaker_id=speaker_id))

    speakers_sorted = sorted(used_speakers)
    return SpeakerMergeResult(
        segments=merged,
        speaker_count=len(speakers_sorted),
        speakers=speakers_sorted,
        low_confidence_count=low_confidence,
    )


def _pick_best_speaker(
    segment: TranscriptSegment,
    turns: Sequence[DiarizationSegment],
    min_ratio: float,
) -> str | None:
    """Find the speaker turn with the largest overlap; return None on miss.

    Ratio is taken against the transcript segment's duration. Zero-length
    segments (start == end) are treated as low-confidence — there is no
    meaningful overlap to compute.
    """
    segment_duration = max(0.0, float(segment.end) - float(segment.start))
    if segment_duration <= 0.0 or not turns:
        return None

    best_speaker: str | None = None
    best_overlap = 0.0
    for turn in turns:
        overlap = _interval_overlap(segment.start, segment.end, turn.start, turn.end)
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = turn.speaker_id

    if best_speaker is None:
        return None

    ratio = best_overlap / segment_duration
    return best_speaker if ratio >= min_ratio else None


def _interval_overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    """Length of the temporal intersection of two intervals (≥ 0.0)."""
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))
