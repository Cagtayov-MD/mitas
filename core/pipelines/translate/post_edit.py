"""Small Turkish broadcast-language post-edit rules for MT output."""

from __future__ import annotations

import re


def polish_turkish_broadcast(
    text: str,
    *,
    source_text: str = "",
    source_lang: str = "",
) -> str:
    """Apply conservative post-editing for TRT/news subtitle Turkish."""
    polished = _normalize_spaces(text)
    if not polished:
        return polished

    source_key = source_text.casefold()
    if "prime minister" in source_key:
        polished = re.sub(r"^Başbakan,", "Sayın Başbakan,", polished, count=1)

    replacements = (
        (r"\btartışmayı tekrar başlatamayız\b", "tartışmayı yeniden açamayız"),
        (r"\btartışmayı yeniden başlatamayız\b", "tartışmayı yeniden açamayız"),
        (r"\btartışmayı tekrar başlatamazsınız\b", "tartışmayı yeniden açamazsınız"),
        (r"\btartışmayı yeniden başlatamazsınız\b", "tartışmayı yeniden açamazsınız"),
        (r"\bsadece zamanımız yok\b", "buna zamanımız yok"),
        (r"\bsadece vaktimiz yok\b", "buna vaktimiz yok"),
    )
    for pattern, replacement in replacements:
        polished = re.sub(pattern, replacement, polished, flags=re.IGNORECASE)

    polished = re.sub(r",\s*lütfen,\s*buna zamanımız yok", ", lütfen; buna zamanımız yok", polished, flags=re.IGNORECASE)
    polished = re.sub(r",\s*lütfen,\s*buna vaktimiz yok", ", lütfen; buna vaktimiz yok", polished, flags=re.IGNORECASE)
    return _normalize_spaces(polished)


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
