from __future__ import annotations

from core.pipelines.asr.vad import VadSpeechSegment
from tools.asr_ab.common import build_merged_chunks


def test_build_merged_chunks_never_creates_negative_or_overlapping_chunks() -> None:
    vad_segments = [
        VadSpeechSegment(start=0.2, end=2.4, duration=2.2),
        VadSpeechSegment(start=7.2, end=7.3, duration=0.1),
        VadSpeechSegment(start=9.8, end=10.0, duration=0.2),
        VadSpeechSegment(start=11.0, end=38.4, duration=27.4),
        VadSpeechSegment(start=50.0, end=50.2, duration=0.2),
    ]

    chunks = build_merged_chunks(vad_segments, audio_duration=60.0)

    assert chunks
    assert all(chunk.end > chunk.start for chunk in chunks)
    assert all(left.end <= right.start for left, right in zip(chunks, chunks[1:]))
