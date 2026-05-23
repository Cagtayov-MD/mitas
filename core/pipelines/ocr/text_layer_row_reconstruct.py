"""Row-first reconstruction for vertically scrolling credit text.

This is the next step after the scene router recommends ``row_reconstruct``:
build a center-strip composite, infer the role/name split, and export physical
row crops for later OCR.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from statistics import median
from typing import Any, Iterable


@dataclass(frozen=True)
class RowReconstructResult:
    output_dir: Path
    summary_path: Path
    report_path: Path
    composite_path: Path
    sharpened_path: Path
    auto_split_path: Path


def run_text_layer_row_reconstruct(
    item_dir: str | Path | None = None,
    *,
    frame_paths: Iterable[str | Path] | None = None,
    output_dir: str | Path | None = None,
    max_frames: int | None = None,
    scale_for_rows: int = 2,
) -> RowReconstructResult:
    """Build a row-first composite from OCR experiment frames."""
    item_path = Path(item_dir) if item_dir else None
    output = Path(output_dir) if output_dir else (item_path / "text_layer_row_reconstruct" if item_path else Path("text_layer_row_reconstruct"))
    output.mkdir(parents=True, exist_ok=True)

    frames = _resolve_frame_paths(item_path, frame_paths)
    if max_frames and len(frames) > max_frames:
        frames = _evenly_sample(frames, max_frames)
    if not frames:
        raise ValueError("No frames found for row reconstruction")

    try:
        import cv2
        import numpy as np
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(f"OpenCV/Numpy unavailable: {exc}") from exc

    images = _read_frames(frames, cv2)
    if not images:
        raise ValueError("Frames could not be read")
    original_image_count = len(images)
    images, frame_filter = _filter_low_dark_frames(images, cv2, np)

    selected_candidate, candidates = _select_best_row_candidate(images, cv2, np)
    composite = selected_candidate.get("composite")
    motion = selected_candidate.get("motion") or {}
    if composite is None:
        raise RuntimeError("Composite could not be built")
    quality = selected_candidate.get("quality") or quality_score(composite, cv2)

    split = selected_candidate.get("auto_split") or detect_auto_split(composite)
    rows = selected_candidate.get("rows") or detect_rows(composite)

    tail_trim, composite, rows = _trim_composite_by_row_gap(composite, rows)
    if tail_trim.get("applied"):
        quality = quality_score(composite, cv2)
    quality_warning = bool(quality.get("score", 0.0) < 0.45)

    composite_path = output / "row_composite.png"
    sharpened_path = output / "row_composite_sharpened.png"
    _cv2_imwrite(composite_path, composite, cv2)
    sharpened = _sharpen(composite, cv2)
    _cv2_imwrite(sharpened_path, sharpened, cv2)
    _write_candidate_previews(output / "row_candidates", candidates, cv2)
    rows_dir = output / "rows"
    role_dir = output / "role_crops"
    name_dir = output / "name_crops"
    rows_dir.mkdir(parents=True, exist_ok=True)
    role_dir.mkdir(parents=True, exist_ok=True)
    name_dir.mkdir(parents=True, exist_ok=True)
    exported_rows = _export_rows(composite, rows, split.get("split_x"), rows_dir, role_dir, name_dir, cv2, scale=scale_for_rows)

    auto_split_path = output / "auto_split.json"
    auto_split_path.write_text(json.dumps(split, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "strategy": "text_layer_row_reconstruct_v1",
        "item_dir": str(item_path) if item_path else None,
        "frame_count": len(frames),
        "input_frame_count": len(frames),
        "read_frame_count": original_image_count,
        "processed_frame_count": len(images),
        "frame_filter": frame_filter,
        "composite_path": str(composite_path),
        "sharpened_path": str(sharpened_path),
        "composite_size": [int(composite.shape[1]), int(composite.shape[0])],
        "quality": quality,
        "quality_warning": quality_warning,
        "candidate_selector": _candidate_summary(selected_candidate, candidates),
        "motion": motion,
        "auto_split": split,
        "row_count": len(rows),
        "rows": exported_rows,
        "tail_trim": tail_trim,
    }
    summary_path = output / "row_reconstruct_summary.json"
    report_path = output / "row_reconstruct_report.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(summary), encoding="utf-8")
    return RowReconstructResult(
        output_dir=output,
        summary_path=summary_path,
        report_path=report_path,
        composite_path=composite_path,
        sharpened_path=sharpened_path,
        auto_split_path=auto_split_path,
    )


def detect_auto_split(image: Any) -> dict[str, Any]:
    """Infer role/name split from vertical text-pixel projection."""
    import cv2
    import numpy as np

    mask = _composite_text_mask(image, cv2, np)
    height, width = mask.shape[:2]
    projection = (mask > 0).sum(axis=0).astype(float)
    if projection.size == 0 or float(projection.max()) <= 0.0:
        return {"split_x": None, "confidence": 0.0, "status": "no_text_pixels"}

    smooth_width = max(9, int(width * 0.025))
    kernel = np.ones(smooth_width) / smooth_width
    smooth = np.convolve(projection, kernel, mode="same")
    threshold = max(2.0, float(smooth.max()) * 0.12, height * 0.025)
    runs = _active_runs(smooth > threshold, min_width=max(8, int(width * 0.025)))
    if len(runs) < 2:
        return {
            "split_x": None,
            "confidence": 0.0,
            "status": "no_clear_column_gap",
            "projection_runs": [[int(a), int(b)] for a, b in runs],
        }

    candidates = []
    for left, right in zip(runs, runs[1:]):
        gap_start, gap_end = left[1], right[0]
        gap_width = max(0, gap_end - gap_start)
        if gap_width <= 0:
            continue
        split_x = int(round((gap_start + gap_end) / 2.0))
        if not (width * 0.20 <= split_x <= width * 0.82):
            continue
        left_mass = float(smooth[:split_x].sum())
        right_mass = float(smooth[split_x:].sum())
        if min(left_mass, right_mass) <= 0:
            continue
        valley = float(smooth[gap_start:gap_end].mean()) if gap_end > gap_start else float(smooth[split_x])
        peak = max(float(smooth[left[0] : left[1]].max()), float(smooth[right[0] : right[1]].max()), 1.0)
        valley_depth = max(0.0, 1.0 - valley / peak)
        balance = min(left_mass, right_mass) / max(left_mass, right_mass)
        gap_score = min(1.0, gap_width / max(1.0, width * 0.12))
        score = (0.50 * valley_depth) + (0.30 * gap_score) + (0.20 * balance)
        candidates.append((score, split_x, gap_width, valley_depth, balance))

    if not candidates:
        return {
            "split_x": None,
            "confidence": 0.0,
            "status": "no_balanced_gap",
            "projection_runs": [[int(a), int(b)] for a, b in runs],
        }
    score, split_x, gap_width, valley_depth, balance = max(candidates, key=lambda item: item[0])
    if score < 0.42:
        split_x_value: int | None = None
        status = "low_confidence_gap"
    elif score < 0.60:
        split_x_value = int(split_x)
        status = "detected_low_confidence"
    else:
        split_x_value = int(split_x)
        status = "detected"
    return {
        "split_x": split_x_value,
        "confidence": round(float(score), 4),
        "status": status,
        "gap_width": int(gap_width),
        "valley_depth": round(float(valley_depth), 4),
        "balance": round(float(balance), 4),
        "projection_runs": [[int(a), int(b)] for a, b in runs],
    }


def _trim_composite_by_row_gap(
    composite: Any,
    rows: list[dict[str, Any]],
    *,
    min_gap_px: int = 150,
    gap_factor: float = 3.0,
    pad_px: int = 12,
) -> tuple[dict[str, Any], Any, list[dict[str, Any]]]:
    """Crop the bottom tail of a composite when a large vertical gap follows the last text rows.

    Credit rolls often outlast their text — the segment ends in a brief post-credit shot or fade,
    and those non-text frames get aligned into the composite tail. We detect the first oversized
    inter-row gap and drop everything after it.
    """
    if composite is None or getattr(composite, "size", 0) == 0:
        return {"applied": False, "reason": "no_composite"}, composite, rows
    if not rows or len(rows) < 4:
        return {"applied": False, "reason": "too_few_rows"}, composite, rows

    ordered = sorted(rows, key=lambda row: int(row.get("y0", 0)))
    gaps: list[int] = []
    for prev, curr in zip(ordered, ordered[1:]):
        gap = int(curr.get("y0", 0)) - int(prev.get("y1", 0))
        if gap > 0:
            gaps.append(gap)
    if not gaps:
        return {"applied": False, "reason": "no_positive_gaps"}, composite, rows
    median_gap = float(median(gaps))
    threshold = max(float(min_gap_px), median_gap * gap_factor)

    cut_index: int | None = None
    cut_gap: int | None = None
    for index in range(len(ordered) - 1):
        gap = int(ordered[index + 1].get("y0", 0)) - int(ordered[index].get("y1", 0))
        if gap >= threshold:
            cut_index = index
            cut_gap = gap
            break
    if cut_index is None:
        return {
            "applied": False,
            "reason": "no_oversized_gap",
            "median_gap_px": round(median_gap, 2),
            "threshold_px": round(threshold, 2),
        }, composite, rows

    kept_rows = ordered[: cut_index + 1]
    cut_y = min(int(composite.shape[0]), int(kept_rows[-1].get("y1", 0)) + pad_px)
    if cut_y <= 0:
        return {"applied": False, "reason": "cut_y_non_positive"}, composite, rows
    trimmed = composite[:cut_y]
    relabeled: list[dict[str, Any]] = []
    for index, row in enumerate(kept_rows, 1):
        new_row = dict(row)
        new_row["index"] = index
        relabeled.append(new_row)
    info = {
        "applied": True,
        "reason": "oversized_inter_row_gap",
        "median_gap_px": round(median_gap, 2),
        "threshold_px": round(threshold, 2),
        "cut_gap_px": int(cut_gap or 0),
        "cut_y": int(cut_y),
        "kept_rows": len(relabeled),
        "dropped_rows": len(ordered) - len(relabeled),
        "original_height": int(composite.shape[0]),
        "trimmed_height": int(trimmed.shape[0]),
    }

    # Self-correction: only revert when an extreme imbalance (≤2 rows kept, ≥5
    # dropped) signals the trim ate real content, not a tail.  The old 30%-kept
    # threshold was too wide — it falsely reversed legitimate large-tail trims
    # (e.g. JURASSIC: 82 kept / 211 dropped).  Keeping the threshold at ≤2
    # limits reversion to truly degenerate cases like ANJELIK (1 kept / 13 dropped).
    kept_count = len(relabeled)
    dropped_count = len(ordered) - kept_count
    if kept_count <= 2 and dropped_count >= 5:
        reverted_info = {
            "applied": False,
            "reason": "self_corrected_kept_too_few",
            "median_gap_px": round(median_gap, 2),
            "threshold_px": round(threshold, 2),
            "cut_gap_px": int(cut_gap or 0),
            "would_keep_rows": kept_count,
            "would_drop_rows": dropped_count,
            "total_rows": len(ordered),
        }
        return reverted_info, composite, rows

    return info, trimmed, relabeled


def detect_rows(image: Any, *, min_dist: int = 15) -> list[dict[str, Any]]:
    """Detect physical text rows in a reconstructed composite."""
    import cv2
    import numpy as np

    mask = _composite_text_mask(image, cv2, np)
    profile = (mask > 0).sum(axis=1).astype(float)
    if profile.size == 0 or float(profile.max()) <= 0.0:
        return []
    kernel = np.ones(5) / 5
    smooth = np.convolve(profile, kernel, mode="same")
    floor = max(float(smooth.max()) * 0.07, image.shape[1] * 0.018)
    peaks: list[int] = []
    index = 0
    while index < len(smooth):
        lo = max(0, index - min_dist)
        hi = min(len(smooth), index + min_dist + 1)
        if smooth[index] >= smooth[lo:hi].max() and smooth[index] > floor:
            peaks.append(index)
            index += min_dist
        else:
            index += 1

    rows = []
    for row_index, peak in enumerate(peaks, 1):
        prev_mid = (peaks[row_index - 2] + peak) // 2 if row_index > 1 else max(0, peak - min_dist)
        next_mid = (peaks[row_index] + peak) // 2 if row_index < len(peaks) else min(len(smooth), peak + min_dist)
        y0 = max(prev_mid, peak - min_dist - 5, 0)
        y1 = min(next_mid, peak + min_dist + 5, len(smooth))
        if y1 - y0 < 5:
            continue
        rows.append({"index": len(rows) + 1, "y0": int(y0), "y1": int(y1), "peak_y": int(peak), "score": round(float(smooth[peak]), 4)})
    return rows


def _select_best_row_candidate(frames: list[Any], cv2: Any, np: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    builders = [
        ("current_displacement", _center_strip_composite),
        ("static_best_frame", _best_frame_composite),
    ]
    candidates: list[dict[str, Any]] = []
    for name, builder in builders:
        try:
            composite, motion = builder(frames, cv2, np)
        except Exception as exc:  # pragma: no cover - candidate failure must not kill the run
            candidates.append(
                {
                    "name": name,
                    "status": "failed",
                    "error": str(exc),
                    "score": 0.0,
                    "selected": False,
                    "composite": None,
                    "motion": {"status": "failed", "estimator": name, "error": str(exc)},
                    "quality": {"score": 0.0, "sharpness": 0.0, "contrast": 0.0, "text_density": 0.0},
                    "auto_split": {"split_x": None, "confidence": 0.0, "status": "failed"},
                    "rows": [],
                }
            )
            continue
        if composite is None:
            quality = {"score": 0.0, "sharpness": 0.0, "contrast": 0.0, "text_density": 0.0}
            split = {"split_x": None, "confidence": 0.0, "status": "no_composite"}
            rows: list[dict[str, Any]] = []
        else:
            quality = quality_score(composite, cv2)
            split = detect_auto_split(composite)
            rows = detect_rows(composite)
        score, score_parts = _score_row_candidate(name, composite, motion, quality, split, rows)
        candidates.append(
            {
                "name": name,
                "status": "ok" if composite is not None else "no_composite",
                "score": score,
                "score_parts": score_parts,
                "selected": False,
                "composite": composite,
                "motion": motion,
                "quality": quality,
                "auto_split": split,
                "row_count": len(rows),
                "rows": rows,
            }
        )
    if not candidates:
        raise RuntimeError("No row reconstruction candidates were produced")
    current = next((candidate for candidate in candidates if candidate.get("name") == "current_displacement"), candidates[0])
    viable = [candidate for candidate in candidates if candidate.get("composite") is not None]
    if not viable:
        return current, candidates
    best = max(viable, key=lambda candidate: float(candidate.get("score") or 0.0))
    current_score = float(current.get("score") or 0.0)
    best_score = float(best.get("score") or 0.0)
    if best.get("name") != "current_displacement" and best_score < current_score + 0.06:
        selected = current if current.get("composite") is not None else best
    else:
        selected = best
    for candidate in candidates:
        candidate["selected"] = candidate is selected
    return selected, candidates


def _score_row_candidate(
    name: str,
    composite: Any,
    motion: dict[str, Any],
    quality: dict[str, float],
    split: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[float, dict[str, float]]:
    if composite is None:
        return 0.0, {"quality": 0.0, "rows": 0.0, "split": 0.0, "motion": 0.0, "penalty": 1.0, "bias": 0.0}
    q = max(0.0, min(1.0, float(quality.get("score") or 0.0)))
    row_count = len(rows)
    row_score = max(0.0, min(1.0, row_count / 24.0))
    split_conf = max(0.0, min(1.0, float(split.get("confidence") or 0.0)))
    status = str((motion or {}).get("status") or "")
    motion_score = 0.75
    if status == "ok":
        motion_score = 1.0
    elif status in {"static_or_low_scroll", "static_best_frame"}:
        motion_score = 0.72
    elif status in {"no_active_scroll_frames", "failed"}:
        motion_score = 0.35
    penalty = 0.0
    if row_count == 0:
        penalty += 0.45
    elif row_count > 300:
        # Only penalize *very* dense composites (>300 rows is usually a broken stitch
        # with ghosting). A long real credit scroll commonly has 100-250 rows and
        # should NOT be considered worse than a 10-row static best-frame.
        penalty += 0.10
    height, width = composite.shape[:2]
    if height < 80:
        penalty += 0.16
    if height > max(1200, width * 5):
        penalty += 0.08
    bias = 0.03 if name == "current_displacement" else 0.0
    score = (0.46 * q) + (0.24 * row_score) + (0.15 * split_conf) + (0.15 * motion_score) + bias - penalty
    return round(max(0.0, min(1.0, float(score))), 4), {
        "quality": round(q, 4),
        "rows": round(row_score, 4),
        "split": round(split_conf, 4),
        "motion": round(motion_score, 4),
        "penalty": round(penalty, 4),
        "bias": round(bias, 4),
    }


def _candidate_summary(selected: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "selected": selected.get("name"),
        "selection_policy": "highest_score_with_current_bias_and_006_margin",
        "candidates": [
            {
                "name": candidate.get("name"),
                "selected": bool(candidate.get("selected")),
                "status": candidate.get("status"),
                "score": candidate.get("score"),
                "score_parts": candidate.get("score_parts"),
                "quality": candidate.get("quality"),
                "row_count": candidate.get("row_count", len(candidate.get("rows") or [])),
                "auto_split": candidate.get("auto_split"),
                "motion": candidate.get("motion"),
                "preview_path": candidate.get("preview_path"),
                "error": candidate.get("error"),
            }
            for candidate in candidates
        ],
    }


def _write_candidate_previews(directory: Path, candidates: list[dict[str, Any]], cv2: Any) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        composite = candidate.get("composite")
        if composite is None:
            continue
        path = directory / f"{candidate.get('name', 'candidate')}.png"
        _cv2_imwrite(path, composite, cv2)
        candidate["preview_path"] = str(path)


def _resolve_frame_paths(item_dir: Path | None, frame_paths: Iterable[str | Path] | None) -> list[Path]:
    if frame_paths is not None:
        return [Path(path) for path in frame_paths if Path(path).exists()]
    if item_dir is None:
        return []
    frame_ocr = item_dir / "frame_ocr.json"
    if frame_ocr.exists():
        try:
            payload = json.loads(frame_ocr.read_text(encoding="utf-8"))
            frames = [Path(path) for path in payload.get("frames", []) if Path(path).exists()]
            if frames:
                return frames
        except Exception:
            pass
    frames_dir = item_dir / "frames"
    return sorted(frames_dir.glob("*.png")) if frames_dir.exists() else []


def _evenly_sample(paths: list[Path], limit: int) -> list[Path]:
    if len(paths) <= limit:
        return paths
    if limit <= 1:
        return [paths[len(paths) // 2]]
    step = (len(paths) - 1) / (limit - 1)
    return [paths[round(index * step)] for index in range(limit)]


def _read_frames(paths: list[Path], cv2: Any) -> list[Any]:
    import numpy as np

    images = []
    target_size = None
    for path in paths:
        image = _cv2_imread(path, cv2, np)
        if image is None:
            continue
        if target_size is None:
            target_size = (image.shape[1], image.shape[0])
        elif (image.shape[1], image.shape[0]) != target_size:
            image = cv2.resize(image, target_size, interpolation=cv2.INTER_AREA)
        images.append(image)
    return images


def _filter_low_dark_frames(frames: list[Any], cv2: Any, np: Any, *, threshold: float = 0.15) -> tuple[list[Any], dict[str, Any]]:
    if len(frames) < 6:
        return frames, {"status": "skipped", "reason": "too_few_frames", "threshold": threshold, "kept_count": len(frames), "input_count": len(frames)}
    dark_ratios = [_dark_ratio(frame, cv2, np) for frame in frames]
    keep = [index for index, ratio in enumerate(dark_ratios) if ratio >= threshold]
    min_keep = max(4, min(len(frames), int(round(len(frames) * 0.65))))
    if len(keep) < min_keep:
        return frames, {
            "status": "skipped",
            "reason": "too_many_frames_would_drop",
            "threshold": threshold,
            "input_count": len(frames),
            "kept_count": len(frames),
            "candidate_keep_count": len(keep),
            "candidate_drop_count": len(frames) - len(keep),
            "median_dark_ratio": _round_or_none(_median_or_none(dark_ratios)),
        }
    filtered = [frames[index] for index in keep]
    return filtered, {
        "status": "applied",
        "strategy": "dark_ratio_frame_filter",
        "threshold": threshold,
        "input_count": len(frames),
        "kept_count": len(filtered),
        "dropped_count": len(frames) - len(filtered),
        "median_dark_ratio": _round_or_none(_median_or_none(dark_ratios)),
    }


def _dark_ratio(frame: Any, cv2: Any, np: Any) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    return float((gray < 34).sum() / max(1, gray.size))


def _center_strip_composite(frames: list[Any], cv2: Any, np: Any) -> tuple[Any | None, dict[str, Any]]:
    displacements, active = _estimate_displacements(frames, cv2, np)
    return _center_strip_composite_from_motion(frames, displacements, active, cv2, np, estimator="current_displacement")


def _best_frame_composite(frames: list[Any], cv2: Any, np: Any) -> tuple[Any | None, dict[str, Any]]:
    if not frames:
        return None, {"status": "failed", "estimator": "static_best_frame"}
    best_index = _select_best_text_frame(frames, cv2, np)
    return frames[best_index].copy(), {
        "status": "static_best_frame",
        "estimator": "static_best_frame",
        "frame_count": len(frames),
        "best_frame_index": int(best_index),
        "active_frame_count": 1,
        "stopped_frame_count": max(0, len(frames) - 1),
    }


def _center_strip_composite_from_motion(
    frames: list[Any],
    displacements: list[float],
    active: list[bool],
    cv2: Any,
    np: Any,
    *,
    estimator: str,
) -> tuple[Any | None, dict[str, Any]]:
    if not displacements:
        return None, {"status": "failed", "estimator": estimator}
    h, w = frames[0].shape[:2]
    active_displacements = [d for d, is_active in zip(displacements, active) if is_active]
    if not active_displacements:
        best_index = _select_best_text_frame(frames, cv2, np)
        return frames[best_index].copy(), {"status": "no_active_scroll_frames", "estimator": estimator, "best_frame_index": int(best_index)}
    min_d = min(active_displacements)
    max_d = max(active_displacements)
    displacement_range = float(max_d - min_d)
    if displacement_range < 12.0:
        best_index = _select_best_text_frame(frames, cv2, np)
        return frames[best_index].copy(), {
            "status": "static_or_low_scroll",
            "estimator": estimator,
            "frame_count": len(frames),
            "active_frame_count": int(sum(1 for value in active if value)),
            "stopped_frame_count": int(sum(1 for value in active if not value)),
            "best_frame_index": int(best_index),
            "median_dy_per_frame": _round_or_none(_median_or_none([b - a for a, b in zip(displacements, displacements[1:])])),
            "displacement_range_px": round(displacement_range, 4),
        }
    canvas_h = h + int(np.ceil(max_d - min_d)) + 2
    canvas = np.zeros((canvas_h, w, 3), dtype=np.uint8)
    written = np.zeros(canvas_h, dtype=bool)
    offsets = [max_d - d for d in displacements]
    centers = [offset + h / 2.0 for offset in offsets]
    active_indices = [index for index, is_active in enumerate(active) if is_active]
    prev_active: dict[int, int | None] = {}
    next_active: dict[int, int | None] = {}
    for pos, index in enumerate(active_indices):
        prev_active[index] = active_indices[pos - 1] if pos > 0 else None
        next_active[index] = active_indices[pos + 1] if pos + 1 < len(active_indices) else None
    for index, (frame, offset) in enumerate(zip(frames, offsets)):
        if not active[index]:
            continue
        integer_offset = int(np.floor(offset))
        fractional_offset = float(offset - integer_offset)
        matrix = np.float32([[1, 0, 0], [0, 1, fractional_offset]])
        shifted = cv2.warpAffine(frame, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        center = integer_offset + fractional_offset + h / 2.0
        previous_index = prev_active.get(index)
        next_index = next_active.get(index)
        top = (centers[previous_index] + center) / 2.0 if previous_index is not None else float(integer_offset)
        bottom = (centers[next_index] + center) / 2.0 if next_index is not None else float(integer_offset + h)
        y0 = max(int(round(top)), integer_offset, 0)
        y1 = min(int(round(bottom)), integer_offset + h, canvas_h)
        if y1 <= y0:
            continue
        canvas[y0:y1] = shifted[y0 - integer_offset : y1 - integer_offset]
        written[y0:y1] = True
    covered = np.where(written)[0]
    composite = canvas[covered[0] : covered[-1] + 1] if len(covered) else canvas
    return composite, {
        "status": "ok",
        "estimator": estimator,
        "frame_count": len(frames),
        "active_frame_count": int(sum(1 for value in active if value)),
        "stopped_frame_count": int(sum(1 for value in active if not value)),
        "median_dy_per_frame": _round_or_none(_median_or_none([b - a for a, b in zip(displacements, displacements[1:])])),
        "displacement_range_px": round(float(max_d - min_d), 4),
    }


def _estimate_displacements(frames: list[Any], cv2: Any, np: Any) -> tuple[list[float], list[bool]]:
    return _estimate_displacements_cruise(frames, cv2, np)


def _estimate_displacements_cruise(frames: list[Any], cv2: Any, np: Any) -> tuple[list[float], list[bool]]:
    """Estimate scroll displacement with LK plus Opus-style cruise speed fallback."""
    if len(frames) < 2:
        return [0.0] * len(frames), [True] * len(frames)
    prev = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    feature_params = dict(maxCorners=80, qualityLevel=0.10, minDistance=7, blockSize=7)
    lk_params = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    pts = cv2.goodFeaturesToTrack(prev, mask=_frame_text_mask(prev, cv2, np), **feature_params)
    per_frame: list[float | None] = []
    boot_values: list[float] = []
    cruise_speed: float | None = None
    deviant_streak: list[float] = []
    boot_min = 50
    reset_min = 5
    reset_dev = 0.35
    ema_alpha = 0.95
    for frame in frames[1:]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if pts is None or len(pts) < 6:
            pts = cv2.goodFeaturesToTrack(prev, mask=_frame_text_mask(prev, cv2, np), **feature_params)
        if pts is None:
            per_frame.append(None)
            prev = gray
            continue
        nxt, status, _err = cv2.calcOpticalFlowPyrLK(prev, gray, pts, None, **lk_params)
        if nxt is None or status is None:
            per_frame.append(None)
            prev = gray
            continue
        keep = status.ravel().astype(bool)
        if int(keep.sum()) < 6:
            per_frame.append(None)
            pts = cv2.goodFeaturesToTrack(gray, mask=_frame_text_mask(gray, cv2, np), **feature_params)
            prev = gray
            continue
        good_prev = pts[keep]
        good_nxt = nxt[keep]
        dy = good_nxt[:, 0, 1] - good_prev[:, 0, 1]
        dx = good_nxt[:, 0, 0] - good_prev[:, 0, 0]
        measured = _dominant_dy(dy, dx, np)
        if cruise_speed is None:
            boot_values.append(measured)
            if len(boot_values) >= boot_min:
                cruise_speed = float(median(boot_values))
                deviant_streak = []
        else:
            ref = max(0.5, abs(cruise_speed))
            if abs(measured - cruise_speed) / ref > reset_dev:
                deviant_streak.append(measured)
                if len(deviant_streak) >= reset_min:
                    cruise_speed = float(median(deviant_streak))
                    deviant_streak = []
            else:
                deviant_streak = []
                cruise_speed = (ema_alpha * cruise_speed) + ((1.0 - ema_alpha) * measured)
        per_frame.append(measured)
        pts = good_nxt.reshape(-1, 1, 2)
        prev = gray

    if cruise_speed is None:
        valid_boot = [value for value in boot_values if value is not None]
        cruise_speed = float(median(valid_boot)) if valid_boot else 0.0
    measured_values = [value for value in per_frame if value is not None]
    measured_median = float(median(measured_values)) if measured_values else 0.0
    if abs(cruise_speed) < 0.5 and abs(measured_median) >= 0.5:
        cruise_speed = measured_median
    causal_values: list[float] = []
    filled: list[float] = []
    for value in per_frame:
        if value is not None:
            causal_values.append(value)
            filled.append(value)
        elif len(causal_values) >= boot_min:
            filled.append(float(cruise_speed))
        elif causal_values:
            filled.append(float(median(causal_values)))
        else:
            filled.append(0.0)
    if abs(cruise_speed) >= 0.5:
        band = max(6.0, abs(cruise_speed) * 2.0)
        filled = [value if abs(value - cruise_speed) <= band else float(cruise_speed) for value in filled]
    active_transitions = _detect_active(filled, min_stop=8)
    active_values = [value for value, is_active in zip(filled, active_transitions) if is_active]
    if active_values:
        smoothed_active = _median_filter(active_values, 7)
        smoothed_active = _moving_average(smoothed_active, 25)
    else:
        smoothed_active = []
    smoothed: list[float] = []
    active_index = 0
    for is_active in active_transitions:
        if is_active and active_index < len(smoothed_active):
            smoothed.append(smoothed_active[active_index])
            active_index += 1
        else:
            smoothed.append(0.0)
    cumulative = [0.0]
    for value in smoothed:
        cumulative.append(cumulative[-1] + value)
    return cumulative, [True] + active_transitions


def _dominant_dy(dy: Any, dx: Any, np: Any) -> float:
    keep_dx = np.abs(dx) <= 4.0
    dy_use = dy[keep_dx] if int(keep_dx.sum()) >= 4 else dy
    if len(dy_use) < 4:
        return float(np.median(dy))
    hist, edges = np.histogram(dy_use, bins=41, range=(-24.0, 24.0))
    peak = int(np.argmax(hist))
    center = float((edges[peak] + edges[peak + 1]) / 2.0)
    near = np.abs(dy_use - center) <= 2.0
    return float(np.median(dy_use[near])) if int(near.sum()) >= 3 else float(np.median(dy_use))


def _detect_active(values: list[float], *, threshold: float = 0.35, min_stop: int = 8) -> list[bool]:
    active = [True] * len(values)
    index = 0
    while index < len(values):
        if abs(values[index]) < threshold:
            end = index
            while end < len(values) and abs(values[end]) < threshold:
                end += 1
            if end - index >= min_stop:
                for pos in range(index, end):
                    active[pos] = False
            index = end
        else:
            index += 1
    return active


def _median_filter(values: list[float], width: int) -> list[float]:
    if not values:
        return values
    half = width // 2
    return [float(median(values[max(0, index - half) : index + half + 1])) for index in range(len(values))]


def _moving_average(values: list[float], width: int) -> list[float]:
    if len(values) < 2 or width < 2:
        return list(values)
    import numpy as np

    pad = width // 2
    padded = np.pad(np.asarray(values, dtype=float), pad, mode="edge")
    kernel = np.ones(width) / width
    return np.convolve(padded, kernel, mode="valid")[: len(values)].tolist()


def _text_mask_mode() -> str:
    """Env var'dan mode oku. OCR_TEXT_MASK_MODE: current|strict_global|hybrid. Default current."""
    import os

    value = os.environ.get("OCR_TEXT_MASK_MODE", "current").strip().lower()
    if value not in {"current", "strict_global", "hybrid"}:
        return "current"
    return value


