"""Output-image quality checks for OCR experiment artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from PIL import Image


QualityStatus = Literal[
    "OK",
    "BROKEN_EMPTY",
    "BROKEN_BLACK",
    "BROKEN_NO_TEXT",
    "BROKEN_BACKGROUND_LEAK",
    "BROKEN_SMEAR",
    "BROKEN_LOW_CONTRAST",
    "SUSPICIOUS_NEEDS_REVIEW",
]


def assess_output(
    png_path: Path,
    ocr_json_path: Path | None = None,
    expected_kind: Literal["row_canvas", "frame", "fused"] = "row_canvas",
) -> dict[str, Any]:
    """Assess a generated OCR PNG without changing pipeline decisions."""

    image_path = Path(png_path)
    metrics: dict[str, Any] = {
        "png_path": str(image_path),
        "ocr_json_path": str(ocr_json_path) if ocr_json_path else None,
        "expected_kind": expected_kind,
    }
    if not image_path.exists():
        metrics.update(_empty_metrics())
        return {
            "status": "BROKEN_EMPTY",
            "reasons": ["png_missing"],
            "metrics": metrics,
            "suggested_fallback": "best_frame",
        }

    gray = _read_grayscale(image_path)
    height, width = gray.shape[:2]
    total_pixels = max(1, int(width * height))
    records_payload = _read_json(ocr_json_path) if ocr_json_path else {}
    text_boxes = _extract_text_boxes(records_payload, image_path=image_path, width=width, height=height)
    text_mask = _text_mask(text_boxes, width=width, height=height)
    edges = cv2.Canny(gray, 50, 150)
    edge_pixels = edges > 0
    edge_count = int(np.count_nonzero(edge_pixels))
    non_text_edge_count = int(np.count_nonzero(edge_pixels & (text_mask == 0)))
    confidences = _extract_confidences(records_payload)
    y_centers = [box[1] + box[3] / 2.0 for box in text_boxes]

    metrics.update(
        {
            "width": width,
            "height": height,
            "black_pixel_ratio": round(float(np.count_nonzero(gray < 8)) / total_pixels, 6),
            "white_pixel_ratio": round(float(np.count_nonzero(gray > 247)) / total_pixels, 6),
            "edge_density": round(float(edge_count) / total_pixels, 6),
            "connected_component_count": _connected_component_count(gray),
            "ocr_record_count": len(_extract_records(records_payload)),
            "mean_ocr_confidence": round(sum(confidences) / len(confidences), 6) if confidences else None,
            "text_bbox_area_ratio": round(float(np.count_nonzero(text_mask)) / total_pixels, 6),
            "non_text_edge_ratio": round(float(non_text_edge_count) / max(1, edge_count), 6),
            "non_text_edge_pixel_ratio": round(float(non_text_edge_count) / total_pixels, 6),
            "row_uniformity_score": _row_uniformity_score(y_centers),
            "aspect_ratio": round(float(width) / max(1, height), 6),
            "grayscale_std": round(float(np.std(gray)), 6),
        }
    )

    status, reasons, fallback = _decide(metrics)
    return {
        "status": status,
        "reasons": reasons,
        "metrics": metrics,
        "suggested_fallback": fallback,
    }


def _decide(metrics: dict[str, Any]) -> tuple[QualityStatus, list[str], str | None]:
    black = float(metrics["black_pixel_ratio"])
    white = float(metrics["white_pixel_ratio"])
    edge_density = float(metrics["edge_density"])
    component_count = int(metrics["connected_component_count"])
    record_count = int(metrics["ocr_record_count"])
    text_area = float(metrics["text_bbox_area_ratio"])
    non_text_edges = float(metrics["non_text_edge_ratio"])
    non_text_edge_pixels = float(metrics["non_text_edge_pixel_ratio"])
    gray_std = float(metrics["grayscale_std"])
    mean_conf = metrics.get("mean_ocr_confidence")

    if black > 0.95:
        return "BROKEN_BLACK", [f"black_pixel_ratio>{black:.3f}"], "best_frame"
    if white > 0.95 or (record_count == 0 and edge_density < 0.01):
        return "BROKEN_EMPTY", ["white_or_low_edge_empty"], "best_frame"
    if record_count == 0:
        return "BROKEN_NO_TEXT", ["ocr_record_count==0"], "frame_stride"
    if edge_density > 0.15 and text_area < 0.10:
        return "BROKEN_BACKGROUND_LEAK", ["high_edge_density_low_text_area"], "frame_stride"
    if non_text_edges > 0.65 and non_text_edge_pixels > 0.06 and text_area < 0.30:
        return "BROKEN_BACKGROUND_LEAK", ["edges_outside_text_boxes"], "frame_stride"
    if component_count < 5 and record_count < 3 and edge_density > 0.05:
        return "BROKEN_SMEAR", ["low_components_with_edges"], "best_frame"
    if gray_std < 15:
        return "BROKEN_LOW_CONTRAST", ["grayscale_std<15"], "best_frame"
    if mean_conf is not None and float(mean_conf) < 0.4:
        return "SUSPICIOUS_NEEDS_REVIEW", ["mean_ocr_confidence<0.4"], "frame_stride"
    return "OK", [], None


def _read_grayscale(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is not None:
        return image
    with Image.open(path) as pil_image:
        return np.asarray(pil_image.convert("L"))


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not Path(path).exists():
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _empty_metrics() -> dict[str, Any]:
    return {
        "width": 0,
        "height": 0,
        "black_pixel_ratio": 0.0,
        "white_pixel_ratio": 0.0,
        "edge_density": 0.0,
        "connected_component_count": 0,
        "ocr_record_count": 0,
        "mean_ocr_confidence": None,
        "text_bbox_area_ratio": 0.0,
        "non_text_edge_ratio": 0.0,
        "non_text_edge_pixel_ratio": 0.0,
        "row_uniformity_score": None,
        "aspect_ratio": None,
        "grayscale_std": 0.0,
    }


def _extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("records")
    if isinstance(records, list):
        return [record for record in records if isinstance(record, dict)]
    records = payload.get("ocr_records")
    if isinstance(records, list):
        return [record for record in records if isinstance(record, dict)]
    return []


def _extract_confidences(payload: dict[str, Any]) -> list[float]:
    confidences = []
    for record in _extract_records(payload):
        value = record.get("confidence")
        if isinstance(value, (int, float)):
            confidences.append(float(value))
    return confidences


def _extract_text_boxes(
    payload: dict[str, Any],
    *,
    image_path: Path,
    width: int,
    height: int,
) -> list[tuple[float, float, float, float]]:
    records = _extract_records(payload)
    row_offsets = _row_offsets_for_crop_records(payload, image_path)
    boxes: list[tuple[float, float, float, float]] = []
    for record in records:
        bbox = record.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) >= 4):
            continue
        try:
            x, y, box_width, box_height = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        except (TypeError, ValueError):
            continue
        row_index = record.get("row_index")
        if row_index is not None and row_index in row_offsets:
            y += row_offsets[row_index]
        if box_width <= 0 or box_height <= 0:
            continue
        x = max(0.0, min(float(width), x))
        y = max(0.0, min(float(height), y))
        x2 = max(0.0, min(float(width), x + box_width))
        y2 = max(0.0, min(float(height), y + box_height))
        if x2 > x and y2 > y:
            boxes.append((x, y, x2 - x, y2 - y))
    return boxes


def _row_offsets_for_crop_records(payload: dict[str, Any], image_path: Path) -> dict[Any, float]:
    if not _extract_records(payload):
        return {}
    row_reconstruct_path = image_path.parents[1] / "row_reconstruct.json" if len(image_path.parents) >= 2 else None
    if row_reconstruct_path is None or not row_reconstruct_path.exists():
        return {}
    row_payload = _read_json(row_reconstruct_path)
    offsets: dict[Any, float] = {}
    for row in row_payload.get("rows") or []:
        if not isinstance(row, dict) or "index" not in row or "y0" not in row:
            continue
        offsets[row.get("index")] = float(row.get("y0") or 0.0)
    return offsets


def _text_mask(boxes: list[tuple[float, float, float, float]], *, width: int, height: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    for x, y, box_width, box_height in boxes:
        x0 = int(max(0, min(width, round(x))))
        y0 = int(max(0, min(height, round(y))))
        x1 = int(max(0, min(width, round(x + box_width))))
        y1 = int(max(0, min(height, round(y + box_height))))
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = 1
    return mask


def _connected_component_count(gray: np.ndarray) -> int:
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    useful = 0
    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])
        if area >= 5:
            useful += 1
    return useful


def _row_uniformity_score(y_centers: list[float]) -> float | None:
    if len(y_centers) < 3:
        return None
    ordered = sorted(y_centers)
    spacings = [b - a for a, b in zip(ordered, ordered[1:]) if b > a]
    if len(spacings) < 2:
        return None
    mean_spacing = float(np.mean(spacings))
    if mean_spacing <= 0:
        return None
    return round(float(np.std(spacings) / mean_spacing), 6)
