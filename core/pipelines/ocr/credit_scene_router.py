"""Lightweight scene router for credit and video-text OCR experiments.

The router does not perform OCR. It samples frames, estimates motion/layout/
difficulty features, and returns an explainable pipeline recommendation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
from pathlib import Path
from statistics import median, pstdev
from typing import Any, Iterable

from core.pipelines.ocr.credit_pipeline_selector import select_credit_pipeline


@dataclass(frozen=True)
class FeatureDecision:
    type: str
    confidence: float
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DifficultyDecision:
    labels: tuple[str, ...]
    score: float
    confidence: float
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["labels"] = list(self.labels)
        return payload


@dataclass(frozen=True)
class CreditSceneProfile:
    segment_id: str
    time_range: tuple[float, float] | None
    background: FeatureDecision
    text_motion: FeatureDecision
    layout: FeatureDecision
    difficulty: DifficultyDecision
    recommended_pipeline: dict[str, Any]
    raw_features: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "time_range": list(self.time_range) if self.time_range else None,
            "background": self.background.to_dict(),
            "text_motion": self.text_motion.to_dict(),
            "layout": self.layout.to_dict(),
            "difficulty": self.difficulty.to_dict(),
            "recommended_pipeline": self.recommended_pipeline,
            "raw_features": self.raw_features,
        }


def analyze_credit_scene(
    frames: Iterable[str | Path],
    *,
    segment_id: str = "segment",
    time_range: tuple[float, float] | None = None,
    max_frames: int = 48,
) -> CreditSceneProfile:
    """Analyze sampled frames and recommend a credit OCR pipeline."""
    frame_paths = [Path(frame) for frame in frames if Path(frame).exists()]
    if max_frames > 0 and len(frame_paths) > max_frames:
        frame_paths = _evenly_sample(frame_paths, max_frames)
    if not frame_paths:
        unknown = FeatureDecision("unknown", 0.0, {"error": "no_frames"})
        difficulty = DifficultyDecision(("unknown",), 1.0, 0.0, {"error": "no_frames"})
        pipeline = select_credit_pipeline({"background": unknown.to_dict(), "text_motion": unknown.to_dict(), "layout": unknown.to_dict(), "difficulty": difficulty.to_dict()})
        return CreditSceneProfile(segment_id, time_range, unknown, unknown, unknown, difficulty, pipeline.to_dict(), {"frame_count": 0})

    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        unknown = FeatureDecision("unknown", 0.0, {"error": f"cv_unavailable:{exc}"})
        difficulty = DifficultyDecision(("unknown",), 1.0, 0.0, {"error": f"cv_unavailable:{exc}"})
        pipeline = select_credit_pipeline({"background": unknown.to_dict(), "text_motion": unknown.to_dict(), "layout": unknown.to_dict(), "difficulty": difficulty.to_dict()})
        return CreditSceneProfile(segment_id, time_range, unknown, unknown, unknown, difficulty, pipeline.to_dict(), {"frame_count": len(frame_paths)})

    images = [_cv2_imread(path, cv2, np) for path in frame_paths]
    images = [image for image in images if image is not None]
    if not images:
        unknown = FeatureDecision("unknown", 0.0, {"error": "frames_not_readable"})
        difficulty = DifficultyDecision(("unknown",), 1.0, 0.0, {"error": "frames_not_readable"})
        pipeline = select_credit_pipeline({"background": unknown.to_dict(), "text_motion": unknown.to_dict(), "layout": unknown.to_dict(), "difficulty": difficulty.to_dict()})
        return CreditSceneProfile(segment_id, time_range, unknown, unknown, unknown, difficulty, pipeline.to_dict(), {"frame_count": len(frame_paths)})

    frames_cv = _resize_to_first(images, cv2)
    grays = [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in frames_cv]
    masks = [_text_mask(gray, cv2, np) for gray in grays]

    motion_features = _motion_features(grays, masks, cv2, np)
    layout_features = _layout_features(masks, grays[0].shape)
    difficulty_features = _difficulty_features(grays, masks, cv2, np)
    background = _classify_background(grays, masks, motion_features)
    text_motion = _classify_text_motion(motion_features, layout_features)
    layout = _classify_layout(layout_features)
    difficulty = _classify_difficulty(difficulty_features)

    profile_for_selector = {
        "background": background.to_dict(),
        "text_motion": text_motion.to_dict(),
        "layout": layout.to_dict(),
        "difficulty": difficulty.to_dict(),
    }
    pipeline = select_credit_pipeline(profile_for_selector)
    raw_features = {
        "frame_count": len(frames_cv),
        "motion": motion_features,
        "layout": layout_features,
        "difficulty": difficulty_features,
    }
    return CreditSceneProfile(
        segment_id=segment_id,
        time_range=time_range,
        background=background,
        text_motion=text_motion,
        layout=layout,
        difficulty=difficulty,
        recommended_pipeline=pipeline.to_dict(),
        raw_features=raw_features,
    )


def refine_credit_scene_with_ocr(profile: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    """Refine a visual-only router profile using OCR/temporal bbox records."""
    refined = copy.deepcopy(profile)
    motion = _ocr_motion_features(records)
    raw = refined.setdefault("raw_features", {})
    raw["ocr_text_motion"] = motion
    if motion.get("status") != "ok":
        return refined

    velocity_y = abs(float(motion.get("median_dy_per_second") or 0.0))
    velocity_x = abs(float(motion.get("median_dx_per_second") or 0.0))
    consistency = float(motion.get("direction_consistency") or 0.0)
    if velocity_y >= 5.0 and velocity_y >= velocity_x * 1.25 and consistency >= 0.58:
        direction = "up" if float(motion.get("median_dy_per_second") or 0.0) < 0 else "down"
        refined["text_motion"] = {
            "type": "vertical_scroll",
            "confidence": round(min(0.96, 0.56 + consistency * 0.32 + min(velocity_y / 80.0, 0.08)), 4),
            "evidence": {"direction": direction, **motion},
        }
    elif velocity_x >= 5.0 and velocity_x >= velocity_y * 1.25 and consistency >= 0.58:
        direction = "left" if float(motion.get("median_dx_per_second") or 0.0) < 0 else "right"
        refined["text_motion"] = {
            "type": "horizontal_crawl",
            "confidence": round(min(0.96, 0.56 + consistency * 0.32 + min(velocity_x / 80.0, 0.08)), 4),
            "evidence": {"direction": direction, **motion},
        }
    elif velocity_x < 2.0 and velocity_y < 2.0 and int(motion.get("track_count") or 0) >= 2:
        refined["text_motion"] = {
            "type": "static_card",
            "confidence": 0.82,
            "evidence": motion,
        }

    refined["recommended_pipeline"] = select_credit_pipeline(refined).to_dict()
    return refined


def _ocr_motion_features(records: list[dict[str, Any]]) -> dict[str, Any]:
    tracks: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        bbox = record.get("bbox")
        timestamp = record.get("timestamp_seconds")
        group_id = str(record.get("line_group_id") or "")
        if not group_id or not bbox or len(bbox) < 4 or timestamp is None:
            continue
        try:
            float(timestamp)
            float(bbox[0])
            float(bbox[1])
            float(bbox[2])
            float(bbox[3])
        except (TypeError, ValueError):
            continue
        tracks.setdefault(f"{record.get('engine') or 'unknown'}:{group_id}", []).append(record)

    velocities_x = []
    velocities_y = []
    for values in tracks.values():
        points = []
        for record in values:
            bbox = record["bbox"]
            timestamp = float(record["timestamp_seconds"])
            center_x = float(bbox[0]) + float(bbox[2]) / 2.0
            center_y = float(bbox[1]) + float(bbox[3]) / 2.0
            points.append((timestamp, center_x, center_y))
        points.sort()
        if len(points) < 3:
            continue
        dt = points[-1][0] - points[0][0]
        if abs(dt) < 1e-6:
            continue
        velocities_x.append((points[-1][1] - points[0][1]) / dt)
        velocities_y.append((points[-1][2] - points[0][2]) / dt)

    if not velocities_y:
        return {"status": "insufficient_tracks", "track_count": 0}
    med_y = median(velocities_y)
    med_x = median(velocities_x) if velocities_x else 0.0
    signs = [1 if value > 0 else -1 if value < 0 else 0 for value in velocities_y if abs(value) >= 1.0]
    if signs:
        positive = sum(1 for sign in signs if sign > 0)
        negative = sum(1 for sign in signs if sign < 0)
        direction_consistency = max(positive, negative) / len(signs)
    else:
        direction_consistency = 0.0
    return {
        "status": "ok",
        "track_count": len(velocities_y),
        "median_dx_per_second": round(float(med_x), 4),
        "median_dy_per_second": round(float(med_y), 4),
        "abs_median_dx_per_second": round(abs(float(med_x)), 4),
        "abs_median_dy_per_second": round(abs(float(med_y)), 4),
        "direction_consistency": round(float(direction_consistency), 4),
    }


def _evenly_sample(paths: list[Path], max_frames: int) -> list[Path]:
    if len(paths) <= max_frames:
        return paths
    if max_frames <= 1:
        return [paths[len(paths) // 2]]
    step = (len(paths) - 1) / (max_frames - 1)
    return [paths[round(index * step)] for index in range(max_frames)]


def _resize_to_first(images: list[Any], cv2: Any) -> list[Any]:
    height, width = images[0].shape[:2]
    resized = []
    for image in images:
        if image.shape[:2] == (height, width):
            resized.append(image)
        else:
            resized.append(cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA))
    return resized


def _cv2_imread(path: Path, cv2: Any, np: Any) -> Any:
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size > 0:
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if image is not None:
                return image
    except Exception:
        pass
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def _text_mask(gray: Any, cv2: Any, np: Any) -> Any:
    blur = cv2.GaussianBlur(gray, (0, 0), 3)
    local = cv2.absdiff(gray, blur)
    threshold = max(7.0, float(local.mean()) + float(local.std()) * 1.2)
    bright = gray > max(58.0, float(gray.mean()) + float(gray.std()) * 0.35)
    mask = ((local > threshold) & bright).astype(np.uint8) * 255
    edges = cv2.Canny(gray, 70, 180)
    mask = cv2.bitwise_or(mask, cv2.bitwise_and(cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1), bright.astype(np.uint8) * 255))
    return cv2.dilate(_filter_text_components(mask, cv2, np), np.ones((7, 7), np.uint8), iterations=1)


def _filter_text_components(mask: Any, cv2: Any, np: Any) -> Any:
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    if count <= 1:
        return mask
    height, width = mask.shape[:2]
    filtered = np.zeros_like(mask)
    effective_height = min(height, max(120, int(width * 1.2)))
    max_area = max(80, int(width * effective_height * 0.035))
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        if area < 3 or area > max_area:
            continue
        if w > width * 0.82 or h > height * 0.35:
            continue
        filtered[labels == label] = 255
    return filtered


def _motion_features(grays: list[Any], masks: list[Any], cv2: Any, np: Any) -> dict[str, Any]:
    text_dx: list[float] = []
    text_dy: list[float] = []
    bg_diff: list[float] = []
    text_pixel_ratios: list[float] = []

    for mask in masks:
        text_pixel_ratios.append(float(mask.mean()) / 255.0)

    lk_params = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 25, 0.01))
    feature_params = dict(maxCorners=80, qualityLevel=0.08, minDistance=6, blockSize=5)

    for prev, cur, prev_mask, cur_mask in zip(grays, grays[1:], masks, masks[1:]):
        dilated_text = cv2.dilate(cv2.bitwise_or(prev_mask, cur_mask), np.ones((19, 19), np.uint8), iterations=1)
        bg_region = cv2.bitwise_not(dilated_text)
        diff = cv2.absdiff(prev, cur)
        if int(bg_region.sum()) > 0:
            bg_diff.append(float(diff[bg_region > 0].mean()))
        pts = cv2.goodFeaturesToTrack(prev, mask=prev_mask, **feature_params)
        if pts is None or len(pts) < 4:
            continue
        nxt, status, _err = cv2.calcOpticalFlowPyrLK(prev, cur, pts, None, **lk_params)
        if nxt is None or status is None:
            continue
        keep = status.ravel().astype(bool)
        if int(keep.sum()) < 4:
            continue
        good_prev = pts[keep]
        good_nxt = nxt[keep]
        dx = good_nxt[:, 0, 0] - good_prev[:, 0, 0]
        dy = good_nxt[:, 0, 1] - good_prev[:, 0, 1]
        text_dx.append(float(np.median(dx)))
        text_dy.append(float(np.median(dy)))

    return {
        "text_dx_median": _round_or_none(_median_or_none(text_dx)),
        "text_dy_median": _round_or_none(_median_or_none(text_dy)),
        "text_dx_abs_median": _round_or_none(_median_or_none([abs(value) for value in text_dx])),
        "text_dy_abs_median": _round_or_none(_median_or_none([abs(value) for value in text_dy])),
        "text_dy_consistency": _motion_consistency(text_dy),
        "text_dx_consistency": _motion_consistency(text_dx),
        "text_motion_samples": len(text_dy),
        "background_diff_mean": _round_or_none(sum(bg_diff) / len(bg_diff) if bg_diff else None),
        "text_pixel_ratio_median": _round_or_none(_median_or_none(text_pixel_ratios)),
    }


def _layout_features(masks: list[Any], shape: tuple[int, int]) -> dict[str, Any]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"status": "unavailable"}
    height, width = shape
    union = np.zeros((height, width), dtype=np.uint8)
    for mask in masks:
        union = cv2.bitwise_or(union, mask)
    ys, xs = np.where(union > 0)
    if len(xs) < 20:
        return {"status": "no_text_region", "column_count": 0}

    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    region_width = max(1, x1 - x0 + 1)
    region_height = max(1, y1 - y0 + 1)
    y_center_ratio = ((y0 + y1) / 2.0) / max(1, height)
    x_center_ratio = ((x0 + x1) / 2.0) / max(1, width)
    coverage_y = region_height / max(1, height)
    coverage_x = region_width / max(1, width)
    projection = (union > 0).sum(axis=0).astype(float)
    column_count, valley_score = _projection_columns(projection, height)
    return {
        "status": "ok",
        "bbox": [x0, y0, region_width, region_height],
        "x_center_ratio": round(x_center_ratio, 4),
        "y_center_ratio": round(y_center_ratio, 4),
        "coverage_x": round(coverage_x, 4),
        "coverage_y": round(coverage_y, 4),
        "column_count": column_count,
        "column_valley_score": round(valley_score, 4),
        "text_pixel_count": int(len(xs)),
    }


def _projection_columns(projection: Any, height: int) -> tuple[int, float]:
    import numpy as np

    if projection.size == 0 or float(projection.max()) <= 0.0:
        return 0, 0.0
    smooth_width = max(7, int(projection.size * 0.025))
    kernel = np.ones(smooth_width) / smooth_width
    smooth = np.convolve(projection, kernel, mode="same")
    threshold = max(2.0, float(smooth.max()) * 0.16, height * 0.03)
    active = smooth > threshold
    runs = []
    start = None
    for index, is_active in enumerate(active):
        if is_active and start is None:
            start = index
        elif not is_active and start is not None:
            if index - start >= max(8, projection.size * 0.025):
                runs.append((start, index))
            start = None
    if start is not None and len(active) - start >= max(8, projection.size * 0.025):
        runs.append((start, len(active)))
    if len(runs) <= 1:
        return max(1, len(runs)), 0.0
    gaps = []
    for left, right in zip(runs, runs[1:]):
        gap = max(0, right[0] - left[1])
        gaps.append(gap / max(1, projection.size))
    return min(len(runs), 4), max(gaps) if gaps else 0.0


def _difficulty_features(grays: list[Any], masks: list[Any], cv2: Any, np: Any) -> dict[str, Any]:
    blur_scores = []
    contrast_scores = []
    clutter_scores = []
    dark_ratios = []
    for gray, mask in zip(grays, masks):
        blur_scores.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        dark_ratios.append(float((gray < 28).mean()))
        text_pixels = gray[mask > 0]
        bg_mask = cv2.dilate(mask, np.ones((17, 17), np.uint8), iterations=1)
        bg_pixels = gray[(bg_mask > 0) & (mask == 0)]
        if len(text_pixels) and len(bg_pixels):
            contrast_scores.append(abs(float(text_pixels.mean()) - float(bg_pixels.mean())) / 255.0)
            edges = cv2.Canny(gray, 60, 160)
            clutter_scores.append(float(edges[(bg_mask > 0) & (mask == 0)].mean()) / 255.0 if len(bg_pixels) else 0.0)
    blur = _median_or_none(blur_scores) or 0.0
    contrast = _median_or_none(contrast_scores)
    clutter = _median_or_none(clutter_scores)
    return {
        "blur_laplacian_median": round(float(blur), 4),
        "contrast_median": _round_or_none(contrast),
        "background_clutter_median": _round_or_none(clutter),
        "dark_pixel_ratio_median": _round_or_none(_median_or_none(dark_ratios)),
    }


def _classify_background(grays: list[Any], masks: list[Any], motion: dict[str, Any]) -> FeatureDecision:
    dark_ratio = float(_median_or_none([float((gray < 28).mean()) for gray in grays]) or 0.0)
    bg_diff = float(motion.get("background_diff_mean") or 0.0)
    text_ratio = float(motion.get("text_pixel_ratio_median") or 0.0)
    if dark_ratio > 0.72 and bg_diff < 3.5:
        kind = "flat_static"
        confidence = 0.88
    elif bg_diff < 2.2:
        kind = "image_static"
        confidence = 0.78
    elif bg_diff > 12.0:
        kind = "moving_scene"
        confidence = 0.82
    elif bg_diff > 4.5:
        kind = "camera_motion"
        confidence = 0.62
    else:
        kind = "unknown"
        confidence = 0.35
    return FeatureDecision(kind, confidence, {"background_diff_mean": round(bg_diff, 4), "dark_pixel_ratio": round(dark_ratio, 4), "text_pixel_ratio": round(text_ratio, 4)})


def _classify_text_motion(motion: dict[str, Any], layout: dict[str, Any]) -> FeatureDecision:
    dx = float(motion.get("text_dx_abs_median") or 0.0)
    dy = float(motion.get("text_dy_abs_median") or 0.0)
    signed_dx = float(motion.get("text_dx_median") or 0.0)
    signed_dy = float(motion.get("text_dy_median") or 0.0)
    samples = int(motion.get("text_motion_samples") or 0)
    dy_consistency = float(motion.get("text_dy_consistency") or 0.0)
    dx_consistency = float(motion.get("text_dx_consistency") or 0.0)
    if samples < 2:
        return FeatureDecision("unknown", 0.25, {"reason": "insufficient_text_motion_samples", **motion})
    if dy >= 0.55 and dy >= dx * 1.35 and dy_consistency >= 0.55:
        confidence = min(0.95, 0.55 + dy_consistency * 0.35 + min(dy / 8.0, 0.15))
        return FeatureDecision("vertical_scroll", round(confidence, 4), {"direction": "up" if signed_dy < 0 else "down", **motion})
    if dx >= 0.55 and dx >= dy * 1.35 and dx_consistency >= 0.55:
        confidence = min(0.95, 0.55 + dx_consistency * 0.35 + min(dx / 8.0, 0.15))
        return FeatureDecision("horizontal_crawl", round(confidence, 4), {"direction": "left" if signed_dx < 0 else "right", **motion})
    if max(dx, dy) < 0.35 and layout.get("status") == "ok":
        return FeatureDecision("static_card", 0.78, motion)
    return FeatureDecision("mixed", 0.52, motion)


def _classify_layout(layout: dict[str, Any]) -> FeatureDecision:
    if layout.get("status") != "ok":
        return FeatureDecision("unknown", 0.25, layout)
    y_center = float(layout.get("y_center_ratio") or 0.0)
    coverage_y = float(layout.get("coverage_y") or 0.0)
    coverage_x = float(layout.get("coverage_x") or 0.0)
    column_count = int(layout.get("column_count") or 0)
    if y_center > 0.70 and coverage_y < 0.38:
        return FeatureDecision("lower_third", 0.88, layout)
    valley_score = float(layout.get("column_valley_score") or 0.0)
    if column_count >= 2 and valley_score >= 0.055:
        return FeatureDecision("multi_column", min(0.9, 0.72 + float(layout.get("column_valley_score") or 0.0)), layout)
    if coverage_x < 0.72:
        return FeatureDecision("center_single_column", 0.78, layout)
    return FeatureDecision("unknown", 0.45, layout)


def _classify_difficulty(features: dict[str, Any]) -> DifficultyDecision:
    labels = []
    contrast = features.get("contrast_median")
    blur = float(features.get("blur_laplacian_median") or 0.0)
    clutter = features.get("background_clutter_median")
    low_contrast_score = 1.0 - min(1.0, float(contrast if contrast is not None else 0.35) / 0.42)
    blur_score = 1.0 if blur < 55 else 0.65 if blur < 120 else 0.15
    clutter_score = min(1.0, float(clutter if clutter is not None else 0.0) / 0.18)
    if low_contrast_score > 0.48:
        labels.append("low_contrast")
    if blur_score > 0.55:
        labels.append("blur_or_lowres")
    if clutter_score > 0.50:
        labels.append("background_clutter")
    score = (0.42 * low_contrast_score) + (0.30 * blur_score) + (0.28 * clutter_score)
    if not labels and score < 0.24:
        labels.append("easy")
    difficulty = "hard" if score >= 0.66 else "medium" if score >= 0.33 else "easy"
    return DifficultyDecision(tuple(dict.fromkeys(labels)), round(score, 4), 0.74, {**features, "difficulty": difficulty})


def _motion_consistency(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    med = median(values)
    spread = pstdev(values)
    return round(max(0.0, 1.0 - min(1.0, spread / (abs(med) + 1.0))), 4)


def _median_or_none(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def _round_or_none(value: float | None) -> float | None:
    return round(float(value), 4) if value is not None else None
