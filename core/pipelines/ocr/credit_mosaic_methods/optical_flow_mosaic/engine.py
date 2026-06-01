"""Optical-Flow Credit Mosaic Engine
=====================================
Turns a film credit sequence (mixed static cards + variable-speed scroll,
possibly moving background) into ONE tall master PNG where each text line
appears EXACTLY ONCE, with sharp text.

ALGORITHM — flow-registered accumulator + median blend:

1. TEXT MASK  (top-hat morphology + connected-component filter)
   Build a binary text mask per frame, suppressing background blobs.

2. FLOW ESTIMATION  (Lucas-Kanade sparse, restricted to text mask)
   - cv2.goodFeaturesToTrack inside text-mask regions
   - cv2.calcOpticalFlowPyrLK → per-feature (dx, dy)
   - Robust median of vertical displacements = sub-pixel scroll velocity dy_px
   Restricting to text features means a moving background does NOT corrupt
   the velocity estimate.

3. CUMULATIVE PLACEMENT + BLEND
   - Tall float32 accumulator canvas (3-channel sum) + weight canvas (count).
   - Track cumulative sub-pixel vertical offset since sequence start.
   - Each frame is PLACED at its cumulative offset row (sub-pixel shift via
     float offset → integer row). Where multiple frames land on the same canvas
     rows, values are SUMMED (weight counted). Final master = sum / weight.
   - Consequence: each text line always maps to the SAME canvas rows → appears
     exactly once. Multi-observation averaging sharpens text (super-resolution)
     and suppresses moving background (background moves to different canvas rows
     each frame, so weight stays low → gets averaged down).

4. STATIC CARD DETECTION  (flow consensus near zero)
   When |dy_sm| < S_LO for consecutive frames, we are on a static card or a
   scroll pause. Frames continue to be placed at the same offset → they blend
   in place without growing the canvas, effectively sharpening the card.

5. SCENE CUT / RESET
   Detected by: large global pixel diff (gdiff) AND small phase-corr response.
   On cut: flush current accumulator section → insert gap → reset offset.

OUTPUT
   master.png     — blended accumulator (sum/weight, normalized to [0,255])
   debug.json     — per-frame metrics + section list

KEY CONSTANT CHOICES (tunable):
   TOPHAT_KSIZE     25 px   structural element wider than text stroke
   MASK_DILATION     6 px   join glyphs into text-line blobs
   CC_MAX_H         45 px   reject blobs taller than one text line
   CC_MIN_W         50 px   reject narrow square blobs (scene edges)
   CC_MIN_ASPECT   1.8      text lines are wide, not square
   DRIFT_N          12      median window for dy smoothing
   DY_CLIP          15.0    hard clip per-frame dy to reject outliers
   S_LO              0.25   |dy_sm| below this → canvas does NOT advance
   S_HI              0.7    |dy_sm| above this → scroll confirmed
   MAX_CANVAS_H  200000     generous ceiling; trimmed before output

FAILURE MODES AVOIDED:
   - Previous phase-correlation engine accumulated dy and wrote a fresh strip
     per frame with NO blending → same line written 2-15x.
     This engine uses cumulative offset PLACEMENT so each line occupies the
     same canvas rows across ALL frames; blending sharpens instead of ghosting.

Turkish-İ path trap: NEVER use cv2.imread / cv2.imwrite.
Use np.fromfile + cv2.imdecode / cv2.imencode + .tofile everywhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# --- Text mask ---
TOPHAT_KSIZE: int = 25          # structural element size (px); larger than text stroke
MASK_DILATION: int = 6          # dilation to join glyphs
MIN_TEXT_RATIO: float = 0.002   # minimum text-pixel fraction → has_text

# --- Connected-component filter (rejects scene blobs) ---
CC_MIN_H: int = 5
CC_MAX_H: int = 45
CC_MIN_W: int = 40
CC_MIN_ASPECT: float = 1.5      # w/h ratio; text lines are wide
CC_MAX_AREA_FRAC: float = 0.05
MIN_CC_BLOBS: int = 2

# --- Background uniformity filter ---
# Credits sequences have uniform backgrounds (red, black, white).
# Scene footage has complex, textured backgrounds.
# We measure std-dev of background pixels (pixels NOT in text mask).
# Frames with BG std above this threshold are treated as scene footage → NO_TEXT.
# Empirically: credits bg_std < 20, scene footage bg_std > 30.
BG_STD_MAX: float = 28.0        # max allowed background std-dev → credits only
# Strip top/bottom 10% of image height (black bars) before measuring BG
BG_INNER_FRAC: float = 0.10

# --- Frame brightness (HSV value) filter ---
# Dark scene footage (archival film, nighttime scenes) can have very low mean
# brightness but nearly uniform backgrounds, fooling the BG_STD filter.
# Credits on red/white/black backgrounds have distinctly higher mean brightness.
# We measure mean HSV Value channel in the inner frame area.
# Empirically: credit frames val >= 110, dark scene footage val < 60.
FRAME_VAL_MIN: float = 90.0     # reject frames with mean inner brightness below this

# --- Optical flow (Lucas-Kanade sparse, text-masked) ---
MAX_LK_CORNERS: int = 300       # max features to track per frame
LK_QUALITY: float = 0.01        # corner quality level
LK_MIN_DIST: int = 7            # minimum distance between corners
LK_WIN_SIZE: int = 15           # LK window size

# Fallback: dense Farneback if LK yields too few good points
LK_MIN_GOOD: int = 10           # minimum accepted good LK points; else use Farneback
FARNEBACK_LEVELS: int = 3
FARNEBACK_WIN: int = 15
FARNEBACK_ITER: int = 3

# --- Flow smoothing ---
DRIFT_N: int = 12               # median window (frames)
DY_CLIP: float = 15.0           # hard clip per-frame raw dy
DY_MIN_MAGNITUDE: float = 0.05  # sub-threshold dy treated as 0 (avoid rounding drift)

# --- State machine (scroll vs static) ---
S_HI: float = 0.70              # |dy_sm| >= S_HI → scroll candidate
S_LO: float = 0.25              # |dy_sm| < S_LO  → static candidate
SCROLL_CONFIRM: int = 3
STATIC_CONFIRM: int = 3

# --- Scene cut detection ---
CUT_RESPONSE_MAX: float = 0.04  # phase-corr response below this → suspect cut
CUT_GLOBAL_MIN: float = 40.0    # mean absolute pixel diff above this → confirmed cut

# --- Canvas ---
MAX_CANVAS_H: int = 200_000     # generous ceiling; trimmed at end
GAP_HEIGHT: int = 18
GAP_GRAY: int = 40

# --- Sub-pixel placement resolution ---
# We track offset as float but only advance canvas_row when int(offset) changes.
# This avoids sub-pixel jitter creating duplicate rows.

# --- Labeled output colors (BGR) ---
LABEL_STATIC_COLOR: tuple = (60, 180, 60)
LABEL_SCROLL_COLOR: tuple = (60, 60, 220)
LABEL_BAND_H: int = 3


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class MosaicResult:
    master_path: Path
    debug_path: Path
    canvas_size: tuple[int, int]        # (W, H)
    sections: list[dict[str, Any]] = field(default_factory=list)
    n_static_blocks: int = 0
    n_scroll_sections: int = 0
    n_cut_events: int = 0
    runtime_sec: float = 0.0


# ---------------------------------------------------------------------------
# I/O helpers — Turkish-İ safe
# ---------------------------------------------------------------------------

def _read(path: Path) -> np.ndarray | None:
    """Read BGR frame. NEVER use cv2.imread."""
    try:
        buf = np.fromfile(str(path), np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _write(path: Path, img: np.ndarray) -> bool:
    """Write PNG. NEVER use cv2.imwrite."""
    try:
        ok, buf = cv2.imencode(".png", img)
        if ok:
            buf.tofile(str(path))
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Image processing helpers
# ---------------------------------------------------------------------------

def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()


def _build_text_mask(gray: np.ndarray) -> tuple[np.ndarray, int]:
    """Top-hat + CC filter → binary text mask.

    Returns (mask, n_surviving_blobs).
    If n_surviving_blobs < MIN_CC_BLOBS → caller should treat frame as NO_TEXT.
    """
    k = max(3, TOPHAT_KSIZE | 1)
    se = cv2.getStructuringElement(cv2.MORPH_RECT, (k, max(3, k // 4)))
    opened = cv2.morphologyEx(gray, cv2.MORPH_OPEN, se)
    tophat = cv2.subtract(gray, opened)

    _, mask = cv2.threshold(tophat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if MASK_DILATION > 0:
        dse = cv2.getStructuringElement(cv2.MORPH_RECT, (MASK_DILATION, max(2, MASK_DILATION // 3)))
        mask = cv2.dilate(mask, dse)

    total_px = gray.shape[0] * gray.shape[1]
    max_area_px = int(CC_MAX_AREA_FRAC * total_px)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    filt = np.zeros_like(mask)
    n_surv = 0
    for lbl in range(1, n_labels):
        h_b = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        w_b = int(stats[lbl, cv2.CC_STAT_WIDTH])
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if h_b < CC_MIN_H or h_b > CC_MAX_H:
            continue
        if w_b < CC_MIN_W:
            continue
        if w_b / max(1, h_b) < CC_MIN_ASPECT:
            continue
        if area > max_area_px:
            continue
        filt[labels == lbl] = 255
        n_surv += 1

    return filt, n_surv


def _frame_val(img_bgr: np.ndarray) -> float:
    """Mean HSV Value (brightness) in the inner vertical band of the frame.

    Credits on red/white backgrounds: typically val >= 110.
    Dark archival footage: val < 60.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h = img_bgr.shape[0]
    margin = max(1, int(h * BG_INNER_FRAC))
    inner_v = hsv[margin:h - margin, :, 2].astype(np.float32)
    return float(inner_v.mean())