def _frame_text_mask_current(gray: Any, cv2: Any, np: Any) -> Any:
    """Mevcut MITAS davranışı — değiştirme."""
    blur = cv2.GaussianBlur(gray, (0, 0), 3)
    local = cv2.absdiff(gray, blur)
    threshold = max(7.0, float(local.mean()) + float(local.std()) * 1.2)
    bright = gray > max(58.0, float(gray.mean()) + float(gray.std()) * 0.35)
    mask = ((local > threshold) & bright).astype(np.uint8) * 255
    edges = cv2.Canny(gray, 70, 180)
    mask = cv2.bitwise_or(mask, cv2.bitwise_and(cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1), bright.astype(np.uint8) * 255))
    return cv2.dilate(_filter_text_components(mask, cv2, np), np.ones((7, 7), np.uint8), iterations=1)


def _frame_text_mask_strict_global(gray: Any, cv2: Any, np: Any) -> Any:
    """Eski tools/scroll_reconstructor.py:_text_mask portu.

    Global sıkı parlaklık eşiği — sadece gerçekten parlak pikseller geçer.
    Hareketli BG dokusunu eler, LK feature tracker'ı text harflerine kilitler.
    """
    threshold = max(45.0, float(gray.mean()) + float(gray.std()))
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return cv2.dilate(mask, np.ones((11, 11), np.uint8))


