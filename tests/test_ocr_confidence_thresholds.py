"""Faz 5 — Tip-spesifik confidence eşiği testleri (madde 7).

Eşik altı event'ler low_confidence=True flag'lenir, atılmaz.
DEFAULT_THRESHOLDS § custom override § fallback davranışları doğrulanır.
"""

from __future__ import annotations

from core.pipelines.ocr.confidence_thresholds import (
    DEFAULT_THRESHOLDS,
    apply_thresholds,
    get_threshold,
)
from core.pipelines.ocr.text_event import TextEvent


def _make_event(*, event_type: str, confidence: float, event_id: str = "evt_0001") -> TextEvent:
    """Test helper — minimal valid TextEvent."""
    return TextEvent(
        event_id=event_id,
        start_sec=0.0,
        end_sec=1.0,
        type=event_type,
        type_reason=f"test {event_type}",
        text="SAMPLE TEXT",
        confidence=confidence,
    )


def test_default_thresholds_loaded():
    """DEFAULT_THRESHOLDS dict 5 type key içerir."""
    assert isinstance(DEFAULT_THRESHOLDS, dict)
    assert set(DEFAULT_THRESHOLDS.keys()) == {
        "scroll_credit",
        "card",
        "intertitle",
        "kj",
        "scene_text",
    }
    # Sıralama: scroll_credit < card == intertitle < kj < scene_text
    assert DEFAULT_THRESHOLDS["scroll_credit"] < DEFAULT_THRESHOLDS["card"]
    assert DEFAULT_THRESHOLDS["card"] == DEFAULT_THRESHOLDS["intertitle"]
    assert DEFAULT_THRESHOLDS["intertitle"] < DEFAULT_THRESHOLDS["kj"]
    assert DEFAULT_THRESHOLDS["kj"] < DEFAULT_THRESHOLDS["scene_text"]


def test_get_threshold_known_type():
    """get_threshold bilinen tip için DEFAULT değerini döner."""
    assert get_threshold("card") == 0.75
    assert get_threshold("scroll_credit") == 0.50
    assert get_threshold("kj") == 0.85
    assert get_threshold("scene_text") == 0.90
    assert get_threshold("intertitle") == 0.75


def test_get_threshold_unknown_fallback():
    """Bilinmeyen tip için 0.50 fallback."""
    assert get_threshold("xyz") == 0.50
    assert get_threshold("") == 0.50
    assert get_threshold("unknown_type_42") == 0.50


def test_get_threshold_custom_override():
    """custom dict DEFAULT'tan üstün; karışım da çalışmalı."""
    custom = {"card": 0.90}
    assert get_threshold("card", custom=custom) == 0.90
    # Karışım: custom'da olmayan tip → DEFAULT'a düşmeli
    assert get_threshold("scroll_credit", custom=custom) == 0.50
    # Custom'da unknown type override → fallback'i geçer
    custom2 = {"xyz": 0.42}
    assert get_threshold("xyz", custom=custom2) == 0.42


def test_apply_low_confidence_below_threshold():
    """conf=0.60 type=card (eşik=0.75) → low_confidence=True."""
    ev = _make_event(event_type="card", confidence=0.60)
    assert ev.low_confidence is False  # başlangıç
    count = apply_thresholds([ev])
    assert ev.low_confidence is True
    assert count == 1


def test_apply_normal_confidence_above_threshold():
    """conf=0.80 type=card (eşik=0.75) → low_confidence=False."""
    ev = _make_event(event_type="card", confidence=0.80)
    count = apply_thresholds([ev])
    assert ev.low_confidence is False
    assert count == 0


def test_apply_returns_count():
    """Karışık liste: 3 düşük + 5 normal → count=3."""
    events = [
        # 3 düşük (card eşik=0.75)
        _make_event(event_type="card", confidence=0.50, event_id="evt_0001"),
        _make_event(event_type="card", confidence=0.60, event_id="evt_0002"),
        _make_event(event_type="card", confidence=0.70, event_id="evt_0003"),
        # 5 normal
        _make_event(event_type="card", confidence=0.80, event_id="evt_0004"),
        _make_event(event_type="card", confidence=0.85, event_id="evt_0005"),
        _make_event(event_type="card", confidence=0.90, event_id="evt_0006"),
        _make_event(event_type="card", confidence=0.95, event_id="evt_0007"),
        _make_event(event_type="card", confidence=1.00, event_id="evt_0008"),
    ]
    count = apply_thresholds(events)
    assert count == 3
    # Flag dağılımı doğru
    low_flags = [ev.low_confidence for ev in events]
    assert low_flags == [True, True, True, False, False, False, False, False]


def test_apply_does_not_drop_events():
    """apply_thresholds atma yapmaz; liste uzunluğu korunur."""
    events = [
        _make_event(event_type="card", confidence=0.10, event_id="evt_0001"),
        _make_event(event_type="kj", confidence=0.30, event_id="evt_0002"),
        _make_event(event_type="scene_text", confidence=0.20, event_id="evt_0003"),
    ]
    len_before = len(events)
    apply_thresholds(events)
    assert len(events) == len_before
    # Hepsi düşük conf, hepsi flag'lenmiş olmalı (atılmamış)
    assert all(ev.low_confidence for ev in events)


def test_apply_scroll_credit_lower_threshold():
    """conf=0.55 type=scroll_credit (eşik=0.50) → low_confidence=False."""
    ev = _make_event(event_type="scroll_credit", confidence=0.55)
    count = apply_thresholds([ev])
    assert ev.low_confidence is False
    assert count == 0
    # Sınırın altı 0.49 → True
    ev2 = _make_event(event_type="scroll_credit", confidence=0.49)
    count2 = apply_thresholds([ev2])
    assert ev2.low_confidence is True
    assert count2 == 1


def test_apply_custom_override_per_call():
    """apply_thresholds custom={'card': 0.95} → 0.80 confidence card düşük olmalı."""
    ev = _make_event(event_type="card", confidence=0.80)
    count = apply_thresholds([ev], custom={"card": 0.95})
    assert ev.low_confidence is True
    assert count == 1


def test_apply_unknown_type_uses_fallback():
    """Bilinmeyen tip için 0.50 fallback; 0.40 → low, 0.60 → normal."""
    ev_low = _make_event(event_type="unknown_xyz", confidence=0.40, event_id="evt_0001")
    ev_ok = _make_event(event_type="unknown_xyz", confidence=0.60, event_id="evt_0002")
    count = apply_thresholds([ev_low, ev_ok])
    assert ev_low.low_confidence is True
    assert ev_ok.low_confidence is False
    assert count == 1


def test_apply_empty_list():
    """Boş liste → count=0, exception yok."""
    count = apply_thresholds([])
    assert count == 0
