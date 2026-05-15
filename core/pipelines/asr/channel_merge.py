"""Merge split-channel ASR results while preserving channel provenance."""

from __future__ import annotations

from dataclasses import replace
import re
from typing import Iterable

from core.pipelines.asr.result import ChannelDuplicateDrop, ProductionTranscribeResult, TranscriptSegment, TranscribeTiming


def merge_channel_results(
    left: ProductionTranscribeResult,
    right: ProductionTranscribeResult,
    *,
    time_iou_threshold: float = 0.60,
    token_jaccard_threshold: float = 0.85,
    min_segment_seconds: float = 0.5,
    min_tokens: int = 3,
) -> ProductionTranscribeResult:
    """Merge L/R transcripts and remove high-confidence cross-channel duplicates."""
    if abs(left.audio_duration - right.audio_duration) >= 0.1:
        raise ValueError(
            f"Cannot merge channel results with different durations: L={left.audio_duration}, R={right.audio_duration}"
        )

    raw_segments = _sort_segments([*left.raw_segments, *right.raw_segments])
    candidates = _sort_segments([*left.clean_segments, *right.clean_segments])
    kept: list[TranscriptSegment] = []
    duplicate_drops: list[ChannelDuplicateDrop] = []
    handled_ids: set[int] = set()
    dropped_ids: set[int] = set()

    for index, segment in enumerate(candidates):
        if id(segment) in handled_ids:
            continue
        duplicate_index = _find_duplicate_index(
            segment,
            candidates,
            start_index=index + 1,
            dropped_ids=dropped_ids,
            time_iou_threshold=time_iou_threshold,
            token_jaccard_threshold=token_jaccard_threshold,
            min_segment_seconds=min_segment_seconds,
            min_tokens=min_tokens,
        )
        if duplicate_index is None:
            kept.append(segment)
            handled_ids.add(id(segment))
            continue

        other = candidates[duplicate_index]
        winner, loser = _pick_winner(segment, other)
        kept.append(winner)
        handled_ids.add(id(winner))
        handled_ids.add(id(loser))
        dropped_ids.add(id(loser))
        duplicate_drops.append(
            ChannelDuplicateDrop(
                dropped_segment=loser,
                kept_segment=winner,
                time_iou=round(_time_iou(segment, other), 4),
                token_jaccard=round(_jaccard(set(_tokenize(segment.text)), set(_tokenize(other.text))), 4),
                dropped_score=round(_score(loser), 4),
                kept_score=round(_score(winner), 4),
            )
        )

    kept = [
        replace(segment, index=index)
        for index, segment in enumerate(_sort_segments(kept))
    ]
    return replace(
        left,
        audio_path=left.audio_path,
        audio_duration=max(left.audio_duration, right.audio_duration),
        fallback_triggered=left.fallback_triggered or right.fallback_triggered,
        fallback_reason=left.fallback_reason or right.fallback_reason,
        raw_segments=raw_segments,
        clean_segments=kept,
        verbatim_transcript=_build_verbatim(kept),
        clean_transcript=_build_clean_paragraphs(kept),
        quality_drops=[*left.quality_drops, *right.quality_drops],
        speaker_segments=[*left.speaker_segments, *right.speaker_segments],
        normalized_entities=[*left.normalized_entities, *right.normalized_entities],
        selection_reason=left.selection_reason or right.selection_reason,
        timing=_merge_timing(left.timing, right.timing),
        channel_mode="split",
        duplicate_drops=[*left.duplicate_drops, *right.duplicate_drops, *duplicate_drops],
        vad_speech_seconds=_max_optional(left.vad_speech_seconds, right.vad_speech_seconds),
        # Audit MED-6: max(L, R) speech ratio'nun gercek union'unun alt sinirini
        # raporlar; gercek union per-segment merge gerektirir. Iki kanal sicakca
        # konusursa true ratio max'in ustundedir. Capped union (min(1, L+R))
        # ust sinir verir; gercek deger bu iki bound arasinda yatar.
        vad_speech_ratio=_union_ratio_bound(left.vad_speech_ratio, right.vad_speech_ratio),
        vad_segment_count=_sum_optional(left.vad_segment_count, right.vad_segment_count),
    )


def tag_result_channel(result: ProductionTranscribeResult, channel: str) -> ProductionTranscribeResult:
    """Return a copy of a result with all transcript segments tagged with an audio channel."""
    return replace(
        result,
        raw_segments=[replace(segment, channel=channel) for segment in result.raw_segments],
        clean_segments=[replace(segment, channel=channel) for segment in result.clean_segments],
        channel_mode="split",
    )


