from __future__ import annotations

import pytest

from core.pipelines.asr.chunking import build_merged_chunks
from core.pipelines.asr.vad import VadSpeechSegment


def _mk(start: float, end: float) -> VadSpeechSegment:
    return VadSpeechSegment(start=start, end=end, duration=end - start)


class TestMergedChunks:
    def test_empty_input(self) -> None:
        assert build_merged_chunks([], audio_duration=10.0) == []

    def test_single_segment(self) -> None:
        chunks = build_merged_chunks([_mk(1.0, 5.0)], audio_duration=10.0)

        assert len(chunks) == 1
        assert chunks[0].source_vad_indices == (0,)
        assert chunks[0].duration > 0

    def test_merges_close_segments(self) -> None:
        chunks = build_merged_chunks(
            [_mk(0.0, 5.0), _mk(5.5, 10.0)],
            audio_duration=15.0,
        )

        assert len(chunks) == 1
        assert chunks[0].source_vad_indices == (0, 1)

    def test_splits_when_too_long(self) -> None:
        chunks = build_merged_chunks(
            [_mk(0.0, 20.0), _mk(20.5, 40.0)],
            audio_duration=50.0,
        )

        assert len(chunks) == 2

    def test_no_negative_chunks(self) -> None:
        chunks = build_merged_chunks(
            [_mk(0.0, 1.0), _mk(1.5, 3.0), _mk(3.2, 5.0)],
            audio_duration=10.0,
            padding_seconds=2.0,
        )

        for chunk in chunks:
            assert chunk.duration > 0
            assert chunk.end > chunk.start

    def test_no_overlap_between_chunks(self) -> None:
        chunks = build_merged_chunks(
            [_mk(0.0, 15.0), _mk(20.0, 35.0)],
            audio_duration=40.0,
        )

        for left, right in zip(chunks, chunks[1:]):
            assert left.end <= right.start

    def test_rejects_negative_parameters(self) -> None:
        with pytest.raises(ValueError):
            build_merged_chunks([_mk(0.0, 1.0)], audio_duration=2.0, padding_seconds=-1.0)
