from __future__ import annotations

import argparse
import json
from difflib import SequenceMatcher
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.pipelines.ocr.credit_experiment import (
    build_default_engine_factories,
    normalize_text,
    _build_engines,
    _run_frame_ocr,
)


TARGET_ROW_HEIGHT_PX = 30.0
SCROLL_CONFIDENCE_THRESHOLD = 0.85


def run_item(
    item_id: str,
    *,
    pilot_output: Path,
    output_dir: Path,
    engines: list[str],
) -> dict[str, Any]:
    item_dir = pilot_output / "items" / item_id
    item_output_dir = output_dir / item_id
    item_output_dir.mkdir(parents=True, exist_ok=True)
    scene = _read_json(item_dir / "scene_router_refined.json") or _read_json(item_dir / "scene_router.json") or {}
    summary = _read_json(item_dir / "item_summary.json") or {}
    confidence = _vertical_scroll_confidence(scene)
    fps = float(summary.get("fps") or 6.0)
    dy_per_second = _dy_per_second(scene)
    dy_per_frame = dy_per_second / max(fps, 0.001)

    if confidence < SCROLL_CONFIDENCE_THRESHOLD or abs(dy_per_frame) <= 0.001:
        result = {
            "item_id": item_id,
            "status": "skipped",
            "reason": "low_vertical_scroll_confidence_or_motion",
            "vertical_scroll_confidence": confidence,
            "dy_per_frame": dy_per_frame,
            "rows": [],
        }
        _write_json(item_output_dir / "frame_stride_rows.json", result)
        _write_json(item_output_dir / "comparison.json", _comparison(item_dir, []))
        return result

    frame_ocr = _read_json(item_dir / "frame_ocr.json") or {}
    frame_paths = [Path(path) for path in frame_ocr.get("frames") or [] if Path(path).exists()]
    stride_frames = max(1, round(TARGET_ROW_HEIGHT_PX / abs(dy_per_frame)))
    sampled_frames = frame_paths[::stride_frames]
    records, ocr_source = _records_for_sampled_frames(
        frame_ocr,
        sampled_frames,
        engines=engines,
        fps=fps,
        start_seconds=float(summary.get("start_seconds") or 0.0),
    )
    rows = _dedupe_rows(records)
    result = {
        "item_id": item_id,
        "status": "done",
        "vertical_scroll_confidence": confidence,
        "dy_per_second": round(dy_per_second, 6),
        "dy_per_frame": round(dy_per_frame, 6),
        "target_row_height_px": TARGET_ROW_HEIGHT_PX,
        "stride_frames": stride_frames,
        "sampled_frame_count": len(sampled_frames),
        "ocr_source": ocr_source,
        "rows": rows,
    }
    comparison = _comparison(item_dir, rows)
    _write_json(item_output_dir / "frame_stride_rows.json", result)
    _write_json(item_output_dir / "comparison.json", comparison)
    result["comparison"] = comparison
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Frame-stride OCR POC for vertical rolling credits.")
    parser.add_argument("--items", required=True, help="Comma-separated item ids")
    parser.add_argument("--pilot-output", required=True, type=Path, help="Existing credit_experiment output directory")
    parser.add_argument("--output", required=True, type=Path, help="Output directory for POC JSON")
    parser.add_argument("--engines", default="paddle", help="Comma-separated engines for cache miss OCR fallback")
    args = parser.parse_args()

    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    engines = [part.strip() for part in args.engines.split(",") if part.strip()]
    item_ids = [part.strip() for part in args.items.split(",") if part.strip()]
    results = [
        run_item(item_id, pilot_output=args.pilot_output, output_dir=output_dir, engines=engines)
        for item_id in item_ids
    ]
    summary = {
        "status": "done",
        "pilot_output": str(args.pilot_output),
        "output": str(output_dir),
        "items": [
            {
                "item_id": result.get("item_id"),
                "status": result.get("status"),
                "frame_stride_unique_rows": len(result.get("rows") or []),
                "row_reconstruct_unique_rows": (result.get("comparison") or {}).get("row_reconstruct_unique_rows"),
                "shared_rows": (result.get("comparison") or {}).get("shared_rows"),
                "stride_frames": result.get("stride_frames"),
            }
            for result in results
        ],
    }
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _records_for_sampled_frames(
    frame_ocr: dict[str, Any],
    sampled_frames: list[Path],
    *,
    engines: list[str],
    fps: float,
    start_seconds: float,
) -> tuple[list[dict[str, Any]], str]:
    sampled_names = {frame.name for frame in sampled_frames}
    cached = []
    for record in frame_ocr.get("records") or []:
        frame = Path(str(record.get("frame") or ""))
        if frame.name in sampled_names:
            cached.append(record)
    if cached or not sampled_frames:
        return cached, "cached_frame_ocr"

    active_engines, _ = _build_engines(engines, build_default_engine_factories(engines))
    frame_result = _run_frame_ocr(sampled_frames, active_engines, start_seconds=start_seconds, fps=fps, strategy="frame_stride_ocr")
    return list(frame_result.get("records") or []), "fresh_ocr"


