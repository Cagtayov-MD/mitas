"""TextEvent dataclass + helpers — Faz 1 (text-first mimari, madde 1+8).

Pipeline çıktısını generic `text_event` formatına maple. Schema:
`core/pipelines/ocr/schemas/text_event.schema.json` (v1.0.0).

Bu modülün sorumluluğu:
- `TextEvent` dataclass + JSON round-trip (`to_dict` / `from_dict`)
- `validate_events()` — schema'ya karşı manuel doğrulama (jsonschema opsiyonel)
- `build_text_events_from_unified()` — UnifiedCreditResult artifact'larını
  events listesine maple

Mevcut çıktılar (`cards/card_NN.json`, `scroll/scroll_text_lines.json`,
`summary.json`) bozulmaz — events.json YANINDA yazılır.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

# Schema constants (mirror text_event.schema.json — keep in sync)
_VALID_TYPES = {"scroll_credit", "card", "intertitle", "kj", "scene_text"}
_VALID_STABILITY = {"static", "scroll", "ephemeral"}
_REQUIRED_FIELDS = (
    "event_id",
    "start_sec",
    "end_sec",
    "type",
    "type_reason",
    "text",
    "confidence",
)


@dataclass
class TextEvent:
    """Single text event (one card, one scroll, one KJ).

    Required: event_id, start_sec, end_sec, type, type_reason, text, confidence
    Optional everything else; defaults reflect schema defaults.
    """

    event_id: str
    start_sec: float
    end_sec: float
    type: str
    type_reason: str
    text: str
    confidence: float
    duration_sec: float = 0.0
    bbox: list[float] | None = None  # [x, y, w, h]
    secondary_text: str | None = None
    low_confidence: bool = False
    tracker_id: int | None = None
    stability: str | None = None
    frame_count: int = 1
    lines: list[dict[str, Any]] | None = None
    paired_role_name: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict. None'ları siler (schema optional)."""
        data = asdict(self)
        # Schema'da bbox optional ama liste olunca [x,y,w,h] zorunlu
        # None değerleri çıkarırken required field'lara dokunma
        cleaned: dict[str, Any] = {}
        for key, value in data.items():
            if key in _REQUIRED_FIELDS or key in ("duration_sec", "frame_count", "low_confidence"):
                cleaned[key] = value
            elif value is not None:
                cleaned[key] = value
        return cleaned

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextEvent":
        """Roundtrip identity for to_dict() output."""
        return cls(
            event_id=data["event_id"],
            start_sec=float(data["start_sec"]),
            end_sec=float(data["end_sec"]),
            type=data["type"],
            type_reason=data["type_reason"],
            text=data["text"],
            confidence=float(data["confidence"]),
            duration_sec=float(data.get("duration_sec", 0.0)),
            bbox=list(data["bbox"]) if data.get("bbox") is not None else None,
            secondary_text=data.get("secondary_text"),
            low_confidence=bool(data.get("low_confidence", False)),
            tracker_id=data.get("tracker_id"),
            stability=data.get("stability"),
            frame_count=int(data.get("frame_count", 1)),
            lines=list(data["lines"]) if data.get("lines") is not None else None,
            paired_role_name=dict(data["paired_role_name"]) if data.get("paired_role_name") is not None else None,
        )


def validate_events(events: list[TextEvent]) -> list[str]:
    """Schema validation — boş liste = valid; her error event_id ile başlar.

    jsonschema yoksa manuel kontrol yapar. jsonschema varsa onu kullanır.
    """
    errors: list[str] = []
    try:
        import jsonschema  # type: ignore
        schema = _load_schema()
        validator = jsonschema.Draft7Validator(schema["definitions"]["TextEvent"])
        for ev in events:
            data = ev.to_dict()
            event_id = data.get("event_id", "<no_id>")
            # Manuel ek kontroller (jsonschema enum/required'i kaçırsa diye katmanlı)
            errors.extend(_manual_check_event(data, event_id))
            for err in validator.iter_errors(data):
                errors.append(f"{event_id}: schema {'/'.join(str(p) for p in err.path)}: {err.message}")
    except ImportError:
        # Pure manuel validation
        for ev in events:
            data = ev.to_dict()
            event_id = data.get("event_id", "<no_id>")
            errors.extend(_manual_check_event(data, event_id))
    return errors


