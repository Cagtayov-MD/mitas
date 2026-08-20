"""Karşılaştırma kopyaları; ham OCR metni burada asla değiştirilmez."""
from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).upper()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def distance(left: str, right: str) -> int:
    """Damerau-Levenshtein (komşu transpozisyon dahil)."""
    if left == right:
        return 0
    if len(left) > len(right):
        left, right = right, left
    previous = list(range(len(left) + 1))
    previous_previous: list[int] | None = None
    for i, char_r in enumerate(right, 1):
        current = [i]
        for j, char_l in enumerate(left, 1):
            value = min(previous[j] + 1, current[j - 1] + 1,
                        previous[j - 1] + (char_l != char_r))
            if (previous_previous is not None and i > 1 and j > 1 and
                    char_l == right[i - 2] and left[j - 2] == char_r):
                value = min(value, previous_previous[j - 2] + 1)
            current.append(value)
        previous_previous, previous = previous, current
    return previous[-1]


def near(left: str, right: str, max_edits: int = 3) -> bool:
    left, right = normalize(left), normalize(right)
    if not left or not right or len(left.split()) != len(right.split()):
        return False
    # Tek kısa isimler, ör. Ali/Alp, otomatik ilişkilenmez.
    if len(left) < 6 or len(right) < 6:
        return False
    return distance(left, right) <= min(max_edits, max(1, max(len(left), len(right)) // 5))

