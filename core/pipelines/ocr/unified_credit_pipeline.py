"""Box-track first unified OCR pipeline for credits.

Replaces the 8-stage credit_experiment.py path for credits when
USE_BOX_TRACK_PIPELINE=1. The old path remains for regression.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

# Module-level import: image_quality_police pulls in cv2 + numpy + PIL.
# Importing it lazily inside the A-fb decision block (per-pipeline call) was
# colliding with Paddle's GPU session in some 4-film runs (pilot v7 X-MEN
# composite OCR crash, exit 255). Hoisting the import here loads cv2/PIL once
# at module load — before Paddle init — and the conflict disappears.
from core.pipelines.ocr.image_quality_police import assess_output as _qa_assess  # noqa: E402


@dataclass(frozen=True)
class UnifiedCreditResult:
    cards_dir: Path  # static cards output dir (cards/card_NN.json + .png)
    scroll_canvas_path: Path | None  # if any scroll tracks present
    summary_path: Path
    summary: dict[str, Any]
    runtime_sec: float
    events_path: Path | None = None  # Faz 1: text_event events.json
    events_count: int = 0


def run_unified_credit_pipeline(
    frames: list[Path],
    *,
    output_dir: Path,
    paddle_engine,  # existing PaddleOcrEngine instance, reuse
    detection_stride: int = 3,
    static_speed_threshold: float = 2.0,
    source_fps: float = 6.0,
) -> UnifiedCreditResult:
    """Orchestrate: detection-only OCR → tracks → classify → static cards + scroll canvas → recognition.

    Each strided OCR record receives a synthesized timestamp_seconds derived from
    its original frame index (idx / source_fps). PaddleOCR records do not carry
    timestamps natively, but downstream grouping needs them to identify cards.
    """
    from core.pipelines.ocr.box_tracker import (
        build_text_tracks,
        classify_track_motion,
        group_static_tracks_into_cards,
        select_best_frame_per_card,
    )

    started = perf_counter()
    output_dir = Path(output_dir)
    cards_dir = output_dir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 1: OCR every detection_stride-th frame ---
    frame_paths = [str(f) for f in frames]
    strided_frames = frames[::detection_stride]

    ocr_records: list[dict[str, Any]] = []
    ocr_errors: list[str] = []
    fps_safe = source_fps if source_fps and source_fps > 0 else 6.0
    if paddle_engine is not None:
        for strided_index, frame in enumerate(strided_frames):
            original_frame_index = strided_index * detection_stride
            timestamp_seconds = original_frame_index / fps_safe
            frame_path = Path(frame)
            frame_str = str(frame_path)
            try:
                records = paddle_engine.recognize(
                    frame_path,
                    strategy="unified_detection",
                    timestamp_seconds=timestamp_seconds,
                )
                for rec in (records or []):
                    rec_copy = dict(rec)
                    if "frame" not in rec_copy:
                        rec_copy["frame"] = frame_str
                    if rec_copy.get("timestamp_seconds") is None:
                        rec_copy["timestamp_seconds"] = timestamp_seconds
                    ocr_records.append(rec_copy)
            except Exception as exc:
                ocr_errors.append(f"frame{strided_index}:{type(exc).__name__}:{exc}")

    # --- Step 2: Build tracks ---
    tracks = build_text_tracks(ocr_records, frames=frame_paths)

    # --- Step 3: Classify tracks ---
    track_classes = {t.track_id: classify_track_motion(t, static_speed_threshold=static_speed_threshold) for t in tracks}
    static_tracks = [t for t in tracks if track_classes[t.track_id] == "static_text"]
    scroll_tracks = [t for t in tracks if track_classes[t.track_id] == "scrolling_text"]

    # --- Step 4: Group static tracks into cards ---
    cards = group_static_tracks_into_cards(static_tracks)

    # --- Step 5: Best frame per card + extract text from existing records ---
    card_results: list[dict[str, Any]] = []
    for card in cards:
        frame_selection = select_best_frame_per_card(card, tracks, frame_paths)
        best_frame_path = frame_selection.get("best_frame_path")
        best_fi = frame_selection.get("best_frame_index", 0)

        # Gather text lines from OCR records for the best frame (no re-OCR)
        card_track_ids = set(card["track_ids"])
        text_lines: list[dict[str, Any]] = []
        for rec in ocr_records:
            rec_frame = str(rec.get("frame") or rec.get("source_frame") or "")
            if rec_frame == best_frame_path:
                text = rec.get("text") or rec.get("normalized_text") or ""
                if text:
                    text_lines.append({"text": text, "bbox": rec.get("bbox"), "confidence": rec.get("confidence")})

        card_out = {
            "card_id": card["card_id"],
            "best_frame_path": best_frame_path,
            "best_frame_index": best_fi,
            "score": frame_selection.get("score", 0.0),
            "first_timestamp": card.get("first_timestamp"),
            "last_timestamp": card.get("last_timestamp"),
            "y_range": card.get("y_range"),
            "member_count": card.get("member_count"),
            "contributing_tracks": frame_selection.get("contributing_tracks", []),
            "text_lines": text_lines,
        }
        card_results.append(card_out)
        _write_json(cards_dir / f"{card['card_id']}.json", card_out)

    # --- Step 6: Scrolling tracks → row reconstruct canvas + OCR ---
    scroll_canvas_path: Path | None = None
    scroll_text_lines: list[dict[str, Any]] = []
    scroll_fallback_used = False
    scroll_fallback_reason: str | None = None
    d_split_x: int | None = None
    d_split_source: str | None = None
    paired_lines: list[dict[str, Any]] = []
    if scroll_tracks:
        try:
            from core.pipelines.ocr.text_layer_row_reconstruct import run_text_layer_row_reconstruct

            scroll_frame_indices: set[int] = set()
            for t in scroll_tracks:
                for obs in t.observations:
                    scroll_frame_indices.add(obs.frame_index)

            scroll_frame_paths = [frames[i] for i in sorted(scroll_frame_indices) if i < len(frames)]
            if scroll_frame_paths:
                scroll_dir = output_dir / "scroll"
                rr_result = run_text_layer_row_reconstruct(
                    frame_paths=scroll_frame_paths,
                    output_dir=scroll_dir,
                )
                scroll_canvas_path = rr_result.composite_path
        except Exception as exc:
            ocr_errors.append(f"scroll_reconstruct:{type(exc).__name__}:{exc}")

        # OCR the scroll canvas — eski tools full_pipeline_test.py path
        if scroll_canvas_path and scroll_canvas_path.exists() and paddle_engine is not None:
            try:
                scroll_records = paddle_engine.recognize(
                    scroll_canvas_path,
                    strategy="scroll_canvas_ocr",
                    timestamp_seconds=None,
                )
                for rec in (scroll_records or []):
                    scroll_text_lines.append({
                        "text": rec.get("text") or rec.get("normalized_text") or "",
                        "bbox": rec.get("bbox"),
                        "confidence": rec.get("confidence"),
                    })
                # Sort top-to-bottom by y so the credit roll reads naturally
                scroll_text_lines.sort(key=lambda r: (r["bbox"][1] if r.get("bbox") else 0))
                _write_json(output_dir / "scroll" / "scroll_text_lines.json", {
                    "canvas_path": str(scroll_canvas_path),
                    "line_count": len(scroll_text_lines),
                    "lines": scroll_text_lines,
                })
            except Exception as exc:
                ocr_errors.append(f"scroll_canvas_ocr:{type(exc).__name__}:{exc}")

        # --- A-fb: scroll fallback emniyet ağı ---
        if _scroll_fallback_mode() == "auto":
            should_fallback = False
            reason: str | None = None
            if not scroll_canvas_path or not scroll_canvas_path.exists():
                should_fallback = True
                reason = "no_composite"
            elif len(scroll_text_lines) == 0:
                try:
                    qa = _qa_assess(scroll_canvas_path)
                    if qa.get("status") != "OK":
                        should_fallback = True
                        reason = f"composite_broken:{qa.get('status')}"
                    else:
                        should_fallback = True
                        reason = "ocr_returned_zero_lines"
                except Exception:
                    should_fallback = True
                    reason = "ocr_returned_zero_lines"

            if should_fallback:
                fallback_lines = _scroll_track_fallback_lines(scroll_tracks)
                if fallback_lines:
                    scroll_text_lines = fallback_lines
                    scroll_fallback_used = True
                    scroll_fallback_reason = reason
                    scroll_dir = output_dir / "scroll"
                    scroll_dir.mkdir(parents=True, exist_ok=True)
                    _write_json(scroll_dir / "scroll_text_lines.json", {
                        "canvas_path": str(scroll_canvas_path) if scroll_canvas_path else None,
                        "line_count": len(scroll_text_lines),
                        "lines": scroll_text_lines,
                        "fallback_used": True,
                        "fallback_reason": reason,
                    })

        # --- D-split: rol|isim sütun ayrımı ---
        if scroll_text_lines:
            scroll_dir = output_dir / "scroll"
            d_split_x, d_split_source = _read_auto_split_x(scroll_dir)
            if d_split_x is None:
                derived = _derive_split_x_from_bboxes(scroll_text_lines)
                if derived is not None:
                    d_split_x = derived
                    d_split_source = "bbox_derived"
            if d_split_x is not None:
                paired_lines = _pair_lines_by_split(scroll_text_lines, d_split_x)
                # scroll_text_lines.json'a ek alanlar yaz (overwrite)
                _write_json(scroll_dir / "scroll_text_lines.json", {
                    "canvas_path": str(scroll_canvas_path) if scroll_canvas_path else None,
                    "line_count": len(scroll_text_lines),
                    "lines": scroll_text_lines,  # geri uyumlu
                    "split_x": d_split_x,
                    "split_source": d_split_source,
                    "paired_lines": paired_lines,
                    "paired_count": len(paired_lines),
                })

    # --- Step 7: Write summary ---
    runtime_sec = round(perf_counter() - started, 3)
    summary: dict[str, Any] = {
        "total_frames": len(frames),
        "strided_frames_processed": len(strided_frames),
        "detection_stride": detection_stride,
        "total_tracks": len(tracks),
        "static_tracks": len(static_tracks),
        "scroll_tracks": len(scroll_tracks),
        "cards_found": len(cards),
        "scroll_canvas_path": str(scroll_canvas_path) if scroll_canvas_path else None,
        "scroll_text_line_count": len(scroll_text_lines),
        "scroll_fallback_used": scroll_fallback_used if scroll_tracks else False,
        "scroll_fallback_reason": scroll_fallback_reason if scroll_tracks else None,
        "d_split_x": d_split_x if scroll_tracks else None,
        "d_split_source": d_split_source if scroll_tracks else None,
        "paired_line_count": len(paired_lines) if scroll_tracks else 0,
        "runtime_sec": runtime_sec,
        "ocr_record_count": len(ocr_records),
        "ocr_error_count": len(ocr_errors),
        "ocr_errors_sample": ocr_errors[:5],
    }
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)

    # --- Step 8 (Faz 1): text_event events.json (yan yana, eski format dokunulmuyor) ---
    events_path: Path | None = None
    events_count = 0
    try:
        from core.pipelines.ocr.text_event import (
            SCHEMA_VERSION,
            build_text_events_from_unified,
        )

        scroll_lines_path = output_dir / "scroll" / "scroll_text_lines.json"
        events = build_text_events_from_unified(
            unified_summary=summary,
            cards_dir=cards_dir,
            scroll_lines_path=scroll_lines_path if scroll_lines_path.exists() else None,
            scroll_canvas_path=scroll_canvas_path,
            paired_lines=paired_lines if scroll_tracks else None,
        )
        by_type: dict[str, int] = {}
        for ev in events:
            by_type[ev.type] = by_type.get(ev.type, 0) + 1
        events_summary = {
            "engine": "k_box_track_unified",
            "version": SCHEMA_VERSION,
            "total_events": len(events),
            "by_type": by_type,
            "runtime_sec": runtime_sec,
            "low_confidence_count": 0,  # Faz 5'te doldurulacak
            "fallback_used": bool(summary.get("scroll_fallback_used")),
            "fallback_reason": summary.get("scroll_fallback_reason"),
        }
        # video_id: unified dir 'unified' adıyla geliyor; gerçek item id'si parent dir
        item_id = output_dir.name
        if item_id == "unified" and output_dir.parent != output_dir:
            item_id = output_dir.parent.name
        events_payload = {
            "schema_version": SCHEMA_VERSION,
            "video_id": item_id,
            "source_path": str(frames[0]) if frames else "",
            "events": [ev.to_dict() for ev in events],
            "summary": events_summary,
        }
        events_path = output_dir / "events.json"
        _write_json(events_path, events_payload)
        events_count = len(events)
    except Exception as exc:
        # Events yazımı pipeline başarısını bozmamalı
        ocr_errors.append(f"text_events:{type(exc).__name__}:{exc}")

    return UnifiedCreditResult(
        cards_dir=cards_dir,
        scroll_canvas_path=scroll_canvas_path,
        summary_path=summary_path,
        summary=summary,
        runtime_sec=runtime_sec,
        events_path=events_path,
        events_count=events_count,
    )


def _scroll_fallback_mode() -> str:
    """Env var'dan oku. OCR_SCROLL_FALLBACK: auto|off. Default auto."""
    import os
    value = os.environ.get("OCR_SCROLL_FALLBACK", "auto").strip().lower()
    return value if value in {"auto", "off"} else "auto"


