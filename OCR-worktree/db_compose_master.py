"""Standalone DATABASE -> master PNG composer (dual-mode, hardened).

Upgrade of the original db_compose_standalone.py with two engines:

  --mode slit    : hardened version of the original slit-scan pipeline.
  --mode mosaic  : two-pass, text-masked, motion-compensated vertical mosaic
                   (the "panoramic photo" approach). Estimates a single global
                   vertical offset per frame from TEXT (background ignored),
                   then composites every frame onto a tall canvas at its
                   integrated offset with mask-weighted blending. Static cards
                   and scrolling cast are handled by the same pass, no regime
                   switch, no per-box identity tracking.

Fixes vs the original (marked `# FIX:` inline):
  1. Resolution-normalized thresholds (calibrated to ~720x576 baseline).
  2. Natural frame sort (frame_2 < frame_10), not lexicographic.
  3. Polarity-aware text mask: tophat (bright-on-dark) OR blackhat
     (dark-on-bright), auto-detected per frame.
  4. Per-frame None guard: a corrupt/unreadable frame is skipped, not fatal.
  5. Slit strip height = actual motion (no artificial VMAX drop -> no content
     holes on fast scroll); only sub-pixel jitter and cut-residue are skipped.
  6. Optional --deinterlace (bob) fixes combing + the false-sharpness it causes.
  7. Cross-card dedup (dHash) so a repeated card is not OCR'd twice.
  8. Optional --hash-names to avoid output-folder collisions (off by default,
     keeps your existing db_masters layout untouched).
  9. Decode cache: each frame is read from disk once per segment, not 3-4x.
 10. luma-key wired to --luma-key (was dead code), manifest records source
     frame names for traceability.

Input  : F:/REPO_GitHub/DATABASE/<film>/{entry_frames,exit_frames}
Output : E:/MITAS/OCR-worktree/db_masters/<film_safe>/{giris,cikis}/master.png
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


DB = Path(r"F:\REPO_GitHub\DATABASE")
OUT = Path(r"E:\MITAS\OCR-worktree\db_masters")
SEGS = [("giris", "entry_frames"), ("cikis", "exit_frames")]

SLIT_FRAC = 0.55      # slit position as fraction of frame height
SEP_PX = 12           # black separator between stacked slit blocks
DUP_HAM = 8           # dHash hamming distance below which two cards are "same"
CONSEC_DUP = 14       # looser bound vs the IMMEDIATELY-previous block (kills "THE END" x2)
MAX_CANVAS_H = 80000  # mosaic safety cap to avoid OOM on pathological motion

# DEDUP-VETO: the coarse 8x8 dedup below MERGES distinct same-layout credit cards
# (role-left/name-right) -> a real card is dropped (kukla lost its crew card; x-men
# its "EDITED BY"). A 256-bit content hash (dhash_hi) VETOES the merge when content
# clearly differs. Completeness-safe by construction: only flips drop->keep, never
# keep->drop. Validated on 47 films (0 content loss). Default ON.
DEDUP_HIRES = os.environ.get("MITAS_MASTER_DEDUP_HIRES", "1") == "1"
DEDUP_HI_SIZE = int(os.environ.get("MITAS_DEDUP_HI_SIZE", "16"))
DEDUP_TDIFF = int(os.environ.get("MITAS_DEDUP_TDIFF", "40"))  # hi-res hamming above which two cards are DISTINCT (rescue)


# --------------------------------------------------------------------------- #
# resolution-normalized parameters
# --------------------------------------------------------------------------- #
@dataclass
class Params:
    h: int
    w: int
    thk: int          # tophat/blackhat kernel width
    tht: int          # morph binarize threshold (intensity, NOT scaled)
    min_h: int        # text component height bounds
    max_h: int
    min_w: int        # text component min width
    static_dy: float  # state-machine thresholds (slit)
    scroll_dy: float
    cut: float        # |dy| above this == cut / scene change
    vmin: float       # slit: ignore sub-pixel jitter below this
    vmax: float       # slit/mosaic: |dy| above this == glitch, skip / treat as cut
    pad: int          # padding around a detected card text band
    min_hold: int


def _odd(x: int) -> int:
    x = int(round(x))
    return x if x % 2 == 1 else x + 1


def derive_params(h: int, w: int, args) -> Params:
    # FIX(1): everything spatial is a fraction of frame size; the literals below
    # reproduce the original constants at the ~720x576 baseline they were tuned on.
    return Params(
        h=h,
        w=w,
        thk=max(9, _odd(0.021 * w)),       # was 15 @ w=720
        tht=args.tht,                       # intensity threshold, resolution-independent
        min_h=max(4, round(0.009 * h)),     # was 5  @ h=576
        max_h=max(12, round(0.18 * h)),     # was 52 @ h=576; loosened so big title cards pass
        min_w=max(18, round(0.055 * w)),    # was 40 @ w=720
        static_dy=0.0026 * h,               # was 1.5 @ h=576
        scroll_dy=0.0043 * h,               # was 2.5 @ h=576
        cut=0.07 * h,                        # was 40  @ h=576
        vmin=max(1.0, 0.0018 * h),           # was 1   @ h=576
        vmax=0.5 * h,                        # FIX(5): generous; only true glitches dropped
        pad=max(4, round(0.014 * h)),        # was 8   @ h=576
        min_hold=args.min_hold,
    )


# --------------------------------------------------------------------------- #
# IO + cache
# --------------------------------------------------------------------------- #
_CACHE: dict[str, np.ndarray] = {}
_CACHE_CAP = 2000  # credit sequences are small; cap just bounds memory


def clear_cache() -> None:
    _CACHE.clear()


def rd_cached(path: str | Path) -> np.ndarray | None:
    key = str(path)
    img = _CACHE.get(key)
    if img is not None:
        return img
    # FIX(4): imdecode returns None on a corrupt/missing file -> caller skips.
    try:
        img = cv2.imdecode(np.fromfile(key, np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        img = None
    if img is not None and len(_CACHE) < _CACHE_CAP:
        _CACHE[key] = img
    return img


def wr(path: str | Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"PNG encode failed: {path}")
    encoded.tofile(str(path))


def safe(name: str, hash_names: bool) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name).strip("_")
    if not hash_names:
        return slug[:70]
    # FIX(8): append a short content hash so two films that collapse to the
    # same first-70-chars slug don't overwrite each other.
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:60]}_{digest}"


def nat_sort_key(path: str):
    # FIX(2): sort by the last integer in the filename, falling back to name.
    name = Path(path).name
    nums = re.findall(r"\d+", name)
    return (int(nums[-1]) if nums else -1, name)


# --------------------------------------------------------------------------- #
# image helpers
# --------------------------------------------------------------------------- #
def deinterlace(image: np.ndarray) -> np.ndarray:
    # FIX(6): bob deinterlace - keep one field, line-double it. Kills combing
    # (which otherwise inflates Laplacian sharpness and breaks morphology).
    top = image[::2]
    return cv2.resize(top, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)


def luma_key(image: np.ndarray, thr: int = 150) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    out = np.zeros_like(image)
    out[gray > thr] = image[gray > thr]
    return out


def text_mask(gray: np.ndarray, p: Params, polarity: str = "auto") -> np.ndarray:
    # FIX(3): pick tophat or blackhat based on background brightness so dark
    # text on a light background is no longer silently missed.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (p.thk, 5))
    pol = polarity
    if pol == "auto":
        pol = "dark" if float(np.median(gray)) > 127 else "bright"
    op = cv2.MORPH_TOPHAT if pol == "bright" else cv2.MORPH_BLACKHAT
    morph = cv2.morphologyEx(gray, op, kernel)
    _, mask = cv2.threshold(morph, p.tht, 255, cv2.THRESH_BINARY)
    return mask


def has_text(mask: np.ndarray, p: Params) -> bool:
    # FIX: merge adjacent letters into a word-blob with a horizontal kernel before
    # labelling, so large display titles (tall, narrow per-letter) aren't rejected
    # by the per-letter aspect test that was tuned for small wide cast lines.
    kx = max(15, _odd(0.015 * p.w))
    merged = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (kx, 3)))
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(merged, 8)
    for label in range(1, n_labels):
        height = stats[label, cv2.CC_STAT_HEIGHT]
        width = stats[label, cv2.CC_STAT_WIDTH]
        if p.min_h <= height <= p.max_h and width >= p.min_w and width / max(1, height) >= 1.5:
            return True
    return False


def sharpv(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def text_band(mask: np.ndarray) -> tuple[int, int] | None:
    rows = np.where(mask.sum(axis=1) > 0)[0]
    if not rows.size:
        return None
    return int(rows.min()), int(rows.max())


def text_rows(mask: np.ndarray, p: Params) -> tuple[int, int] | None:
    """Row span of TEXT-like components only — wide-short word blobs, excluding
    big/square blobs (portraits, logos). So a card crops to its NAME line(s), not
    the photo + solid-colour void (son_metro: Deneuve's name, not her portrait)."""
    kx = max(15, _odd(0.015 * p.w))
    merged = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (kx, 3)))
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(merged, 8)
    spans = []
    for label in range(1, n_labels):
        y = int(stats[label, cv2.CC_STAT_TOP])
        hh = int(stats[label, cv2.CC_STAT_HEIGHT])
        ww = int(stats[label, cv2.CC_STAT_WIDTH])
        if p.min_h <= hh <= p.max_h and ww >= p.min_w and ww / max(1, hh) >= 1.5:
            spans.append((y, y + hh))
    if not spans:
        return None
    return min(a for a, _ in spans), max(b for _, b in spans)