def _frame_text_mask(gray: Any, cv2: Any, np: Any, *, mode: str | None = None) -> Any:
    """LK feature tracker için text mask.

    mode:
      None/"current" → mevcut lokal kontrast + Canny + filter_text_components (default).
      "strict_global" → eski tools yaklaşımı (max(45, mean+std) BINARY + dilate(11×11)).
                         Hareketli BG'li scroll jeneriklerinde LK tracker'ı harflere kilitler.
      "hybrid" → current AND strict_global (her ikisi de işaret eden pikseller).
    """
    if mode is None:
        mode = _text_mask_mode()
    if mode == "strict_global":
        return _frame_text_mask_strict_global(gray, cv2, np)
    if mode == "hybrid":
        current = _frame_text_mask_current(gray, cv2, np)
        strict = _frame_text_mask_strict_global(gray, cv2, np)
        return cv2.bitwise_and(current, strict)
    # "current" (default)
    return _frame_text_mask_current(gray, cv2, np)


def _composite_text_mask(image: Any, cv2: Any, np: Any) -> Any:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV) if len(image.shape) == 3 else None
    blur = cv2.GaussianBlur(gray, (0, 0), 3)
    local = cv2.absdiff(gray, blur)
    local_threshold = max(6.0, float(local.mean()) + float(local.std()) * 0.95)
    bright_gate = gray > max(55.0, float(gray.mean()) + float(gray.std()) * 0.25)
    bright = ((local > local_threshold) & bright_gate).astype(np.uint8) * 255
    if hsv is not None:
        saturated = ((hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 75) & (local > max(5.0, local_threshold * 0.6))).astype(np.uint8) * 255
        mask = cv2.bitwise_or(bright, saturated)
    else:
        mask = bright
    edges = cv2.Canny(gray, 60, 160)
    edge_mask = cv2.bitwise_and(cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1), cv2.bitwise_or(bright, mask))
    mask = cv2.bitwise_or(mask, edge_mask)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    return _filter_text_components(mask, cv2, np)