def _scroll_track_fallback_lines(scroll_tracks: list[Any], *, min_confidence: float = 0.5) -> list[dict[str, Any]]:
    """For each scroll track pick highest-confidence observation as a line.

    Used when composite OCR fails (broken canvas / 0 lines). Each scroll track has
    multiple observations from PaddleOCR detection; the best one per track is
    treated as that track's representative line, then sorted top-to-bottom by y.
    Duplicate texts (same uppercase strip) are deduped, keeping the highest conf.
    """
    lines: list[dict[str, Any]] = []
    for track in scroll_tracks:
        valid = [
            obs for obs in track.observations
            if getattr(obs, "text", None)
            and getattr(obs, "confidence", None) is not None
            and float(obs.confidence) >= min_confidence
        ]
        if not valid:
            continue
        best = max(valid, key=lambda o: float(o.confidence or 0.0))
        bbox = list(best.bbox) if best.bbox is not None else None
        lines.append({
            "text": best.text,
            "bbox": bbox,
            "confidence": float(best.confidence or 0.0),
            "source": "track_observation_fallback",
        })
    # Sort top-to-bottom
    lines.sort(key=lambda line: (line["bbox"][1] if line.get("bbox") else 0))
    # Dedupe by uppercase-stripped text, keep highest confidence
    seen: dict[str, dict[str, Any]] = {}
    for line in lines:
        key = (line["text"] or "").strip().upper()
        if not key:
            continue
        if key not in seen or line["confidence"] > seen[key]["confidence"]:
            seen[key] = line
    return list(seen.values())


