"""
Overlap-Template Credit Mosaic Engine  v8
==========================================
Stitches a credit sequence (static cards + variable-speed scroll,
possibly moving background / letterbox) into ONE tall master PNG where
each text line appears EXACTLY ONCE.

ALGORITHM
---------
The canvas is grown by tracking frame-to-frame overlap.

Frame classification:
  - credit-like: density >= MIN_TEXT_DENSITY, few active rows, low BG std.
  - scene/black: skip, close section after CLOSE_AFTER consecutive skips.

For each credit frame, compare with PREVIOUS FRAME via cosine similarity on
top-hat text masks:

  sim >= STATIC_THRESH  -> same card held (dedup). Skip, append nothing.

  sim < SCENE_CUT_THRESH -> hard cut / new card. Close section, start new.

  otherwise (scroll/transition):
    1. Detect content region (letterbox-crop) in both prev and curr frame.
    2. In prev_content_mask, find bottom-most TEMPLATE_H strip with text.
       (floating search upward if bottom is empty).
    3. NCC-match that strip in curr_content_mask.
    4. Compute dy = scroll distance:
         text_end_prev_content - (match_y_in_content + TEMPLATE_H)
    5. Append frame[curr_top + text_end_curr_content :
                    curr_top + text_end_prev_content]
       This appends the CONTENT ROWS newly scrolled into view.
    6. If NCC score < NCC_CONF: fall back to new card.

MIN_SECTION_FRAMES: after a section break, suppress immediate re-break
  for MIN_SECTION_FRAMES frames (absorbs dissolve transitions).

NO per-frame velocity strip-writing.
NO cv2.imread/imwrite (Turkish-path trap) — np.fromfile+imdecode / imencode+tofile.
"""

from __future__ import annotations

import json
import os
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

# =====================================================================
# Constants
# =====================================================================

TEMPLATE_H        = 110     # height of prev-frame bottom strip for NCC
STATIC_THRESH     = 0.78    # cosine sim >= this -> same card, skip (lowered to absorb dissolve)
SCENE_CUT_THRESH  = 0.06    # cosine sim < this -> hard cut, new section
NCC_CONF          = 0.30    # NCC score threshold for scroll match
MIN_TEXT_DENSITY  = 0.008   # raised: excludes film-grain noise (was 0.0018)
MAX_ACTIVE_ROWS_F = 0.55    # for credit-frame classification
MAX_BG_COLOR_STD  = 45.0
MAX_NEW_ROWS_F    = 0.90    # safety cap on new rows per step
GAP_ROWS          = 4       # blank rows between sections
TOPHAT_W          = 27
TOPHAT_H          = 5
TOPHAT_THRESH     = 28      # raised: less film-grain sensitivity (was 18)
DILATE_ITER       = 1
CLOSE_AFTER       = 4       # non-credit streak before closing section
MIN_SECTION_FRAMES = 8      # minimum frames a section must have before newcard fires
                             # absorbs dissolve transitions within same card

# --- Style-agnostic film-rejection: connected-component shape filter ---
# A credit frame has >=2 text-LINE-shaped blobs (wide, short). Film scenes
# (faces, rooms, objects) produce large / square / non-line blobs → rejected.
# This is colour-AGNOSTIC (works for white-on-black scroll AND red cards), so it
# does NOT overfit to bright backgrounds the way a brightness gate would.
CC_MIN_H        = 5
CC_MAX_H        = 48        # taller than one text line → not a credit line
CC_MIN_W        = 40        # narrower → not a credit line
CC_MIN_ASPECT   = 1.5       # text lines are wide (w/h); faces/objects are ~square
CC_MAX_AREA_FRAC = 0.06     # a single blob covering >6% of frame → scene blob
MIN_CC_BLOBS    = 2         # need at least this many text-line blobs
# Dominant-background-colour coverage: a credit frame has ONE colour (red/black/
# white) covering most of the non-text area, even with a small portrait inset.
# Film scenes are colour-varied → low coverage. Combined with the CC blob gate
# (AND), a film frame must have BOTH text-line blobs AND a dominant colour to leak
# — white rooms lack blobs, busy closeups lack a dominant colour → both rejected.
DOMINANT_BG_MIN = 0.45


