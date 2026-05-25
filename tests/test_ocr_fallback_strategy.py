"""Unit tests for V2.1 akıllı OneOCR fallback (`fallback_strategy.py`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.pipelines.ocr.fallback_strategy import (
    FallbackDecision,
    evaluate_fallback_need,
    fallback_enabled_from_env,
    run_oneocr_fallback,
)


# ---------------------------------------------------------------------------
# evaluate_fallback_need
# ---------------------------------------------------------------------------


def test_no_fallback_when_paddle_healthy():
    """scroll=200, cards=10, quality OK → False."""
    summary = {"scroll_text_line_count": 200, "cards_found": 10}
    qa = {"status": "OK"}
    decision = evaluate_fallback_need(summary, qa)
    assert isinstance(decision, FallbackDecision)
    assert decision.should_trigger is False
    assert decision.reason is None
    assert decision.paddle_metrics["scroll_text_line_count"] == 200
    assert decision.paddle_metrics["cards_found"] == 10


def test_fallback_when_scroll_zero_and_cards_zero():
    """Tam fail — paddle hiçbir şey üretmedi."""
    summary = {"scroll_text_line_count": 0, "cards_found": 0}
    decision = evaluate_fallback_need(summary, None)
    assert decision.should_trigger is True
    assert decision.reason == "paddle_zero_lines_and_cards"


def test_fallback_when_scroll_zero_low_cards():
    """scroll=0 + cards<=3 → composite scroll çuvalladı."""
    summary = {"scroll_text_line_count": 0, "cards_found": 2}
    decision = evaluate_fallback_need(summary, None)
    assert decision.should_trigger is True
    assert decision.reason == "paddle_zero_scroll_low_cards"


def test_no_fallback_when_scroll_zero_but_many_cards():
    """scroll=0 + cards=20 → cards healthy, fallback gereksiz.

    Eşik cards<=3; 20 cards açık ara üzerinde, tetiklenmemeli.
    """
    summary = {"scroll_text_line_count": 0, "cards_found": 20}
    decision = evaluate_fallback_need(summary, None)
    assert decision.should_trigger is False
    assert decision.reason is None


def test_fallback_when_composite_broken_no_text():
    summary = {"scroll_text_line_count": 5, "cards_found": 5}
    qa = {"status": "BROKEN_NO_TEXT"}
    decision = evaluate_fallback_need(summary, qa)
    assert decision.should_trigger is True
    assert decision.reason == "composite_broken:BROKEN_NO_TEXT"


def test_fallback_when_composite_broken_black():
    summary = {"scroll_text_line_count": 100, "cards_found": 10}
    qa = {"status": "BROKEN_BLACK"}
    decision = evaluate_fallback_need(summary, qa)
    assert decision.should_trigger is True
    assert decision.reason == "composite_broken:BROKEN_BLACK"


def test_composite_broken_overrides_healthy_counts():
    """quality_label öncelikli — sayılar iyi olsa bile BROKEN ise re-run."""
    summary = {"scroll_text_line_count": 250, "cards_found": 30}
    qa = {"status": "BROKEN_BACKGROUND_LEAK"}
    decision = evaluate_fallback_need(summary, qa)
    assert decision.should_trigger is True
    assert decision.reason == "composite_broken:BROKEN_BACKGROUND_LEAK"


def test_fallback_reason_field_set_correctly():
    """Reason string formatı her senaryoda doğru olsun."""
    # Composite broken — "composite_broken:<label>"
    d1 = evaluate_fallback_need({"scroll_text_line_count": 0, "cards_found": 0}, {"status": "BROKEN_LOW_CONTRAST"})
    assert d1.reason == "composite_broken:BROKEN_LOW_CONTRAST"
    # Tam fail — exact string
    d2 = evaluate_fallback_need({"scroll_text_line_count": 0, "cards_found": 0}, None)
    assert d2.reason == "paddle_zero_lines_and_cards"
    # Low cards scroll zero
    d3 = evaluate_fallback_need({"scroll_text_line_count": 0, "cards_found": 1}, None)
    assert d3.reason == "paddle_zero_scroll_low_cards"
    # Healthy — None
    d4 = evaluate_fallback_need({"scroll_text_line_count": 100, "cards_found": 5}, {"status": "OK"})
    assert d4.reason is None


def test_no_fallback_when_only_qa_status_ok():
    """status='OK' (BROKEN_ prefix yok) → tetiklemez."""
    summary = {"scroll_text_line_count": 50, "cards_found": 5}
    qa = {"status": "OK"}
    decision = evaluate_fallback_need(summary, qa)
    assert decision.should_trigger is False


def test_no_fallback_when_suspicious_status():
    """SUSPICIOUS_NEEDS_REVIEW BROKEN_ prefix değil — fallback değil."""
    summary = {"scroll_text_line_count": 10, "cards_found": 5}
    qa = {"status": "SUSPICIOUS_NEEDS_REVIEW"}
    decision = evaluate_fallback_need(summary, qa)
    assert decision.should_trigger is False


def test_evaluate_handles_missing_summary_gracefully():
    """None summary → 0/0 olarak yorumla, tam fail tetikle."""
    decision = evaluate_fallback_need(None, None)
    assert decision.should_trigger is True
    assert decision.reason == "paddle_zero_lines_and_cards"


# ---------------------------------------------------------------------------
# fallback_enabled_from_env
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["", "oneocr", "1", "true", "yes", "on"])
def test_fallback_enabled_default_on(value):
    assert fallback_enabled_from_env({"MITAS_OCR_FALLBACK": value}) is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "disabled"])
def test_fallback_disabled_explicit_off(value):
    assert fallback_enabled_from_env({"MITAS_OCR_FALLBACK": value}) is False


def test_fallback_enabled_when_env_missing():
    assert fallback_enabled_from_env({}) is True


# ---------------------------------------------------------------------------
# run_oneocr_fallback — composite path
# ---------------------------------------------------------------------------


class _FakeOneOcrEngine:
    """Test double; deterministic line outputs per call."""

    def __init__(self, scripted: list[list[dict[str, Any]]]):
        self._scripted = list(scripted)
        self.calls: list[tuple[Path, str]] = []

    def recognize(self, image_path: Path, *, strategy: str, timestamp_seconds: float | None = None):
        self.calls.append((Path(image_path), strategy))
        if not self._scripted:
            return []
        return self._scripted.pop(0)


def _make_record(text: str, conf: float = 0.9, y: int = 100) -> dict[str, Any]:
    return {"text": text, "bbox": [10, y, 200, 30], "confidence": conf}


def test_run_oneocr_fallback_composite_merges_lines(tmp_path: Path):
    composite = tmp_path / "composite.png"
    composite.write_bytes(b"fake")
    engine = _FakeOneOcrEngine([
        [_make_record("PHOEBE MCAULEY", 0.95, 100), _make_record("GEORGE BUZA", 0.92, 200)]
    ])
    paddle_lines = [{"text": "MUSIC BY X", "bbox": [10, 50, 100, 20], "confidence": 0.8}]
    result = run_oneocr_fallback(
        oneocr_engine=engine,
        scroll_canvas_path=composite,
        scroll_frame_paths=None,
        paddle_lines=paddle_lines,
    )
    assert result["fallback_source"] == "composite"
    assert result["fallback_event_count"] == 2
    assert result["fallback_engine"] == "oneocr"
    assert len(result["lines"]) == 3  # 1 paddle + 2 fallback
    # Engine bir kez çağrıldı (composite)
    assert len(engine.calls) == 1
    assert engine.calls[0][1] == "oneocr_fallback_composite"


def test_run_oneocr_fallback_dedupes_paddle_overlap(tmp_path: Path):
    """Paddle'da olan text OneOCR'da da gelirse dedupe edilmeli."""
    composite = tmp_path / "composite.png"
    composite.write_bytes(b"fake")
    engine = _FakeOneOcrEngine([
        [_make_record("SHARED TEXT", 0.95), _make_record("NEW NAME", 0.9, 200)]
    ])
    paddle_lines = [{"text": "shared text", "bbox": [0, 0, 100, 20], "confidence": 0.7}]
    result = run_oneocr_fallback(
        oneocr_engine=engine,
        scroll_canvas_path=composite,
        paddle_lines=paddle_lines,
    )
    # SHARED TEXT zaten paddle'da var → sadece NEW NAME eklenmeli
    assert result["fallback_event_count"] == 1
    assert len(result["lines"]) == 2


def test_run_oneocr_fallback_frames_when_no_composite(tmp_path: Path):
    """Composite yok → frame örnekleme yolu."""
    f1 = tmp_path / "f1.png"; f1.write_bytes(b"a")
    f2 = tmp_path / "f2.png"; f2.write_bytes(b"b")
    engine = _FakeOneOcrEngine([
        [_make_record("TAJJA ISEN", 0.9, 50)],
        [_make_record("JUAN CHIORAN", 0.91, 80)],
    ])
    result = run_oneocr_fallback(
        oneocr_engine=engine,
        scroll_canvas_path=None,
        scroll_frame_paths=[f1, f2],
        paddle_lines=[],
    )
    assert result["fallback_source"] == "frames"
    assert result["fallback_frames_processed"] == 2
    assert result["fallback_event_count"] == 2


def test_run_oneocr_fallback_low_conf_filtered(tmp_path: Path):
    composite = tmp_path / "c.png"
    composite.write_bytes(b"x")
    engine = _FakeOneOcrEngine([
        [_make_record("GOOD", 0.9), _make_record("BAD", 0.1)]
    ])
    result = run_oneocr_fallback(
        oneocr_engine=engine,
        scroll_canvas_path=composite,
        paddle_lines=[],
        min_confidence=0.4,
    )
    assert result["fallback_event_count"] == 1
    assert result["lines"][0]["text"] == "GOOD"


def test_run_oneocr_fallback_zero_events_when_engine_empty(tmp_path: Path):
    composite = tmp_path / "c.png"
    composite.write_bytes(b"x")
    engine = _FakeOneOcrEngine([[]])
    result = run_oneocr_fallback(
        oneocr_engine=engine,
        scroll_canvas_path=composite,
        scroll_frame_paths=None,
        paddle_lines=[{"text": "ORIG", "bbox": [0, 0, 50, 20], "confidence": 0.8}],
    )
    # OneOCR hiçbir şey vermedi, scroll_frame_paths da yok
    assert result["fallback_event_count"] == 0
    assert len(result["lines"]) == 1  # sadece paddle
