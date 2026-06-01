"""
cv_stitcher_scans/engine.py
===========================
Credit-mosaic baseline using OpenCV's high-level Stitcher in SCANS (affine) mode.

SCANS mode uses an affine model designed for translational camera motion scanning
a flat surface.  For credit sequences this maps to a camera (or text) scrolling
vertically.  For static-card sequences the stitcher degenerates (see FINDINGS below).

FINDINGS (observed on Le Dernier Métro opening + closing):
----------------------------------------------------------
Both sequences are STATIC-CARD sequences (not scrolling):
  • Opening : 7 unique red-background title cards, each held ~30–160 frames,
    separated by fade-to-black transitions.
  • Closing : 18 unique red-background portrait+name cards, 20-23 frames each.

cv2.Stitcher_SCANS on static cards:
  • Returns Stitcher_OK but produces DEGENERATE output (e.g. 18290×22656 canvas
    that is ~99% black) because the stitcher finds SPURIOUS feature matches between
    repeated red-background regions and text glyphs across completely different cards,
    then applies wildly incorrect affine transforms that scatter content across a
    massive canvas.
  • Even on card PAIRS it "succeeds" but outputs only ~504×620 (≈ one frame) instead
    of the expected ~960×600 — the stitcher decides the two cards overlap completely.
  • Chunk-stitching (10–15 cards per chunk) has the same failure.

Root cause: credit cards are *low-texture / uniform background + repetitive stroke
patterns*.  Feature detectors (ORB/AKAZE used by SCANS) find many keypoints in text
glyphs, but because all cards share the same red BG and similar text layout the
descriptor matching is essentially random across cards.  The affine estimator then
picks the "best" random transform, which is arbitrary and often near-singular.

Fallback: VSTACK of deduplicated card representatives.  This is the correct result
for a static-card credit sequence — each unique card appears exactly once.

Pipeline
--------
1.  Load frames (np.fromfile / cv2.imdecode — Turkish-İ path safe).
2.  Skip pure-black leader/trailer.
3.  Classify: SCROLL vs STATIC-CARD using score-based template tracking.
4a. STATIC-CARD → deduplicate by frame-diff run detection, pick mid-run
    representative, attempt SCANS stitch, validate output geometry;
    fall back to vertical stack on failure or degenerate result.
4b. SCROLL      → subsample (target ~60% overlap per stride), attempt SCANS
    stitch; fall back to chunk-stitch + NCC-align concatenation; fall back to
    raw vstack.
5.  Write master.png (tofile) + debug.json.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

# Disable OpenCL to avoid GPU memory errors on some Windows setups
cv2.ocl.setUseOpenCL(False)


# ---------------------------------------------------------------------------
# I/O helpers — Turkish-İ path trap avoidance
# ---------------------------------------------------------------------------

def _imread(path: str) -> Optional[np.ndarray]:
    """Load image from any path (handles non-ASCII/Turkish chars)."""
    buf = np.fromfile(path, dtype=np.uint8)
    if buf.size == 0:
        return None
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return img


def _imwrite(path: str, img: np.ndarray) -> None:
    """Write image to any path (handles non-ASCII/Turkish chars)."""
    ext = os.path.splitext(path)[1].lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise RuntimeError(f"cv2.imencode failed for {path}")
    buf.tofile(path)


# ---------------------------------------------------------------------------
# Frame analysis helpers
# ---------------------------------------------------------------------------

def _is_black(img: np.ndarray, threshold: float = 4.0) -> bool:
    return float(img.mean()) < threshold


def _preprocess_for_features(img: np.ndarray) -> np.ndarray:
    """
    Boost text contrast to help feature detectors on low-contrast credit frames.
    Returns a 3-channel BGR image with CLAHE-enhanced grayscale.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    # Top-hat to isolate bright strokes on dark/uniform BG
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    tophat = cv2.morphologyEx(enhanced, cv2.MORPH_TOPHAT, kernel)
    combined = cv2.add(enhanced, tophat)
    return cv2.cvtColor(combined, cv2.COLOR_GRAY2BGR)


# ---------------------------------------------------------------------------
# Scroll detection — score-based template tracking
# ---------------------------------------------------------------------------

