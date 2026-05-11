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
class TranscribeTiming:
    """Performance metrics."""

    total_seconds: float
    chunk_count: int
    decode_seconds: float
    fallback_seconds: float = 0.0


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

    def to_archive_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable archive payload."""
        return {
            "audio_path": str(self.audio_path),
            "audio_duration": self.audio_duration,
            "model": self.model_name,
            "profile": self.profile_used,
            "fallback": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "transcript": {
                "verbatim": self.verbatim_transcript,
                "clean": self.clean_transcript,
                "normalized": self.normalized_transcript,
            },
            "segments": [
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "speaker": segment.speaker_id,
                    "flags": list(segment.flags),
                    "language": segment.language,
                }
                for segment in self.clean_segments
            ],
            "quality": {
                "drops": len(self.quality_drops),
                "drop_reasons": _count_reasons(self.quality_drops),
                "safety_passed": self.safety.safe if self.safety else None,
            },
            "timing": {
                "total_seconds": self.timing.total_seconds if self.timing else None,
                "chunk_count": self.timing.chunk_count if self.timing else None,
                "decode_seconds": self.timing.decode_seconds if self.timing else None,
                "fallback_seconds": self.timing.fallback_seconds if self.timing else None,
            },
        }


def _count_reasons(drops: list[DropRecord]) -> dict[str, int]:
    return dict(Counter(drop.reason for drop in drops))