def _bg_std(img_bgr: np.ndarray, text_mask: np.ndarray) -> float:
    """Std-dev of background pixels (not in text mask) in the inner vertical band.

    Low value (< ~20) = uniform background = credits frame.
    High value (> 30)  = complex background = scene footage → reject.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    h = gray.shape[0]
    margin = max(1, int(h * BG_INNER_FRAC))
    inner_g = gray[margin:h - margin]
    inner_m = text_mask[margin:h - margin]
    bg_pixels = inner_g[inner_m == 0].astype(np.float32)
    if bg_pixels.size < 100:
        return 0.0  # not enough pixels to judge → don't reject
    return float(bg_pixels.std())


def _estimate_dy_lk(
    prev_gray: np.ndarray,
    cur_gray: np.ndarray,
    text_mask: np.ndarray,
) -> float | None:
    """Estimate vertical displacement via sparse Lucas-Kanade on text regions.

    Returns median vertical displacement (positive = content moved DOWN in frame,
    i.e. text scrolling UP means dy < 0).
    Returns None if too few good features found.
    """
    pts = cv2.goodFeaturesToTrack(
        prev_gray,
        maxCorners=MAX_LK_CORNERS,
        qualityLevel=LK_QUALITY,
        minDistance=LK_MIN_DIST,
        mask=text_mask,
    )
    if pts is None or len(pts) < LK_MIN_GOOD:
        return None

    pts2, status, _ = cv2.calcOpticalFlowPyrLK(
        prev_gray, cur_gray, pts, None,
        winSize=(LK_WIN_SIZE, LK_WIN_SIZE),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )
    if pts2 is None or status is None:
        return None

    good_mask = status.ravel() == 1
    if good_mask.sum() < LK_MIN_GOOD:
        return None

    dy_vals = (pts2[good_mask, 0, 1] - pts[good_mask, 0, 1])
    return float(np.median(dy_vals))


def _estimate_dy_farneback(
    prev_gray: np.ndarray,
    cur_gray: np.ndarray,
    text_mask: np.ndarray,
) -> float:
    """Dense Farneback optical flow, median vy over text mask pixels."""
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, cur_gray, None,
        pyr_scale=0.5,
        levels=FARNEBACK_LEVELS,
        winsize=FARNEBACK_WIN,
        iterations=FARNEBACK_ITER,
        poly_n=5,
        poly_sigma=1.1,
        flags=0,
    )
    mask_bool = text_mask > 0
    if not mask_bool.any():
        return 0.0
    vy = flow[mask_bool, 1]  # vertical component
    return float(np.median(vy))


def _estimate_dy(
    prev_gray: np.ndarray,
    cur_gray: np.ndarray,
    text_mask: np.ndarray,
    method_log: list,
) -> float:
    """Try LK first; fall back to Farneback."""
    dy = _estimate_dy_lk(prev_gray, cur_gray, text_mask)
    if dy is not None:
        method_log.append("lk")
        return dy
    dy = _estimate_dy_farneback(prev_gray, cur_gray, text_mask)
    method_log.append("farneback")
    return dy


def _gdiff(g1: np.ndarray, g2: np.ndarray) -> float:
    return float(np.mean(np.abs(g1.astype(np.float32) - g2.astype(np.float32))))


def _unsharp(img: np.ndarray, amount: float = 0.6, sigma: float = 1.0) -> np.ndarray:
    """Light unsharp mask to recover small-text crispness lost to multi-frame
    blending. Mild amount avoids halos around the large headers / portrait photos."""
    blur = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1.0 + amount, blur, -amount, 0)


def _hann2d(h: int, w: int) -> np.ndarray:
    return (
        np.hanning(h).reshape(-1, 1).astype(np.float32)
        * np.hanning(w).reshape(1, -1).astype(np.float32)
    )


def _phase_corr_response(g1: np.ndarray, g2: np.ndarray, hann: np.ndarray) -> float:
    try:
        _, rsp = cv2.phaseCorrelate(
            g1.astype(np.float32) * hann,
            g2.astype(np.float32) * hann,
        )
        return float(rsp)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Accumulator canvas helpers
# ---------------------------------------------------------------------------

class AccumulatorCanvas:
    """Float32 accumulator canvas with per-pixel weight counting.

    Tracks:
      _sum   (H_max, W, 3)  float32  — sum of placed BGR pixel values
      _cnt   (H_max, W)     float32  — number of observations per pixel

    After all frames are placed, master = (_sum / max(1, _cnt)).clip(0, 255).

    Placement is done at integer row offsets. Sub-pixel offsets are tracked
    externally; caller converts to int before calling place().
    """

    def __init__(self, h_max: int, w: int) -> None:
        self.h_max = h_max
        self.w = w
        self._sum = np.zeros((h_max, w, 3), dtype=np.float64)
        self._cnt = np.zeros((h_max, w), dtype=np.float32)
        self.highest_row_written: int = 0   # inclusive high-water mark

    def place(self, img_bgr: np.ndarray, canvas_row0: int) -> None:
        """Add img_bgr rows starting at canvas_row0.

        img_bgr can be a full frame or a crop. Each row of img_bgr is added
        to the corresponding canvas row (canvas_row0 + i). This is the KEY
        operation: because canvas_row0 is derived from cumulative displacement,
        the SAME text line from different frames always lands on the SAME canvas
        rows, and multiple observations blend together (average = sharpen).
        """
        fh = img_bgr.shape[0]
        end_row = min(canvas_row0 + fh, self.h_max)
        if canvas_row0 < 0:
            # Frame starts before canvas top: clip
            src_start = -canvas_row0
            canvas_row0 = 0
        else:
            src_start = 0

        rows_to_place = end_row - canvas_row0
        if rows_to_place <= 0:
            return

        src_slice = img_bgr[src_start:src_start + rows_to_place]
        self._sum[canvas_row0:end_row] += src_slice.astype(np.float64)
        self._cnt[canvas_row0:end_row] += 1.0

        if end_row > self.highest_row_written:
            self.highest_row_written = end_row

    def place_gap(self, canvas_row0: int, height: int, gray_val: int = GAP_GRAY) -> None:
        end_row = min(canvas_row0 + height, self.h_max)
        rows = end_row - canvas_row0
        if rows <= 0:
            return
        # Write a solid-colored gap (observed once so it renders cleanly)
        gap_bgr = np.full((rows, self.w, 3), gray_val, dtype=np.float64)
        self._sum[canvas_row0:end_row] += gap_bgr
        self._cnt[canvas_row0:end_row] += 1.0
        if end_row > self.highest_row_written:
            self.highest_row_written = end_row

    def get_next_row(self) -> int:
        """First canvas row not yet written (high-water mark)."""
        return self.highest_row_written

    def finalize(self) -> np.ndarray:
        """Produce uint8 BGR master image from accumulated sum/count."""
        h = max(1, self.highest_row_written)
        cnt = self._cnt[:h].copy()
        cnt[cnt == 0] = 1.0  # avoid division by zero; unobserved rows stay black
        master = (self._sum[:h] / cnt[..., np.newaxis]).clip(0, 255).astype(np.uint8)
        return master


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

def run(
    frames: list[Path],
    out_dir: Path,
    *,
    source_fps: float = 6.0,
    verbose: bool = True,
) -> MosaicResult:
    """Build optical-flow mosaic from a sorted list of frame paths.

    Args:
        frames:     Sorted list of frame paths (Path objects).
        out_dir:    Output directory; will be created if missing.
        source_fps: FPS hint stored in debug.json (does not affect algorithm).
        verbose:    Print progress to stdout.

    Returns:
        MosaicResult with paths and statistics.
    """
    t0 = perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)

    n = len(frames)
    if n == 0:
        raise ValueError("frames list is empty")

    def log(msg: str) -> None:
        if verbose:
            print(f"  [OF-Mosaic] {msg}", flush=True)

    # Determine frame size from first readable frame
    fh = fw = None
    for fp in frames:
        img0 = _read(fp)
        if img0 is not None:
            fh, fw = img0.shape[:2]
            break
    if fh is None:
        raise RuntimeError("Could not read any frame")
    log(f"Frame size: {fw}x{fh}, total: {n} frames")

    total_px = fh * fw
    hann = _hann2d(fh, fw)

    # Accumulator canvas
    acc = AccumulatorCanvas(MAX_CANVAS_H, fw)

    # Cumulative sub-pixel offset tracking
    # offset_accum: how many pixels the content has scrolled since the start
    # of the current section.  When we place frame i, we place it at
    #   canvas_row0 = section_base_row + round(offset_accum)
    # where section_base_row is fixed at start of section.
    # Note: for a scroll-up sequence, dy from LK is negative (features move up
    # in frame coordinates), so content is moving up, meaning the canvas GROWS
    # downward.  We track cumulative |scroll| = cumulative downward canvas growth.
    section_base_row: int = 0    # canvas row where current section starts
    cum_scroll: float = 0.0      # cumulative content displacement (px, always >= 0 for upward scroll)
    # Note on sign convention:
    #   LK dy < 0 → features moved up → text scrolled UP → new content enters from bottom
    #   The canvas grows downward; cum_scroll tracks how many new canvas rows to allocate.
    #   Specifically: for frame i with cumulative displacement D pixels up,
    #   frame i's content starts at canvas row (section_base_row + D) — the text that
    #   was at the top of frame i is now D pixels down from section start.
    # For downward scroll (dy > 0): same logic inverted; handle via sign-aware offset.

    # For simplicity we handle both scroll directions.
    # cum_offset_signed: signed running sum of dy (positive = content drifted down in canvas)
    cum_offset_signed: float = 0.0

    # State machine
    state: str = "INIT"          # INIT | NO_TEXT | STATIC | SCROLL
    dy_buf: list[float] = []
    scroll_consec: int = 0
    static_consec: int = 0

    # Section tracking
    sections: list[dict] = []
    sec_id: int = 0
    n_static = 0
    n_scroll = 0
    n_cut = 0

    # Current section info for section log
    cur_section_start_frame: int = 0
    cur_section_start_row: int = 0
    cur_section_kind: str = "none"

    def _close_section(end_frame: int) -> None:
        nonlocal sec_id, n_static, n_scroll
        if cur_section_kind == "none":
            return
        sec = {
            "section_id": sec_id,
            "kind": cur_section_kind,
            "start_frame_idx": cur_section_start_frame,
            "end_frame_idx": end_frame,
            "start_row": cur_section_start_row,
            "end_row": acc.get_next_row(),
        }
        sections.append(sec)
        sec_id += 1
        if cur_section_kind == "static":
            n_static += 1
        elif cur_section_kind == "scroll":
            n_scroll += 1

    def _open_section(kind: str, frame_idx: int) -> None:
        nonlocal cur_section_kind, cur_section_start_frame, cur_section_start_row
        cur_section_kind = kind
        cur_section_start_frame = frame_idx
        cur_section_start_row = acc.get_next_row()

    # Per-frame debug records
    debug_frames: list[dict] = []

    prev_gray: np.ndarray | None = None
    prev_text_mask: np.ndarray | None = None
    method_log: list[str] = []

    for i, fp in enumerate(frames):
        if verbose and i % 200 == 0:
            log(f"  frame {i}/{n}  canvas_rows={acc.get_next_row()}  state={state}")

        img = _read(fp)
        if img is None:
            debug_frames.append({
                "frame_idx": i, "event": "read_error", "state": state,
                "has_text": False, "dy_raw": 0.0, "dy_sm": 0.0,
                "canvas_row": acc.get_next_row(),
            })
            prev_gray = None
            prev_text_mask = None
            continue

        if img.shape[:2] != (fh, fw):
            img = cv2.resize(img, (fw, fh), interpolation=cv2.INTER_AREA)

        gray = _gray(img)

        # Build text mask
        text_mask, n_blobs = _build_text_mask(gray)
        text_ratio = float(np.count_nonzero(text_mask)) / total_px
        # Background uniformity + brightness checks: reject scene footage
        _candidate = text_ratio >= MIN_TEXT_RATIO and n_blobs >= MIN_CC_BLOBS
        bg_std_val = _bg_std(img, text_mask) if _candidate else 0.0
        frame_val = _frame_val(img) if _candidate else 0.0
        is_uniform_bg = (bg_std_val <= BG_STD_MAX or bg_std_val == 0.0)
        is_bright_enough = (frame_val >= FRAME_VAL_MIN or frame_val == 0.0)
        has_text = _candidate and is_uniform_bg and is_bright_enough

        # Flow estimation
        dy_raw = 0.0
        gdiff_val = 0.0
        rsp_val = 1.0
        flow_method = "none"

        if prev_gray is not None and has_text and prev_text_mask is not None:
            ml: list[str] = []
            dy_raw = _estimate_dy(prev_gray, gray, text_mask, ml)
            flow_method = ml[0] if ml else "none"
            dy_raw = float(np.clip(dy_raw, -DY_CLIP, DY_CLIP))
            if abs(dy_raw) < DY_MIN_MAGNITUDE:
                dy_raw = 0.0
            gdiff_val = _gdiff(prev_gray, gray)
            rsp_val = _phase_corr_response(prev_gray, gray, hann)

        # Smooth dy
        if has_text and prev_text_mask is not None and prev_gray is not None:
            dy_buf.append(dy_raw)
            if len(dy_buf) > DRIFT_N * 4:
                dy_buf.pop(0)
        dy_sm = float(np.median(dy_buf[-DRIFT_N:])) if len(dy_buf) >= 2 else 0.0

        # Scene cut detection
        is_cut = (
            i > 0
            and rsp_val < CUT_RESPONSE_MAX
            and gdiff_val > CUT_GLOBAL_MIN
        )

        event = "none"

        if not has_text:
            event = "no_text"
            scroll_consec = 0
            static_consec = 0
            dy_buf.clear()
            if state not in ("NO_TEXT", "INIT"):
                _close_section(i - 1)
                _open_section("none", i)
            state = "NO_TEXT"

        elif is_cut:
            event = "cut"
            n_cut += 1
            _close_section(i - 1)
            # Insert gap
            gap_row = acc.get_next_row()
            acc.place_gap(gap_row, GAP_HEIGHT)
            # Reset offset tracking
            cum_offset_signed = 0.0
            section_base_row = acc.get_next_row()
            dy_buf.clear()
            scroll_consec = 0
            static_consec = 0
            _open_section("none", i)
            state = "NO_TEXT"

        else:
            # Update hysteresis counters
            if abs(dy_sm) >= S_HI:
                scroll_consec += 1
                static_consec = 0
            elif abs(dy_sm) < S_LO:
                static_consec += 1
                scroll_consec = 0
            # else in hysteresis band: keep current state, counters unchanged

            # Warm-up guard: don't commit to SCROLL until buffer has data
            buf_ready = len(dy_buf) >= min(DRIFT_N, 4)

            # State transitions
            if state != "SCROLL" and scroll_consec >= SCROLL_CONFIRM and buf_ready:
                if state == "STATIC":
                    _close_section(i - 1)
                    # Start new scroll section; base row is current canvas high-water
                    section_base_row = acc.get_next_row()
                    cum_offset_signed = 0.0
                elif state in ("NO_TEXT", "INIT"):
                    section_base_row = acc.get_next_row()
                    cum_offset_signed = 0.0
                _open_section("scroll", i)
                state = "SCROLL"
                event = "start_scroll"

            elif state != "STATIC" and static_consec >= STATIC_CONFIRM:
                if state == "SCROLL":
                    _close_section(i - 1)
                    section_base_row = acc.get_next_row()
                    cum_offset_signed = 0.0
                elif state in ("NO_TEXT", "INIT"):
                    section_base_row = acc.get_next_row()
                    cum_offset_signed = 0.0
                _open_section("static", i)
                state = "STATIC"
                event = "start_static"
            else:
                event = state.lower()

            # --- Place frame on accumulator canvas ---
            # Key insight:
            #   cum_offset_signed tracks how much the content has drifted
            #   since section_base_row was set.
            #   If text scrolls UP, dy is negative (features move up in frame coords).
            #   The text that was at pixel row R in frame 0 is now at row (R + cum) in
            #   the canvas — i.e. we need to place the frame such that its pixel row R
            #   maps to canvas row (section_base_row + cum).
            #   Equivalently: canvas_row_for_frame_top = section_base_row + round(cum)
            #   where cum = -cumulative_upward_drift (positive since scroll is upward).
            #
            #   For downward scroll (dy > 0): same equation, cum is negative → frame placed
            #   above section_base_row, correct for downward-scroll mosaics.

            if state in ("SCROLL", "STATIC"):
                # Accumulate displacement
                cum_offset_signed += dy_sm  # dy_sm < 0 for upward scroll
                # Sub-pixel placement: the frame's top maps to the CONTINUOUS
                # canvas coordinate row_float. Placing at int(round(...)) snaps to
                # the integer grid, so frames whose true offset differs by up to
                # ±0.5px get averaged while misaligned → small text blurs. Instead
                # we split into an integer row + fractional shift, and shift the
                # frame content DOWN by `frac` (sub-pixel, bilinear) so EVERY frame
                # aligns to the same canvas grid. The mean blend of precisely-aligned
                # observations is then sharp (true super-resolution), not smeared.
                row_float = section_base_row + (-cum_offset_signed)
                row_int = int(np.floor(row_float))
                frac = float(row_float - row_int)
                if 1e-3 < frac < 0.999:
                    M = np.float32([[1.0, 0.0, 0.0], [0.0, 1.0, frac]])
                    img_place = cv2.warpAffine(
                        img, M, (fw, fh),
                        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT,
                    )
                else:
                    img_place = img

                # Place the (sub-pixel-aligned) full frame
                acc.place(img_place, row_int)

        # Debug record
        debug_frames.append({
            "frame_idx": i,
            "event": event,
            "state": state,
            "has_text": has_text,
            "text_ratio": round(text_ratio, 4),
            "n_blobs": n_blobs,
            "bg_std": round(bg_std_val, 1),
            "frame_val": round(frame_val, 1),
            "dy_raw": round(dy_raw, 3),
            "dy_sm": round(dy_sm, 3),
            "flow_method": flow_method,
            "gdiff": round(gdiff_val, 2),
            "rsp": round(rsp_val, 4),
            "cum_offset_signed": round(cum_offset_signed, 2),
            "canvas_row": acc.get_next_row(),
        })

        prev_gray = gray
        prev_text_mask = text_mask if has_text else prev_text_mask

    # Close last open section
    _close_section(n - 1)

    # ---------------------------------------------------------------------------
    # Finalize and output
    # ---------------------------------------------------------------------------
    master = acc.finalize()
    master = _unsharp(master)  # crisp small scroll text softened by multi-frame blend
    mh, mw = master.shape[:2]
    log(f"Master canvas: {mw}x{mh} px")

    master_path = out_dir / "master.png"
    _write(master_path, master)
    log(f"Wrote master.png -> {master_path}")

    # Debug JSON
    runtime = perf_counter() - t0
    dbg: dict[str, Any] = {
        "engine": "optical_flow_mosaic",
        "run_params": {
            "source_fps": source_fps,
            "n_frames": n,
            "frame_size_wh": [fw, fh],
            "TOPHAT_KSIZE": TOPHAT_KSIZE,
            "MASK_DILATION": MASK_DILATION,
            "MIN_TEXT_RATIO": MIN_TEXT_RATIO,
            "CC_MIN_H": CC_MIN_H,
            "CC_MAX_H": CC_MAX_H,
            "CC_MIN_W": CC_MIN_W,
            "CC_MIN_ASPECT": CC_MIN_ASPECT,
            "MIN_CC_BLOBS": MIN_CC_BLOBS,
            "BG_STD_MAX": BG_STD_MAX,
            "FRAME_VAL_MIN": FRAME_VAL_MIN,
            "MAX_LK_CORNERS": MAX_LK_CORNERS,
            "LK_QUALITY": LK_QUALITY,
            "LK_WIN_SIZE": LK_WIN_SIZE,
            "LK_MIN_GOOD": LK_MIN_GOOD,
            "DRIFT_N": DRIFT_N,
            "DY_CLIP": DY_CLIP,
            "DY_MIN_MAGNITUDE": DY_MIN_MAGNITUDE,
            "S_LO": S_LO,
            "S_HI": S_HI,
            "SCROLL_CONFIRM": SCROLL_CONFIRM,
            "STATIC_CONFIRM": STATIC_CONFIRM,
            "CUT_RESPONSE_MAX": CUT_RESPONSE_MAX,
            "CUT_GLOBAL_MIN": CUT_GLOBAL_MIN,
        },
        "canvas_size_wh": [mw, mh],
        "n_static_blocks": n_static,
        "n_scroll_sections": n_scroll,
        "n_cut_events": n_cut,
        "runtime_sec": round(runtime, 2),
        "sections": sections,
        "frames": debug_frames,
    }

    debug_path = out_dir / "debug.json"
    debug_path.write_text(
        json.dumps(dbg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"Wrote debug.json -> {debug_path}")
    log(f"Done in {runtime:.1f}s  |  {n_static} static, {n_scroll} scroll, {n_cut} cuts")

    return MosaicResult(
        master_path=master_path,
        debug_path=debug_path,
        canvas_size=(mw, mh),
        sections=sections,
        n_static_blocks=n_static,
        n_scroll_sections=n_scroll,
        n_cut_events=n_cut,
        runtime_sec=round(runtime, 2),
    )