def _classify_motion(
    frames_gray: List[np.ndarray],
    n_test: int = 20,
    good_score_threshold: float = 0.55,
    good_match_fraction: float = 0.5,
    min_dy: float = 0.8,
    directional_fraction: float = 0.65,
) -> Tuple[bool, float]:
    """
    Classify a frame sequence as SCROLL or STATIC-CARD.

    Returns (is_scroll, median_dy_px_per_frame).

    Strategy: track a central horizontal strip via template matching across
    consecutive frames.  For a genuine scroll:
      - Most matches score > 0.55 (template found in next frame)
      - Median |dy| > min_dy  (content is actually moving)
      - >= 65% of dy values share the same sign (directional)

    For static cards:
      - Template score drops to < 0.4 when next card appears (no overlap)
      - Median dy is near-zero within stable runs
    """
    if len(frames_gray) < 2:
        return False, 0.0

    h, w = frames_gray[0].shape
    strip_h = max(30, h // 4)
    y0 = h // 3
    search_margin = 25  # px above/below strip to search

    shifts: List[Tuple[float, float]] = []  # (dy, score)
    for i in range(min(n_test, len(frames_gray) - 1)):
        f1 = frames_gray[i].astype(np.float32)
        f2 = frames_gray[i + 1].astype(np.float32)
        strip = f1[y0: y0 + strip_h, :]
        y_lo = max(0, y0 - search_margin)
        y_hi = min(h, y0 + strip_h + search_margin)
        search = f2[y_lo:y_hi, :]
        if search.shape[0] < strip.shape[0]:
            continue
        res = cv2.matchTemplate(search, strip, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        dy = maxloc[1] - search_margin  # positive = strip moved down = content scrolls up
        shifts.append((float(dy), float(maxv)))

    if not shifts:
        return False, 0.0

    good = [(dy, s) for dy, s in shifts if s > good_score_threshold]
    if len(good) < len(shifts) * good_match_fraction:
        # Most frames didn't track — static cards or scene cuts
        return False, 0.0

    dys = [dy for dy, _ in good]
    median_dy = float(np.median(dys))
    if abs(median_dy) < min_dy:
        return False, abs(median_dy)

    # Check directionality
    same_sign = sum(1 for d in dys if d * median_dy >= 0) / len(dys)
    if same_sign < directional_fraction:
        return False, abs(median_dy)

    return True, abs(median_dy)


# ---------------------------------------------------------------------------
# Deduplicate static cards
# ---------------------------------------------------------------------------

def _deduplicate_cards(
    frames: List[np.ndarray],
    diff_threshold: float = 3.0,
    min_stable_frames: int = 5,
    exclude_dark: bool = True,
) -> List[np.ndarray]:
    """
    For static-card sequences: group frames into stable runs (low inter-frame diff),
    return one mid-run representative per unique card.

    diff_threshold     : mean pixel diff to declare a card boundary.
    min_stable_frames  : discard transient fades shorter than this.
    exclude_dark       : skip cards whose representative is nearly black.
    """
    if not frames:
        return []

    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames]
    diffs = [0.0] + [
        float(np.mean(np.abs(grays[i] - grays[i - 1]))) for i in range(1, len(grays))
    ]

    runs: List[Tuple[int, int]] = []
    run_start = 0
    for i in range(1, len(diffs)):
        if diffs[i] > diff_threshold:
            if i - run_start >= min_stable_frames:
                runs.append((run_start, i))
            run_start = i
    if len(frames) - run_start >= min_stable_frames:
        runs.append((run_start, len(frames)))

    reps = []
    for s, e in runs:
        mid = (s + e) // 2
        rep = frames[mid]
        if exclude_dark and _is_black(rep, threshold=5.0):
            continue
        reps.append(rep)
    return reps


# ---------------------------------------------------------------------------
# Validate stitcher output geometry
# ---------------------------------------------------------------------------

def _is_degenerate(
    pano: np.ndarray,
    n_source_frames: int,
    frame_h: int,
    frame_w: int,
    max_multiplier: float = 3.0,
) -> bool:
    """
    Return True if the stitcher output looks degenerate (wrong scale).

    For N frames stacked vertically the expected height is ~N * frame_h.
    Degenerate if:
      - output is MUCH LARGER than expected (hallucinated panorama)
      - output is MUCH SMALLER than expected (collapsed to ~1 frame)
      - output is mostly black (content scattered off-canvas)
    """
    if pano is None:
        return True

    ph, pw = pano.shape[:2]
    expected_h = n_source_frames * frame_h

    # Too large → spurious transforms scattered content across giant canvas
    if ph > expected_h * max_multiplier or pw > frame_w * max_multiplier:
        return True

    # Too small → stitcher collapsed N frames into too few rows (spurious overlap).
    # For N > 2 frames: expect at least 25% of N×frame_h (accounts for real overlap).
    # For N <= 2: expect at least 1.5× frame_h.
    if n_source_frames > 2:
        if ph < n_source_frames * frame_h * 0.25:
            return True
    elif n_source_frames == 2:
        if ph < frame_h * 1.5:
            return True

    # Mostly black → content was scattered off-canvas
    sample = pano[::4, ::4]
    non_black_frac = float(np.mean(sample > 5))
    if non_black_frac < 0.01:
        return True

    return False


# ---------------------------------------------------------------------------
# NCC-based chunk alignment for fallback concatenation
# ---------------------------------------------------------------------------

def _ncc_vstack(
    panoramas: List[np.ndarray], overlap_px: int = 80
) -> np.ndarray:
    """
    Vertically concatenate panoramas by NCC-aligning consecutive overlap strips
    to remove duplicate rows.
    """
    if not panoramas:
        raise ValueError("Empty panorama list")
    result = panoramas[0]
    for next_pano in panoramas[1:]:
        w = min(result.shape[1], next_pano.shape[1])
        h2 = next_pano.shape[0]
        strip1 = cv2.cvtColor(result[-overlap_px:, :w], cv2.COLOR_BGR2GRAY).astype(np.float32)
        strip2 = cv2.cvtColor(next_pano[:, :w], cv2.COLOR_BGR2GRAY).astype(np.float32)
        search_len = min(h2, overlap_px * 2)
        cut = 0
        if strip2.shape[0] >= strip1.shape[0] > 0:
            res = cv2.matchTemplate(strip2[:search_len], strip1, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > 0.3:
                cut = max(0, max_loc[1])
        result = np.vstack([result, next_pano[cut:, :w]])
    return result


# ---------------------------------------------------------------------------
# Core SCANS stitcher attempt
# ---------------------------------------------------------------------------

def _try_scans_stitch(
    frames: List[np.ndarray],
    registration_resol: float = 0.6,
    confidence_thresh: float = 0.3,
    use_preprocessed: bool = True,
) -> Tuple[Optional[np.ndarray], str]:
    """
    Attempt cv2.Stitcher_SCANS on a list of frames.
    Returns (panorama_or_None, status_message).
    Does NOT validate geometry — caller must call _is_degenerate.
    """
    if len(frames) < 2:
        return None, "need_at_least_2_frames"

    proc = [_preprocess_for_features(f) if use_preprocessed else f for f in frames]

    stitcher = cv2.Stitcher_create(cv2.Stitcher_SCANS)
    stitcher.setRegistrationResol(registration_resol)
    stitcher.setPanoConfidenceThresh(confidence_thresh)

    try:
        status, pano = stitcher.stitch(proc)
    except cv2.error as e:
        return None, f"cv2_error:{e}"

    status_map = {
        cv2.Stitcher_OK: "OK",
        cv2.Stitcher_ERR_NEED_MORE_IMGS: "ERR_NEED_MORE_IMGS",
        cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "ERR_HOMOGRAPHY_EST_FAIL",
        cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "ERR_CAMERA_PARAMS_ADJUST_FAIL",
    }
    msg = status_map.get(int(status), f"ERR_UNKNOWN_{status}")

    if status == cv2.Stitcher_OK and pano is not None:
        return pano, msg
    return None, msg


# ---------------------------------------------------------------------------
# Chunk-stitch fallback
# ---------------------------------------------------------------------------

def _chunk_stitch(
    frames: List[np.ndarray],
    chunk_size: int = 15,
    registration_resol: float = 0.8,
    confidence_thresh: float = 0.2,
) -> Tuple[List[np.ndarray], List[str]]:
    """
    Stitch frames in overlapping chunks; return successful chunk panoramas.
    """
    panoramas: List[np.ndarray] = []
    statuses: List[str] = []
    frame_h = frames[0].shape[0] if frames else 480
    frame_w = frames[0].shape[1] if frames else 600

    for start in range(0, len(frames), chunk_size // 2):
        end = min(start + chunk_size, len(frames))
        chunk = frames[start:end]
        if len(chunk) < 2:
            continue
        pano, msg = _try_scans_stitch(chunk, registration_resol, confidence_thresh)
        is_deg = _is_degenerate(pano, len(chunk), frame_h, frame_w)
        label = f"chunk_{start}-{end}: {msg}" + (" [DEGENERATE]" if is_deg else "")
        statuses.append(label)
        if pano is not None and not is_deg:
            panoramas.append(pano)

    return panoramas, statuses


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(
    frames_dir: str,
    out_dir: str,
    stride: Optional[int] = None,
    chunk_size: int = 15,
    registration_resol: float = 0.6,
    confidence_thresh: float = 0.3,
    min_stable_frames: int = 5,
    diff_threshold: float = 3.0,
) -> dict:
    """
    Build a credit mosaic from all frames in frames_dir.

    Parameters
    ----------
    frames_dir         : directory of PNG frames (sorted alphabetically = temporal order)
    out_dir            : output directory; master.png + debug.json written here
    stride             : if set, use every N-th frame (scroll mode only);
                         None = auto-detect from motion estimate
    chunk_size         : frames per chunk in fallback chunked-stitching
    registration_resol : Stitcher.setRegistrationResol (lower = faster but less accurate)
    confidence_thresh  : Stitcher.setPanoConfidenceThresh (lower = more permissive)
    min_stable_frames  : min run length to count as a unique card (dedup)
    diff_threshold     : mean-pixel-diff threshold for card-boundary detection

    Returns
    -------
    dict with keys: master_path, dims, mode, stride, stitch_status, runtime_s,
                    n_frames_loaded, n_frames_fed, n_unique_cards, warnings
    """
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)

    result: dict = {
        "frames_dir": frames_dir,
        "out_dir": out_dir,
        "master_path": None,
        "dims": None,
        "mode": None,
        "stride": stride,
        "stitch_status": None,
        "runtime_s": None,
        "n_frames_loaded": 0,
        "n_frames_fed": 0,
        "n_unique_cards": 0,
        "warnings": [],
    }

    # ------------------------------------------------------------------
    # 1. Load all frames
    # ------------------------------------------------------------------
    frame_files = sorted(
        [f for f in os.listdir(frames_dir) if f.lower().endswith(".png")]
    )
    if not frame_files:
        result["warnings"].append("No PNG frames found")
        result["stitch_status"] = "no_frames"
        result["runtime_s"] = round(time.time() - t0, 2)
        return result

    frames_all: List[np.ndarray] = []
    for fn in frame_files:
        img = _imread(os.path.join(frames_dir, fn))
        if img is not None:
            frames_all.append(img)

    result["n_frames_loaded"] = len(frames_all)
    if not frames_all:
        result["stitch_status"] = "load_failed"
        result["runtime_s"] = round(time.time() - t0, 2)
        return result

    frame_h, frame_w = frames_all[0].shape[:2]

    # ------------------------------------------------------------------
    # 2. Skip black leader/trailer
    # ------------------------------------------------------------------
    first_nb = next((i for i, f in enumerate(frames_all) if not _is_black(f)), 0)
    last_nb = next(
        (i for i in range(len(frames_all) - 1, -1, -1) if not _is_black(frames_all[i])),
        len(frames_all) - 1,
    )
    frames_content = frames_all[first_nb: last_nb + 1]

    if len(frames_content) == 0:
        result["warnings"].append("All frames are black")
        result["stitch_status"] = "all_black"
        result["runtime_s"] = round(time.time() - t0, 2)
        return result

    result["warnings"].append(
        f"Black trim: kept {len(frames_content)} frames (idx {first_nb}–{last_nb})"
    )

    # ------------------------------------------------------------------
    # 3. Detect scroll vs static-card
    #    Sample from the FIRST HALF only to avoid film-scene contamination
    # ------------------------------------------------------------------
    half_len = max(2, len(frames_content) // 2)
    sample_step = max(1, half_len // 30)
    sample_grays = [
        cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        for f in frames_content[:half_len:sample_step]
    ][:30]

    is_scroll, measured_dy = _classify_motion(sample_grays)
    result["mode"] = "scroll" if is_scroll else "static_cards"
    result["warnings"].append(
        f"Motion classification: is_scroll={is_scroll}, "
        f"measured_dy={measured_dy:.2f} px/frame"
    )

    # ------------------------------------------------------------------
    # 4a. STATIC CARD path
    # ------------------------------------------------------------------
    if not is_scroll:
        result["warnings"].append(
            "STATIC CARD mode: deduplicating runs, then attempting SCANS stitch "
            "on representative frames (expected to fail — see module docstring)."
        )
        reps = _deduplicate_cards(
            frames_content,
            diff_threshold=diff_threshold,
            min_stable_frames=min_stable_frames,
            exclude_dark=True,
        )
        result["n_unique_cards"] = len(reps)
        result["warnings"].append(f"Unique credit cards after dedup: {len(reps)}")
        result["n_frames_fed"] = len(reps)

        master: Optional[np.ndarray] = None

        if len(reps) == 0:
            result["warnings"].append("No stable cards found — using first non-black frame")
            master = frames_content[0]
            result["stitch_status"] = "single_frame_emergency"

        elif len(reps) == 1:
            master = reps[0]
            result["stitch_status"] = "single_card_passthrough"

        else:
            # --- Attempt 1: whole-set SCANS stitch ---
            pano, status = _try_scans_stitch(
                reps,
                registration_resol=registration_resol,
                confidence_thresh=confidence_thresh,
            )
            deg = _is_degenerate(pano, len(reps), frame_h, frame_w)
            result["stitch_status"] = status + (" [DEGENERATE]" if deg else "")
            result["warnings"].append(
                f"SCANS stitch attempt 1: {result['stitch_status']}"
            )

            if pano is not None and not deg:
                master = pano
            else:
                # --- Attempt 2: lower confidence ---
                result["warnings"].append(
                    "Attempt 1 failed/degenerate; retrying with "
                    "confidence=0.1, resol=0.9"
                )
                pano2, status2 = _try_scans_stitch(
                    reps,
                    registration_resol=0.9,
                    confidence_thresh=0.1,
                )
                deg2 = _is_degenerate(pano2, len(reps), frame_h, frame_w)
                result["stitch_status"] += f" → retry2:{status2}"
                if deg2:
                    result["stitch_status"] += " [DEGENERATE]"
                result["warnings"].append(
                    f"SCANS stitch attempt 2: {status2}, degenerate={deg2}"
                )

                if pano2 is not None and not deg2:
                    master = pano2
                else:
                    # --- Fallback: vertical stack ---
                    result["warnings"].append(
                        "Both SCANS attempts failed or produced degenerate output. "
                        "VSTACK FALLBACK: stacking deduplicated card representatives "
                        "vertically (correct output for static-card sequence)."
                    )
                    master = np.vstack(reps)
                    result["stitch_status"] += " → VSTACK_FALLBACK"

    # ------------------------------------------------------------------
    # 4b. SCROLL path
    # ------------------------------------------------------------------
    else:
        if stride is None:
            if measured_dy < 0.5:
                stride = max(1, frame_h // 3)
            else:
                stride_px = int(0.4 * frame_h)
                stride = max(1, int(stride_px / measured_dy))
        result["stride"] = stride

        frames_sub = frames_content[::stride]
        result["n_frames_fed"] = len(frames_sub)
        result["warnings"].append(
            f"Scroll stride={stride}, feeding {len(frames_sub)} frames to stitcher"
        )

        # Attempt 1: whole-sequence
        pano, status = _try_scans_stitch(
            frames_sub,
            registration_resol=registration_resol,
            confidence_thresh=confidence_thresh,
        )
        deg = _is_degenerate(pano, len(frames_sub), frame_h, frame_w)
        result["stitch_status"] = status + (" [DEGENERATE]" if deg else "")

        if pano is not None and not deg:
            master = pano
        else:
            result["warnings"].append(
                f"Whole-sequence SCANS failed ({result['stitch_status']}); "
                "trying chunk stitching"
            )
            chunk_panos, chunk_statuses = _chunk_stitch(
                frames_sub,
                chunk_size=chunk_size,
                registration_resol=0.8,
                confidence_thresh=0.2,
            )
            result["warnings"].extend(chunk_statuses)

            if chunk_panos:
                try:
                    master = _ncc_vstack(chunk_panos, overlap_px=100)
                    result["stitch_status"] += (
                        f" → chunk_ncc_ok ({len(chunk_panos)} chunks)"
                    )
                except Exception as exc:
                    result["warnings"].append(f"NCC vstack error: {exc}")
                    master = np.vstack(chunk_panos)
                    result["stitch_status"] += " → chunk_vstack"
            else:
                result["warnings"].append(
                    "All chunk stitches failed; raw vertical stack fallback"
                )
                master = np.vstack(frames_sub)
                result["stitch_status"] += " → raw_vstack_fallback"

    # ------------------------------------------------------------------
    # 5. Save outputs
    # ------------------------------------------------------------------
    master_path = os.path.join(out_dir, "master.png")
    _imwrite(master_path, master)
    result["master_path"] = master_path
    result["dims"] = {"width": int(master.shape[1]), "height": int(master.shape[0])}

    result["runtime_s"] = round(time.time() - t0, 2)
    debug_path = os.path.join(out_dir, "debug.json")
    with open(debug_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)

    return result
