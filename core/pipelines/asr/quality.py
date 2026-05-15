from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any


STOCK_ARTIFACTS = [
    "izlediğiniz için teşekkür ederim",
    "altyazı m.k.",
    "altyazı:",
    "abone olmayı",
    "abone olun",
    "yorum yapmayı",
    "beğen butonuna",
    "beğen butonuna tıklamayı",
    "bildirim zilini",
    "kanalımıza abone",
    "videoyu beğenmeyi",
    "altyazı m k",
    "subscribe to",
    "thanks for watching",
    "like and subscribe",
]


@dataclass(frozen=True)
class SegmentQualityDecision:
    keep: bool
    drop_reason: str | None
    flags: list[str]


@dataclass(frozen=True)
class QualityConfig:
    no_speech_hard_threshold: float = 0.6
    avg_logprob_hard_threshold: float = -1.0
    min_text_tokens_hard: int = 3
    no_speech_flag_threshold: float = 0.4
    avg_logprob_flag_threshold: float = -0.8
    very_low_logprob_short_text_threshold: float = -1.15
    very_low_logprob_short_text_max_tokens: int = 5
    allowed_languages: tuple[str, ...] = ("tr", "en")
    drop_stock_artifacts: bool = True
    drop_repetition_collapses: bool = True
    segment_repetition_min_run: int = 20
    segment_max_token_length: int = 80


@dataclass(frozen=True)
class ResultSafetyDecision:
    safe: bool
    failure_reason: str | None
    diagnostics: dict[str, Any]


def is_stock_artifact(text: str) -> tuple[bool, str | None]:
    """Returns (is_artifact, matched_pattern)."""
    lowered = normalize_quality_text(text)
    for pattern in STOCK_ARTIFACTS:
        if normalize_quality_text(pattern) in lowered:
            return True, pattern
    return False, None


def detect_repetition_collapse(text: str, *, min_run: int = 20) -> tuple[bool, int, str | None]:
    """Whisper repetition loop detection."""
    tokens = text.split()
    if len(tokens) < min_run:
        return False, 0, None

    max_run = 1
    current_run = 1
    current_token = tokens[0]
    current_key = _repetition_key(current_token)
    longest_token = current_token

    for token in tokens[1:]:
        token_key = _repetition_key(token)
        if token_key == current_key:
            current_run += 1
            if current_run > max_run:
                max_run = current_run
                longest_token = current_token
        else:
            current_run = 1
            current_token = token
            current_key = token_key

    return max_run >= min_run, max_run, longest_token


def detect_word_density_anomaly(
    word_count: int,
    speech_seconds: float,
    *,
    max_words_per_second: float = 5.0,
) -> tuple[bool, float]:
    """Returns (is_anomalous, actual_words_per_second)."""
    if speech_seconds <= 0:
        return False, 0.0
    words_per_second = word_count / speech_seconds
    return words_per_second > max_words_per_second, words_per_second


def evaluate_segment(
    text: str,
    no_speech_prob: float,
    avg_logprob: float,
    language: str | None,
    *,
    config: QualityConfig | None = None,
) -> SegmentQualityDecision:
    cfg = config or QualityConfig()
    text_stripped = text.strip()
    token_count = len(text_stripped.split())
    flags: list[str] = []

    if not any(character.isalnum() for character in text_stripped):
        return SegmentQualityDecision(keep=False, drop_reason="no_alnum", flags=[])

    is_artifact, pattern = is_stock_artifact(text_stripped)
    if is_artifact:
        if cfg.drop_stock_artifacts:
            return SegmentQualityDecision(
                keep=False,
                drop_reason=f"stock_artifact:{pattern}",
                flags=["stock_artifact"],
            )
        flags.append("stock_artifact")

    is_collapsed, max_run, token = detect_repetition_collapse(
        text_stripped,
        min_run=cfg.segment_repetition_min_run,
    )
    if is_collapsed and cfg.drop_repetition_collapses:
        return SegmentQualityDecision(
            keep=False,
            drop_reason=f"repetition_collapse:{token}:run={max_run}",
            flags=["repetition_collapse"],
        )

    longest_token = max((len(token) for token in text_stripped.split()), default=0)
    if longest_token > cfg.segment_max_token_length:
        return SegmentQualityDecision(
            keep=False,
            drop_reason=f"long_token_artifact:length={longest_token}",
            flags=["long_token_artifact"],
        )

    if (
        avg_logprob < cfg.very_low_logprob_short_text_threshold
        and token_count <= cfg.very_low_logprob_short_text_max_tokens
    ):
        return SegmentQualityDecision(
            keep=False,
            drop_reason="very_low_logprob_short_text",
            flags=["very_low_logprob"],
        )

    hard_drop_signals = (
        no_speech_prob > cfg.no_speech_hard_threshold,
        avg_logprob < cfg.avg_logprob_hard_threshold,
        token_count < cfg.min_text_tokens_hard,
        language is not None and language not in cfg.allowed_languages,
    )
    if all(hard_drop_signals[:3]):
        return SegmentQualityDecision(keep=False, drop_reason="multi_signal_low_quality", flags=[])

    if no_speech_prob > cfg.no_speech_flag_threshold:
        flags.append("high_no_speech_prob")
    if avg_logprob < cfg.avg_logprob_flag_threshold:
        flags.append("low_logprob")
    if language is not None and language not in cfg.allowed_languages:
        flags.append("unexpected_language")
    if flags:
        flags.append("low_confidence")

    return SegmentQualityDecision(keep=True, drop_reason=None, flags=flags)


