"""Phase 2: diarization smoothing and entity normalization hooks."""

from core.pipelines.asr.phase2.entity_normalization import normalize_entities
from core.pipelines.asr.phase2.speaker_merge import merge_speakers_into_transcript

__all__ = ["merge_speakers_into_transcript", "normalize_entities"]