def dhash(image: np.ndarray, size: int = 8) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (size + 1, size))
    diff = gray[:, 1:] > gray[:, :-1]
    bits = 0
    for value in diff.flatten():
        bits = (bits << 1) | int(value)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def dhash_hi(image: np.ndarray, size: int = DEDUP_HI_SIZE) -> int:
    """Higher-resolution dHash (default 16x16 = 256-bit) for the dedup-veto. Captures
    glyph-level differences the 8x8 dhash misses, so DISTINCT same-layout cards
    (x-men 'DIRECTOR OF PHOTOGRAPHY' vs 'EDITED BY') are not merged as duplicates."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (size + 1, size))
    diff = gray[:, 1:] > gray[:, :-1]
    bits = 0
    for value in diff.flatten():
        bits = (bits << 1) | int(value)
    return bits


# --------------------------------------------------------------------------- #
# content-based static-card split  (son_metro fix)
# --------------------------------------------------------------------------- #
# Why: split_runs() finds card boundaries from FULL-FRAME motion. When the
# background is a constant color (e.g. son_metro's red), the inter-card motion is
# ~0 (measured: 0 cuts over 318 frames) so a whole sequence of ~22 distinct cards
# collapses into ONE static run -> only one card kept, the rest of the cast lost.
# X-Men's cards sit on black, so the inter-card change is large (192 cuts) and
# split_runs separates them already. The text-mask dHash below is background-
# invariant: it tracks the TEXT layout, so it exposes the hidden card boundaries
# (measured: ~21-26 cards on son_metro, matching the truth). Debounced so a new
# layout must persist >= min_hold frames -> dissolves / 1-frame noise don't
# over-split, and X-Men's already-distinct cards are not broken up.
def _textmask_dhash(image: np.ndarray, p: Params, args) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = text_mask(gray, p, args.polarity)
    small = cv2.resize(mask, (9, 8), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    bits = 0
    for value in diff.flatten():
        bits = (bits << 1) | int(value)
    return bits


def split_static_cards(run_frames: list[str], p: Params, args) -> list[list[str]]:
    """Split a 'static' run into distinct cards by CONTENT (text-mask dHash).

    A boundary is a SUDDEN jump vs the PREVIOUS frame that then forms a STABLE
    plateau (held >= min_hold frames). Comparing consecutive frames (not a fixed
    reference) means a GRADUAL background drift -- kansas's panning map, drakula's
    flickering fire -- never trips a boundary (each step is small, nothing new
    stabilises), so a single held card is not split into copies. A real cut
    (son_metro: new name+portrait) is a big, sustained jump -> split."""
    same_thr = int(getattr(args, "card_same_thr", 6))
    min_hold = max(2, int(getattr(args, "card_min_hold", p.min_hold)))
    valid = []
    for i, frame in enumerate(run_frames):
        image = _prep(frame, p, args)
        if image is not None:
            valid.append((i, _textmask_dhash(image, p, args)))
    if len(valid) < 2:
        return [run_frames]

    bounds = [0]                          # run-frame index where each card starts
    k = 1
    while k < len(valid):
        idx, h = valid[k]
        prev_h = valid[k - 1][1]
        if hamming(h, prev_h) > same_thr:           # sudden change vs previous frame
            persist, j = 1, k + 1
            while j < len(valid) and hamming(valid[j][1], h) <= same_thr:
                persist += 1
                j += 1
            if persist >= min_hold:                 # new layout HELD -> a real card
                bounds.append(idx)
                k = j
                continue
        k += 1
    bounds.append(len(run_frames))
    return [run_frames[bounds[i]: bounds[i + 1]]
            for i in range(len(bounds) - 1) if bounds[i + 1] > bounds[i]]


def _prep(frame: str, p: Params, args) -> np.ndarray | None:
    """Read + (optional) deinterlace + size-normalize a frame, or None if unreadable."""
    image = rd_cached(frame)
    if image is None:
        return None
    if args.deinterlace:
        image = deinterlace(image)
    if image.shape[:2] != (p.h, p.w):
        image = cv2.resize(image, (p.w, p.h))
    return image


def first_readable(frames: list[str]):
    for frame in frames:
        image = rd_cached(frame)
        if image is not None:
            return image
    return None


# --------------------------------------------------------------------------- #
# MODE A: slit-scan
# --------------------------------------------------------------------------- #
def split_runs(frames: list[str], p: Params, args) -> list[list]:
    """Split timeline into static/scroll/cut runs via full-frame vertical motion."""
    hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
    prev = None
    abs_dy: list[float] = []

    for frame in frames:
        image = _prep(frame, p, args)
        if image is None:
            abs_dy.append(0.0)  # treat missing as no motion
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        dy = 0.0
        if prev is not None:
            (_, dy), _ = cv2.phaseCorrelate(prev * hann, gray * hann)
        prev = gray
        abs_dy.append(abs(dy))

    abs_dy_arr = np.array(abs_dy)
    is_cut = abs_dy_arr > p.cut
    smooth = np.array(
        [
            np.median(np.clip(abs_dy_arr, 0, p.cut)[max(0, i - 2): i + 3])
            for i in range(len(abs_dy_arr))
        ]
    )

    labels = []
    state = "S"
    for i, value in enumerate(smooth):
        if is_cut[i]:
            labels.append("C")
            continue
        if value < p.static_dy:
            state = "S"
        elif value > p.scroll_dy:
            state = "R"
        labels.append(state)

    runs = []
    start = 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start]:
            runs.append([start, i - 1, labels[start]])
            start = i

    return [
        run for run in runs
        if run[2] != "C" and (int(run[1]) - int(run[0]) + 1) >= p.min_hold
    ]


def slitscan(frames: list[str], p: Params, args) -> np.ndarray | None:
    hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
    ref = round(SLIT_FRAC * p.h)
    prev = None
    prev_has_text = False
    strips = []
    seed_top = None       # FIX: first frame's region ABOVE the slit (else it's lost)
    last_image = None
    last_v = 0

    for frame in frames:
        image = _prep(frame, p, args)
        if image is None:
            continue
        if args.luma_key:  # FIX(10): wired up, was dead code
            image = luma_key(image)
        if seed_top is None:
            seed_top = image[:ref, :].copy()
        last_image = image

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray_float = gray.astype(np.float32)
        mask = text_mask(gray, p, args.polarity)
        dilated = cv2.dilate(mask, np.ones((11, 11), np.uint8))
        masked = gray_float.copy()
        masked[dilated == 0] = 0.0

        dy = 0.0
        if prev is not None and bool(dilated.any()) and prev_has_text:
            (_, dy), _ = cv2.phaseCorrelate(prev * hann, masked * hann)
        prev = masked
        prev_has_text = bool(dilated.any())

        velocity = int(round(abs(dy)))
        # FIX(5): strip height == real motion; drop only jitter or glitch/cut.
        if velocity < p.vmin or velocity > p.vmax:
            continue
        strip = image[ref: ref + velocity, :].copy()
        if strip.shape[0] > 0:
            strips.append(strip)
            last_v = velocity

    if not strips:
        return None
    # FIX: prepend the first frame's above-slit content and append the last
    # frame's below-slit content so the head/tail of the roll aren't dropped.
    parts = []
    if seed_top is not None and seed_top.shape[0] > 0:
        parts.append(seed_top)
    parts.append(np.vstack(strips))
    if last_image is not None and ref + last_v < p.h:
        parts.append(last_image[ref + last_v:, :].copy())
    return np.vstack(parts)


def compose_slit(frames: list[str], p: Params, args) -> tuple[np.ndarray | None, list[dict]]:
    runs = split_runs(frames, p, args)
    blocks = []
    manifest = []
    seen_hashes: list[int] = []
    seen_text: list[int] = []   # text-mask hashes (bg-tolerant) for moving-bg dedup
    seen_hi: list[int] = []     # hi-res 256-bit content hashes (DEDUP_HIRES veto anchors)

    def _sharpest_with_text(card_frames):
        """Return (best_frame, best_image, best_mask) for the sharpest readable
        frame of a card, or (None, None, None) if none has text."""
        sh = []
        for frame in card_frames:
            image = _prep(frame, p, args)
            if image is None:
                continue
            sh.append((sharpv(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)), frame))
        if not sh:
            return None, None, None
        _, bf = max(sh, key=lambda item: item[0])
        bi = _prep(bf, p, args)
        bm = text_mask(cv2.cvtColor(bi, cv2.COLOR_BGR2GRAY), p, args.polarity)
        return bf, bi, bm

    for start, end, label in runs:
        si, ei = int(start), int(end)
        run_frames = frames[si: ei + 1]

        if label == "R":
            # scroll: gate on the sharpest frame, then slit-scan the whole run
            best_frame, _bi, best_mask = _sharpest_with_text(run_frames)
            if best_frame is None:
                manifest.append({"run": [si, ei], "lab": label, "skip": "unreadable"})
                continue
            if not has_text(best_mask, p):
                manifest.append({"run": [si, ei], "lab": label, "skip": "no-text"})
                continue
            block = slitscan(run_frames, p, args)
            if block is not None and block.size:
                blocks.append(block)
                manifest.append({"run": [si, ei], "lab": label, "kind": "scroll",
                                 "h": int(block.shape[0]), "src": Path(best_frame).name})
            else:
                manifest.append({"run": [si, ei], "lab": label, "skip": "empty"})
            continue

        # static run -> split into distinct cards by CONTENT (son_metro fix),
        # crop each to its TEXT rows (drop photo + solid-colour void), dedup on
        # the text crop (so different names are not merged like the old whole-card
        # dHash did on son_metro's near-identical red layouts).
        cards = [run_frames] if getattr(args, "no_card_split", False) else \
            split_static_cards(run_frames, p, args)
        for ci, card_frames in enumerate(cards):
            best_frame, best_image, best_mask = _sharpest_with_text(card_frames)
            if best_frame is None or not has_text(best_mask, p):
                manifest.append({"run": [si, ei], "card": ci, "lab": label, "skip": "no-text"})
                continue
            band = text_rows(best_mask, p) or text_band(best_mask)
            block = (
                best_image[max(0, band[0] - p.pad): min(best_image.shape[0], band[1] + p.pad), :]
                if band else None
            )
            if block is None or not block.size:
                manifest.append({"run": [si, ei], "card": ci, "lab": label, "skip": "empty"})
                continue
            if not args.no_dedup:
                # raw dHash catches identical-bg repeats; the text-mask dHash is
                # background-tolerant and catches a card repeated over a MOVING bg
                # (kansas drifting map) the raw hash misses. Neither fully cleans a
                # heavily-textured moving bg (drakula fire) -> some repeats remain.
                hh = dhash(block)
                thh = _textmask_dhash(block, p, args)
                consec = bool(seen_hashes) and hamming(hh, seen_hashes[-1]) <= CONSEC_DUP
                coarse_dup = (consec
                              or any(hamming(hh, ph) <= DUP_HAM for ph in seen_hashes)
                              or any(hamming(thh, pt) <= DUP_HAM for pt in seen_text))
                # HI-RES VETO: the coarse hashes above MERGE distinct same-layout cards
                # (role-left/name-right) -> a real card is dropped (kukla lost its crew
                # card; x-men its editors). If coarse says "drop" but the 256-bit content
                # hash differs from EVERY kept card by > DEDUP_TDIFF, the cards are
                # genuinely different -> KEEP. Only flips drop->keep, never keep->drop,
                # so it can never lose a coarse-kept card (worst case = old behavior + a
                # cosmetic fade-variant dup, which no geometric metric can separate from
                # a distinct card -> accepted; cosmetic dup << dropped real credit).
                hhi = None
                if DEDUP_HIRES and coarse_dup and seen_hi:
                    hhi = dhash_hi(block)
                    if min(hamming(hhi, ph) for ph in seen_hi) > DEDUP_TDIFF:
                        coarse_dup = False
                if coarse_dup:
                    manifest.append({"run": [si, ei], "card": ci, "lab": label, "kind": "card",
                                     "skip": "dup", "src": Path(best_frame).name})
                    continue
                seen_hashes.append(hh)
                seen_text.append(thh)
                if DEDUP_HIRES:
                    seen_hi.append(hhi if hhi is not None else dhash_hi(block))
            blocks.append(block)
            manifest.append({"run": [si, ei], "card": ci, "lab": label, "kind": "card",
                             "h": int(block.shape[0]), "src": Path(best_frame).name})

    if not blocks:
        return None, manifest, None

    max_width = max(block.shape[1] for block in blocks)
    normalized = [
        cv2.copyMakeBorder(block, 0, 0, 0, max_width - block.shape[1],
                           cv2.BORDER_CONSTANT, value=(0, 0, 0))
        if block.shape[1] < max_width else block
        for block in blocks
    ]
    stacked = []
    for block in normalized:
        stacked.append(block)
        stacked.append(np.zeros((SEP_PX, max_width, 3), np.uint8))
    return np.vstack(stacked[:-1]), manifest, None


# --------------------------------------------------------------------------- #
# MODE B: motion-compensated mosaic
# --------------------------------------------------------------------------- #
def estimate_offsets(frames: list[str], p: Params, args):
    """Pass 1: per-frame global vertical offset from TEXT motion (bg ignored)."""
    hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
    prev = None
    prev_any = False
    dys = []
    resp = []
    valid = []          # True only if phaseCorrelate actually ran for this frame
    dropped = 0

    for frame in frames:
        image = _prep(frame, p, args)
        if image is None:
            dropped += 1
            dys.append(0.0)
            resp.append(0.0)
            valid.append(False)
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = cv2.dilate(text_mask(gray, p, args.polarity), np.ones((11, 11), np.uint8))
        masked = gray.astype(np.float32)
        masked[mask == 0] = 0.0

        dy, r, measured = 0.0, 0.0, False
        if prev is not None and prev_any and bool(mask.any()):
            (_, dy), r = cv2.phaseCorrelate(prev * hann, masked * hann)
            measured = True
        prev = masked
        prev_any = bool(mask.any())
        dys.append(dy)
        resp.append(r)
        valid.append(measured)

    dys = np.array(dys)
    resp = np.array(resp)
    valid = np.array(valid)

    # FIX: a cut is only meaningful where we actually measured motion. The first
    # frame and any dropped/blank frame are NOT cuts (they used to be, because
    # their correlation peak is 0 -> they wrongly shoved the canvas).
    cut = valid & ((np.abs(dys) > p.cut) | (resp < args.cut_resp))

    # FIX: resolve dominant scroll direction up front so static->scroll segments
    # don't get mis-stacked by a post-integration flip.
    scroll_vals = dys[valid & ~cut]
    scroll_vals = scroll_vals[np.abs(scroll_vals) > p.vmin]
    sign = 1.0
    if scroll_vals.size and float(np.median(scroll_vals)) < 0:
        sign = -1.0
    if args.flip:
        sign = -sign

    clean = dys * sign
    clean[cut] = 0.0
    clean[~valid] = 0.0   # dropped / blank frame -> no advance
    clean = np.array([np.median(clean[max(0, i - 1): i + 2]) for i in range(len(clean))])
    return clean, cut, valid, dropped, dys, resp, sign


def _mosaic_debug(frames, raw, resp, valid, cut, clean, pos, sign) -> dict:
    return {
        "frames": [Path(f).name for f in frames],
        "dy_raw": [round(float(x), 3) for x in raw],
        "resp": [round(float(x), 4) for x in resp],
        "valid": [int(x) for x in valid],
        "cut": [int(x) for x in cut],
        "dy_used": [round(float(x), 3) for x in clean],
        "pos": [round(float(x), 2) for x in pos],
        "sign": float(sign),
    }


def compose_mosaic(frames: list[str], p: Params, args):
    """Pass 2: integrate offsets, composite frames with mask-weighted blend.

    Returns (master | None, manifest, debug | None).
    """
    clean, cut, valid, dropped, raw, resp, sign = estimate_offsets(frames, p, args)

    pos = np.zeros(len(frames))
    acc = 0.0
    for i in range(len(frames)):
        if i == 0:
            continue
        # A cut pushes a full frame down so pre/post-cut content does not overlap.
        acc += p.h if cut[i] else clean[i]
        pos[i] = acc

    # direction already resolved in estimate_offsets; just normalize to >= 0.
    pos -= pos.min()
    debug = _mosaic_debug(frames, raw, resp, valid, cut, clean, pos, sign) if args.debug else None

    canvas_h = int(round(pos.max())) + p.h
    if canvas_h > MAX_CANVAS_H:
        return None, {"mode": "mosaic", "frames": len(frames),
                      "err": f"canvas too tall ({canvas_h}px); motion likely noisy"}, debug

    # BLOAT / CUT-STORM guard: on scroll or noisy motion the offset integration
    # runs away (measured: diriliş 136x/0.39, yalaza 88x/0.37). A GOOD footage
    # static-card mosaic stays small (measured: drakula 3.7x/0.005 = clean cast,
    # once). Reject > 5x or cut-storm > 0.25 -> catches the catastrophes, keeps the
    # clean small ones; the (always-built) slit takes over when rejected.
    bloat = canvas_h / max(1.0, float(p.h))
    cut_frac = float(cut.sum()) / max(1, len(frames))
    if bloat > 5.0 or cut_frac > 0.25:
        return None, {"mode": "mosaic", "frames": len(frames), "reject": True,
                      "bloat": round(bloat, 2), "cut_frac": round(cut_frac, 3),
                      "err": f"reject mosaic: bloat {bloat:.1f}x / cut-storm {cut_frac:.2f}"}, debug

    acc_img = np.zeros((canvas_h, p.w, 3), np.float32)
    wsum = np.zeros((canvas_h, p.w), np.float32)
    # eps lets background contribute faintly; --text-only sets it to 0 so only
    # masked text composites and everything else stays pure black (OCR-ready).
    eps = 0.0 if args.text_only else 0.05
    used = 0

    for i, frame in enumerate(frames):
        image = _prep(frame, p, args)
        if image is None:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = cv2.dilate(text_mask(gray, p, args.polarity), np.ones((5, 5), np.uint8))
        weight = mask.astype(np.float32) / 255.0 + eps  # text dominates, bg ~ eps
        y0 = int(round(pos[i]))
        y0 = max(0, min(y0, canvas_h - p.h))
        acc_img[y0: y0 + p.h] += image.astype(np.float32) * weight[..., None]
        wsum[y0: y0 + p.h] += weight
        used += 1

    wsum[wsum == 0] = 1.0
    master = (acc_img / wsum[..., None]).clip(0, 255).astype(np.uint8)

    # crop to the rows that actually carry text
    full_mask = text_mask(cv2.cvtColor(master, cv2.COLOR_BGR2GRAY), p, args.polarity)
    rows = np.where(full_mask.sum(axis=1) > 0)[0]
    if not rows.size:
        return None, {"mode": "mosaic", "frames": len(frames), "used": used,
                      "dropped": int(dropped), "master": None}, debug
    a = max(0, int(rows.min()) - p.pad)
    b = min(master.shape[0], int(rows.max()) + p.pad)
    master = master[a:b]

    manifest = {
        "mode": "mosaic",
        "frames": len(frames),
        "used": used,
        "dropped": int(dropped),
        "cuts": int(cut.sum()),
        "canvas": [int(master.shape[1]), int(master.shape[0])],
    }
    return master, manifest, debug


# --------------------------------------------------------------------------- #
# debug instrumentation
# --------------------------------------------------------------------------- #
def write_debug(base: Path, debug: dict) -> None:
    """Dump per-frame motion estimate. CSV always; PNG plot if matplotlib exists.

    Columns: idx, frame, dy_raw, resp, valid, cut, dy_used, pos
      dy_raw : raw vertical shift from text-masked phase correlation
      resp   : correlation peak (low -> poor match -> likely cut/bg-lock)
      valid  : 1 if phaseCorrelate actually ran (prev+cur both had text)
      cut    : 1 if this frame was treated as a scene cut (canvas pushed)
      dy_used: shift after sign-resolve + cut-zero + median smoothing
      pos    : integrated canvas position (where the frame was placed)
    Look for: pos going flat then jumping, resp collapsing, or runs of cut=1
    inside what should be smooth scroll -> that frame range is the culprit.
    """
    csv_path = base.with_suffix(".debug.csv")
    rows = ["idx,frame,dy_raw,resp,valid,cut,dy_used,pos"]
    fr = debug["frames"]
    for i in range(len(fr)):
        rows.append(
            f'{i},{fr[i]},{debug["dy_raw"][i]},{debug["resp"][i]},'
            f'{debug["valid"][i]},{debug["cut"][i]},{debug["dy_used"][i]},{debug["pos"][i]}'
        )
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        idx = list(range(len(fr)))
        cut_idx = [i for i in idx if debug["cut"][i]]
        fig, ax = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
        ax[0].plot(idx, debug["pos"], lw=1.2)
        for c in cut_idx:
            ax[0].axvline(c, color="r", alpha=0.35, lw=0.8)
        ax[0].set_ylabel("pos (canvas y)")
        ax[0].set_title(f"{base.name}  (red = detected cut)  sign={debug['sign']}")
        ax[1].plot(idx, debug["dy_raw"], lw=0.8, label="dy_raw")
        ax[1].plot(idx, debug["dy_used"], lw=1.0, label="dy_used")
        ax[1].axhline(0, color="k", lw=0.5)
        ax[1].set_ylabel("dy / frame")
        ax[1].legend(loc="upper right")
        ax[2].plot(idx, debug["resp"], lw=0.8, color="g")
        ax[2].set_ylabel("corr peak")
        ax[2].set_xlabel("frame index")
        fig.tight_layout()
        fig.savefig(base.with_suffix(".debug.png"), dpi=110)
        plt.close(fig)
    except Exception:
        pass  # matplotlib not installed -> CSV is enough



def process_film(film_dir: Path, out_dir: Path, args) -> dict:
    result = {"film": film_dir.name}
    modes = ["slit", "mosaic"] if args.mode == "both" else [args.mode]

    for seg, subdir in SEGS:
        if args.seg and seg != args.seg:
            continue
        clear_cache()  # FIX(9): bound cache memory per segment

        frames = sorted(glob.glob(str(film_dir / subdir / "*.png")), key=nat_sort_key)
        film_safe = safe(film_dir.name, args.hash_names)
        segment_dir = out_dir / film_safe / seg
        segment_dir.mkdir(parents=True, exist_ok=True)

        if not frames:
            (segment_dir / "manifest.json").write_text("{}", encoding="utf-8")
            result[seg] = {"frames": 0}
            continue

        first = first_readable(frames)
        if first is None:
            (segment_dir / "manifest.json").write_text("{}", encoding="utf-8")
            result[seg] = {"frames": len(frames), "err": "no readable frame"}
            continue
        h, w = first.shape[:2]
        if args.deinterlace:
            h = deinterlace(first).shape[0]
        p = derive_params(h, w, args)

        # ----- legacy explicit modes (slit / mosaic / both) for debugging -----
        if args.mode != "master":
            seg_result = {}
            for mode in modes:
                stem = "master" if args.mode != "both" else f"master_{mode}"
                mpath = segment_dir / f"{stem}.png"
                manifest_path = segment_dir / (f"{stem}.json" if args.mode == "both" else "manifest.json")
                if mpath.exists() and not args.overwrite:
                    seg_result[mode] = {"skip": "exists", "path": str(mpath)}
                    continue
                try:
                    if mode == "slit":
                        master, manifest, debug = compose_slit(frames, p, args)
                    else:
                        master, manifest, debug = compose_mosaic(frames, p, args)
                    if master is not None:
                        wr(mpath, master)
                        if args.flat_out is not None:
                            args.flat_out.mkdir(parents=True, exist_ok=True)
                            tag = seg if args.mode != "both" else f"{seg}_{mode}"
                            wr(args.flat_out / f"{film_safe}__{tag}.png", master)
                        seg_result[mode] = {"frames": len(frames),
                                            "master": [int(master.shape[1]), int(master.shape[0])],
                                            "path": str(mpath)}
                    else:
                        seg_result[mode] = {"frames": len(frames), "master": None,
                                            "note": manifest.get("err", "no text") if isinstance(manifest, dict) else "no text"}
                    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                    if args.debug and debug is not None:
                        write_debug(mpath, debug)
                        seg_result[mode]["debug"] = str(mpath.with_suffix(".debug.csv"))
                except Exception as exc:
                    seg_result[mode] = {"frames": len(frames), "err": repr(exc)[:200]}
            result[seg] = seg_result if args.mode == "both" else seg_result[modes[0]]
            continue

        # ----- smart "master" mode: slit canonical + optional mosaic candidate -----
        master_path = segment_dir / "master.png"
        if master_path.exists() and not args.overwrite:
            result[seg] = {"skip": "exists", "path": str(master_path)}
            continue

        info = {"frames": len(frames), "h": int(h), "w": int(w), "flags": [], "warnings": []}
        try:
            runs = split_runs(frames, p, args)
            s_frames = sum((int(r[1]) - int(r[0]) + 1) for r in runs if r[2] == "S")
            r_frames = sum((int(r[1]) - int(r[0]) + 1) for r in runs if r[2] == "R")
            tot = max(1, s_frames + r_frames)
            scroll_frac = r_frames / tot
            info["regime"] = {"runs": len(runs), "static_frames": s_frames,
                              "scroll_frames": r_frames, "scroll_frac": round(scroll_frac, 3)}

            # canonical = slit (scroll via slit-scan + multi-card static via content split)
            slit_master, slit_manifest, _ = compose_slit(frames, p, args)
            kept = [m for m in slit_manifest if isinstance(m, dict) and "h" in m and "skip" not in m]
            n_blocks = len(kept)
            n_card = sum(1 for m in kept if m.get("kind") == "card")
            n_scroll = sum(1 for m in kept if m.get("kind") == "scroll")
            info["slit_blocks"] = n_blocks
            info["card_blocks"] = n_card
            info["scroll_blocks"] = n_scroll
            if slit_master is not None:
                wr(segment_dir / "master_slit.png", slit_master)

            # secondary candidate: mosaic, only on card-heavy films (skip on scroll
            # for speed; it self-rejects on runaway anyway)
            mosaic_master, mos_meta = None, {}
            if scroll_frac < 0.5:
                mosaic_master, mos_meta, _ = compose_mosaic(frames, p, args)
                if mosaic_master is not None:
                    wr(segment_dir / "master_mosaic.png", mosaic_master)
            if isinstance(mos_meta, dict) and mos_meta.get("reject"):
                info["flags"].append("bloat" if mos_meta.get("bloat", 0) > 5 else "cut_storm")
                info["mosaic_reject"] = {k: mos_meta[k] for k in ("bloat", "cut_frac") if k in mos_meta}

            # dispatch: a footage card film with SOME motion (0.10-0.40 scroll) and
            # a VALID (non-bloated) mosaic prefers it -- the motion-comp blend aligns
            # and renders the card sequence ONCE (drakula cast on moving fire), where
            # slit's per-card split repeats over the moving bg. PURE-static films
            # (scroll ~0, kansas) are kept on slit: their mosaic just averages
            # distinct cards into a GHOST. Scroll + rejected-mosaic films keep slit.
            # FIX A: prefer mosaic ONLY when it did not COLLAPSE. A truncated mosaic
            # (motion-comp integration ran away / averaged to ~one card) is shorter
            # than ~1.6 frame-heights and drops most of the roll; the slit candidate
            # keeps the full card sequence. Guarding on mosaic height routes those to
            # slit. (Verified: only flips the collapsed-mosaic case; non-collapsed
            # mosaic films and all slit films are unchanged.)
            mosaic_ok = mosaic_master is not None and mosaic_master.shape[0] >= 1.6 * h
            if mosaic_ok and 0.10 <= scroll_frac < 0.40:
                canonical, info["selected_mode"] = mosaic_master, "mosaic"
            elif slit_master is not None:
                canonical, info["selected_mode"] = slit_master, "slit"
            elif mosaic_master is not None:
                canonical, info["selected_mode"] = mosaic_master, "mosaic"
            else:
                canonical, info["selected_mode"] = None, None

            if canonical is None:
                info["status"] = "NO_OUTPUT"
                info["flags"].append("no_output")
            else:
                wr(master_path, canonical)
                if args.flat_out is not None:
                    args.flat_out.mkdir(parents=True, exist_ok=True)
                    wr(args.flat_out / f"{film_safe}__{seg}.png", canonical)
                info["status"] = "OK"
                info["master"] = [int(canonical.shape[1]), int(canonical.shape[0])]
                # upstream flags (free, structural) — composer FLAGS, does not fix
                if canonical.shape[0] < int(1.6 * h):
                    info["flags"].append("very_short_master")
                # single_card = ONE card and NO scroll (a real scroll block is not "single card")
                if n_card <= 1 and n_scroll == 0:
                    info["flags"].append("single_card_only")
                if "very_short_master" in info["flags"] and "single_card_only" in info["flags"]:
                    info["flags"].append("no_cast")
                    info["warnings"].append("kredi yok gibi (tek kart / cok kisa) -> upstream klip?")

            info["slit_manifest"] = slit_manifest
            if mos_meta:
                info["mosaic_manifest"] = mos_meta
        except Exception as exc:
            import traceback
            info["status"] = "ERROR"
            info["err"] = repr(exc)[:300]
            info["trace"] = traceback.format_exc()[-700:]

        (segment_dir / "manifest.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        result[seg] = {k: info.get(k) for k in ("status", "selected_mode", "master", "flags", "frames")}

    return result


def select_films(db_root: Path, film_filter: str | None, start: int, count: int) -> list[Path]:
    dirs = sorted([path for path in db_root.iterdir() if path.is_dir()], key=lambda p: p.name)
    if film_filter:
        needle = film_filter.lower()
        matches = [path for path in dirs if needle in path.name.lower()]
        if len(matches) > 1:
            # FIX(12): don't silently swallow extra matches.
            print(f"[warn] --film '{film_filter}' matched {len(matches)} films; "
                  f"using '{matches[0].name}'. Others: "
                  f"{', '.join(m.name for m in matches[1:4])}"
                  + (" ..." if len(matches) > 4 else ""), flush=True)
        return matches[:1]
    return dirs[start: start + count]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--db-root", type=Path, default=DB)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--flat-out", type=Path, default=None)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--film", default=None, help="substring -> single film")
    parser.add_argument("--seg", choices=["giris", "cikis"], default=None)
    parser.add_argument("--overwrite", action="store_true")
    # engine
    parser.add_argument("--mode", choices=["master", "slit", "mosaic", "both"], default="master",
                        help="master (default) = smart dispatch: canonical master.png (slit + content "
                             "card-split) + mosaic candidate + flags. slit/mosaic/both = legacy debug.")
    parser.add_argument("--no-card-split", action="store_true",
                        help="disable content-based static-card splitting (son_metro fix)")
    parser.add_argument("--card-same-thr", type=int, default=6,
                        help="text-mask dHash hamming <= this == same held card")
    parser.add_argument("--card-min-hold", type=int, default=5,
                        help="a new card layout must persist >= this many frames (debounce)")
    parser.add_argument("--polarity", choices=["auto", "bright", "dark"], default="auto",
                        help="bright=light text/dark bg, dark=dark text/light bg")
    parser.add_argument("--deinterlace", action="store_true",
                        help="bob deinterlace for interlaced SD content")
    parser.add_argument("--no-dedup", action="store_true",
                        help="slit: keep duplicate cards instead of dropping them")
    parser.add_argument("--luma-key", action="store_true",
                        help="slit: keep only bright pixels before slit-scan")
    parser.add_argument("--text-only", action="store_true",
                        help="mosaic: drop the background, composite only text on black (OCR-ready)")
    parser.add_argument("--debug", action="store_true",
                        help="mosaic: dump per-frame motion estimate (CSV + plot) next to master")
    parser.add_argument("--hash-names", action="store_true",
                        help="append a hash to output folder names (avoids collisions)")
    parser.add_argument("--flip", action="store_true",
                        help="mosaic: force-flip vertical stacking direction")
    # tunables (kept as flags so you can A/B without editing the file)
    parser.add_argument("--tht", type=int, default=22, help="morph binarize threshold")
    parser.add_argument("--min-hold", type=int, default=5, help="slit: min frames per run")
    parser.add_argument("--cut-resp", type=float, default=0.05,
                        help="mosaic: phaseCorrelate peak below this == cut")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    selected = select_films(args.db_root, args.film, args.start, args.count)
    total = len([path for path in args.db_root.iterdir() if path.is_dir()])
    print(
        f"=== DB-COMPOSE [{args.mode}]: {len(selected)} film "
        f"(total {total}; range {args.start}-{args.start + args.count}) ===",
        flush=True,
    )

    def _brief(entry):
        if not entry:
            return "-"
        if "slit" in entry or "mosaic" in entry:   # --mode both -> nested
            return " ".join(
                f"{m}:{v.get('master') or v.get('skip') or v.get('err') or v.get('frames')}"
                for m, v in entry.items()
            )
        return str(entry.get("master") or entry.get("skip")
                   or entry.get("frames") or entry.get("err"))

    summary = []
    for offset, film_dir in enumerate(selected):
        t0 = time.time()
        record = process_film(film_dir, args.out, args)
        elapsed = round(time.time() - t0, 1)
        print(
            f"[{args.start + offset:3}] {film_dir.name[:46]:46} | "
            f"giris:{_brief(record.get('giris', {}))} "
            f"cikis:{_brief(record.get('cikis', {}))} "
            f"({elapsed}s)",
            flush=True,
        )
        summary.append(record)

    suffix = f"{args.mode}_{args.start}_{args.start + args.count}"
    if args.seg:
        suffix = f"{suffix}_{args.seg}"
    summary_path = args.out / f"_SUMMARY_{suffix}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {summary_path}", flush=True)


if __name__ == "__main__":
    main()
