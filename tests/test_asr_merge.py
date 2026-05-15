"""Unit tests for the segment-speaker merge module (v0.1.x Paket 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.pipelines.asr.diarize import DiarizationResult, DiarizationSegment
from core.pipelines.asr.merge import (
    SpeakerMergeConfig,
    merge_speakers_into_segments,
)
from core.pipelines.asr.result import TranscriptSegment


def _seg(index: int, start: float, end: float, text: str = "konuşma") -> TranscriptSegment:
    return TranscriptSegment(
        index=index,
        start=start,
        end=end,
        text=text,
        language="tr",
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        source_chunk_index=0,
    )


def _diarization(*turns: DiarizationSegment) -> DiarizationResult:
    speakers = sorted({turn.speaker_id for turn in turns})
    return DiarizationResult(
        audio_path=Path("/fake/normalized.wav"),
        model_id="pyannote/test",
        device="cpu",
        segments=list(turns),
        speaker_count=len(speakers),
        speakers=speakers,
    )


def _turn(start: float, end: float, speaker: str) -> DiarizationSegment:
    return DiarizationSegment(
        start=start,
        end=end,
        duration=round(end - start, 3),
        speaker_id=speaker,
    )


class TestMergeBasics:
    def test_full_overlap_assigns_speaker(self) -> None:
        segments = [_seg(0, 1.0, 4.0)]
        diarization = _diarization(_turn(0.5, 4.5, "SPEAKER_00"))

        result = merge_speakers_into_segments(segments, diarization)

        assert result.segments[0].speaker_id == "SPEAKER_00"
        assert result.speaker_count == 1
        assert result.speakers == ["SPEAKER_00"]
        assert result.low_confidence_count == 0

    def test_overlap_below_threshold_returns_null(self) -> None:
        # transcript 0.0-4.0; turn covers 0.0-1.0 only (25%) → below default 0.5
        segments = [_seg(0, 0.0, 4.0)]
        diarization = _diarization(_turn(0.0, 1.0, "SPEAKER_00"))

        result = merge_speakers_into_segments(segments, diarization)

        assert result.segments[0].speaker_id is None
        assert result.low_confidence_count == 1
        assert result.speakers == []
        assert result.speaker_count == 0

    def test_picks_speaker_with_largest_overlap(self) -> None:
        # transcript 0.0-4.0; speaker A covers 0.0-1.0 (25%), B covers 1.0-3.5 (62.5%)
        segments = [_seg(0, 0.0, 4.0)]
        diarization = _diarization(
            _turn(0.0, 1.0, "SPEAKER_A"),
            _turn(1.0, 3.5, "SPEAKER_B"),
        )

        result = merge_speakers_into_segments(segments, diarization)

        assert result.segments[0].speaker_id == "SPEAKER_B"
        assert result.speakers == ["SPEAKER_B"]

    def test_speakers_list_only_reflects_used_labels(self) -> None:
        # diarization knows about A, B, C; only A meets threshold for the one segment
        segments = [_seg(0, 0.0, 2.0)]
        diarization = _diarization(
            _turn(0.0, 2.0, "SPEAKER_A"),
            _turn(5.0, 6.0, "SPEAKER_B"),
            _turn(7.0, 8.0, "SPEAKER_C"),
        )

        result = merge_speakers_into_segments(segments, diarization)

        assert result.segments[0].speaker_id == "SPEAKER_A"
        assert result.speakers == ["SPEAKER_A"]
        assert result.speaker_count == 1

    def test_no_diarization_turns_returns_all_null(self) -> None:
        segments = [_seg(0, 0.0, 2.0), _seg(1, 2.0, 4.0)]
        diarization = _diarization()

        result = merge_speakers_into_segments(segments, diarization)

        assert all(segment.speaker_id is None for segment in result.segments)
        assert result.low_confidence_count == 2
        assert result.speaker_count == 0

    def test_zero_duration_segment_returns_null(self) -> None:
        segments = [_seg(0, 1.0, 1.0)]
        diarization = _diarization(_turn(0.5, 2.0, "SPEAKER_00"))

        result = merge_speakers_into_segments(segments, diarization)

        assert result.segments[0].speaker_id is None
        assert result.low_confidence_count == 1

    def test_no_temporal_overlap_returns_null(self) -> None:
        segments = [_seg(0, 0.0, 2.0)]
        diarization = _diarization(_turn(5.0, 8.0, "SPEAKER_00"))

        result = merge_speakers_into_segments(segments, diarization)

        assert result.segments[0].speaker_id is None
        assert result.low_confidence_count == 1


class TestMergeConfig:
    def test_custom_min_overlap_ratio_is_respected(self) -> None:
        # transcript 0.0-4.0; turn covers 0.0-1.2 (30%)
        segments = [_seg(0, 0.0, 4.0)]
        diarization = _diarization(_turn(0.0, 1.2, "SPEAKER_00"))

        relaxed = merge_speakers_into_segments(
            segments,
            diarization,
            config=SpeakerMergeConfig(min_speaker_overlap_ratio=0.25),
        )
        strict = merge_speakers_into_segments(
            segments,
            diarization,
            config=SpeakerMergeConfig(min_speaker_overlap_ratio=0.5),
        )

        assert relaxed.segments[0].speaker_id == "SPEAKER_00"
        assert strict.segments[0].speaker_id is None


class TestMergeManySegments:
    def test_mixed_threshold_outcomes_counted_correctly(self) -> None:
        segments = [
            _seg(0, 0.0, 2.0),   # fully inside SPEAKER_A
            _seg(1, 2.0, 4.0),   # half SPEAKER_A, half SPEAKER_B → tie 50/50 picks A (first encountered with >0)
            _seg(2, 4.0, 6.0),   # fully inside SPEAKER_B
            _seg(3, 6.0, 10.0),  # SPEAKER_B covers only first 1s (25%) → null
        ]
        diarization = _diarization(
            _turn(0.0, 3.0, "SPEAKER_A"),
            _turn(3.0, 7.0, "SPEAKER_B"),
        )

        result = merge_speakers_into_segments(segments, diarization)

        speakers = [segment.speaker_id for segment in result.segments]
        assert speakers[0] == "SPEAKER_A"
        # segment 1: A covers 2-3 (1s, 50%), B covers 3-4 (1s, 50%); equal overlap,
        # tie-break = first one with strictly greater value, so it lands on A.
        assert speakers[1] == "SPEAKER_A"
        assert speakers[2] == "SPEAKER_B"
        assert speakers[3] is None
        assert result.low_confidence_count == 1
        assert result.speaker_count == 2
        assert result.speakers == ["SPEAKER_A", "SPEAKER_B"]
