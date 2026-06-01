"""OCR Line-Based Temporal Dedup — credit mosaic engine.

Each text LINE is detected in every frame, grouped into temporal tracks by
(normalized-text similarity + y-position continuity), deduplicated so each
unique logical line appears exactly once, then the best crop of each unique
line is stacked into one tall master PNG.

Method mirrors academic "video text temporal redundancy" approaches and reuses
track-building ideas from core/pipelines/ocr/text_layer_descroll.py.

Input OCR source:
  - unified/<segment>/cards/card_*.json  (static card lines, best_frame_path + bbox)
  - unified/<segment>/scroll/scroll_text_lines.json  (scroll composite, canvas only)
  - PLUS fresh per-frame PaddleOCR on raw frames for temporal per-frame lines

Track building:
  - Group per-frame detections into tracks by normalized-text SequenceMatcher
    ratio > TRACK_MERGE_RATIO and y-center within Y_BAND_PX pixels
  - Dedup across tracks: SequenceMatcher ratio > DEDUP_RATIO → keep best-quality
  - Order: card lines first (by timestamp), then scroll lines (by track median-y)

Render quality (v2):
  - Card-sourced lines: grouped by best_frame, rendered as ONE generous card crop
    (not per-line thin slivers). Best frame chosen by local contrast (std-dev).
  - Scroll lines: per-line band as before.
  - Light unsharp mask on final master (sigma=1.0, amount=0.6) to crisp small text.
  - Tighter boundary dedup: overlapping bboxes from same frame collapse.

Output:
  - master.png  — full-width bands stacked top-to-bottom, one per unique line
  - debug.json  — dedup stats, track counts, line list
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# ── tunables ──────────────────────────────────────────────────────────────────
FRAME_STRIDE: int = 8          # OCR every Nth frame (credits move slowly; 8 still sees each line)
TRACK_MERGE_RATIO: float = 0.88  # SequenceMatcher ratio to merge detections → track
Y_BAND_PX: float = 30.0        # max |Δy_center| to merge into same track
DEDUP_RATIO: float = 0.82      # ratio above which two tracks are considered same line
SUBSET_DEDUP: bool = True      # also dedup if one norm is substring of the other
MIN_CONFIDENCE: float = 0.45   # drop detections below this (raised to cut noise)
BAND_PAD_Y: int = 6            # px padding above/below bbox for crop band
MASTER_WIDTH: int = 800        # output PNG width (crops rescaled to this)
MIN_ALPHA_CHARS: int = 3       # minimum alphabetic chars to accept a detection
# Cheap text-gate: skip film/blank frames BEFORE the expensive OCR call. Top-hat
# highlights bright thin strokes (credit text) regardless of background colour;
# film scenes are smooth → low density → skipped. Big speedup + drops film-text noise.
TEXT_GATE: bool = True
TEXT_GATE_DENSITY: float = 0.0015  # min bright-stroke pixel fraction to OCR a frame
TOPHAT_KSIZE: int = 15
TOPHAT_THRESH: int = 25

# ── render quality tunables ───────────────────────────────────────────────────
# Card rendering: use generous crop instead of thin per-line band.
# The card region is expanded by CARD_MARGIN_FRAC * frame_height above the top
# text line and below the bottom text line so portraits/backgrounds show cleanly.
CARD_MARGIN_FRAC: float = 0.08   # fraction of frame height added above/below card bbox
CARD_MIN_HEIGHT_FRAC: float = 0.20  # card band must be at least this fraction of frame
# When multiple unique lines share the SAME best_frame AND their y-ranges overlap or
# are within this many pixels of each other, they are grouped into ONE card render.
CARD_GROUP_Y_GAP: int = 60       # px gap allowed between y-ranges of same-frame lines
# Best-frame selection for card tracks: prefer frames with higher local contrast
# (std-dev in the text bbox region) so over/underexposed frames are avoided.
CARD_BEST_FRAME_BY_CONTRAST: bool = True
# Unsharp mask applied to the final master PNG (sigma, amount). Set amount=0 to disable.
UNSHARP_SIGMA: float = 1.0
UNSHARP_AMOUNT: float = 0.6
# Tight dedup: also merge two unique tracks if they have the SAME best_frame and
# their bbox y-ranges overlap (catches boundary duplicates from same-frame word boxes).
SAME_FRAME_BBOX_DEDUP: bool = True
# ─────────────────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parents[5]  # E:\MITAS


def run(
    item_dir: str | Path,
    out_dir: str | Path,
    *,
    segment: str | None = None,
    frame_stride: int = FRAME_STRIDE,
) -> dict[str, Any]:
    """Build a deduped credit mosaic for one segment.

    Parameters
    ----------
    item_dir:
        Root of the item (contains unified/ and frames/).
    out_dir:
        Output directory — master.png and debug.json land here.
    segment:
        'opening' or 'closing'. If None, tries 'closing' first then 'opening'.
    frame_stride:
        OCR every Nth frame to control speed vs coverage trade-off.

    Returns
    -------
    dict with keys: master_path, debug_path, unique_lines, runtime_sec.
    """
    t0 = time.perf_counter()
    item_dir = Path(item_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve segment
    if segment is None:
        for candidate in ("closing", "opening"):
            if (item_dir / "unified" / candidate).exists():
                segment = candidate
                break
    if segment is None:
        raise ValueError(f"No segment found under {item_dir}/unified/")

    unified_seg = item_dir / "unified" / segment
    frames_dir = item_dir / "frames" / segment

    # ── Step 1: collect existing OCR from unified JSON ───────────────────────
    existing = _load_existing_ocr(unified_seg, _PROJECT_ROOT)

    # ── Step 2: run per-frame OCR ─────────────────────────────────────────────
    frame_detections = _run_perframe_ocr(frames_dir, stride=frame_stride)

    # ── Step 3: merge all detections into per-line-type buckets ──────────────
    #   card_detections: list of {text, norm_text, confidence, bbox, source, order_key, frame_path}
    #   scroll_detections: same, sourced from per-frame OCR
    card_detections = existing["card_detections"]
    scroll_detections = frame_detections  # per-frame lines (includes both card + scroll frames)

    # ── Step 4: build temporal tracks from per-frame detections ──────────────
    tracks = _build_tracks(scroll_detections, y_band_px=Y_BAND_PX, merge_ratio=TRACK_MERGE_RATIO)

    # ── Step 5: incorporate existing card data as guaranteed unique lines ─────
    # Each card detection is treated as a single-frame track
    card_tracks = _build_tracks(card_detections, y_band_px=40.0, merge_ratio=0.80)

    # ── Step 6: deduplicate across all tracks ─────────────────────────────────
    # Sort so higher-quality (larger, more confident) tracks come first.
    # This ensures the better instance "wins" in the dedup loop.
    all_tracks = card_tracks + tracks
    all_tracks.sort(key=lambda t: -_quality(t))
    unique_tracks = _deduplicate(all_tracks, ratio=DEDUP_RATIO)

    # ── Step 7: order unique tracks for reading ───────────────────────────────
    ordered_tracks = _order_for_reading(unique_tracks)

    # ── Step 7b: final collapse ───────────────────────────────────────────────
    # Dense two-column scrolls (e.g. X-MEN) detect the same line at many y-positions
    # across frames; some EXACT-norm duplicates + OCR variants survive _deduplicate
    # and render as visibly repeated/overlapping lines. Collapse them so each unique
    # line appears once.
    ordered_tracks = _final_collapse_lines(ordered_tracks)

    # ── Step 8: crop bands, MERGING same-row tracks ──────────────────────────
    # Two-column scrolls detect role (left) + name (right) as SEPARATE tracks at
    # the SAME row; one full-width band per track double-prints the row (ghosting).
    # Row-merge renders each row once.
    bands = _crop_bands_rowmerged(ordered_tracks, target_width=MASTER_WIDTH, pad_y=BAND_PAD_Y)

    # ── Step 9: stack bands into master PNG ──────────────────────────────────
    if not bands:
        # Fallback: empty placeholder
        placeholder = np.zeros((120, MASTER_WIDTH, 3), dtype=np.uint8)
        cv2.putText(placeholder, "No lines detected", (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
        master = placeholder
    else:
        # 2px gap between line bands so adjacent lines never visually touch/overlap.
        gap = np.zeros((2, MASTER_WIDTH, 3), dtype=np.uint8)
        stacked: list[np.ndarray] = []
        for b in bands:
            stacked.append(b)
            stacked.append(gap)
        master = np.vstack(stacked[:-1])

    # Light unsharp mask to recover small-text crispness
    if UNSHARP_AMOUNT > 0:
        master = _unsharp(master, amount=UNSHARP_AMOUNT, sigma=UNSHARP_SIGMA)

    master_path = out_dir / "master.png"
    _imwrite(master_path, master)

    runtime = round(time.perf_counter() - t0, 2)

    # ── Step 10: debug JSON ───────────────────────────────────────────────────
    debug = {
        "item_dir": str(item_dir),
        "segment": segment,
        "frames_dir": str(frames_dir),
        "frame_stride": frame_stride,
        "existing_card_detections": len(card_detections),
        "existing_scroll_lines": len(existing["scroll_lines"]),
        "perframe_detections": len(scroll_detections),
        "total_tracks_before_dedup": len(all_tracks),
        "unique_tracks_after_dedup": len(unique_tracks),
        "bands_stacked": len(bands),
        "master_path": str(master_path),
        "master_size": [master.shape[1], master.shape[0]],
        "runtime_sec": runtime,
        "dedup_params": {
            "TRACK_MERGE_RATIO": TRACK_MERGE_RATIO,
            "Y_BAND_PX": Y_BAND_PX,
            "DEDUP_RATIO": DEDUP_RATIO,
            "MIN_CONFIDENCE": MIN_CONFIDENCE,
            "FRAME_STRIDE": frame_stride,
        },
        "lines": [
            {
                "rank": i + 1,
                "text": t["winner_text"],
                "norm": t["norm_text"],
                "confidence": round(t["best_confidence"], 4),
                "source": t["source"],
                "track_size": t["size"],
                "order_key": t["order_key"],
                "best_frame": t.get("best_frame", ""),
                "bbox": t.get("best_bbox"),
            }
            for i, t in enumerate(ordered_tracks)
        ],
    }
    debug_path = out_dir / "debug.json"
    debug_path.write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "master_path": str(master_path),
        "debug_path": str(debug_path),
        "unique_lines": len(unique_tracks),
        "master_size": [master.shape[1], master.shape[0]],
        "runtime_sec": runtime,
    }


# ── OCR loading helpers ───────────────────────────────────────────────────────

def _load_existing_ocr(unified_seg: Path, project_root: Path) -> dict[str, Any]:
    """Load card + scroll text from existing unified JSON files."""
    card_detections: list[dict[str, Any]] = []
    scroll_lines: list[dict[str, Any]] = []

    # Cards
    cards_dir = unified_seg / "cards"
    if cards_dir.exists():
        for fn in sorted(cards_dir.iterdir()):
            if fn.suffix != ".json":
                continue
            card = _read_json(fn)
            frame_path_raw = card.get("best_frame_path", "")
            # Resolve relative path
            frame_path = _resolve_frame_path(frame_path_raw, project_root)
            ts = float(card.get("first_timestamp", 0.0))
            for line in card.get("text_lines", []):
                text = str(line.get("text", "")).strip()
                conf = float(line.get("confidence", 0.0))
                bbox = line.get("bbox")  # [x, y, w, h]
                if not text or conf < MIN_CONFIDENCE:
                    continue
                if sum(c.isalpha() for c in text) < MIN_ALPHA_CHARS:
                    continue
                card_detections.append({
                    "text": text,
                    "norm_text": _norm(text),
                    "confidence": conf,
                    "bbox": bbox,
                    "frame_path": frame_path,
                    "source": "card_json",
                    "order_key": ts,
                    "frame_idx": int(card.get("best_frame_index", 0)),
                })

    # Scroll composite lines (from row_composite — used only for text inventory,
    # actual crops come from per-frame OCR)
    scroll_json = unified_seg / "scroll" / "scroll_text_lines.json"
    if scroll_json.exists():
        sd = _read_json(scroll_json)
        scroll_lines = sd.get("lines", [])

    return {"card_detections": card_detections, "scroll_lines": scroll_lines}


def _run_perframe_ocr(frames_dir: Path, stride: int = FRAME_STRIDE) -> list[dict[str, Any]]:
    """Run PaddleOCR on every (stride-th) frame and return flat detection list."""
    if not frames_dir.exists():
        return []

    frame_files = sorted(frames_dir.glob("*.png")) + sorted(frames_dir.glob("*.jpg"))
    if not frame_files:
        return []

    # Import lazily so module loads without GPU
    from paddleocr import PaddleOCR  # type: ignore
    import warnings
    warnings.filterwarnings("ignore")

    ocr = PaddleOCR(lang="en")

    detections: list[dict[str, Any]] = []
    frame_files_strided = frame_files[::stride]

    for idx, fp in enumerate(frame_files_strided):
        frame_idx = int(fp.stem.split("_")[-1]) if "_" in fp.stem else idx * stride
        arr = np.fromfile(str(fp), dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            continue

        # Cheap text-gate before the expensive OCR: skip film/blank frames.
        if TEXT_GATE and _text_density(img) < TEXT_GATE_DENSITY:
            continue

        try:
            result = ocr.ocr(img)
        except Exception:
            continue

        if not result or not isinstance(result, list):
            continue

        page = result[0] if result else {}
        if not isinstance(page, dict):
            continue

        texts = page.get("rec_texts") or []
        scores = page.get("rec_scores") or []
        boxes = page.get("rec_boxes")  # ndarray shape (N,4): x1,y1,x2,y2

        for i, text in enumerate(texts):
            text = str(text).strip()
            conf = float(scores[i]) if i < len(scores) else 0.0
            if conf < MIN_CONFIDENCE:
                continue
            if sum(c.isalpha() for c in text) < MIN_ALPHA_CHARS:
                continue

            # Convert rec_boxes [x1,y1,x2,y2] → [x, y, w, h]
            bbox = None
            if boxes is not None and i < len(boxes):
                b = boxes[i]
                x1, y1, x2, y2 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
                bbox = [x1, y1, x2 - x1, y2 - y1]

            detections.append({
                "text": text,
                "norm_text": _norm(text),
                "confidence": conf,
                "bbox": bbox,
                "frame_path": str(fp),
                "source": "perframe_ocr",
                "order_key": frame_idx,
                "frame_idx": frame_idx,
            })

    return detections


# ── Track building ────────────────────────────────────────────────────────────

def _build_tracks(
    detections: list[dict[str, Any]],
    *,
    y_band_px: float,
    merge_ratio: float,
) -> list[dict[str, Any]]:
    """Group detections into temporal tracks.

    Two detections belong to the same track if:
      - SequenceMatcher(norm_texts).ratio() > merge_ratio, AND
      - |y_center_A - y_center_B| < y_band_px
    """
    tracks: list[dict[str, Any]] = []

    for det in detections:
        norm = det["norm_text"]
        y_c = _y_center(det["bbox"])
        placed = False
        for track in tracks:
            # Text similarity
            ratio = SequenceMatcher(None, norm, track["norm_text"]).ratio()
            if ratio < merge_ratio:
                continue
            # Y-position: compare against track's running median y
            if abs(y_c - track["y_center"]) > y_band_px:
                continue
            # Merge: update track
            track["members"].append(det)
            track["size"] += 1
            # Update winner if this detection has higher confidence
            if det["confidence"] > track["best_confidence"]:
                track["winner_text"] = det["text"]
                track["norm_text"] = det["norm_text"]
                track["best_confidence"] = det["confidence"]
                track["best_frame"] = det.get("frame_path", "")
                track["best_bbox"] = det["bbox"]
            # Running mean of y_center
            track["y_sum"] += y_c
            track["y_center"] = track["y_sum"] / track["size"]
            # order_key: keep earliest
            if det["order_key"] < track["order_key"]:
                track["order_key"] = det["order_key"]
            # track source upgrades: prefer card_json
            if det["source"] == "card_json":
                track["source"] = "card_json"
            placed = True
            break

        if not placed:
            tracks.append({
                "winner_text": det["text"],
                "norm_text": norm,
                "best_confidence": det["confidence"],
                "best_frame": det.get("frame_path", ""),
                "best_bbox": det["bbox"],
                "source": det["source"],
                "order_key": det["order_key"],
                "y_center": y_c,
                "y_sum": y_c,
                "size": 1,
                "members": [det],
            })

    return tracks


# ── Deduplication ─────────────────────────────────────────────────────────────

def _deduplicate(tracks: list[dict[str, Any]], ratio: float) -> list[dict[str, Any]]:
    """Remove near-identical tracks, keeping the highest-quality instance.

    Two tracks are considered the same logical line if:
      - SequenceMatcher ratio > ratio, OR
      - SUBSET_DEDUP: one normalized text is a word-boundary substring of the other
        (e.g., "HEINZ" is a whole-word substring of "HEINZ BENNENT"), OR
      - SAME_FRAME_BBOX_DEDUP: same best_frame + overlapping y-range (boundary dups
        where the same text appears twice from adjacent word-boxes in one frame).

    Quality = best_confidence * sqrt(track_size).
    """
    unique: list[dict[str, Any]] = []
    for track in tracks:
        norm_a = track["norm_text"]
        merged = False
        for existing in unique:
            norm_b = existing["norm_text"]
            r = SequenceMatcher(None, norm_a, norm_b).ratio()
            is_dup = r >= ratio
            if not is_dup and SUBSET_DEDUP:
                # Whole-word subset check: shorter must be contained in longer
                short, long_ = (norm_a, norm_b) if len(norm_a) <= len(norm_b) else (norm_b, norm_a)
                if len(short) >= 3:
                    is_dup = _is_word_substring(short, long_)
                if not is_dup and len(short) >= 3:
                    # Suffix-token overlap: last 1–2 tokens of long_ match last 1–2 tokens of short
                    # e.g., "PARDIEU" in "GERARD DEPARDIEU", "NATA" in "RENATA" → share suffix
                    is_dup = _is_token_suffix_overlap(short, long_, min_shared_chars=4)
            if not is_dup and SAME_FRAME_BBOX_DEDUP:
                # Same best_frame AND y-ranges overlap → boundary dup from same-frame word boxes
                fp_a = track.get("best_frame", "")
                fp_b = existing.get("best_frame", "")
                if fp_a and fp_b and fp_a == fp_b:
                    if _bboxes_y_overlap(track.get("best_bbox"), existing.get("best_bbox")):
                        is_dup = True
            if not is_dup:
                continue
            # Same logical line — keep the longer/better quality instance
            if _quality(track) > _quality(existing) or len(norm_a) > len(norm_b):
                # If track has longer text AND higher quality, take it
                if len(norm_a) > len(norm_b) or _quality(track) > _quality(existing):
                    existing.update(track)
            merged = True
            break
        if not merged:
            unique.append(track)
    return unique


def _bboxes_y_overlap(bbox_a: list | None, bbox_b: list | None) -> bool:
    """Return True if two [x, y, w, h] bboxes overlap on the y-axis."""
    if not bbox_a or not bbox_b or len(bbox_a) < 4 or len(bbox_b) < 4:
        return False
    y1a, h1a = int(bbox_a[1]), int(bbox_a[3])
    y1b, h1b = int(bbox_b[1]), int(bbox_b[3])
    y2a = y1a + h1a
    y2b = y1b + h1b
    return y1a < y2b and y1b < y2a


def _quality(track: dict[str, Any]) -> float:
    return float(track["best_confidence"]) * (float(track["size"]) ** 0.5)


# ── Ordering ──────────────────────────────────────────────────────────────────

def _final_collapse_lines(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse EXACT-norm duplicates (anywhere) + LOCAL near-duplicates (OCR
    variants of the same scrolled line, within a short window) while preserving
    reading order. Each track already carries its best instance, so keeping the
    first occurrence is fine. Guarantees each unique line renders once."""
    kept: list[dict[str, Any]] = []
    kept_norms: list[str] = []
    seen_exact: set[str] = set()
    for t in tracks:
        nm = (t.get("norm_text") or "").strip()
        if not nm:
            kept.append(t)
            continue
        if nm in seen_exact:
            continue
        if any(SequenceMatcher(None, nm, kn).ratio() >= 0.90 for kn in kept_norms[-12:]):
            continue
        seen_exact.add(nm)
        kept_norms.append(nm)
        kept.append(t)
    return kept


