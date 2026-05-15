"""Small text repairs for the live STT preview path."""

from __future__ import annotations

import re
import unicodedata


LIVE_STT_INITIAL_PROMPT: str | None = None

_ONE_MINUTE_REPAIR = re.compile(
    r"\b(?:one|wan|uan|on)\s+min(?:ute|ut|it|ıt|üt)?"
    r"(?:\s+(?:five|faiv|fayv)\s+min(?:ute|ut|it|ıt|üt)?)?\b",
    re.IGNORECASE,
)
_LIVE_TEXT_REPAIRS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_ONE_MINUTE_REPAIR, "One minute"),
    (re.compile(r"\bfive\s+minutes\b", re.IGNORECASE), "One minute"),
    (re.compile(r"\bthe\s+(?:guardian|guardiyan|gardiyan|gardian)\b", re.IGNORECASE), "The Guardian"),
    (re.compile(r"\b(?:guardian|guardiyan|gardiyan|gardian)\b", re.IGNORECASE), "Guardian"),
    (re.compile(r"\b[üu]ngiliz\b", re.IGNORECASE), "İngiliz"),
)
_STOCK_LIVE_ARTIFACTS = (
    "izlediğiniz için teşekkür ederim",
    "altyazı m.k",
    "altyazı m. k",
    "özel kalıplar",
)


def repair_live_text(text: str) -> str:
    """Repair narrow, known live-preview ASR glitches without broad rewriting."""
    repaired = " ".join(text.split())
    if _looks_like_live_artifact(repaired):
        return ""
    for pattern, replacement in _LIVE_TEXT_REPAIRS:
        repaired = pattern.sub(replacement, repaired)
    return repaired.strip()


def _looks_like_live_artifact(text: str) -> bool:
    normalized = _normalize_for_artifact_match(text).strip(" .,:;!?")
    if not normalized:
        return True
    artifacts = tuple(_normalize_for_artifact_match(artifact) for artifact in _STOCK_LIVE_ARTIFACTS)
    if any(artifact in normalized for artifact in artifacts):
        return True
    words = [word.strip(".,:;!?()[]{}\"'") for word in normalized.split()]
    words = [word for word in words if word]
    if len(words) >= 12:
        most_common = max(words.count(word) for word in set(words))
        if most_common / len(words) >= 0.65:
            return True
    return False


def _normalize_for_artifact_match(text: str) -> str:
    return unicodedata.normalize("NFKD", text.casefold()).replace("\u0307", "")