def _select_best_text_frame(frames: list[Any], cv2: Any, np: Any) -> int:
    best_index = 0
    best_score = -1
    for index, frame in enumerate(frames):
        mask = _composite_text_mask(frame, cv2, np)
        score = int((mask > 0).sum())
        if score > best_score:
            best_index = index
            best_score = score
    return best_index


def _filter_text_components(mask: Any, cv2: Any, np: Any) -> Any:
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    if count <= 1:
        return mask
    height, width = mask.shape[:2]
    filtered = np.zeros_like(mask)
    effective_height = min(height, max(120, int(width * 1.2)))
    max_area = max(80, int(width * effective_height * 0.035))
    min_area = 3
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        if area < min_area or area > max_area:
            continue
        if w > width * 0.82 or h > height * 0.35:
            continue
        filtered[labels == label] = 255
    return filtered


def _sharpen(image: Any, cv2: Any) -> Any:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 3)


def quality_score(composite: Any, cv2: Any | None = None) -> dict[str, float]:
    if composite is None or getattr(composite, "size", 0) == 0:
        return {"score": 0.0, "sharpness": 0.0, "contrast": 0.0, "text_density": 0.0, "ghost_penalty": 0.0}
    if cv2 is None:
        import cv2 as cv2_module

        cv2 = cv2_module
    import numpy as np

    height, width = composite.shape[:2]
    if height < 10 or width < 10:
        return {"score": 0.0, "sharpness": 0.0, "contrast": 0.0, "text_density": 0.0, "ghost_penalty": 0.0}
    gray = cv2.cvtColor(composite, cv2.COLOR_BGR2GRAY) if len(composite.shape) == 3 else composite
    laplacian_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharpness_score = min(1.0, laplacian_variance / 600.0)
    threshold, _binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright = gray[gray > threshold]
    dark = gray[gray <= threshold]
    contrast = (float(bright.mean()) - float(dark.mean())) / 255.0 if bright.size and dark.size else 0.0
    contrast_score = min(1.0, contrast / 0.40)
    density = float(bright.size) / max(1, gray.size)
    if density < 0.02:
        density_score = density / 0.02
    elif density <= 0.25:
        density_score = 1.0
    else:
        density_score = max(0.0, 1.0 - ((density - 0.25) / 0.25))
    ghost_penalty = _ghost_penalty(composite, cv2, np)
    score = (0.45 * sharpness_score) + (0.35 * contrast_score) + (0.20 * density_score) - (0.30 * ghost_penalty)
    score = max(0.0, min(1.0, score))
    return {
        "score": round(float(score), 3),
        "sharpness": round(float(laplacian_variance), 1),
        "contrast": round(float(contrast), 3),
        "text_density": round(float(density), 4),
        "ghost_penalty": round(float(ghost_penalty), 4),
    }


