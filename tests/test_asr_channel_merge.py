from __future__ import annotations

from pathlib import Path

import pytest

from core.pipelines.asr.channel_merge import merge_channel_results, tag_result_channel
from core.pipelines.asr.quality import ResultSafetyDecision
from core.pipelines.asr.result import ProductionTranscribeResult, TranscriptSegment, TranscribeTiming


def test_duplicate_center_panned_segment_drops_lower_score() -> None:
    left = _result("L", [_segment("aynı haber metni burada", channel="L", avg_logprob=-0.1)])
    right = _result("R", [_segment("aynı haber metni burada", channel="R", avg_logprob=-0.5)])

    merged = merge_channel_results(left, right)

    assert len(merged.clean_segments) == 1
    assert merged.clean_segments[0].channel == "L"
    assert len(merged.duplicate_drops) == 1
    assert merged.duplicate_drops[0].dropped_segment.channel == "R"
    assert merged.duplicate_drops[0].kept_segment.channel == "L"
    assert merged.duplicate_drops[0].time_iou == 1.0
    assert merged.duplicate_drops[0].token_jaccard == 1.0


def test_overlap_with_different_text_keeps_both() -> None:
    left = _result("L", [_segment("ana spiker haberi okuyor", channel="L")])
    right = _result("R", [_segment("saha muhabiri bilgi veriyor", channel="R")])

    merged = merge_channel_results(left, right)

    assert len(merged.clean_segments) == 2
    assert not merged.duplicate_drops


def test_short_segment_is_exempt_from_dedup() -> None:
    left = _result("L", [_segment("çok kısa metin", end=0.4, channel="L")])
    right = _result("R", [_segment("çok kısa metin", end=0.4, channel="R")])

    assert len(merge_channel_results(left, right).clean_segments) == 2


def test_low_token_segment_is_exempt_from_dedup() -> None:
    left = _result("L", [_segment("evet tamam", channel="L")])
    right = _result("R", [_segment("evet tamam", channel="R")])

    assert len(merge_channel_results(left, right).clean_segments) == 2


def test_language_mismatch_is_exempt_from_dedup() -> None:
    left = _result("L", [_segment("same spoken words here", channel="L", language="en")])
    right = _result("R", [_segment("same spoken words here", channel="R", language="tr")])

    assert len(merge_channel_results(left, right).clean_segments) == 2


def test_score_tie_break_prefers_higher_score() -> None:
    left = _result("L", [_segment("aynı haber metni burada", channel="L", avg_logprob=-0.5, no_speech_prob=0.4)])
    right = _result("R", [_segment("aynı haber metni burada", channel="R", avg_logprob=-0.2, no_speech_prob=0.0)])

    merged = merge_channel_results(left, right)

    assert merged.clean_segments[0].channel == "R"
    assert merged.duplicate_drops[0].dropped_score < merged.duplicate_drops[0].kept_score


def test_duration_mismatch_raises() -> None:
    left = _result("L", [_segment("aynı haber metni burada", channel="L")], duration=2.0)
    right = _result("R", [_segment("aynı haber metni burada", channel="R")], duration=2.2)

    with pytest.raises(ValueError):
        merge_channel_results(left, right)


def test_empty_side_returns_other_channel() -> None:
    left = _result("L", [])
    right = _result("R", [_segment("sadece sağ kanal konuşuyor", channel="R")])

    merged = merge_channel_results(left, right)

    assert [segment.channel for segment in merged.clean_segments] == ["R"]
    assert merged.clean_transcript == "sadece sağ kanal konuşuyor"


def test_tag_result_channel_updates_raw_and_clean_segments() -> None:
    segment = _segment("kanal etiketi ekle")
    tagged = tag_result_channel(_result("mono", [segment]), "L")

    assert tagged.raw_segments[0].channel == "L"
    assert tagged.clean_segments[0].channel == "L"
    assert tagged.channel_mode == "split"


def _segment(
    text: str,
    *,
    start: float = 0.0,
    end: float = 1.0,
    channel: str | None = None,
    language: str | None = "tr",
    avg_logprob: float = -0.2,
    no_speech_prob: float = 0.01,
) -> TranscriptSegment:
    return TranscriptSegment(
        index=0,
        start=start,
        end=end,
        text=text,
        language=language,
        avg_logprob=avg_logprob,
        no_speech_prob=no_speech_prob,
        source_chunk_index=0,
        channel=channel,
    )


def _result(name: str, segments: list[TranscriptSegment], *, duration: float = 2.0) -> ProductionTranscribeResult:
    return ProductionTranscribeResult(
        audio_path=Path(f"{name}.wav"),
        audio_duration=duration,
        profile_requested="fast",
        profile_used="fast",
        model_name="large-v3-turbo",
        fallback_triggered=False,
        fallback_reason=None,
        raw_segments=segments,
        clean_segments=segments,
        verbatim_transcript=" ".join(segment.text for segment in segments),
        clean_transcript=" ".join(segment.text for segment in segments),
        safety=ResultSafetyDecision(safe=True, failure_reason=None, diagnostics={}),
        timing=TranscribeTiming(total_seconds=1.0, chunk_count=1, decode_seconds=0.5),
    )