def _order_for_reading(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort all unique lines by temporal order then y-position.

    order_key for card_json sources is the card's first_timestamp (seconds),
    for perframe_ocr it is the frame_idx. To unify, perframe order_key is
    normalized to seconds by assuming 6fps sampling (stride=5 at 30fps).
    We sort by (order_key, y_center) so temporally earlier lines come first
    and ties are broken by vertical position within that frame.
    """
    # Normalise order_key to a comparable float for both sources.
    # card_json order_key = timestamp in seconds (float)
    # perframe order_key = frame_idx (int)
    # Estimate fps from frame names: assume 30fps, stride 5 → frame_idx / 30 ≈ sec
    FPS_ESTIMATE = 30.0
    def sort_key(t: dict) -> tuple[float, float]:
        ok = float(t["order_key"])
        if t["source"] != "card_json":
            ok = ok / FPS_ESTIMATE
        return (ok, t["y_center"])

    return sorted(tracks, key=sort_key)


# ── Cropping ──────────────────────────────────────────────────────────────────

def _crop_bands_rowmerged(
    tracks: list[dict[str, Any]],
    *,
    target_width: int,
    pad_y: int,
) -> list[np.ndarray]:
    """Render ONE full-width band per ROW, merging tracks that share the same
    best_frame and a close y-position.

    In a dense two-column scroll, the role (left column) and the name (right
    column) sit at the SAME y and are detected as two separate tracks. Cropping a
    full-width band per track prints that row TWICE (slightly offset → ghosting).
    Grouping same-frame, same-y tracks and emitting one full-width band per group
    renders each row exactly once (the full-width crop already shows both columns).
    """
    ROW_GAP = 26  # px: tracks within this vertical distance in the same frame = one row
    groups: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for t in tracks:
        bf = t.get("best_frame", "")
        bb = t.get("best_bbox")
        if not bf or not bb or len(bb) < 4:
            cur = None
            continue
        y = int(bb[1]); h = int(bb[3])
        if cur is not None and cur["bf"] == bf and abs(y - cur["y"]) <= ROW_GAP:
            cur["y0"] = min(cur["y0"], y); cur["y1"] = max(cur["y1"], y + h); cur["y"] = y
        else:
            cur = {"bf": bf, "y0": y, "y1": y + h, "y": y}
            groups.append(cur)

    bands: list[np.ndarray] = []
    for g in groups:
        if not os.path.exists(g["bf"]):
            continue
        img = cv2.imdecode(np.fromfile(g["bf"], dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        y0 = max(0, g["y0"] - pad_y); y1 = min(h, g["y1"] + pad_y)
        if y1 <= y0:
            continue
        band = img[y0:y1, 0:w]
        bh, bw = band.shape[:2]
        new_h = max(8, int(bh * target_width / bw))
        bands.append(cv2.resize(band, (target_width, new_h), interpolation=cv2.INTER_AREA))
    return bands


def _crop_bands(
    tracks: list[dict[str, Any]],
    *,
    target_width: int,
    pad_y: int,
) -> list[np.ndarray]:
    """For each track, crop a band from its best frame.

    Card-sourced tracks are GROUPED by best_frame: all unique lines that belong
    to the same frame and whose y-ranges are close enough get ONE generous card
    crop (not N thin slivers).  The representative frame is picked by highest
    local contrast (std-dev in the combined text region).

    Scroll tracks get per-line bands as before.
    """
    bands: list[np.ndarray] = []

    # Separate card vs scroll tracks (preserve ordering index for output order)
    card_indices = [i for i, t in enumerate(tracks) if t.get("source") == "card_json"]
    scroll_indices = [i for i, t in enumerate(tracks) if t.get("source") != "card_json"]

    # Group card tracks by best_frame, then merge close y-ranges
    # Result: list of (output_position, band_image) to interleave correctly
    band_map: dict[int, np.ndarray] = {}  # index → band

    # Process card groups
    if card_indices:
        # Build groups: card tracks whose best_frames are the same AND y-ranges are adjacent
        groups: list[list[int]] = []  # each element = list of track indices
        used = [False] * len(card_indices)
        for ii, ci in enumerate(card_indices):
            if used[ii]:
                continue
            group = [ci]
            used[ii] = True
            fp_ci = tracks[ci].get("best_frame", "")
            for jj, cj in enumerate(card_indices):
                if used[jj] or cj == ci:
                    continue
                fp_cj = tracks[cj].get("best_frame", "")
                if fp_ci and fp_cj and fp_ci == fp_cj:
                    # Same frame → same group
                    group.append(cj)
                    used[jj] = True
                elif _card_tracks_adjacent(tracks[ci], tracks[cj]):
                    # Different frames but same card sequence: treat as individual
                    pass
            groups.append(group)

        for group in groups:
            # Determine the full y-extent of all lines in this group
            all_bboxes = [tracks[idx].get("best_bbox") for idx in group]
            all_frames = [tracks[idx].get("best_frame", "") for idx in group]
            all_members = []
            for idx in group:
                all_members.extend(tracks[idx].get("members", []))

            # Pick best frame by contrast in the text region
            best_fp, best_bbox_union = _best_frame_by_contrast(all_frames, all_bboxes, all_members)

            # Make generous card crop
            band = _make_card_band(best_fp, all_bboxes, target_width=target_width)
            if band is None:
                # fallback: make per-line bands
                for idx in group:
                    b = _make_band(tracks[idx].get("best_frame", ""),
                                   tracks[idx].get("best_bbox"),
                                   target_width=target_width, pad_y=pad_y,
                                   label=tracks[idx]["winner_text"])
                    if b is not None:
                        band_map[group[0]] = b  # only map to first idx
                    for idx2 in group[1:]:
                        band_map[idx2] = None  # mark rest as already emitted
                continue
            # Map the band to the first (lowest ordered) index in the group
            first_idx = min(group)
            band_map[first_idx] = band
            for idx in group:
                if idx != first_idx:
                    band_map[idx] = None  # mark as grouped (skip individual emit)

    # Process scroll tracks individually
    for idx in scroll_indices:
        track = tracks[idx]
        b = _make_band(track.get("best_frame", ""), track.get("best_bbox"),
                       target_width=target_width, pad_y=pad_y, label=track["winner_text"])
        band_map[idx] = b

    # Emit in original ordering
    for i in range(len(tracks)):
        if i in band_map:
            b = band_map[i]
            if b is not None:
                bands.append(b)
        elif tracks[i].get("source") != "card_json":
            # scroll track not yet mapped (shouldn't happen, but safety)
            track = tracks[i]
            b = _make_band(track.get("best_frame", ""), track.get("best_bbox"),
                           target_width=target_width, pad_y=pad_y, label=track["winner_text"])
            if b is not None:
                bands.append(b)

    return bands


def _card_tracks_adjacent(t1: dict[str, Any], t2: dict[str, Any]) -> bool:
    """Return True if two card tracks are from adjacent frames (y-ranges close)."""
    b1 = t1.get("best_bbox")
    b2 = t2.get("best_bbox")
    if not b1 or not b2:
        return False
    # Check y-center distance
    y1 = float(b1[1]) + float(b1[3]) / 2
    y2 = float(b2[1]) + float(b2[3]) / 2
    return abs(y1 - y2) < CARD_GROUP_Y_GAP


def _best_frame_by_contrast(
    frame_paths: list[str],
    bboxes: list[list | None],
    members: list[dict[str, Any]],
) -> tuple[str, list | None]:
    """Return (frame_path, unified_bbox) with highest local text-region std-dev.

    Picks from the union of frame_paths and member frame_paths. Falls back to
    first non-empty frame if contrast computation fails.
    """
    if not CARD_BEST_FRAME_BY_CONTRAST:
        return (frame_paths[0] if frame_paths else ""), (bboxes[0] if bboxes else None)

    # Collect all (frame_path, bbox) candidates
    candidates: list[tuple[str, list | None]] = []
    for fp, bb in zip(frame_paths, bboxes):
        if fp:
            candidates.append((fp, bb))
    # Also check member frames
    for m in members:
        fp = m.get("frame_path", "")
        bb = m.get("bbox")
        if fp and (fp, bb) not in candidates:
            candidates.append((fp, bb))

    best_fp = ""
    best_bbox: list | None = None
    best_score = -1.0

    for fp, bb in candidates:
        if not fp or not os.path.exists(fp):
            continue
        arr = np.fromfile(fp, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        if bb and len(bb) >= 4:
            x, y, bw, bh = int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])
            # Expand region slightly for context
            pad = 10
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
            region = gray[y1:y2, x1:x2]
        else:
            margin = int(h * 0.2)
            region = gray[margin:h - margin, :]
        if region.size < 9:
            continue
        score = float(region.std())
        if score > best_score:
            best_score = score
            best_fp = fp
            best_bbox = bb

    if not best_fp and candidates:
        best_fp, best_bbox = candidates[0]

    return best_fp, best_bbox


def _make_card_band(
    frame_path: str,
    bboxes: list[list | None],
    *,
    target_width: int,
) -> np.ndarray | None:
    """Render a generous crop of a credit card frame covering all text lines.

    Uses CARD_MARGIN_FRAC to add breathing room above/below the combined text
    region, and ensures a minimum height of CARD_MIN_HEIGHT_FRAC * frame_height.
    Returns None if the frame cannot be read.
    """
    if not frame_path or not os.path.exists(frame_path):
        return None

    arr = np.fromfile(frame_path, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    h, w = img.shape[:2]

    # Find union of all text bboxes
    valid_bboxes = [bb for bb in bboxes if bb and len(bb) >= 4]
    if valid_bboxes:
        y_tops = [int(bb[1]) for bb in valid_bboxes]
        y_bots = [int(bb[1]) + int(bb[3]) for bb in valid_bboxes]
        text_y1 = min(y_tops)
        text_y2 = max(y_bots)
    else:
        # No bbox info: use center third
        text_y1 = h // 3
        text_y2 = 2 * h // 3

    # Add generous margins
    margin = max(int(h * CARD_MARGIN_FRAC), 12)
    crop_y1 = max(0, text_y1 - margin)
    crop_y2 = min(h, text_y2 + margin)

    # Enforce minimum height
    min_h = max(int(h * CARD_MIN_HEIGHT_FRAC), 60)
    if crop_y2 - crop_y1 < min_h:
        mid = (crop_y1 + crop_y2) // 2
        crop_y1 = max(0, mid - min_h // 2)
        crop_y2 = min(h, crop_y1 + min_h)

    if crop_y2 <= crop_y1:
        crop_y1, crop_y2 = 0, h

    card_crop = img[crop_y1:crop_y2, 0:w]
    if card_crop.size == 0:
        return None

    band_h, band_w = card_crop.shape[:2]
    new_h = max(8, int(band_h * target_width / band_w))
    resized = cv2.resize(card_crop, (target_width, new_h), interpolation=cv2.INTER_AREA)
    return resized


def _make_band(
    frame_path: str,
    bbox: list[int] | None,
    *,
    target_width: int,
    pad_y: int,
    label: str = "",
) -> np.ndarray | None:
    """Crop a horizontal band from frame at bbox row, resize to target_width."""
    if not frame_path or not os.path.exists(frame_path):
        return _text_only_band(label, target_width)

    arr = np.fromfile(frame_path, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return _text_only_band(label, target_width)

    h, w = img.shape[:2]

    if bbox is not None and len(bbox) >= 4:
        x, y, bw, bh = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        # Full-width band at the text row
        y1 = max(0, y - pad_y)
        y2 = min(h, y + bh + pad_y)
        if y2 <= y1:
            y1, y2 = max(0, h // 4), min(h, 3 * h // 4)
        band_crop = img[y1:y2, 0:w]
    else:
        # No bbox: use middle third of frame
        y1 = h // 3
        y2 = 2 * h // 3
        band_crop = img[y1:y2, 0:w]

    if band_crop.size == 0:
        return _text_only_band(label, target_width)

    # Resize to target_width preserving aspect ratio
    band_h, band_w = band_crop.shape[:2]
    new_h = max(8, int(band_h * target_width / band_w))
    resized = cv2.resize(band_crop, (target_width, new_h), interpolation=cv2.INTER_AREA)
    return resized


def _text_only_band(label: str, width: int, height: int = 40) -> np.ndarray:
    """Fallback: black band with white text label when no frame is available."""
    band = np.zeros((height, width, 3), dtype=np.uint8)
    if label:
        cv2.putText(band, label[:80], (8, height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
    return band


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unsharp(img: np.ndarray, amount: float = 0.6, sigma: float = 1.0) -> np.ndarray:
    """Light unsharp mask to recover small-text crispness.

    amount=0.6, sigma=1.0 crisps thin strokes without halos on large headers.
    """
    blur = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1.0 + amount, blur, -amount, 0)


def _is_word_substring(short: str, long_: str) -> bool:
    """Return True if 'short' appears as a whole-word sequence inside 'long_'."""
    idx = long_.find(short)
    if idx < 0:
        return False
    before_ok = idx == 0 or long_[idx - 1] == " "
    after_ok = idx + len(short) == len(long_) or long_[idx + len(short)] == " "
    return before_ok and after_ok


def _is_token_suffix_overlap(short: str, long_: str, min_shared_chars: int = 5) -> bool:
    """Return True if the last token(s) of short significantly overlap with
    the last token(s) of long_, e.g. 'PARDIEU' overlaps 'DEPARDIEU'.

    Strategy: check if the last token of long_ ENDS WITH any significant
    suffix of the last token of short (or vice versa).
    """
    short_tokens = short.split()
    long_tokens = long_.split()
    if not short_tokens or not long_tokens:
        return False
    last_short = short_tokens[-1]
    last_long = long_tokens[-1]
    # Check if last_short is a suffix of last_long of sufficient length
    if len(last_short) >= min_shared_chars and last_long.endswith(last_short):
        return True
    if len(last_long) >= min_shared_chars and last_short.endswith(last_long):
        return True
    # Check if one starts with the other (prefix truncation like "Z BENNENT" vs "HEINZ BENNENT")
    # Compare last token similarity
    r = SequenceMatcher(None, last_short, last_long).ratio()
    if r >= 0.80 and len(last_short) >= min_shared_chars:
        # Also check full trailing token sequence matches
        n = min(len(short_tokens), len(long_tokens))
        trailing_short = " ".join(short_tokens[-n:])
        trailing_long = " ".join(long_tokens[-n:])
        full_r = SequenceMatcher(None, trailing_short, trailing_long).ratio()
        return full_r >= 0.75
    return False


def _norm(text: str) -> str:
    """Normalize text for comparison: uppercase, strip accents, collapse spaces."""
    text = str(text or "").strip()
    # NFD decompose, drop combining chars, uppercase
    nfd = unicodedata.normalize("NFD", text)
    ascii_approx = "".join(c for c in nfd if not unicodedata.combining(c))
    return " ".join(ascii_approx.upper().split())


def _y_center(bbox: list | None) -> float:
    if not bbox or len(bbox) < 4:
        return 0.0
    return float(bbox[1]) + float(bbox[3]) / 2.0


def _text_density(img: np.ndarray) -> float:
    """Fraction of bright thin-stroke pixels (white top-hat). High for credit text
    (bright strokes on darker bg, any colour); low for smooth film scenes."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (TOPHAT_KSIZE, TOPHAT_KSIZE))
    th = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, k)
    return float(np.count_nonzero(th > TOPHAT_THRESH)) / float(th.size)


def _resolve_frame_path(raw: str, project_root: Path) -> str:
    """Make a relative frame path absolute using project_root."""
    if not raw:
        return ""
    p = Path(raw)
    if p.is_absolute() and p.exists():
        return str(p)
    candidate = project_root / p
    if candidate.exists():
        return str(candidate)
    return raw


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _imwrite(path: Path, img: np.ndarray) -> None:
    """Turkish-I safe imwrite via imencode + tofile."""
    _, buf = cv2.imencode(path.suffix or ".png", img)
    buf.tofile(str(path))
