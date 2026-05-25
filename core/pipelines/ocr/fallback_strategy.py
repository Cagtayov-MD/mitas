"""OneOCR akıllı fallback (V2.1).

Paddle çuvalladığında OneOCR ile re-run yapar. Tetiklenme kuralları:
- scroll_text_line_count == 0 ve cards_found == 0 → tam çöküş
- scroll_text_line_count == 0 ve cards_found <= 3 → composite scroll çuvallamış
- composite quality_label `BROKEN_*` ile başlıyor → BG leak / black / no_text / smear

OneOCR Windows-only native DLL (Snipping Tool engine). Pipeline boyunca
DLL load pahalı (~2-4sn), bu yüzden engine instance singleton'a yakın
ele alınmalı (caller'a bırakılıyor).

Fallback olarak:
1. Eğer composite (scroll_canvas) varsa → tek görsel üzerinde OneOCR koş,
   bbox bazlı line'lar üret.
2. Composite yoksa → scroll_frames listesinden alt-örnek (max N frame)
   alıp her birinde OneOCR koş, en yüksek conf satırı temsilci olarak al.

Sonuçlar paddle çıktısıyla MERGE edilir (paddle line'lar korunur, OneOCR
line'lar ek olarak işaretli `source="oneocr_fallback"` ile gelir). Çağıran
bu merged listeyi `scroll/scroll_text_lines.json`'a yazar ve events.json'ı
yeniden build eder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# Composite_broken için sayılan etiket prefix'i
_BROKEN_PREFIX = "BROKEN_"


@dataclass(frozen=True)
class FallbackDecision:
    """Fallback gerekli mi + nedeni + paddle ölçütleri (telemetri)."""

    should_trigger: bool
    reason: str | None
    paddle_metrics: dict[str, Any] = field(default_factory=dict)


def evaluate_fallback_need(
    paddle_unified_summary: dict[str, Any] | None,
    composite_quality_report: dict[str, Any] | None = None,
) -> FallbackDecision:
    """Paddle çıktısına bakıp OneOCR fallback gerekli mi karar ver.

    Öncelik sırası:
      1. composite_quality_report.status `BROKEN_*` ise → trigger
      2. scroll_lines == 0 ve cards == 0 → trigger (tam fail)
      3. scroll_lines == 0 ve cards <= 3 → trigger (composite scroll çuvalladı)
      4. Aksi halde → False
    """
    summary = paddle_unified_summary or {}
    metrics = {
        "scroll_text_line_count": int(summary.get("scroll_text_line_count") or 0),
        "cards_found": int(summary.get("cards_found") or 0),
        "composite_quality": (composite_quality_report or {}).get("status"),
    }

    # 1) composite broken kontrolü (öncelikli — quality_label kazanır)
    if composite_quality_report:
        status = str(composite_quality_report.get("status") or "")
        if status.startswith(_BROKEN_PREFIX):
            return FallbackDecision(True, f"composite_broken:{status}", metrics)

    # 2) tam fail
    if metrics["scroll_text_line_count"] == 0 and metrics["cards_found"] == 0:
        return FallbackDecision(True, "paddle_zero_lines_and_cards", metrics)

    # 3) scroll boş + kart az
    if metrics["scroll_text_line_count"] == 0 and metrics["cards_found"] <= 3:
        return FallbackDecision(True, "paddle_zero_scroll_low_cards", metrics)

    return FallbackDecision(False, None, metrics)


def run_oneocr_fallback(
    *,
    oneocr_engine: Any,
    scroll_canvas_path: Path | None,
    scroll_frame_paths: list[Path] | None = None,
    paddle_lines: list[dict[str, Any]] | None = None,
    max_frame_samples: int = 12,
    min_confidence: float = 0.4,
) -> dict[str, Any]:
    """OneOCR ile fallback OCR koş, paddle lines'la merge et.

    Çıktı:
        {
          "lines": list[dict],          # paddle + fallback merged (sorted by y)
          "fallback_lines": list[dict], # sadece OneOCR'dan gelenler (source="oneocr_fallback")
          "fallback_event_count": int,
          "fallback_source": "composite"|"frames"|"none",
          "fallback_frames_processed": int,
          "fallback_engine": "oneocr",
        }

    OneOCR engine recognize(image_path, *, strategy, timestamp_seconds) bekler
    (PaddleOcrEngine ile aynı kontrat — `OneOcrEngine` zaten bu arayüze
    uyuyor, credit_experiment.py line 521).
    """
    paddle_lines = list(paddle_lines or [])
    fallback_lines: list[dict[str, Any]] = []
    frames_processed = 0
    source = "none"

    # 1) Composite varsa onu tek seferde OCR'la (hızlı, doğru)
    if scroll_canvas_path is not None and Path(scroll_canvas_path).exists():
        source = "composite"
        try:
            records = oneocr_engine.recognize(
                Path(scroll_canvas_path),
                strategy="oneocr_fallback_composite",
                timestamp_seconds=None,
            )
            for rec in records or []:
                text = str(rec.get("text") or "").strip()
                if not text:
                    continue
                conf = rec.get("confidence")
                if conf is not None and float(conf) < min_confidence:
                    continue
                fallback_lines.append({
                    "text": text,
                    "bbox": rec.get("bbox"),
                    "confidence": float(conf) if conf is not None else 0.0,
                    "source": "oneocr_fallback",
                })
            frames_processed = 1
        except Exception as exc:
            fallback_lines.append({
                "text": "",
                "bbox": None,
                "confidence": 0.0,
                "source": "oneocr_fallback_error",
                "error": f"{type(exc).__name__}:{exc}",
            })
            # Hatayı listede tut ama sonra filtrele
            fallback_lines = [ln for ln in fallback_lines if ln.get("text")]

    # 2) Composite yok / boş geldi → frames'den alt-örnekle
    if not fallback_lines and scroll_frame_paths:
        source = "frames"
        # Eşit aralıklı örnekle (max_frame_samples)
        total = len(scroll_frame_paths)
        if total <= max_frame_samples:
            sampled = list(scroll_frame_paths)
        else:
            step = max(1, total // max_frame_samples)
            sampled = [scroll_frame_paths[i] for i in range(0, total, step)][:max_frame_samples]

        # Tüm sampled frame'lerden gelen line'ları topla, sonra dedupe et
        raw: list[dict[str, Any]] = []
        for frame_path in sampled:
            try:
                records = oneocr_engine.recognize(
                    Path(frame_path),
                    strategy="oneocr_fallback_frame",
                    timestamp_seconds=None,
                )
                frames_processed += 1
                for rec in records or []:
                    text = str(rec.get("text") or "").strip()
                    if not text:
                        continue
                    conf = rec.get("confidence")
                    if conf is not None and float(conf) < min_confidence:
                        continue
                    raw.append({
                        "text": text,
                        "bbox": rec.get("bbox"),
                        "confidence": float(conf) if conf is not None else 0.0,
                        "source": "oneocr_fallback",
                        "source_frame": str(frame_path),
                    })
            except Exception:
                # Sessiz; bir frame'de hata diğerlerini bozmamalı
                continue

        # Dedupe: aynı uppercase-stripped text → en yüksek confidence'lı kaydı tut
        deduped: dict[str, dict[str, Any]] = {}
        for ln in raw:
            key = (ln["text"] or "").strip().upper()
            if not key:
                continue
            if key not in deduped or ln["confidence"] > deduped[key]["confidence"]:
                deduped[key] = ln
        fallback_lines = list(deduped.values())

    # 3) Merge — paddle line'larda olan text'leri dedupe et
    paddle_keys = set()
    for ln in paddle_lines:
        key = (str(ln.get("text") or "")).strip().upper()
        if key:
            paddle_keys.add(key)

    merged = list(paddle_lines)
    extra_count = 0
    for fb in fallback_lines:
        fb_key = (fb.get("text") or "").strip().upper()
        if fb_key in paddle_keys:
            continue
        merged.append(fb)
        extra_count += 1

    # Top-to-bottom sırala (bbox y varsa)
    merged.sort(key=lambda r: (r.get("bbox")[1] if isinstance(r.get("bbox"), (list, tuple)) and len(r.get("bbox") or []) >= 2 else 0))

    return {
        "lines": merged,
        "fallback_lines": fallback_lines,
        "fallback_event_count": extra_count,
        "fallback_source": source,
        "fallback_frames_processed": frames_processed,
        "fallback_engine": "oneocr",
    }


def fallback_enabled_from_env(env: dict[str, str] | None = None) -> bool:
    """`MITAS_OCR_FALLBACK` env var ile aç/kapa. Default açık.

    Kabul edilen değerler:
      - "oneocr" / "1" / "true" / "yes" / "on" / "" / unset → ON
      - "0" / "false" / "no" / "off" / "disabled" → OFF
    """
    import os

    raw = (env or os.environ).get("MITAS_OCR_FALLBACK", "")
    value = (raw or "").strip().lower()
    if value in {"0", "false", "no", "off", "disabled"}:
        return False
    return True