def _ghost_penalty(composite: Any, cv2: Any, np: Any) -> float:
    """Estimate repeated-text ghosting from text-mask overlap across vertical slices."""
    height, _width = composite.shape[:2]
    if height < 200:
        return 0.0
    slice_h = max(20, height // 8)
    masks = []
    for index in range(4):
        y0 = index * slice_h * 2
        y1 = min(height, y0 + slice_h)
        if y1 - y0 < 10:
            continue
        mask = _composite_text_mask(composite[y0:y1], cv2, np)
        masks.append((mask > 0).astype(np.float32))
    if len(masks) < 2:
        return 0.0
    ious = []
    for left, right in zip(masks, masks[1:]):
        if left.shape != right.shape:
            continue
        intersection = float((left * right).sum())
        union = float(((left + right) > 0).sum())
        if union > 0:
            ious.append(intersection / union)
    if not ious:
        return 0.0
    mean_iou = float(np.mean(ious))
    return max(0.0, min(1.0, (mean_iou - 0.20) * 2.0))


def _active_runs(active: Any, *, min_width: int) -> list[tuple[int, int]]:
    runs = []
    start = None
    for index, value in enumerate(active):
        if bool(value) and start is None:
            start = index
        elif not bool(value) and start is not None:
            if index - start >= min_width:
                runs.append((start, index))
            start = None
    if start is not None and len(active) - start >= min_width:
        runs.append((start, len(active)))
    return runs


def _export_rows(
    image: Any,
    rows: list[dict[str, Any]],
    split_x: int | None,
    rows_dir: Path,
    role_dir: Path,
    name_dir: Path,
    cv2: Any,
    *,
    scale: int,
) -> list[dict[str, Any]]:
    exported = []
    height, width = image.shape[:2]
    for row in rows:
        y0 = max(0, int(row["y0"]) - 2)
        y1 = min(height, int(row["y1"]) + 2)
        crop = image[y0:y1, :]
        if crop.size == 0:
            continue
        if scale > 1:
            crop_out = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        else:
            crop_out = crop
        row_path = rows_dir / f"row_{int(row['index']):04d}.png"
        _cv2_imwrite(row_path, crop_out, cv2)
        payload = dict(row)
        payload["row_path"] = str(row_path)
        if split_x is not None and 2 < split_x < width - 2:
            role_crop = image[y0:y1, :split_x]
            name_crop = image[y0:y1, split_x:]
            if scale > 1:
                role_crop = cv2.resize(role_crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                name_crop = cv2.resize(name_crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            role_path = role_dir / f"role_{int(row['index']):04d}.png"
            name_path = name_dir / f"name_{int(row['index']):04d}.png"
            _cv2_imwrite(role_path, role_crop, cv2)
            _cv2_imwrite(name_path, name_crop, cv2)
            payload["role_crop_path"] = str(role_path)
            payload["name_crop_path"] = str(name_path)
        exported.append(payload)
    return exported


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


def _cv2_imwrite(path: Path, image: Any, cv2: Any) -> None:
    ok = cv2.imwrite(str(path), image)
    if ok:
        return
    ext = path.suffix or ".png"
    success, encoded = cv2.imencode(ext, image)
    if not success:
        raise RuntimeError(f"Could not write image: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(str(path))


def _median_or_none(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def _round_or_none(value: float | None) -> float | None:
    return round(float(value), 4) if value is not None else None


def _build_report(summary: dict[str, Any]) -> str:
    split = summary.get("auto_split") or {}
    motion = summary.get("motion") or {}
    quality = summary.get("quality") or {}
    frame_filter = summary.get("frame_filter") or {}
    lines = [
        "# Text-Layer Row Reconstruct v1",
        "",
        f"- Frames: input={summary.get('input_frame_count', summary.get('frame_count'))} read={summary.get('read_frame_count')} processed={summary.get('processed_frame_count')}",
        f"- Frame filter: status={frame_filter.get('status')} kept={frame_filter.get('kept_count')} dropped={frame_filter.get('dropped_count', 0)} median_dark={frame_filter.get('median_dark_ratio')}",
        f"- Composite: {summary.get('composite_path')}",
        f"- Composite size: {summary.get('composite_size')}",
        f"- Quality: score={quality.get('score')} sharpness={quality.get('sharpness')} contrast={quality.get('contrast')} density={quality.get('text_density')} warning={summary.get('quality_warning')}",
        f"- Rows: {summary.get('row_count')}",
        f"- Auto split: x={split.get('split_x')} confidence={split.get('confidence')} status={split.get('status')}",
        f"- Motion: status={motion.get('status')} active={motion.get('active_frame_count')} stopped={motion.get('stopped_frame_count')} dy/frame={motion.get('median_dy_per_frame')}",
        "",
        "## First Rows",
        "",
        "| # | y0 | y1 | row crop |",
        "| ---: | ---: | ---: | --- |",
    ]
    for row in (summary.get("rows") or [])[:24]:
        lines.append(f"| {row.get('index')} | {row.get('y0')} | {row.get('y1')} | {row.get('row_path')} |")
    return "\n".join(lines) + "\n"
