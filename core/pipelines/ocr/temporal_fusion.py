"""Temporal fusion strategies for static-text OCR (K-3, K-4)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class TemporalFusionResult:
    output_path: Path     # path to the fused PNG
    summary_path: Path    # path to a small JSON summary
    report_path: Path     # path to a markdown human-readable report
    strategy: str         # "temporal_median_fusion" or "temporal_variance_masking"


def run_temporal_median_fusion(
    frame_paths: Iterable[str | Path],
    output_dir: str | Path,
    *,
    max_frames: int | None = None,
) -> TemporalFusionResult:
    """K-3: stack N frames, per-pixel median. Writes fused.png + summary.json."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(f"OpenCV/NumPy unavailable: {exc}") from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    frames = list(frame_paths)
    stack = _load_frames(frames, max_frames, cv2, np)

    fused = np.median(stack, axis=0).astype(np.uint8)

    fused_path = output / "fused.png"
    cv2.imwrite(str(fused_path), fused)

    quality = _quality_block(fused, np, cv2)
    summary: dict[str, Any] = {
        "strategy": "temporal_median_fusion",
        "frame_count": stack.shape[0],
        "input_frame_count": len(frames),
        "output_size": [int(fused.shape[1]), int(fused.shape[0])],
        "quality": quality,
    }
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(_round_floats(summary), ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = output / "report.md"
    report_path.write_text(_build_report(summary, fused_path), encoding="utf-8")

    return TemporalFusionResult(
        output_path=fused_path,
        summary_path=summary_path,
        report_path=report_path,
        strategy="temporal_median_fusion",
    )


def run_temporal_variance_masking(
    frame_paths: Iterable[str | Path],
    output_dir: str | Path,
    *,
    max_frames: int | None = None,
    low_var_quantile: float = 0.30,
) -> TemporalFusionResult:
    """K-4: per-pixel temporal variance, keep low-var (static text), suppress high-var BG."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(f"OpenCV/NumPy unavailable: {exc}") from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    frames = list(frame_paths)
    stack = _load_frames(frames, max_frames, cv2, np)

    # Grayscale stack: (N, H, W)
    gray_stack = np.mean(stack.astype(np.float32), axis=-1)

    pixel_variance = np.var(gray_stack, axis=0)  # (H, W)
    threshold = float(np.quantile(pixel_variance, low_var_quantile))
    static_mask = pixel_variance <= threshold  # (H, W) bool

    median_color = np.median(stack, axis=0).astype(np.uint8)
    result = median_color.copy()
    result[~static_mask] = 0  # suppress moving background pixels

    quality = _quality_block(result, np, cv2)
    static_pixel_ratio = float(static_mask.mean())

    fused_path = output / "fused.png"
    cv2.imwrite(str(fused_path), result)

    mask_img = (static_mask.astype(np.uint8)) * 255
    mask_path = output / "mask.png"
    cv2.imwrite(str(mask_path), mask_img)

    summary: dict[str, Any] = {
        "strategy": "temporal_variance_masking",
        "frame_count": stack.shape[0],
        "input_frame_count": len(frames),
        "output_size": [int(result.shape[1]), int(result.shape[0])],
        "quality": quality,
        "low_var_quantile": low_var_quantile,
        "variance_threshold": threshold,
        "static_pixel_ratio": static_pixel_ratio,
    }
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(_round_floats(summary), ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = output / "report.md"
    report_path.write_text(_build_report(summary, fused_path, mask_path=mask_path), encoding="utf-8")

    return TemporalFusionResult(
        output_path=fused_path,
        summary_path=summary_path,
        report_path=report_path,
        strategy="temporal_variance_masking",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_frames(
    frame_paths: list[str | Path],
    max_frames: int | None,
    cv2: Any,
    np: Any,
) -> Any:
    """Read frames, apply max_frames sub-sampling, build (N, H, W, 3) uint8 stack."""
    paths = [Path(p) for p in frame_paths]

    if max_frames is not None and len(paths) > max_frames:
        indices = np.linspace(0, len(paths) - 1, max_frames).astype(int)
        paths = [paths[i] for i in indices]

    images = []
    for path in paths:
        try:
            data = np.fromfile(str(path), dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size > 0 else None
            if img is None:
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        except Exception:
            img = None
        if img is None:
            continue
        images.append(img)

    if len(images) < 2:
        raise RuntimeError(
            f"Need at least 2 readable frames for temporal fusion, got {len(images)} "
            f"(from {len(frame_paths)} supplied paths)."
        )

    # Resize all to first frame's shape
    h0, w0 = images[0].shape[:2]
    resized = []
    for img in images:
        if img.shape[:2] != (h0, w0):
            img = cv2.resize(img, (w0, h0), interpolation=cv2.INTER_AREA)
        resized.append(img)

    return np.stack(resized, axis=0)  # (N, H, W, 3)


def _quality_block(image: Any, np: Any, cv2: Any) -> dict[str, Any]:
    # Convert to uint8 first; cv2.Laplacian with CV_64F needs uint8 source on this build
    gray_uint8 = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = gray_uint8.astype(np.float32)
    lap = cv2.Laplacian(gray_uint8, cv2.CV_64F)
    sharpness = float(lap.var())
    mean_val = float(gray.mean())
    contrast = float(gray.std() / mean_val) if mean_val > 0 else 0.0
    return {
        "sharpness_laplacian_var": round(sharpness, 4),
        "contrast_std_over_mean": round(contrast, 4),
    }


def _build_report(summary: dict[str, Any], fused_path: Path, *, mask_path: Path | None = None) -> str:
    strategy = summary.get("strategy", "temporal_fusion")
    quality = summary.get("quality") or {}
    lines = [
        f"# Temporal fusion — {strategy}",
        "",
        f"- Output: `{fused_path.name}`",
    ]
    if mask_path is not None:
        lines.append(f"- Static-pixel mask: `{mask_path.name}`")
    lines.extend([
        f"- Frames fused: {summary.get('frame_count')} (input: {summary.get('input_frame_count')})",
        f"- Output size (W × H): {summary.get('output_size')}",
        "",
        "## Quality",
        f"- Sharpness (Laplacian variance): {quality.get('sharpness_laplacian_var')}",
        f"- Contrast (std/mean of grayscale): {quality.get('contrast_std_over_mean')}",
    ])
    if "static_pixel_ratio" in summary:
        lines.extend([
            "",
            "## Variance masking",
            f"- Low-variance quantile: {summary.get('low_var_quantile')}",
            f"- Variance threshold: {summary.get('variance_threshold')}",
            f"- Static-pixel ratio: {summary.get('static_pixel_ratio')}",
        ])
    return "\n".join(lines) + "\n"


def _round_floats(obj: Any, decimals: int = 4) -> Any:
    if isinstance(obj, float):
        return round(obj, decimals)
    if isinstance(obj, dict):
        return {k: _round_floats(v, decimals) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v, decimals) for v in obj]
    return obj