def evaluate_result_safety(
    transcript_text: str,
    word_count: int,
    speech_seconds: float,
    *,
    expected_speech_end: float | None = None,
    transcript_last_end: float | None = None,
    max_uncovered_tail_seconds: float = 3.0,
    max_uncovered_tail_ratio: float = 0.25,
    max_repetition_run: int = 20,
    max_token_length: int = 80,
    max_words_per_second: float = 5.0,
) -> ResultSafetyDecision:
    diagnostics: dict[str, Any] = {}

    is_collapsed, max_run, token = detect_repetition_collapse(transcript_text, min_run=max_repetition_run)
    diagnostics["max_run"] = max_run
    diagnostics["repeated_token"] = token

    longest_token = max((len(token) for token in transcript_text.split()), default=0)
    diagnostics["max_token_length"] = longest_token

    is_anomalous, words_per_second = detect_word_density_anomaly(
        word_count,
        speech_seconds,
        max_words_per_second=max_words_per_second,
    )
    diagnostics["words_per_second"] = round(words_per_second, 2)

    uncovered_tail_seconds = 0.0
    uncovered_tail_ratio = 0.0
    effective_max_tail_seconds = max_uncovered_tail_seconds
    if expected_speech_end is not None:
        expected_speech_end = max(0.0, expected_speech_end)
        diagnostics["expected_speech_end"] = round(expected_speech_end, 3)
        if transcript_last_end is None:
            diagnostics["transcript_last_end"] = None
            uncovered_tail_seconds = expected_speech_end
        else:
            transcript_last_end = max(0.0, transcript_last_end)
            diagnostics["transcript_last_end"] = round(transcript_last_end, 3)
            uncovered_tail_seconds = max(0.0, expected_speech_end - transcript_last_end)
        if expected_speech_end > 0.0:
            uncovered_tail_ratio = uncovered_tail_seconds / expected_speech_end
            # Audit HIGH-3: 3s mutlak eşik kisa kliplerde olu bolge birakir;
            # klip suresine olcekle, mevcut uzun-klip davranisi 3s'de kalir.
            effective_max_tail_seconds = min(max_uncovered_tail_seconds, expected_speech_end * 0.15)
    diagnostics["uncovered_tail_seconds"] = round(uncovered_tail_seconds, 3)
    diagnostics["uncovered_tail_ratio"] = round(uncovered_tail_ratio, 4)
    diagnostics["effective_max_tail_seconds"] = round(effective_max_tail_seconds, 3)

    if is_collapsed:
        return ResultSafetyDecision(
            safe=False,
            failure_reason=f"repetition_collapse:{token}:run={max_run}",
            diagnostics=diagnostics,
        )

    if longest_token > max_token_length:
        return ResultSafetyDecision(
            safe=False,
            failure_reason=f"long_token_artifact:length={longest_token}",
            diagnostics=diagnostics,
        )

    if is_anomalous:
        return ResultSafetyDecision(
            safe=False,
            failure_reason=f"word_density_anomaly:wps={words_per_second:.2f}",
            diagnostics=diagnostics,
        )

    if (
        uncovered_tail_seconds >= effective_max_tail_seconds
        and uncovered_tail_ratio >= max_uncovered_tail_ratio
    ):
        return ResultSafetyDecision(
            safe=False,
            failure_reason=f"tail_gap_uncovered:gap={uncovered_tail_seconds:.2f}s",
            diagnostics=diagnostics,
        )

    return ResultSafetyDecision(safe=True, failure_reason=None, diagnostics=diagnostics)


def normalize_quality_text(text: str) -> str:
    lowered = text.casefold().strip()
    lowered = unicodedata.normalize("NFKD", lowered)
    lowered = "".join(character for character in lowered if not unicodedata.combining(character))
    lowered = lowered.replace("ı", "i")
    lowered = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", lowered).strip()


def _repetition_key(token: str) -> str:
    return normalize_quality_text(token).replace(" ", "") or token.casefold()
