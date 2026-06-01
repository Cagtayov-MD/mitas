"""Production transcription result dataclasses with Phase 2 hooks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.pipelines.asr.quality import ResultSafetyDecision


@dataclass(frozen=True)
class TranscriptSegment:
    """Single transcript segment."""

    index: int
    start: float
    end: float
    text: str
    language: str | None
    avg_logprob: float
    no_speech_prob: float
    source_chunk_index: int
    flags: tuple[str, ...] = ()
    speaker_id: str | None = None
    normalized_text: str | None = None
    source_vad_index: int | None = None
    channel: str | None = None
    word_timestamps: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class DropRecord:
    """Record for a segment removed by the quality gate."""

    original_index: int
    text: str
    start: float
    end: float
    reason: str
    flags: tuple[str, ...]


@dataclass(frozen=True)
class ChannelDuplicateDrop:
    """A cross-channel duplicate removed from the merged ASR transcript."""

    dropped_segment: TranscriptSegment
    kept_segment: TranscriptSegment
    time_iou: float
    token_jaccard: float
    dropped_score: float
    kept_score: float
    reason: str = "cross_channel_duplicate"


@dataclass(frozen=True)
class TranscribeTiming:
    """Performance metrics."""

    total_seconds: float
    chunk_count: int
    decode_seconds: float
    fallback_seconds: float = 0.0
    fallback_chunk_count: int = 0
    fallback_total_chunk_count: int = 0
    fallback_mode: str | None = None


@dataclass(frozen=True)
class ProductionTranscribeResult:
    """Main result object consumed by the MITAS pipeline."""

    audio_path: Path
    audio_duration: float
    profile_requested: str
    profile_used: str
    model_name: str
    fallback_triggered: bool
    fallback_reason: str | None
    raw_segments: list[TranscriptSegment]
    clean_segments: list[TranscriptSegment]
    verbatim_transcript: str
    clean_transcript: str
    normalized_transcript: str | None = None
    quality_drops: list[DropRecord] = field(default_factory=list)
    safety: ResultSafetyDecision | None = None
    timing: TranscribeTiming | None = None
    speaker_segments: list[Any] = field(default_factory=list)
    normalized_entities: list[Any] = field(default_factory=list)
    fallback_report: dict[str, Any] = field(default_factory=dict)
    selection_reason: str | None = None
    channel_mode: str = "mono"
    channel_auto_decided: bool = False
    lr_correlation: float | None = None
    duplicate_drops: list[ChannelDuplicateDrop] = field(default_factory=list)
    vad_speech_seconds: float | None = None
    vad_speech_ratio: float | None = None
    vad_segment_count: int | None = None

    def to_archive_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable archive payload."""
        archive = {
            "audio_path": str(self.audio_path),
            "audio_duration": self.audio_duration,
            "model": self.model_name,
            "profile": self.profile_used,
            "fallback": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "fallback_report": dict(self.fallback_report),
            "selection_reason": self.selection_reason,
            "transcript": {
                "verbatim": self.verbatim_transcript,
                "clean": self.clean_transcript,
                "normalized": self.normalized_transcript,
            },
            "segments": [_segment_to_dict(segment) for segment in self.clean_segments],
            "quality": {
                "drops": len(self.quality_drops),
                "drop_reasons": _count_reasons(self.quality_drops),
                "safety_passed": self.safety.safe if self.safety else None,
            },
            "normalized_entities": list(self.normalized_entities),
            "timing": {
                "total_seconds": self.timing.total_seconds if self.timing else None,
                "chunk_count": self.timing.chunk_count if self.timing else None,
                "decode_seconds": self.timing.decode_seconds if self.timing else None,
                "fallback_seconds": self.timing.fallback_seconds if self.timing else None,
                "fallback_chunk_count": self.timing.fallback_chunk_count if self.timing else None,
                "fallback_total_chunk_count": self.timing.fallback_total_chunk_count if self.timing else None,
                "fallback_mode": self.timing.fallback_mode if self.timing else None,
            },
        }
        if self.channel_mode != "mono" or self.channel_auto_decided or self.lr_correlation is not None or self.duplicate_drops:
            archive["channels"] = {
                "mode": self.channel_mode,
                "auto_decided": self.channel_auto_decided,
                "lr_correlation": self.lr_correlation,
                "tracks": _tracks_from_segments(self.clean_segments),
                "duplicate_drops": len(self.duplicate_drops),
                "duplicate_drop_records": [_duplicate_drop_to_dict(drop) for drop in self.duplicate_drops],
            }
        if self.vad_speech_ratio is not None or self.vad_speech_seconds is not None or self.vad_segment_count is not None:
            archive["vad"] = {
                "speech_seconds": self.vad_speech_seconds,
                "speech_ratio": self.vad_speech_ratio,
                "segment_count": self.vad_segment_count,
            }
        return archive


def _count_reasons(drops: list[DropRecord]) -> dict[str, int]:
    return dict(Counter(drop.reason for drop in drops))


def _segment_to_dict(segment: TranscriptSegment) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "start": segment.start,
        "end": segment.end,
        "text": segment.text,
        "speaker": segment.speaker_id,
        "flags": list(segment.flags),
        "language": segment.language,
        "avg_logprob": segment.avg_logprob,
        "no_speech_prob": segment.no_speech_prob,
        "source_chunk_index": segment.source_chunk_index,
    }
    if segment.source_vad_index is not None:
        payload["source_vad_index"] = segment.source_vad_index
    if segment.channel is not None:
        payload["channel"] = segment.channel
    if segment.normalized_text is not None:
        payload["normalized_text"] = segment.normalized_text
    if segment.word_timestamps:
        payload["word_timestamps"] = [dict(word) for word in segment.word_timestamps]
    return payload


def _duplicate_drop_to_dict(drop: ChannelDuplicateDrop) -> dict[str, Any]:
    return {
        "reason": drop.reason,
        "time_iou": drop.time_iou,
        "token_jaccard": drop.token_jaccard,
        "dropped_score": drop.dropped_score,
        "kept_score": drop.kept_score,
        "dropped": _segment_to_dict(drop.dropped_segment),
        "kept": _segment_to_dict(drop.kept_segment),
    }


def _tracks_from_segments(segments: list[TranscriptSegment]) -> list[str]:
    return sorted({segment.channel for segment in segments if segment.channel is not None})
