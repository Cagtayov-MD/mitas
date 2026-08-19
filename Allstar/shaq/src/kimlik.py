"""Film-kapsamlı kimlik desteği için opsiyonel adaptör sınırı."""
from __future__ import annotations

from typing import Protocol

from .normalizasyon import normalize


class KimlikSaglayici(Protocol):
    version: str
    def candidates(self, external_ids: dict[str, str], role: str) -> list[str]: ...


class BosKimlikSaglayici:
    version = "none"
    def candidates(self, external_ids: dict[str, str], role: str) -> list[str]:
        return []


def strong_canonical(provider: KimlikSaglayici, external_ids: dict[str, str], role: str,
                     texts: list[str]) -> str | None:
    """Kesin film ID + kesin rol + tek tam OCR eşleşmesi olmadan düzeltmez."""
    if role not in ("CAST_KESIN", "YONETMEN_KESIN") or not any(external_ids.values()):
        return None
    try:
        candidates = provider.candidates(external_ids, role)
    except Exception:
        # Sağlayıcı kesintisi OCR kararını arızaya dönüştürmez.
        return None
    exact = [name for name in candidates if any(normalize(name) == normalize(text) for text in texts)]
    return exact[0] if len(exact) == 1 else None
