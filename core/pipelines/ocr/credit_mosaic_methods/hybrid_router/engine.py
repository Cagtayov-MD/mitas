"""
Hybrid Router Credit Mosaic Engine
====================================
Style-aware dispatcher: classifies a credit segment as SINGLE-COLUMN or
TWO-COLUMN, then routes to the appropriate engine.

Engine A = overlap_template  (sharp single-column/card credits)
Engine D = ocr_line_dedup    (clean two-column dense scrolls)

TASK 1 — STYLE DETECTOR
-----------------------
Samples ~30 frames across the segment.  For each credit frame (reuses A's
_tophat_mask + _is_credit), computes the X-axis projection of the text mask
(column density = sum over rows per column), smooths, normalises.

TWO-COLUMN signal: left-third mean + right-third mean significantly exceed
the centre-third mean.  Specifically:
    centre_mean < 0.4 * mean(outer_thirds)
    => that frame is "two_column"

If >=40% of sampled credit frames are two_column → segment style = "two_column".
Fewer than MIN_CREDIT_SAMPLE credit frames → default "single_column".

TASK 2 — ROUTER
---------------
run(item_dir, out_dir, *, segment) -> dict

Derives frames_dir = item_dir/frames/<segment>, sorted frame_*.png list.
Detects style; calls the winning engine; normalises the return dict.
Writes router_debug.json.

NO cv2.imread/imwrite — np.fromfile+imdecode / imencode+tofile throughout.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# ── import helpers from engine A ──────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[5]  # E:\MITAS
import sys
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.pipelines.ocr.credit_mosaic_methods.overlap_template import engine as _eng_A
from core.pipelines.ocr.credit_mosaic_methods.ocr_line_dedup import engine as _eng_D

# ── Style detector tunables ────────────────────────────────────────────────────
STYLE_SAMPLE_N: int = 30            # frames to sample across the segment
# Two-column detection: look for a gap at the horizontal CENTER of the ACTIVE text zone.
# The "lobes" are the 10-40% and 60-90% horizontal bands (skipping outer 10% which is
# typically letterbox/black). The "valley" is the center ±5% of the frame width.
# Two-column fires when: valley < TWO_COL_MID_RATIO * mean(lobes)
TWO_COL_MID_RATIO: float = 0.50    # centre valley < this * outer-lobe mean → two_column frame
TWO_COL_MIN_FRAC: float = 0.45     # fraction of credit frames voting two_column to pick D
MIN_CREDIT_SAMPLE: int = 8          # if fewer credit frames sampled → default single_column
SMOOTH_KSIZE: int = 11              # box-filter kernel size for x-profile smoothing


# ── Helpers ────────────────────────────────────────────────────────────────────

def _imread(path: str) -> np.ndarray | None:
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _imwrite(path: str | Path, img: np.ndarray) -> None:
    path = str(path)
    ext = os.path.splitext(path)[1].lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise RuntimeError(f"imencode failed: {path}")
    buf.tofile(path)


def _x_profile(mask: np.ndarray) -> np.ndarray:
    """Return column-wise sum of mask pixels, smoothed and normalised to [0,1]."""
    col_sum = mask.sum(axis=0).astype(np.float32)
    # Smooth with a box filter
    kernel = np.ones((1, SMOOTH_KSIZE), np.float32) / SMOOTH_KSIZE
    col_sum_2d = col_sum.reshape(1, -1)
    smoothed = cv2.filter2D(col_sum_2d, -1, kernel)[0]
    mx = float(smoothed.max())
    if mx > 0:
        smoothed /= mx
    return smoothed


def _is_two_column_frame(profile: np.ndarray) -> bool:
    """Return True if the x-profile shows two lobes with a gap between them.

    Detects the pattern: role label on the left + person name on the right,
    separated by a vertical empty gutter (e.g. X-MEN end credits).

    Algorithm:
      1. Search for the minimum within the CORE zone (30%-70% of frame width).
         This zone always straddles the inter-column gap for side-by-side layouts.
      2. Compute left_lobe = mean of the active non-zero zone LEFT of the gap.
         right_lobe = mean of the active zone RIGHT of the gap.
      3. Two-column fires when:
         - gap_val < TWO_COL_MID_RATIO * mean(left_lobe, right_lobe), AND
         - both lobes have meaningful density (> 0.05), AND
         - the gap position is within 25-75% of frame width.
    """
    w = len(profile)
    if w < 20:
        return False
    # Search gap in core zone 30-70%
    c30 = int(w * 0.30)
    c70 = int(w * 0.70)
    core = profile[c30:c70]
    if len(core) < 4:
        return False
    gap_idx_core = int(np.argmin(core))
    gap_val = float(core[gap_idx_core])
    gap_abs = c30 + gap_idx_core

    # Lobe windows: 10-gap_abs and gap_abs-90% (skip outer 10% letterbox)
    left_start = int(w * 0.10)
    right_end  = int(w * 0.90)
    left_part  = profile[left_start:gap_abs]
    right_part = profile[gap_abs + 1:right_end]

    if len(left_part) < 2 or len(right_part) < 2:
        return False

    left_mean  = float(left_part.mean())
    right_mean = float(right_part.mean())
    outer_mean = (left_mean + right_mean) / 2.0

    if outer_mean < 1e-4:
        return False
    if left_mean < 0.05 or right_mean < 0.05:
        return False
    # Both lobes must be non-trivial. Reject asymmetric cases where one lobe is
    # << the other (e.g. single paragraph with a tab indent, or sparse card text).
    lobe_ratio = min(left_mean, right_mean) / max(left_mean, right_mean)
    if lobe_ratio < 0.20:
        return False
    return gap_val < TWO_COL_MID_RATIO * outer_mean


# ── Public API ─────────────────────────────────────────────────────────────────

def detect_style(frames: list[str]) -> tuple[str, dict[str, Any]]:
    """Sample frames and decide 'single_column' or 'two_column'.

    Returns (style, debug_stats).
    """
    if not frames:
        return "single_column", {"reason": "no_frames"}

    # Sample evenly across the list
    n = min(STYLE_SAMPLE_N, len(frames))
    indices = [int(round(i * (len(frames) - 1) / max(n - 1, 1))) for i in range(n)]
    sampled = [frames[i] for i in indices]

    credit_count = 0
    two_col_count = 0
    profiles: list[dict] = []

    for fpath in sampled:
        img = _imread(fpath)
        if img is None:
            continue
        mask = _eng_A._tophat_mask(img)
        if not _eng_A._is_credit(mask, img):
            continue
        credit_count += 1
        profile = _x_profile(mask)
        is2col = _is_two_column_frame(profile)
        if is2col:
            two_col_count += 1
        profiles.append({
            "path": os.path.basename(fpath),
            "two_col": is2col,
        })

    stats: dict[str, Any] = {
        "sampled": len(sampled),
        "credit_frames": credit_count,
        "two_col_votes": two_col_count,
        "two_col_frac": round(two_col_count / max(credit_count, 1), 3),
        "profiles_sample": profiles[:10],
    }

    if credit_count < MIN_CREDIT_SAMPLE:
        stats["reason"] = "too_few_credit_frames"
        return "single_column", stats

    frac = two_col_count / credit_count
    if frac >= TWO_COL_MIN_FRAC:
        stats["reason"] = f"two_col_frac={frac:.3f} >= {TWO_COL_MIN_FRAC}"
        return "two_column", stats
    else:
        stats["reason"] = f"two_col_frac={frac:.3f} < {TWO_COL_MIN_FRAC}"
        return "single_column", stats


def run(
    item_dir: str | Path,
    out_dir: str | Path,
    *,
    segment: str,
) -> dict[str, Any]:
    """Run the hybrid router on one segment.

    Parameters
    ----------
    item_dir:
        Root of the item (contains frames/<segment>/ and unified/).
    out_dir:
        Output directory — master.png, router_debug.json land here.
    segment:
        'opening' or 'closing'.

    Returns
    -------
    dict with keys: master_path, style, engine_used, master_size, runtime_sec.
    """
    t0 = time.perf_counter()
    item_dir = Path(item_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Collect frames
    frames_dir = item_dir / "frames" / segment
    if not frames_dir.exists():
        raise FileNotFoundError(f"frames_dir not found: {frames_dir}")

    import re
    def _sort_key(p: Path) -> int:
        m = re.search(r"(\d+)", p.stem)
        return int(m.group(1)) if m else 0

    frame_paths = sorted(frames_dir.glob("frame_*.png"), key=_sort_key)
    if not frame_paths:
        frame_paths = sorted(frames_dir.glob("*.png"), key=_sort_key)

    frames_str = [str(p) for p in frame_paths]

    if not frames_str:
        raise FileNotFoundError(f"No PNG frames in {frames_dir}")

    # Detect style
    style, style_stats = detect_style(frames_str)

    engine_out_dir = str(out_dir)

    if style == "two_column":
        # Engine D
        engine_used = "ocr_line_dedup"
        eng_result = _eng_D.run(str(item_dir), engine_out_dir, segment=segment)
        master_path = str(out_dir / "master.png")
        # D may write to a sub-path; copy if needed
        if Path(eng_result["master_path"]).resolve() != Path(master_path).resolve():
            shutil.copy2(eng_result["master_path"], master_path)
        master_size = eng_result.get("master_size", [0, 0])
    else:
        # Engine A
        engine_used = "overlap_template"
        eng_result_A = _eng_A.run(frames_str, engine_out_dir, stride=1, verbose=False)
        master_path = str(out_dir / "master.png")
        if Path(eng_result_A.master_path).resolve() != Path(master_path).resolve():
            shutil.copy2(eng_result_A.master_path, master_path)
        master_size = [eng_result_A.width, eng_result_A.height]

    runtime_sec = round(time.perf_counter() - t0, 2)

    debug = {
        "item_dir": str(item_dir),
        "segment": segment,
        "frames_dir": str(frames_dir),
        "n_frames": len(frames_str),
        "style": style,
        "style_stats": style_stats,
        "engine_used": engine_used,
        "master_path": master_path,
        "master_size": master_size,
        "runtime_sec": runtime_sec,
    }
    debug_path = out_dir / "router_debug.json"
    debug_path.write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "master_path": master_path,
        "style": style,
        "engine_used": engine_used,
        "master_size": master_size,
        "runtime_sec": runtime_sec,
    }
