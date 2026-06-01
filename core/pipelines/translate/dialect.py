"""Dialect hints and conservative source normalization for MT."""

from __future__ import annotations

from dataclasses import dataclass
import re


ARABIC_STANDARD = "ar-standard"
ARABIC_LEVANTINE = "ar-levantine"
ARABIC_EGYPTIAN = "ar-egyptian"
ARABIC_GULF = "ar-gulf"
ARABIC_MAGHREBI = "ar-maghrebi"
SOURCE_VARIANT_AUTO = "auto"

SUPPORTED_SOURCE_VARIANTS = {
    SOURCE_VARIANT_AUTO,
    ARABIC_STANDARD,
    ARABIC_LEVANTINE,
    ARABIC_EGYPTIAN,
    ARABIC_GULF,
    ARABIC_MAGHREBI,
}

SOURCE_VARIANT_ALIASES = {
    "auto": SOURCE_VARIANT_AUTO,
    "ar-auto": SOURCE_VARIANT_AUTO,
    "arabic-auto": SOURCE_VARIANT_AUTO,
    "ar": SOURCE_VARIANT_AUTO,
    "standard": ARABIC_STANDARD,
    "msa": ARABIC_STANDARD,
    "modern-standard-arabic": ARABIC_STANDARD,
    "ar-standard": ARABIC_STANDARD,
    "levantine": ARABIC_LEVANTINE,
    "levant": ARABIC_LEVANTINE,
    "shami": ARABIC_LEVANTINE,
    "syrian": ARABIC_LEVANTINE,
    "palestinian": ARABIC_LEVANTINE,
    "lebanese": ARABIC_LEVANTINE,
    "jordanian": ARABIC_LEVANTINE,
    "ar-levantine": ARABIC_LEVANTINE,
    "egyptian": ARABIC_EGYPTIAN,
    "masri": ARABIC_EGYPTIAN,
    "ar-egyptian": ARABIC_EGYPTIAN,
    "gulf": ARABIC_GULF,
    "khaleeji": ARABIC_GULF,
    "ar-gulf": ARABIC_GULF,
    "maghrebi": ARABIC_MAGHREBI,
    "moroccan": ARABIC_MAGHREBI,
    "algerian": ARABIC_MAGHREBI,
    "tunisian": ARABIC_MAGHREBI,
    "ar-maghrebi": ARABIC_MAGHREBI,
}

_ARABIC_CHARS = "\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff"
_VARIANT_PRIORITY = (ARABIC_LEVANTINE, ARABIC_EGYPTIAN, ARABIC_GULF, ARABIC_MAGHREBI)

_DIALECT_MARKERS: dict[str, tuple[tuple[str, int], ...]] = {
    ARABIC_LEVANTINE: (
        ("هلأ", 3),
        ("هلق", 3),
        ("هلاء", 3),
        ("ليش", 2),
        ("شو", 2),
        ("بدي", 2),
        ("بدنا", 2),
        ("بدك", 2),
        ("بد", 2),
        ("كتير", 1),
        ("مو", 1),
        ("هون", 1),
        ("هونيك", 1),
        ("عالبيت", 2),
    ),
    ARABIC_EGYPTIAN: (
        ("دلوقتي", 3),
        ("عايز", 3),
        ("عاوز", 3),
        ("ايه", 2),
        ("إيه", 2),
        ("ليه", 1),
        ("أوي", 1),
        ("مش", 1),
    ),
    ARABIC_GULF: (
        ("الحين", 3),
        ("وش", 2),
        ("شلون", 2),
        ("أبي", 2),
        ("ابغى", 2),
        ("أبغى", 2),
        ("وايد", 1),
        ("واجد", 1),
        ("وين", 1),
    ),
    ARABIC_MAGHREBI: (
        ("دابا", 3),
        ("شنو", 2),
        ("واش", 2),
        ("علاش", 2),
        ("بزاف", 2),
        ("بغيت", 2),
        ("برشا", 1),
    ),
}


@dataclass(frozen=True)
class DialectPreparation:
    text: str
    source_variant: str | None
    detected_variant: str | None
    normalized: bool


def prepare_source_for_translation(
    source_text: str,
    *,
    source_lang: str,
    source_variant: str | None = None,
) -> DialectPreparation:
    """Return MT-ready source text plus dialect metadata.

    The normalization is intentionally conservative. It handles high-signal
    spoken-Arabic markers before the text reaches a general NLLB Arabic model.
    """
    if source_lang != "ar":
        return DialectPreparation(
            text=source_text,
            source_variant=None,
            detected_variant=None,
            normalized=False,
        )

    requested_variant = normalize_source_variant(source_variant)
    detected_variant = detect_arabic_variant(source_text) if requested_variant == SOURCE_VARIANT_AUTO else requested_variant
    if detected_variant == ARABIC_STANDARD:
        return DialectPreparation(
            text=source_text,
            source_variant=detected_variant,
            detected_variant=detected_variant,
            normalized=False,
        )

    prepared_text = normalize_arabic_dialect_text(source_text, detected_variant)
    return DialectPreparation(
        text=prepared_text,
        source_variant=detected_variant,
        detected_variant=detected_variant,
        normalized=prepared_text != source_text,
    )


