"""Deterministic ASR entity normalization hooks.

This is intentionally conservative: it does not overwrite the ASR text used
for timing/alignment. It writes normalized_text/normalized_transcript and a
reviewable entity report so downstream UI and auditors can decide how to use
the correction.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Literal, Sequence

from core.pipelines.asr.result import ProductionTranscribeResult, TranscriptSegment


EntityType = Literal["person", "place", "organization", "program", "other"]


@dataclass(frozen=True)
class EntityNormalizationRule:
    canonical: str
    variants: tuple[str, ...]
    entity_type: EntityType = "other"
    source: str = "deterministic_lexicon"
    confidence: float = 0.95


DEFAULT_ENTITY_RULES: tuple[EntityNormalizationRule, ...] = (
    EntityNormalizationRule(
        canonical="Barış Manço",
        variants=("Barış Mango", "Baris Mango", "Barış Manco", "Baris Manco", "Barış Março", "Baris Março"),
        entity_type="person",
    ),
    EntityNormalizationRule(
        canonical="TRT Haber",
        variants=("Trt Haber", "TRT haber", "trt haber"),
        entity_type="organization",
    ),
    EntityNormalizationRule(
        canonical="Mostar Köprüsü",
        variants=("Mostar Koprusu", "Mostar Köprusu", "Mostar köprüsü"),
        entity_type="place",
    ),
    EntityNormalizationRule(
        canonical="Neretva",
        variants=("Neretba", "Neretfa", "Neretwa"),
        entity_type="place",
    ),
)


def normalize_entities(
    transcript_result: ProductionTranscribeResult,
    *,
    qwen_endpoint: str | None = None,
    imdb_db_path: str | None = None,
    rules: Sequence[EntityNormalizationRule] = DEFAULT_ENTITY_RULES,
) -> ProductionTranscribeResult:
    """Attach deterministic normalized text and entity suggestions.

    `qwen_endpoint` and `imdb_db_path` are reserved for the later evidence-based
    Phase 2 reviewer. Keeping them in the signature preserves the planned API
    while this first pass stays local, deterministic, and auditable.
    """
    _ = (qwen_endpoint, imdb_db_path)
    if not rules or not transcript_result.clean_segments:
        return transcript_result

    normalized_segments: list[TranscriptSegment] = []
    entities: list[dict[str, Any]] = []
    for segment in transcript_result.clean_segments:
        normalized_text, segment_entities = _normalize_segment_text(segment, rules)
        if normalized_text != segment.text:
            for entity in segment_entities:
                entity["evidence"] = _entity_evidence_packet(segment, normalized_text)
            normalized_segments.append(replace(segment, normalized_text=normalized_text))
            entities.extend(segment_entities)
        else:
            normalized_segments.append(segment)

    if not entities:
        return transcript_result

    return replace(
        transcript_result,
        clean_segments=normalized_segments,
        normalized_transcript=_build_normalized_transcript(normalized_segments),
        normalized_entities=entities,
    )


def _normalize_segment_text(
    segment: TranscriptSegment,
    rules: Sequence[EntityNormalizationRule],
) -> tuple[str, list[dict[str, Any]]]:
    text = segment.text
    entities: list[dict[str, Any]] = []
    for rule in rules:
        for variant in rule.variants:
            pattern = _variant_pattern(variant)

            def replace_match(match: re.Match[str]) -> str:
                matched = match.group(0)
                if matched == rule.canonical:
                    return matched
                entities.append(
                    {
                        "segment_index": segment.index,
                        "start": segment.start,
                        "end": segment.end,
                        "entity_type": rule.entity_type,
                        "matched_text": matched,
                        "canonical": rule.canonical,
                        "char_start": match.start(),
                        "char_end": match.end(),
                        "source": rule.source,
                        "confidence": round(float(rule.confidence), 3),
                        "action": "normalized_text",
                    }
                )
                return rule.canonical

            text = pattern.sub(replace_match, text)
    return text, entities


def _variant_pattern(variant: str) -> re.Pattern[str]:
    # Non-word guards keep "Barış Mango" style phrase corrections from firing
    # inside longer tokens while still preserving Turkish apostrophe suffixes.
    return re.compile(rf"(?<!\w){re.escape(variant)}(?!\w)", flags=re.IGNORECASE)


def _entity_evidence_packet(segment: TranscriptSegment, normalized_text: str) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "segment_index": segment.index,
        "start": segment.start,
        "end": segment.end,
        "source_text": segment.text,
        "normalized_text": normalized_text,
    }
    if segment.speaker_id is not None:
        packet["speaker_id"] = segment.speaker_id
    if segment.channel is not None:
        packet["channel"] = segment.channel
    if segment.word_timestamps:
        packet["word_timestamps"] = [dict(word) for word in segment.word_timestamps]
    return packet


def _build_normalized_transcript(segments: Sequence[TranscriptSegment]) -> str:
    if not segments:
        return ""
    paragraphs: list[list[str]] = [[(segments[0].normalized_text or segments[0].text).strip()]]
    last_end = segments[0].end
    for segment in segments[1:]:
        text = (segment.normalized_text or segment.text).strip()
        if segment.start - last_end >= 2.0:
            paragraphs.append([text])
        else:
            paragraphs[-1].append(text)
        last_end = segment.end
    return "\n\n".join(" ".join(paragraph) for paragraph in paragraphs).strip()