def _manual_check_event(data: dict[str, Any], event_id: str) -> list[str]:
    errors: list[str] = []
    # required
    for field_name in _REQUIRED_FIELDS:
        if field_name not in data:
            errors.append(f"{event_id}: missing required field '{field_name}'")
    # event_id pattern
    eid = str(data.get("event_id", ""))
    if not (eid.startswith("evt_") and eid[4:].isdigit() and len(eid) >= 8):
        errors.append(f"{event_id}: event_id must match ^evt_[0-9]{{4,}}$")
    # type_reason non-empty
    type_reason = data.get("type_reason")
    if not isinstance(type_reason, str) or type_reason == "":
        errors.append(f"{event_id}: type_reason must be non-empty string")
    # type enum
    if data.get("type") not in _VALID_TYPES:
        errors.append(f"{event_id}: type '{data.get('type')}' not in {sorted(_VALID_TYPES)}")
    # stability enum (optional)
    stability = data.get("stability")
    if stability is not None and stability not in _VALID_STABILITY:
        errors.append(f"{event_id}: stability '{stability}' not in {sorted(_VALID_STABILITY)}")
    # confidence range
    conf = data.get("confidence")
    if isinstance(conf, (int, float)):
        if conf < 0.0 or conf > 1.0:
            errors.append(f"{event_id}: confidence {conf} not in [0.0, 1.0]")
    # bbox shape
    bbox = data.get("bbox")
    if bbox is not None:
        if not (isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(v, (int, float)) for v in bbox)):
            errors.append(f"{event_id}: bbox must be [x,y,w,h] numbers")
    return errors