def _find_duplicate_index(
    segment: TranscriptSegment,
    candidates: list[TranscriptSegment],
    *,
    start_index: int,
    dropped_ids: set[int],
    time_iou_threshold: float,
    token_jaccard_threshold: float,
    min_segment_seconds: float,
    min_tokens: int,
) -> int | None:
    for index in range(start_index, len(candidates)):
        other = candidates[index]
        if id(other) in dropped_ids:
            continue
        if _is_duplicate(
            segment,
            other,
            time_iou_threshold=time_iou_threshold,
            token_jaccard_threshold=token_jaccard_threshold,
            min_segment_seconds=min_segment_seconds,
            min_tokens=min_tokens,
        ):
            return index
    return None


def _is_duplicate(
    first: TranscriptSegment,
    second: TranscriptSegment,
    *,
    time_iou_threshold: float,
    token_jaccard_threshold: float,
    min_segment_seconds: float,
    min_tokens: int,
) -> bool:
    if first.channel == second.channel:
        return False
    if first.language != second.language:
        return False
    if first.end - first.start < min_segment_seconds or second.end - second.start < min_segment_seconds:
        return False
    first_tokens = set(_tokenize(first.text))
    second_tokens = set(_tokenize(second.text))
    if len(first_tokens) < min_tokens or len(second_tokens) < min_tokens:
        return False
    return (
        _time_iou(first, second) >= time_iou_threshold
        and _jaccard(first_tokens, second_tokens) >= token_jaccard_threshold
    )


def _pick_winner(first: TranscriptSegment, second: TranscriptSegment) -> tuple[TranscriptSegment, TranscriptSegment]:
    return (first, second) if _score(first) >= _score(second) else (second, first)


def _score(segment: TranscriptSegment) -> float:
    return segment.avg_logprob - (0.5 * segment.no_speech_prob)


def _time_iou(first: TranscriptSegment, second: TranscriptSegment) -> float:
    overlap = max(0.0, min(first.end, second.end) - max(first.start, second.start))
    union = max(first.end, second.end) - min(first.start, second.start)
    return 0.0 if union <= 0.0 else overlap / union


def _jaccard(first: set[str], second: set[str]) -> float:
    if not first and not second:
        return 1.0
    union = first | second
    return 0.0 if not union else len(first & second) / len(union)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def _sort_segments(segments: Iterable[TranscriptSegment]) -> list[TranscriptSegment]:
    return sorted(segments, key=lambda segment: (segment.start, segment.end, segment.channel or ""))


def _build_verbatim(segments: list[TranscriptSegment]) -> str:
    return " ".join(segment.text.strip() for segment in segments).strip()


def _build_clean_paragraphs(segments: list[TranscriptSegment]) -> str:
    if not segments:
        return ""
    paragraphs: list[list[str]] = [[segments[0].text.strip()]]
    last_end = segments[0].end
    for segment in segments[1:]:
        if segment.start - last_end >= 2.0:
            paragraphs.append([segment.text.strip()])
        else:
            paragraphs[-1].append(segment.text.strip())
        last_end = segment.end
    return "\n\n".join(" ".join(paragraph) for paragraph in paragraphs).strip()


def _max_optional(left: float | None, right: float | None) -> float | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _union_ratio_bound(left: float | None, right: float | None) -> float | None:
    """Capped upper bound for the union speech ratio (clipped L + R).

    Channel merge has per-channel ratios, not raw VAD intervals, so the true
    union cannot be computed here. The lower bound is max(L, R) (one channel
    speaks alone the entire time); the upper bound is min(1.0, L + R)
    (channels never overlap). True union sits between them. We surface the
    upper bound for conservative coverage signaling; downstream consumers must
    treat this as a bound, not an exact measurement.
    """
    if left is None:
        return right
    if right is None:
        return left
    return min(1.0, left + right)


def _sum_optional(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)


def _merge_timing(left: TranscribeTiming | None, right: TranscribeTiming | None) -> TranscribeTiming | None:
    if left is None and right is None:
        return None
    if left is None:
        return right
    if right is None:
        return left
    return TranscribeTiming(
        total_seconds=round(left.total_seconds + right.total_seconds, 3),
        chunk_count=left.chunk_count + right.chunk_count,
        decode_seconds=round(left.decode_seconds + right.decode_seconds, 3),
        fallback_seconds=round(left.fallback_seconds + right.fallback_seconds, 3),
    )