def _dedupe_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: (float(item.get("timestamp_seconds") or 0.0), _bbox_center_y(item.get("bbox")))):
        text = str(record.get("text") or "").strip()
        normalized = normalize_text(str(record.get("normalized_text") or text))
        if not normalized:
            continue
        y_center = _bbox_center_y(record.get("bbox"))
        confidence = float(record.get("confidence") or 0.0)
        timestamp = float(record.get("timestamp_seconds") or 0.0)
        match = _find_matching_row(rows, normalized, y_center)
        if match is None:
            rows.append(
                {
                    "text": text,
                    "normalized_text": normalized,
                    "first_seen_t": round(timestamp, 3),
                    "last_seen_t": round(timestamp, 3),
                    "mean_confidence": round(confidence, 6),
                    "frame_count": 1,
                    "mean_y": round(y_center, 3),
                    "_confidence_sum": confidence,
                    "_y_sum": y_center,
                }
            )
            continue
        match["last_seen_t"] = round(max(float(match["last_seen_t"]), timestamp), 3)
        match["frame_count"] = int(match["frame_count"]) + 1
        match["_confidence_sum"] = float(match["_confidence_sum"]) + confidence
        match["_y_sum"] = float(match["_y_sum"]) + y_center
        match["mean_confidence"] = round(float(match["_confidence_sum"]) / int(match["frame_count"]), 6)
        match["mean_y"] = round(float(match["_y_sum"]) / int(match["frame_count"]), 3)
    for row in rows:
        row.pop("_confidence_sum", None)
        row.pop("_y_sum", None)
    return rows


def _find_matching_row(rows: list[dict[str, Any]], normalized: str, y_center: float) -> dict[str, Any] | None:
    for row in rows:
        existing = str(row.get("normalized_text") or "")
        similarity = SequenceMatcher(None, normalized, existing).ratio()
        if normalized == existing and abs(float(row.get("mean_y") or 0.0) - y_center) < 10.0:
            return row
        if similarity > 0.85:
            return row
    return None


def _comparison(item_dir: Path, frame_stride_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rr_rows = _row_reconstruct_texts(item_dir)
    fs_rows = [str(row.get("normalized_text") or normalize_text(str(row.get("text") or ""))) for row in frame_stride_rows]
    shared = _shared_rows(rr_rows, fs_rows)
    rr_only = [row for row in rr_rows if row and not _has_similar(row, fs_rows)]
    fs_only = [row for row in fs_rows if row and not _has_similar(row, rr_rows)]
    return {
        "row_reconstruct_unique_rows": len(rr_rows),
        "frame_stride_unique_rows": len(fs_rows),
        "shared_rows": shared,
        "row_reconstruct_only": rr_only[:10],
        "frame_stride_only": fs_only[:10],
    }


def _row_reconstruct_texts(item_dir: Path) -> list[str]:
    row_ocr = _read_json(item_dir / "row_crop_ocr.json") or {}
    texts = []
    pairs = row_ocr.get("pairs") or []
    if pairs:
        for pair in pairs:
            text = " ".join(
                part.strip()
                for part in [str(pair.get("role_text") or ""), str(pair.get("name_text") or pair.get("row_text") or "")]
                if part.strip()
            )
            normalized = normalize_text(text)
            if normalized:
                texts.append(normalized)
    else:
        for record in row_ocr.get("records") or []:
            normalized = normalize_text(str(record.get("normalized_text") or record.get("text") or ""))
            if normalized:
                texts.append(normalized)
    return _unique_texts(texts)


def _shared_rows(left: list[str], right: list[str]) -> int:
    matched_right: set[int] = set()
    count = 0
    for left_text in left:
        for index, right_text in enumerate(right):
            if index in matched_right:
                continue
            if _similarity(left_text, right_text) > 0.85:
                matched_right.add(index)
                count += 1
                break
    return count


def _has_similar(text: str, candidates: list[str]) -> bool:
    return any(_similarity(text, candidate) > 0.85 for candidate in candidates)


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _unique_texts(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value and not _has_similar(value, unique):
            unique.append(value)
    return unique


def _vertical_scroll_confidence(scene: dict[str, Any]) -> float:
    text_motion = scene.get("text_motion") if isinstance(scene, dict) else {}
    if isinstance(text_motion, dict) and text_motion.get("type") == "vertical_scroll":
        value = text_motion.get("confidence")
        return float(value) if isinstance(value, (int, float)) else 0.0
    return 0.0


def _dy_per_second(scene: dict[str, Any]) -> float:
    text_motion = scene.get("text_motion") if isinstance(scene, dict) else {}
    evidence = text_motion.get("evidence") if isinstance(text_motion, dict) else {}
    value = evidence.get("median_dy_per_second") if isinstance(evidence, dict) else None
    return float(value) if isinstance(value, (int, float)) else 0.0


def _bbox_center_y(bbox: Any) -> float:
    if isinstance(bbox, list) and len(bbox) >= 4:
        try:
            return float(bbox[1]) + float(bbox[3]) / 2.0
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
