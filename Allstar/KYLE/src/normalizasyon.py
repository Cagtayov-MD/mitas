from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_TURKISH_FOLD = str.maketrans({
    "İ": "I", "I": "I", "ı": "I", "i": "I",
    "Ş": "S", "ş": "S", "Ç": "C", "ç": "C",
    "Ğ": "G", "ğ": "G", "Ö": "O", "ö": "O",
    "Ü": "U", "ü": "U",
})
_CONFUSABLE = str.maketrans({"0": "O", "1": "I", "5": "S", "|": "I"})


def normal(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("ı", "I").replace("i", "İ").upper()
    text = re.sub(r"[^0-9A-ZÇĞİÖŞÜÀ-ÖØ-öø-ÿ ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def loose(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.translate(_TURKISH_FOLD).translate(_CONFUSABLE).upper()
    text = re.sub(r"[^A-Z0-9]+", "", text)
    return text


def similarity(a: str, b: str) -> float:
    na, nb = normal(a), normal(b)
    la, lb = loose(a), loose(b)
    if not la or not lb:
        return 0.0
    if la == lb:
        return 1.0
    s1 = SequenceMatcher(None, na, nb).ratio() if na and nb else 0.0
    s2 = SequenceMatcher(None, la, lb).ratio()
    return max(s1, s2)


def diacritic_score(text: str) -> int:
    return sum(ch in "ÇĞİÖŞÜçğıöşü" for ch in (text or ""))


def looks_like_name(text: str, min_chars: int = 4) -> bool:
    n = normal(text)
    letters = sum(ch.isalpha() for ch in n)
    if letters < min_chars:
        return False
    words = n.split()
    if len(words) > 8:
        return False
    if len(n) > 80:
        return False
    return True
