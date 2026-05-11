"""VAD-aware chunk merging for production ASR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.pipelines.asr.vad import VadSpeechSegment


DEFAULT_MIN_CHUNK_SECONDS = 12.0
DEFAULT_MAX_CHUNK_SECONDS = 30.0
DEFAULT_GAP_MERGE_SECONDS = 1.2
DEFAULT_PADDING_SECONDS = 1.0


@dataclass(frozen=True)
class MergedChunk:
    """Decode window built from one or more VAD speech segments."""

    index: int
    start: float
    end: float
    duration: float
    source_vad_indices: tuple[int, ...]


def build_merged_chunks(
    vad_segments: Sequence[VadSpeechSegment],
    *,
    audio_duration: float,
    min_chunk_seconds: float = DEFAULT_MIN_CHUNK_SECONDS,
    max_chunk_seconds: float = DEFAULT_MAX_CHUNK_SECONDS,
    gap_merge_seconds: float = DEFAULT_GAP_MERGE_SECONDS,
    padding_seconds: float = DEFAULT_PADDING_SECONDS,
) -> list[MergedChunk]:
    """Merge adjacent VAD segments into validated 12-30s decode windows."""
    if not vad_segments:
        return []
    if audio_duration <= 0.0:
        return []
    if min_chunk_seconds < 0.0 or max_chunk_seconds <= 0.0 or gap_merge_seconds < 0.0 or padding_seconds < 0.0:
        raise ValueError("chunking parameters must be non-negative and max_chunk_seconds must be positive")

    groups: list[tuple[float, float, list[int]]] = []
    current_start = vad_segments[0].start
    current_end = vad_segments[0].end
    current_indices = [0]

    for index, segment in enumerate(vad_segments[1:], start=1):
        gap = segment.start - current_end
        new_duration = segment.end - current_start
        if gap <= gap_merge_seconds and new_duration <= max_chunk_seconds:
            current_end = segment.end
            current_indices.append(index)
        else:
            groups.append((current_start, current_end, current_indices))
            current_start = segment.start
            current_end = segment.end
            current_indices = [index]
    groups.append((current_start, current_end, current_indices))

    expanded: list[tuple[float, float, list[int]]] = []
    for index, (start, end, indices) in enumerate(groups):
        left_bound = groups[index - 1][1] if index > 0 else 0.0
        right_bound = groups[index + 1][0] if index + 1 < len(groups) else audio_duration
        start = max(0.0, min(audio_duration, start))
        end = max(0.0, min(audio_duration, end))
        if end <= start:
            continue

        if end - start < min_chunk_seconds:
            available = max(0.0, right_bound - left_bound - (end - start))
            needed = min(min_chunk_seconds - (end - start), available)
            left = min(needed / 2.0, max(0.0, start - left_bound))
            right = min(needed - left, max(0.0, right_bound - end))
            remaining = needed - left - right
            if remaining > 0.0:
                left += min(remaining, max(0.0, start - left_bound - left))
            start = max(left_bound, start - left)
            end = min(right_bound, end + right)

        if end > start:
            expanded.append((start, end, indices))

    if not expanded:
        return []

    boundaries = [0.0]
    for index in range(len(expanded) - 1):
        boundary = (expanded[index][1] + expanded[index + 1][0]) / 2.0
        boundaries.append(max(boundaries[-1], min(audio_duration, boundary)))
    boundaries.append(audio_duration)

    chunks: list[MergedChunk] = []
    for index, (start, end, indices) in enumerate(expanded):
        chunk_start = max(boundaries[index], start - padding_seconds, 0.0)
        chunk_end = min(boundaries[index + 1], end + padding_seconds, audio_duration)
        if chunk_end <= chunk_start:
            continue
        duration = chunk_end - chunk_start
        if duration < 0.1:
            continue
        chunks.append(
            MergedChunk(
                index=len(chunks),
                start=round(chunk_start, 3),
                end=round(chunk_end, 3),
                duration=round(duration, 3),
                source_vad_indices=tuple(indices),
            )
        )

    return chunks
