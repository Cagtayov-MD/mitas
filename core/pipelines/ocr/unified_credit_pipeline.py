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


@dataclass(frozen=True)
class UnifiedCreditResult:
    cards_dir: Path  # static cards output dir (cards/card_NN.json + .png)
    scroll_canvas_path: Path | None  # if any scroll tracks present
    summary_path: Path
    summary: dict[str, Any]
    runtime_sec: float


def run_unified_credit_pipeline(
    frames: list[Path],
    *,
    output_dir: Path,
    paddle_engine,  # existing PaddleOcrEngine instance, reuse
    detection_stride: int = 3,
    static_speed_threshold: float = 2.0,
) -> UnifiedCreditResult:
    """Orchestrate: detection-only OCR → tracks → classify → static cards + scroll canvas → recognition."""
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
    if paddle_engine is not None:
        for frame_index, frame in enumerate(strided_frames):
            frame_path = Path(frame)
            frame_str = str(frame_path)
            try:
                records = paddle_engine.recognize(
                    frame_path,
                    strategy="unified_detection",
                    timestamp_seconds=None,
                )
                for rec in (records or []):
                    rec_copy = dict(rec)
                    if "frame" not in rec_copy:
                        rec_copy["frame"] = frame_str
                    ocr_records.append(rec_copy)
            except Exception as exc:
                ocr_errors.append(f"frame{frame_index}:{type(exc).__name__}:{exc}")

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

    # --- Step 6: Scrolling tracks → row reconstruct canvas ---
    scroll_canvas_path: Path | None = None
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
        except Exception:
            pass

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
        "runtime_sec": runtime_sec,
        "ocr_record_count": len(ocr_records),
        "ocr_error_count": len(ocr_errors),
        "ocr_errors_sample": ocr_errors[:5],
    }
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)

    return UnifiedCreditResult(
        cards_dir=cards_dir,
        scroll_canvas_path=scroll_canvas_path,
        summary_path=summary_path,
        summary=summary,
        runtime_sec=runtime_sec,
    )


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
