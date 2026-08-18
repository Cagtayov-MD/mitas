"""Kobe giriş dedektörünün iki bağımsız görüntü primitifi.

Davranış eski credit_detector içindeki üretim fonksiyonlarıyla birebirdir.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _cv2_imread(path: Path, cv2: Any) -> Any:
    import numpy as np

    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size > 0:
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if image is not None:
                return image
    except Exception:
        pass
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def _row_structure_score(mask: Any, np: Any) -> float:
    active = mask > 0
    if int(active.sum()) < 20:
        return 0.0
    height, width = mask.shape[:2]
    profile = active.sum(axis=1).astype(float)
    kernel_width = max(3, int(height * 0.012))
    kernel = np.ones(kernel_width) / kernel_width
    smooth = np.convolve(profile, kernel, mode="same")
    active_rows = smooth > max(2.0, width * 0.006)
    if not active_rows.any():
        return 0.0
    row_coverage = float(active_rows.sum() / max(1, height))
    mean_active = float(smooth[active_rows].mean())
    peak_strength = float(smooth.max()) / max(mean_active, 1.0)
    compactness = 1.0 - min(1.0, row_coverage / 0.55)
    peak_score = min(1.0, peak_strength / 3.5)
    return max(0.0, min(1.0, 0.60 * compactness + 0.40 * peak_score))