def _read_auto_split_x(scroll_dir: Path) -> tuple[int | None, str | None]:
    """row_reconstruct_summary.json'dan auto_split.split_x oku. (split_x, source)."""
    summary_path = scroll_dir / "row_reconstruct_summary.json"
    if not summary_path.exists():
        return None, None
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    auto = data.get("auto_split") or {}
    split_x = auto.get("split_x")
    if isinstance(split_x, (int, float)) and split_x > 0:
        return int(split_x), "auto_split_algorithm"
    return None, None


def _derive_split_x_from_bboxes(
    lines: list[dict[str, Any]],
    *,
    y_tolerance: int = 5,
    min_pairs: int = 3,
    min_gap_px: int = 8,
) -> int | None:
    """Aynı y'deki bbox'lardan sütun gap'inin medyanını hesapla.

    Algoritma:
      1. Her line için (y_center, x_start, x_end) çıkar
      2. y_center'ları y_tolerance ile bucket'la (aynı satır demek)
      3. Bucket'ta 2+ bbox varsa (multi-column), en geniş x_gap'i hesapla
         (gap = sonraki bbox.x_start - önceki bbox.x_end)
      4. min_pairs+ bucket gap üretti ise → median(gap_midpoints) döner
      5. Yoksa None.
    """
    if not lines:
        return None
    items: list[tuple[float, int, int]] = []
    for line in lines:
        bbox = line.get("bbox")
        if not (isinstance(bbox, (list, tuple)) and len(bbox) >= 4):
            continue
        try:
            x = float(bbox[0]); y = float(bbox[1]); w = float(bbox[2]); h = float(bbox[3])
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        items.append((y + h / 2.0, int(round(x)), int(round(x + w))))
    if not items:
        return None
    # y'ye göre sırala, y_tolerance ile bucket'la
    items.sort(key=lambda t: t[0])
    buckets: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    current_y_ref: float | None = None
    for y_c, x0, x1 in items:
        if current_y_ref is None or abs(y_c - current_y_ref) <= y_tolerance:
            current.append((x0, x1))
            if current_y_ref is None:
                current_y_ref = y_c
        else:
            if len(current) >= 2:
                buckets.append(current)
            current = [(x0, x1)]
            current_y_ref = y_c
    if len(current) >= 2:
        buckets.append(current)
    if not buckets:
        return None
    # Her bucket'ta en geniş gap'in midpoint'ini topla
    midpoints: list[int] = []
    for bucket in buckets:
        sorted_b = sorted(bucket, key=lambda t: t[0])
        best_gap = min_gap_px - 1
        best_mid: int | None = None
        for i in range(len(sorted_b) - 1):
            gap_l = sorted_b[i][1]   # sol bbox'ın x_end
            gap_r = sorted_b[i + 1][0]  # sağ bbox'ın x_start
            gap = gap_r - gap_l
            if gap > best_gap:
                best_gap = gap
                best_mid = (gap_l + gap_r) // 2
        if best_mid is not None:
            midpoints.append(best_mid)
    if len(midpoints) < min_pairs:
        return None
    midpoints.sort()
    return int(midpoints[len(midpoints) // 2])


def _pair_lines_by_split(
    lines: list[dict[str, Any]],
    split_x: int,
    *,
    y_tolerance: int = 5,
) -> list[dict[str, Any]]:
    """split_x'e göre satırları role|name çiftleri olarak pair'le.

    Her bbox'ın merkez x'ine bakar: < split_x → role kolonu, >= split_x → name.
    Aynı y ± y_tolerance içindeki sol+sağ bbox'ları birleştirir.
    Tek sütunda kalan satırlar `role`=text, `name`=None (veya tersi) olarak yazılır.
    """
    enriched: list[tuple[float, float, dict[str, Any]]] = []  # (y_center, x_center, line)
    for line in lines:
        bbox = line.get("bbox")
        if not (isinstance(bbox, (list, tuple)) and len(bbox) >= 4):
            continue
        try:
            x = float(bbox[0]); y = float(bbox[1]); w = float(bbox[2]); h = float(bbox[3])
        except (TypeError, ValueError):
            continue
        enriched.append((y + h / 2.0, x + w / 2.0, line))
    enriched.sort(key=lambda t: t[0])

    paired: list[dict[str, Any]] = []
    i = 0
    while i < len(enriched):
        y_c, x_c, line = enriched[i]
        # Aynı y ± tolerance içinde başka bbox var mı bak
        partner: tuple[float, float, dict[str, Any]] | None = None
        for j in range(i + 1, len(enriched)):
            y_c2, x_c2, line2 = enriched[j]
            if y_c2 - y_c > y_tolerance:
                break
            # Farklı sütunda mı?
            if (x_c < split_x and x_c2 >= split_x) or (x_c >= split_x and x_c2 < split_x):
                partner = (y_c2, x_c2, line2)
                # Partner'ı listeden çıkarmak için index'i kaydet
                enriched.pop(j)
                break
        if partner is None:
            # Tek sütun
            if x_c < split_x:
                paired.append({
                    "y": round(y_c, 1),
                    "role": line.get("text"),
                    "name": None,
                    "role_confidence": line.get("confidence"),
                    "name_confidence": None,
                })
            else:
                paired.append({
                    "y": round(y_c, 1),
                    "role": None,
                    "name": line.get("text"),
                    "role_confidence": None,
                    "name_confidence": line.get("confidence"),
                })
        else:
            y_c2, x_c2, line2 = partner
            if x_c < split_x:
                role_line, name_line = line, line2
            else:
                role_line, name_line = line2, line
            paired.append({
                "y": round((y_c + y_c2) / 2.0, 1),
                "role": role_line.get("text"),
                "name": name_line.get("text"),
                "role_confidence": role_line.get("confidence"),
                "name_confidence": name_line.get("confidence"),
            })
        i += 1
    return paired


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