# =====================================================================
# Image helpers
# =====================================================================

def _imread(path: str) -> Optional[np.ndarray]:
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _imwrite(path: str, img: np.ndarray) -> None:
    ext = os.path.splitext(path)[1].lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise RuntimeError(f"imencode failed: {path}")
    buf.tofile(path)


def _tophat_mask(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (TOPHAT_W, TOPHAT_H))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, k)
    _, mask = cv2.threshold(tophat, TOPHAT_THRESH, 255, cv2.THRESH_BINARY)
    if DILATE_ITER > 0:
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=DILATE_ITER)
    return mask


def _density(mask: np.ndarray) -> float:
    return float(np.count_nonzero(mask)) / float(mask.size)


def _detect_content_rows(img: np.ndarray, threshold: int = 12) -> Tuple[int, int]:
    """
    Detect the first and last non-black rows (content region, excluding letterbox).
    Returns (top_row, bottom_row) inclusive.
    If no content found, returns (0, img.shape[0]-1).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    row_max = np.max(gray, axis=1)
    content = np.where(row_max > threshold)[0]
    if len(content) == 0:
        return 0, img.shape[0] - 1
    return int(content[0]), int(content[-1])


def _active_rows_frac(mask: np.ndarray) -> float:
    row_frac = np.sum(mask > 0, axis=1) / float(mask.shape[1])
    return float(np.sum(row_frac > 0.08)) / float(mask.shape[0])


def _bg_color_std(img: np.ndarray, mask: np.ndarray) -> float:
    bg = mask == 0
    if not np.any(bg):
        return 0.0
    return float(np.mean([float(np.std(img[:, :, c][bg])) for c in range(img.shape[2])]))


def _credit_blob_count(mask: np.ndarray) -> int:
    """Count text-LINE-shaped connected components (wide, short). Colour-agnostic
    film rejector: scene blobs (faces/objects) are square/large → not counted."""
    total = mask.shape[0] * mask.shape[1]
    max_area = int(CC_MAX_AREA_FRAC * total)
    n_labels, _labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    n = 0
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
        if area > max_area:
            continue
        n += 1
    return n


def _dominant_bg_frac(img: np.ndarray, mask: np.ndarray) -> float:
    """Fraction of non-text (background) pixels in the single most common coarse
    colour. Uniform credit bg (red/black/white) stays high even with a small
    portrait inset; textured film scenes are low. Colour-agnostic."""
    bg = mask == 0
    if int(np.count_nonzero(bg)) < 200:
        return 1.0
    px = (img[bg].astype(np.int32) // 40)   # ~7 levels per channel
    codes = px[:, 0] * 64 + px[:, 1] * 8 + px[:, 2]
    counts = np.bincount(codes)
    return float(counts.max()) / float(codes.shape[0])


def _is_credit(mask: np.ndarray, img: np.ndarray) -> bool:
    if _density(mask) < MIN_TEXT_DENSITY:
        return False
    if _active_rows_frac(mask) > MAX_ACTIVE_ROWS_F:
        return False
    if _bg_color_std(img, mask) > MAX_BG_COLOR_STD:
        return False
    # Style-agnostic shape gate: reject film scenes lacking text-line blobs.
    if _credit_blob_count(mask) < MIN_CC_BLOBS:
        return False
    # Dominant-colour gate (AND with the blob gate): credit bg is one colour.
    if _dominant_bg_frac(img, mask) < DOMINANT_BG_MIN:
        return False
    return True


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    af = a.astype(np.float32).ravel()
    bf = b.astype(np.float32).ravel()
    num = float(np.dot(af, bf))
    denom = float(np.sqrt(np.dot(af, af) * np.dot(bf, bf)))
    return num / denom if denom > 0 else 0.0


def _ncc_match(template: np.ndarray, target: np.ndarray) -> Tuple[int, float]:
    """NCC of template in target. Returns (match_y, score)."""
    res = cv2.matchTemplate(
        target.astype(np.float32),
        template.astype(np.float32),
        cv2.TM_CCOEFF_NORMED,
    )
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return int(max_loc[1]), float(max_val)


def _find_bottom_text_strip(mask: np.ndarray, strip_h: int) -> Tuple[np.ndarray, int]:
    """
    Find the bottom-most TEMPLATE_H-row strip in mask that contains text.
    Scans from bottom upward in steps.
    Returns (strip, offset_from_bottom) where offset_from_bottom is 0 if
    the strip is the literal bottom TEMPLATE_H rows, or positive if we
    had to scan upward.

    If no text found anywhere, returns the bottom strip with offset=0.
    """
    h, w = mask.shape
    # Try bottom strip first (offset=0)
    bottom = mask[h - strip_h:, :]
    if _density(bottom) >= MIN_TEXT_DENSITY:
        return bottom, 0
    # Scan upward in steps of strip_h//4
    step = max(10, strip_h // 4)
    for offset in range(step, h - strip_h, step):
        top_y = h - strip_h - offset
        strip = mask[top_y: top_y + strip_h, :]
        if _density(strip) >= MIN_TEXT_DENSITY:
            return strip, offset
    # Fallback: return bottom strip regardless
    return bottom, 0


# =====================================================================
# Post-process helpers (FILM-TRIM + CARD-DEDUP)
# =====================================================================

# FILM-TRIM: a section is considered non-credit if its seed frame fails _is_credit
# OR if its pixel height is below this fraction of the first real credit section's height.
# We identify the "main credit run" as the longest contiguous run of credit sections,
# then drop leading/trailing non-credit sections.
TRIM_MIN_BLOB_FRAC = 0.50  # seed frame must have at least this fraction of blobs vs max

# CARD-DEDUP: collapse adjacent sections whose seed-frame text masks have cosine sim
# above this threshold (they show the same card twice).
DEDUP_SIM_THRESH = 0.82


def _section_is_credit(seed_frame: np.ndarray) -> bool:
    """Return True if the seed frame of a section looks like a credit frame."""
    mask = _tophat_mask(seed_frame)
    return _is_credit(mask, seed_frame)


def _section_seed_mask(seed_frame: np.ndarray) -> np.ndarray:
    return _tophat_mask(seed_frame)


def _postprocess_sections(
    sections: List[dict],
    section_strips: List[List[np.ndarray]],
    section_seeds: List[np.ndarray],
    fw: int,
    verbose: bool,
) -> Tuple[List[dict], List[List[np.ndarray]]]:
    """Apply FILM-TRIM and CARD-DEDUP to the raw section list.

    Parameters
    ----------
    sections:        raw section metadata list
    section_strips:  per-section strip lists (same length as sections)
    section_seeds:   per-section seed images (same length as sections)
    fw:              frame width (for empty fallback)
    verbose:         print trim/dedup info

    Returns
    -------
    (filtered_sections, filtered_strips)
    """
    if not sections:
        return sections, section_strips

    n = len(sections)

    # ── FILM-TRIM ─────────────────────────────────────────────────────────────
    # Mark each section as credit-like or not.
    is_cred = [_section_is_credit(seed) for seed in section_seeds]

    # Also compute blob counts to identify obviously non-credit sections.
    blob_counts = []
    for seed in section_seeds:
        mask = _tophat_mask(seed)
        blob_counts.append(_credit_blob_count(mask))
    max_blobs = max(blob_counts) if blob_counts else 1

    # A section is definitely non-credit if:
    #   (a) its seed fails _is_credit, OR
    #   (b) its blob count < TRIM_MIN_BLOB_FRAC * max observed blobs
    def _sec_is_credit_strict(i: int) -> bool:
        if not is_cred[i]:
            return False
        if max_blobs > 0 and blob_counts[i] < TRIM_MIN_BLOB_FRAC * max_blobs:
            return False
        return True

    keep_flags = [_sec_is_credit_strict(i) for i in range(n)]

    # Keep ALL credit sections; drop ONLY non-credit (film/logo) sections.
    # (Previously kept only the single longest contiguous credit run, which
    #  wrongly dropped legitimate credit runs separated by film — e.g. SON METRO
    #  closing has the cast PORTRAIT CARDS, then film, then the song-scroll run.)
    # Credit test = _section_is_credit (uniform dominant-colour bg + text density),
    # which is DENSITY-AGNOSTIC: a sparse 1-name card and a dense song scroll both
    # pass. We do NOT penalise sparse cards by blob-count-vs-max (that wrongly
    # dropped the cast cards because the scroll has far more blobs).
    keep_idx: List[int] = [i for i in range(n) if is_cred[i]]
    if not keep_idx:
        keep_idx = list(range(n))  # safety: keep everything

    trimmed_sections = [sections[i] for i in keep_idx]
    trimmed_strips   = [section_strips[i] for i in keep_idx]
    trimmed_seeds    = [section_seeds[i] for i in keep_idx]

    n_dropped = n - len(keep_idx)
    if verbose and n_dropped:
        print(f"  [FILM-TRIM] dropped {n_dropped} non-credit sections "
              f"(kept {len(keep_idx)}/{n} credit sections)")

    # ── CARD-DEDUP ────────────────────────────────────────────────────────────
    # Compare ADJACENT sections pairwise; collapse if seed masks are near-identical.
    deduped_sections: List[dict] = []
    deduped_strips: List[List[np.ndarray]] = []

    if not trimmed_sections:
        return trimmed_sections, trimmed_strips

    deduped_sections.append(trimmed_sections[0])
    deduped_strips.append(trimmed_strips[0])
    prev_seed_mask = _section_seed_mask(trimmed_seeds[0])
    n_deduped = 0

    for i in range(1, len(trimmed_sections)):
        curr_seed_mask = _section_seed_mask(trimmed_seeds[i])
        sim = _cosine_sim(prev_seed_mask, curr_seed_mask)
        if sim >= DEDUP_SIM_THRESH:
            # Same card repeated — skip this section
            if verbose:
                print(f"  [CARD-DEDUP] collapsed section {keep_idx[i]} "
                      f"(sim={sim:.3f} >= {DEDUP_SIM_THRESH})")
            n_deduped += 1
        else:
            deduped_sections.append(trimmed_sections[i])
            deduped_strips.append(trimmed_strips[i])
            prev_seed_mask = curr_seed_mask

    if verbose and n_deduped:
        print(f"  [CARD-DEDUP] removed {n_deduped} duplicate adjacent card sections")

    return deduped_sections, deduped_strips


# =====================================================================
# Canvas
# =====================================================================

class _Canvas:
    def __init__(self, fh: int, fw: int):
        self.fh = fh
        self.fw = fw
        self.max_new = int(fh * MAX_NEW_ROWS_F)
        self._strips: List[np.ndarray] = []
        # Per-section strips: each section's strips are accumulated here until closed.
        self._section_strips: List[List[np.ndarray]] = []   # completed sections
        self._current_section_strips: List[np.ndarray] = []  # strips for the open section
        self._section_seeds: List[np.ndarray] = []           # seed image per section
        self._h: int = 0
        self._prev_mask: Optional[np.ndarray] = None  # full HxW mask of last appended frame
        self._prev_frame: Optional[np.ndarray] = None  # full HxWx3 last appended frame

    @property
    def height(self) -> int:
        return self._h

    def seed(self, frame: np.ndarray, mask: np.ndarray) -> None:
        self._current_section_strips = [frame.copy()]
        self._section_seeds_pending = frame.copy()
        self._strips.append(frame.copy())
        self._h = self.fh
        self._prev_mask = mask.copy()
        self._prev_frame = frame.copy()

    def append_gap(self) -> None:
        if GAP_ROWS <= 0:
            return
        self._strips.append(np.zeros((GAP_ROWS, self.fw, 3), dtype=np.uint8))
        self._h += GAP_ROWS
        # Don't reset prev_mask/frame - they come from last appended credit frame

    def close_section(self) -> None:
        """Finalize the current open section into _section_strips."""
        if self._current_section_strips:
            self._section_strips.append(list(self._current_section_strips))
            self._section_seeds.append(getattr(self, "_section_seeds_pending", self._current_section_strips[0]))
        self._current_section_strips = []

    def reseed(self, frame: np.ndarray, mask: np.ndarray) -> None:
        """Start a new section: append full frame, update prev references."""
        self._current_section_strips = [frame.copy()]
        self._section_seeds_pending = frame.copy()
        self._strips.append(frame.copy())
        self._h += self.fh
        self._prev_mask = mask.copy()
        self._prev_frame = frame.copy()

    def process(self, frame: np.ndarray, mask: np.ndarray) -> Tuple[str, int, float]:
        """
        Decide what to do with a new credit frame.

        Returns (action, new_rows, score):
          "dedup"    - same card, nothing appended
          "scroll"   - NCC match, new_rows appended
          "newcard"  - content changed -> caller handles section break
          "no_prev"  - no previous reference yet
        """
        if self._prev_mask is None:
            return "no_prev", 0, 1.0

        sim = _cosine_sim(self._prev_mask, mask)

        # --- Same card (static hold) ---
        if sim >= STATIC_THRESH:
            # Update prev to latest (keeps mask fresh for later comparison)
            self._prev_mask = mask.copy()
            self._prev_frame = frame.copy()
            return "dedup", 0, sim

        # --- Hard cut: completely different content ---
        if sim < SCENE_CUT_THRESH:
            return "newcard", 0, sim

        # --- Scroll / transition ---
        # Work in the CONTENT REGION only (letterbox-cropped) for NCC.
        # This ensures NCC is not anchored by black letterbox borders.
        prev_ctop, prev_cbot = _detect_content_rows(self._prev_frame)
        curr_ctop, curr_cbot = _detect_content_rows(frame)

        prev_content_mask = self._prev_mask[prev_ctop:prev_cbot+1, :]
        curr_content_mask = mask[curr_ctop:curr_cbot+1, :]

        curr_density = _density(curr_content_mask)
        tmpl, tmpl_offset = _find_bottom_text_strip(prev_content_mask, TEMPLATE_H)
        tmpl_density = _density(tmpl)

        if tmpl_density >= MIN_TEXT_DENSITY and curr_density >= MIN_TEXT_DENSITY:
            match_y_in_content, ncc_score = _ncc_match(tmpl, curr_content_mask)

            if ncc_score >= NCC_CONF:
                # Geometry (all coordinates in CONTENT space, not full frame space):
                #   Template occupies prev_content rows [ch-TEMPLATE_H-tmpl_offset .. ch-tmpl_offset]
                #   where ch = height of prev content region.
                #   Template found at match_y_in_content in curr_content.
                #   text_end_in_prev_content = ch_prev - tmpl_offset
                #   text_end_in_curr_content = match_y_in_content + TEMPLATE_H
                #   dy = text_end_in_prev_content - text_end_in_curr_content
                #   New rows in curr FULL FRAME: from (curr_ctop + text_end_in_curr_content)
                #                               to   (curr_ctop + text_end_in_prev_content)
                ch_prev = prev_cbot - prev_ctop + 1
                text_end_prev_c = ch_prev - tmpl_offset
                text_end_curr_c = match_y_in_content + TEMPLATE_H
                new_rows = max(0, min(text_end_prev_c - text_end_curr_c, self.max_new))
                if new_rows > 0:
                    # Convert back to full frame coordinates
                    strip_start_full = curr_ctop + text_end_curr_c
                    strip_end_full = curr_ctop + text_end_prev_c
                    strip_end_full = min(strip_end_full, self.fh)
                    strip = frame[strip_start_full:strip_end_full, :].copy()
                    self._strips.append(strip)
                    self._current_section_strips.append(strip)
                    self._h += new_rows
                self._prev_mask = mask.copy()
                self._prev_frame = frame.copy()
                return "scroll", new_rows, ncc_score

        # NCC failed -> treat as new card
        return "newcard", 0, sim

    def build(self) -> np.ndarray:
        if not self._strips:
            return np.zeros((1, self.fw, 3), dtype=np.uint8)
        return np.vstack(self._strips)

    def build_from_sections(self, section_strips: List[List[np.ndarray]]) -> np.ndarray:
        """Rebuild a master PNG from a filtered list of per-section strip lists.

        Gaps are reinserted between sections.
        """
        all_parts: List[np.ndarray] = []
        gap = np.zeros((GAP_ROWS, self.fw, 3), dtype=np.uint8) if GAP_ROWS > 0 else None
        for i, strips in enumerate(section_strips):
            if i > 0 and gap is not None:
                all_parts.append(gap)
            all_parts.extend(strips)
        if not all_parts:
            return np.zeros((1, self.fw, 3), dtype=np.uint8)
        return np.vstack(all_parts)


# =====================================================================
# Result
# =====================================================================

class MosaicResult:
    def __init__(self, master_path, width, height, total_frames, processed_frames,
                 sections, debug_path, runtime_s, constants):
        self.master_path = master_path
        self.width = width
        self.height = height
        self.total_frames = total_frames
        self.processed_frames = processed_frames
        self.sections = sections
        self.debug_path = debug_path
        self.runtime_s = runtime_s
        self.constants = constants


# =====================================================================
# Public API
# =====================================================================

def run(
    frames: List[str],
    out_dir: str,
    stride: int = 1,
    verbose: bool = True,
) -> MosaicResult:
    """Build a credit mosaic from sorted frame PNG paths."""
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)

    if not frames:
        raise ValueError("No frames")

    first = _imread(frames[0])
    fh, fw = first.shape[:2]

    if verbose:
        print(f"[mosaic] {len(frames)} frames  {fh}x{fw}  stride={stride}")
        print(f"[mosaic] TEMPLATE_H={TEMPLATE_H}  STATIC={STATIC_THRESH}  "
              f"CUT={SCENE_CUT_THRESH}  NCC={NCC_CONF}")

    canvas = _Canvas(fh, fw)
    sections: List[dict] = []
    alog: List[dict] = []

    seeded = False
    in_section = False
    sec_start = 0
    sec_y = 0
    sec_fi_start = 0   # frame index (in subset) when current section started
    non_credit_streak = 0

    frame_subset = frames[::stride]
    total = len(frame_subset)

    for fi, fpath in enumerate(frame_subset):
        fidx = fi * stride

        img = _imread(fpath)
        if img is None:
            if verbose:
                print(f"  [WARN] unreadable: {fpath}")
            continue

        mask = _tophat_mask(img)
        is_credit = _is_credit(mask, img)
        den = _density(mask)

        if fi % 100 == 0 and verbose:
            print(f"  [{fi:5d}/{total}] fidx={fidx:5d} den={den:.4f} "
                  f"cred={is_credit} h={canvas.height}")

        # --- Pre-seed ---
        if not seeded:
            if is_credit:
                canvas.seed(img, mask)
                seeded = True
                in_section = True
                sec_start = fidx
                sec_fi_start = fi
                sec_y = 0
                non_credit_streak = 0
                alog.append({"fi": fi, "fidx": fidx, "a": "seed", "d": round(den, 5)})
            else:
                alog.append({"fi": fi, "fidx": fidx, "a": "preseed_skip"})
            continue

        # --- Non-credit frame ---
        if not is_credit:
            non_credit_streak += 1
            alog.append({"fi": fi, "fidx": fidx, "a": "nc", "d": round(den, 5),
                         "streak": non_credit_streak})
            if in_section and non_credit_streak >= CLOSE_AFTER:
                canvas.close_section()
                sections.append({
                    "start_frame": sec_start, "end_frame": fidx,
                    "canvas_y_start": sec_y, "canvas_y_end": canvas.height,
                    "event": "closed_non_credit",
                })
                in_section = False
            continue

        non_credit_streak = 0

        # --- Resume after gap ---
        if not in_section:
            canvas.append_gap()
            canvas.reseed(img, mask)
            in_section = True
            sec_start = fidx
            sec_fi_start = fi
            sec_y = canvas.height - fh
            alog.append({"fi": fi, "fidx": fidx, "a": "reseed", "d": round(den, 5)})
            if verbose:
                print(f"  [NEW SECTION] fi={fi} fidx={fidx} h={canvas.height}")
            continue

        # --- Process credit frame ---
        action, new_rows, score = canvas.process(img, mask)
        alog.append({
            "fi": fi, "fidx": fidx, "a": action,
            "d": round(den, 5), "nr": new_rows, "sc": round(score, 4)
        })

        if action == "newcard":
            # Respect minimum section duration to absorb dissolve transitions
            sec_age = fi - sec_fi_start
            if sec_age < MIN_SECTION_FRAMES:
                # Too young - treat as dedup (still same card dissolving in)
                alog[-1]["a"] = "newcard_suppressed"
                continue
            canvas.close_section()
            sections.append({
                "start_frame": sec_start, "end_frame": fidx,
                "canvas_y_start": sec_y, "canvas_y_end": canvas.height,
                "event": "closed_newcard",
            })
            canvas.append_gap()
            canvas.reseed(img, mask)
            in_section = True
            sec_start = fidx
            sec_fi_start = fi
            sec_y = canvas.height - fh
            if verbose:
                print(f"  [NEW CARD] fi={fi} sc={score:.3f} h={canvas.height}")

    if in_section:
        canvas.close_section()
        sections.append({
            "start_frame": sec_start, "end_frame": len(frames) - 1,
            "canvas_y_start": sec_y, "canvas_y_end": canvas.height,
            "event": "final",
        })

    # ── POST-PROCESS: FILM-TRIM + CARD-DEDUP ─────────────────────────────────
    raw_section_count = len(sections)
    pp_sections, pp_strips = _postprocess_sections(
        sections,
        canvas._section_strips,
        canvas._section_seeds,
        fw,
        verbose,
    )
    sections = pp_sections
    postprocessed = len(pp_strips) < raw_section_count

    if verbose:
        print(f"[mosaic] Assembling h={canvas.height} "
              f"(raw_sections={raw_section_count} -> kept={len(pp_strips)}) ...")

    if postprocessed and pp_strips:
        final_img = canvas.build_from_sections(pp_strips)
    else:
        final_img = canvas.build()

    master_path = os.path.join(out_dir, "master.png")
    _imwrite(master_path, final_img)
    if verbose:
        print(f"[mosaic] Saved {master_path}  ({final_img.shape[1]}x{final_img.shape[0]})")

    constants = {
        "TEMPLATE_H": TEMPLATE_H, "STATIC_THRESH": STATIC_THRESH,
        "SCENE_CUT_THRESH": SCENE_CUT_THRESH, "NCC_CONF": NCC_CONF,
        "MIN_TEXT_DENSITY": MIN_TEXT_DENSITY, "MAX_ACTIVE_ROWS_F": MAX_ACTIVE_ROWS_F,
        "MAX_BG_COLOR_STD": MAX_BG_COLOR_STD, "MAX_NEW_ROWS_F": MAX_NEW_ROWS_F,
        "GAP_ROWS": GAP_ROWS, "TOPHAT_W": TOPHAT_W, "TOPHAT_H": TOPHAT_H,
        "TOPHAT_THRESH": TOPHAT_THRESH, "DILATE_ITER": DILATE_ITER,
        "CLOSE_AFTER": CLOSE_AFTER, "MIN_SECTION_FRAMES": MIN_SECTION_FRAMES,
    }
    runtime_s = time.time() - t0
    debug = {
        "master_path": master_path,
        "width": int(final_img.shape[1]),
        "height": int(final_img.shape[0]),
        "total_frames": len(frames),
        "processed_frames": total,
        "stride": stride,
        "sections": sections,
        "runtime_s": round(runtime_s, 2),
        "constants": constants,
        "alog_first100": alog[:100],
        "alog_last100": alog[-100:],
    }
    debug_path = os.path.join(out_dir, "debug.json")
    with open(debug_path, "w", encoding="utf-8") as f:
        json.dump(debug, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"[mosaic] Done {runtime_s:.1f}s  sections={len(sections)}")

    return MosaicResult(
        master_path=master_path,
        width=int(final_img.shape[1]),
        height=int(final_img.shape[0]),
        total_frames=len(frames),
        processed_frames=total,
        sections=sections,
        debug_path=debug_path,
        runtime_s=runtime_s,
        constants=constants,
    )