def _load_schema() -> dict[str, Any]:
    schema_path = Path(__file__).parent / "schemas" / "text_event.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def build_text_events_from_unified(
    unified_summary: dict[str, Any],
    cards_dir: Path,
    scroll_lines_path: Path | None,
    scroll_canvas_path: Path | None,
    paired_lines: list[dict[str, Any]] | None,
) -> list[TextEvent]:
    """Map UnifiedCreditResult artifacts → list[TextEvent].

    - cards/card_NN.json → type=card events (1 per file)
    - scroll/scroll_text_lines.json → tek scroll_credit event (tüm satırlar `lines` içinde)
    - paired_lines varsa → ilk eşleşen secondary_text + paired_role_name dolar
    """
    events: list[TextEvent] = []
    counter = 1

    static_tracks = int(unified_summary.get("static_tracks") or 0)
    scroll_tracks = int(unified_summary.get("scroll_tracks") or 0)

    # --- Cards ---
    cards_dir = Path(cards_dir)
    if cards_dir.exists():
        card_files = sorted(cards_dir.glob("card_*.json"))
        for card_file in card_files:
            try:
                card = json.loads(card_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            start_sec = float(card.get("first_timestamp") or 0.0)
            end_sec = float(card.get("last_timestamp") or start_sec)
            duration = max(0.0, end_sec - start_sec)
            text_lines = card.get("text_lines") or []
            # Aggregate text for this card
            joined_text = "\n".join(
                str(line.get("text", "")) for line in text_lines if line.get("text")
            )
            # Mean confidence
            confs = [
                float(line.get("confidence"))
                for line in text_lines
                if isinstance(line.get("confidence"), (int, float))
            ]
            mean_conf = sum(confs) / len(confs) if confs else 0.0
            # bbox: ilk satırdan al (y_range varsa onu kullan)
            bbox: list[float] | None = None
            if text_lines and isinstance(text_lines[0].get("bbox"), (list, tuple)) and len(text_lines[0]["bbox"]) == 4:
                bbox = [float(v) for v in text_lines[0]["bbox"]]
            type_reason = (
                f"static_tracks={static_tracks} + duration={duration:.1f}s "
                f"+ grouped_card lines={len(text_lines)} → card"
            )
            events.append(
                TextEvent(
                    event_id=f"evt_{counter:04d}",
                    start_sec=start_sec,
                    end_sec=end_sec,
                    duration_sec=duration,
                    type="card",
                    type_reason=type_reason,
                    bbox=bbox,
                    text=joined_text,
                    confidence=round(mean_conf, 4),
                    stability="static",
                    frame_count=int(card.get("member_count") or 1),
                    lines=None,  # card için lines null (schema rehberi)
                )
            )
            counter += 1

    # --- Scroll: tek event ---
    if scroll_lines_path is not None and scroll_lines_path.exists():
        try:
            scroll_data = json.loads(scroll_lines_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            scroll_data = None
        if scroll_data:
            lines = scroll_data.get("lines") or []
            if lines:
                # Composite OCR'dan timestamp yok; scroll için video penceresi gerekiyor.
                # unified_summary'de scroll için start/end yok — proxy:
                # tüm scroll observation window (yoksa 0..duration_proxy).
                # Şimdilik 0 verme yerine summary'den türetilebilir bir alan yok,
                # bu yüzden start=0 end=duration_proxy (=runtime) yerine
                # start=end=0 bırakıp duration_sec=0 koy. Faz 4 (dynamic_window)
                # gerçek time range'i geri verecek.
                start_sec = 0.0
                end_sec = 0.0
                # confidence: line'ların ortalaması
                line_confs = [
                    float(ln.get("confidence"))
                    for ln in lines
                    if isinstance(ln.get("confidence"), (int, float))
                ]
                mean_conf = sum(line_confs) / len(line_confs) if line_confs else 0.0
                composite_str = (
                    f"+ scroll_canvas={scroll_canvas_path.name}"
                    if scroll_canvas_path is not None
                    else "+ no_composite"
                )
                fb_used = bool(scroll_data.get("fallback_used"))
                fb_str = (
                    f" + fallback={scroll_data.get('fallback_reason')}"
                    if fb_used
                    else ""
                )
                type_reason = (
                    f"scroll_tracks={scroll_tracks} + composite_lines={len(lines)} "
                    f"{composite_str}{fb_str} → scroll_credit"
                )
                # Secondary text + paired role/name: ilk eşleşmeyi yansıt
                secondary_text: str | None = None
                paired_role_name: dict[str, Any] | None = None
                if paired_lines:
                    # İlk role+name dolu olan kayıt
                    for pl in paired_lines:
                        if pl.get("role") and pl.get("name"):
                            paired_role_name = {
                                "role": pl["role"],
                                "name": pl["name"],
                            }
                            secondary_text = pl["name"]
                            break
                # Lines field'ı schema'ya uygun şekilde
                lines_field = [
                    {
                        "text": ln.get("text", ""),
                        "confidence": float(ln.get("confidence") or 0.0),
                        "bbox": ln.get("bbox") or [],
                    }
                    for ln in lines
                ]
                # Aggregate text (ilk satır primary; tümü lines'da)
                first_text = str(lines[0].get("text") or "") if lines else ""
                events.append(
                    TextEvent(
                        event_id=f"evt_{counter:04d}",
                        start_sec=start_sec,
                        end_sec=end_sec,
                        duration_sec=max(0.0, end_sec - start_sec),
                        type="scroll_credit",
                        type_reason=type_reason,
                        bbox=None,  # scroll: birden çok bbox, lines içinde
                        text=first_text,
                        secondary_text=secondary_text,
                        confidence=round(mean_conf, 4),
                        stability="scroll",
                        frame_count=len(lines),
                        lines=lines_field,
                        paired_role_name=paired_role_name,
                    )
                )
                counter += 1

    # --- Faz 5 (madde 7): tip-spesifik confidence eşiği uygula ---
    # Eşik altı event'ler low_confidence=True flag'lenir, atılmaz.
    from core.pipelines.ocr.confidence_thresholds import apply_thresholds
    apply_thresholds(events)

    return events
