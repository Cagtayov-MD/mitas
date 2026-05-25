"""Tip-spesifik confidence eşikleri (Faz 5 madde 7).

text_event.type alanına göre kalite çıtası uygular. Eşik altı event'ler
`low_confidence=True` ile işaretlenir — atılmaz, sadece flag. UI/export
bu flag'e göre filtreleme/highlight yapabilir.

Eşik kararları (§11.7 madde 7 — OCR-OPUS.md):
- scroll_credit: çok satır, hata toleransı yüksek → düşük eşik
- card / intertitle: orta önem, paralel doğrulama yok → orta eşik
- kj: tek görünür, yanlış kabul edilemez → yüksek eşik (V2'de aktif)
- scene_text: gürültü, gerçekten önemliyse net olmalı → en yüksek eşik (V2'de aktif)

Bilinmeyen tip için fallback 0.50.
"""

from __future__ import annotations

DEFAULT_THRESHOLDS: dict[str, float] = {
    "scroll_credit": 0.50,   # Çok satır, hata toleransı yüksek
    "card": 0.75,            # Önemli ama paralel doğrulama yok
    "intertitle": 0.75,
    "kj": 0.85,              # Tek görünür, yanlış kabul edilemez (V2'de aktif)
    "scene_text": 0.90,      # Gürültü, gerçekten önemliyse net olmalı (V2'de aktif)
}


def get_threshold(event_type: str, *, custom: dict[str, float] | None = None) -> float:
    """Tip için eşik dön. custom override DEFAULT_THRESHOLDS'tan üstün.

    Args:
        event_type: text_event.type değeri (scroll_credit, card, kj, ...)
        custom: Opsiyonel override dict (örn. profil bazlı kalibrasyon)

    Returns:
        Eşik değeri (0.0-1.0). Bilinmeyen tip için 0.50 fallback.
    """
    if custom and event_type in custom:
        return custom[event_type]
    return DEFAULT_THRESHOLDS.get(event_type, 0.50)


def apply_thresholds(events: list, *, custom: dict[str, float] | None = None) -> int:
    """Her event'in low_confidence field'ını set et (in-place mutation).

    Eşik altı → True, üstü/eşit → False. Atma YOK, sadece flag.

    Args:
        events: TextEvent listesi (low_confidence, type, confidence field'ları zorunlu)
        custom: Opsiyonel tip→eşik override dict

    Returns:
        low_confidence=True olarak işaretlenen event sayısı.
    """
    count = 0
    for ev in events:
        threshold = get_threshold(ev.type, custom=custom)
        ev.low_confidence = ev.confidence < threshold
        if ev.low_confidence:
            count += 1
    return count