def normalize_source_variant(value: str | None) -> str:
    raw = (value or SOURCE_VARIANT_AUTO).strip().casefold().replace("_", "-").replace(" ", "-")
    if not raw:
        return SOURCE_VARIANT_AUTO
    try:
        return SOURCE_VARIANT_ALIASES[raw]
    except KeyError as exc:
        raise ValueError(f"Unsupported source variant: {value}") from exc


def detect_arabic_variant(text: str) -> str:
    normalized = _strip_arabic_diacritics(text)
    scores: dict[str, int] = {}
    for variant, markers in _DIALECT_MARKERS.items():
        score = 0
        for marker, weight in markers:
            if _contains_arabic_marker(normalized, marker):
                score += weight
        if score:
            scores[variant] = score
    if not scores:
        return ARABIC_STANDARD
    return max(_VARIANT_PRIORITY, key=lambda variant: (scores.get(variant, 0), -_VARIANT_PRIORITY.index(variant)))


def normalize_arabic_dialect_text(text: str, source_variant: str) -> str:
    variant = normalize_source_variant(source_variant)
    if variant == ARABIC_LEVANTINE:
        return _normalize_levantine_arabic(text)
    if variant == ARABIC_EGYPTIAN:
        return _replace_arabic_words(
            text,
            (
                ("دلوقتي", "الآن"),
                ("ايه", "ماذا"),
                ("إيه", "ماذا"),
                ("ليه", "لماذا"),
                ("عايز", "أريد أن"),
                ("عاوز", "أريد أن"),
                ("مش", "ليس"),
                ("أوي", "كثيرا"),
            ),
        )
    if variant == ARABIC_GULF:
        return _replace_arabic_words(
            text,
            (
                ("الحين", "الآن"),
                ("وش", "ماذا"),
                ("شلون", "كيف"),
                ("أبي", "أريد أن"),
                ("ابغى", "أريد أن"),
                ("أبغى", "أريد أن"),
                ("وايد", "كثيرا"),
                ("واجد", "كثيرا"),
                ("وين", "أين"),
            ),
        )
    if variant == ARABIC_MAGHREBI:
        return _replace_arabic_words(
            text,
            (
                ("دابا", "الآن"),
                ("شنو", "ماذا"),
                ("واش", "هل"),
                ("علاش", "لماذا"),
                ("بزاف", "كثيرا"),
                ("بغيت", "أريد أن"),
                ("برشا", "كثيرا"),
            ),
        )
    return text


def _normalize_levantine_arabic(text: str) -> str:
    normalized = _replace_phrases(
        text,
        (
            ("لعندي على البيت", "إلى بيتي"),
            ("لعندي عالبيت", "إلى بيتي"),
            ("عندي على البيت", "إلى بيتي"),
            ("عندي عالبيت", "إلى بيتي"),
            ("على البيت", "إلى البيت"),
            ("عالبيت", "إلى البيت"),
        ),
    )
    normalized = re.sub(f"{_arabic_word_pattern('بد')}\\s+(?=ن)", "يجب أن ", normalized)
    normalized = _replace_arabic_words(
        normalized,
        (
            ("هلأ", "الآن"),
            ("هلاء", "الآن"),
            ("هلق", "الآن"),
            ("هلا", "الآن"),
            ("ليش", "لماذا"),
            ("شو", "ماذا"),
            ("بدنا", "نريد أن"),
            ("بدي", "أريد أن"),
            ("بدك", "تريد أن"),
            ("بدو", "يريد أن"),
            ("بدها", "تريد أن"),
            ("بدهم", "يريدون أن"),
            ("بد", "يجب أن"),
            ("نروح", "نذهب"),
            ("تروح", "تذهب"),
            ("يروح", "يذهب"),
            ("روح", "اذهب"),
            ("كتير", "كثيرا"),
            ("مو", "ليس"),
            ("هون", "هنا"),
            ("هونيك", "هناك"),
        ),
    )
    normalized = normalized.replace("أنا لماذا يجب أن ن", "لماذا يجب أن ن")
    return normalized


def _strip_arabic_diacritics(text: str) -> str:
    return re.sub("[\u064b-\u065f\u0670]", "", text)


def _contains_arabic_marker(text: str, marker: str) -> bool:
    return re.search(_arabic_word_pattern(marker), text) is not None


def _replace_arabic_words(text: str, replacements: tuple[tuple[str, str], ...]) -> str:
    for source, target in replacements:
        text = re.sub(_arabic_word_pattern(source), target, text)
    return text


def _replace_phrases(text: str, replacements: tuple[tuple[str, str], ...]) -> str:
    for source, target in replacements:
        text = text.replace(source, target)
    return text


def _arabic_word_pattern(word: str) -> str:
    escaped = re.escape(word)
    return f"(?<![{_ARABIC_CHARS}]){escaped}(?![{_ARABIC_CHARS}])"
