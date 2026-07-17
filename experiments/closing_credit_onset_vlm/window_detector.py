from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import math
from pathlib import Path
import time
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image

from core.pipelines.ocr.jenerik_frame_pool_detector import (
    DetectorConfig as CvDetectorConfig,
    FrameScore,
    score_frames,
)

from .detector import (
    _append_jsonl,
    _atomic_write_json,
    _inside_any_protected_frames_tree,
    _write_features,
    build_frame_refs,
    default_output_dir,
    frame_source_signature,
    select_cv_proposals,
)
from .models import (
    BoundaryKind,
    Continuity,
    DetectionConfig,
    DetectionResult,
    DetectionStatus,
    FrameRef,
    WindowEvidence,
    WindowVerdict,
)
from .ollama_client import (
    OllamaFrameClassifier,
    VlmCallError,
    VlmCandidateAuditResult,
    VlmWindowResult,
)


WINDOW_SCHEMA_VERSION = "closing-credit-onset-window-test/1.0"
WINDOW_PROTOCOL = "window-boundary-v1"
MAX_REVIEW_RESCUE_CANDIDATES = 5


@dataclass(frozen=True)
class WindowProtocolConfig:
    coarse_window_seconds: float = 120.0
    coarse_anchor_count: int = 9
    coarse_max_cells: int = 24
    terminal_dense_horizon_seconds: float = 15.0
    terminal_dense_step_seconds: float = 1.0
    terminal_blank_tail_seconds: float = 15.0
    fine_pre_seconds: float = 3.0
    fine_post_seconds: float = 15.0
    fine_anchor_count: int = 9
    terminal_fine_max_cells: int = 28
    coarse_tile_width: int = 384
    fine_tile_width: int = 512
    verify_tile_width: int = 640
    verify_min_tile_width: int = 384
    verify_max_mosaic_pixels: int = 2_400_000
    jpeg_quality: int = 95
    verify_dense_frames: int = 8
    verify_dense_post_frames: int = 3
    verify_support_seconds: tuple[float, ...] = (3.0, 8.0, 15.0)
    # Two independent views can place a gradual low-contrast fade on adjacent
    # extracted frames.  A one-frame span is accepted only after both views
    # pass the full semantic, PRE-adjacency, kind and future-support gates; the
    # earliest supported frame is then selected deterministically.
    verification_tolerance_frames: int = 1
    min_support_seconds: float = 8.0
    min_call_budget_seconds: float = 10.0
    review_rescue_max_candidates: int = MAX_REVIEW_RESCUE_CANDIDATES
    rescue_localize_anchor_count: int = 5
    rescue_localize_tile_width: int = 640
    rescue_compact_tile_width: int = 720
    rescue_localize_tolerance_frames: int = 3
    rescue_compact_max_candidate_frames: int = 18
    micro_tile_width: int = 720
    micro_max_disagreement_frames: int = 1

    def validate(self) -> None:
        if self.coarse_window_seconds <= 0:
            raise ValueError("coarse_window_seconds must be > 0")
        if self.coarse_anchor_count < 3:
            raise ValueError("coarse_anchor_count must be >= 3")
        if self.coarse_max_cells < self.coarse_anchor_count:
            raise ValueError("coarse_max_cells must be >= coarse_anchor_count")
        if self.terminal_dense_horizon_seconds <= 0:
            raise ValueError("terminal_dense_horizon_seconds must be > 0")
        if self.terminal_dense_step_seconds <= 0:
            raise ValueError("terminal_dense_step_seconds must be > 0")
        if self.terminal_blank_tail_seconds < 0:
            raise ValueError("terminal_blank_tail_seconds must be >= 0")
        if self.fine_anchor_count < 3:
            raise ValueError("fine_anchor_count must be >= 3")
        if self.terminal_fine_max_cells < self.fine_anchor_count:
            raise ValueError(
                "terminal_fine_max_cells must be >= fine_anchor_count"
            )
        if not 1 <= self.verify_min_tile_width <= self.verify_tile_width:
            raise ValueError(
                "verify_min_tile_width must be between 1 and verify_tile_width"
            )
        if self.verify_max_mosaic_pixels <= 0:
            raise ValueError("verify_max_mosaic_pixels must be > 0")
        if self.verify_dense_frames < 4:
            raise ValueError("verify_dense_frames must be >= 4")
        if self.verify_dense_post_frames < 1:
            raise ValueError("verify_dense_post_frames must be >= 1")
        if self.verification_tolerance_frames < 0:
            raise ValueError("verification_tolerance_frames must be >= 0")
        if self.min_support_seconds <= 0:
            raise ValueError("min_support_seconds must be > 0")
        if self.min_call_budget_seconds <= 0:
            raise ValueError("min_call_budget_seconds must be > 0")
        if not 1 <= self.review_rescue_max_candidates <= MAX_REVIEW_RESCUE_CANDIDATES:
            raise ValueError(
                "review_rescue_max_candidates must be between 1 and "
                f"{MAX_REVIEW_RESCUE_CANDIDATES}"
            )
        if self.rescue_localize_anchor_count < 3:
            raise ValueError("rescue_localize_anchor_count must be >= 3")
        if self.rescue_localize_tile_width < 1:
            raise ValueError("rescue_localize_tile_width must be >= 1")
        if self.rescue_compact_tile_width < self.rescue_localize_tile_width:
            raise ValueError(
                "rescue_compact_tile_width must be >= rescue_localize_tile_width"
            )
        if self.rescue_localize_tolerance_frames < 0:
            raise ValueError("rescue_localize_tolerance_frames must be >= 0")
        if self.rescue_compact_max_candidate_frames < 2:
            raise ValueError("rescue_compact_max_candidate_frames must be >= 2")
        if self.micro_tile_width < self.verify_tile_width:
            raise ValueError("micro_tile_width must be >= verify_tile_width")
        if not 1 <= self.micro_max_disagreement_frames <= 3:
            raise ValueError("micro_max_disagreement_frames must be between 1 and 3")

    def to_dict(self) -> dict[str, Any]:
        return {
            "coarse_window_seconds": self.coarse_window_seconds,
            "coarse_anchor_count": self.coarse_anchor_count,
            "coarse_max_cells": self.coarse_max_cells,
            "terminal_dense_horizon_seconds": self.terminal_dense_horizon_seconds,
            "terminal_dense_step_seconds": self.terminal_dense_step_seconds,
            "terminal_blank_tail_seconds": self.terminal_blank_tail_seconds,
            "fine_pre_seconds": self.fine_pre_seconds,
            "fine_post_seconds": self.fine_post_seconds,
            "fine_anchor_count": self.fine_anchor_count,
            "terminal_fine_max_cells": self.terminal_fine_max_cells,
            "coarse_tile_width": self.coarse_tile_width,
            "fine_tile_width": self.fine_tile_width,
            "verify_tile_width": self.verify_tile_width,
            "verify_min_tile_width": self.verify_min_tile_width,
            "verify_max_mosaic_pixels": self.verify_max_mosaic_pixels,
            "jpeg_quality": self.jpeg_quality,
            "verify_dense_frames": self.verify_dense_frames,
            "verify_dense_post_frames": self.verify_dense_post_frames,
            "verify_support_seconds": list(self.verify_support_seconds),
            "verification_tolerance_frames": self.verification_tolerance_frames,
            "min_support_seconds": self.min_support_seconds,
            "min_call_budget_seconds": self.min_call_budget_seconds,
            "review_rescue_max_candidates": self.review_rescue_max_candidates,
            "rescue_localize_anchor_count": self.rescue_localize_anchor_count,
            "rescue_localize_tile_width": self.rescue_localize_tile_width,
            "rescue_compact_tile_width": self.rescue_compact_tile_width,
            "rescue_localize_tolerance_frames": (
                self.rescue_localize_tolerance_frames
            ),
            "rescue_compact_max_candidate_frames": (
                self.rescue_compact_max_candidate_frames
            ),
            "micro_tile_width": self.micro_tile_width,
            "micro_max_disagreement_frames": self.micro_max_disagreement_frames,
        }


@dataclass
class CoarseOutcome:
    status: str
    reason: str
    bracket: list[int] | None = None
    candidate_starts: list[int] | None = None
    provisional_start: int | None = None
    boundary_kind: str | None = None


@dataclass(frozen=True)
class ReviewRescueCandidate:
    """A chronological coarse hint that still requires fresh semantic proof."""

    bracket: tuple[int, int]
    provisional_start: int
    boundary_kind: str
    source_call_id: str
    source_reject: str
    source_first_cell: int = -1
    source_at_stream_eof: bool = False
    source_last_support_pos: int | None = None
    wide_left: int = 0
    support_hint: int | None = None
    support_call_id: str | None = None
    chronology_positions: tuple[int, ...] = ()
    chronology_groups: tuple[tuple[int, ...], ...] = ()
    requires_chronology_guard: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "bracket": list(self.bracket),
            "provisional_start": self.provisional_start,
            "boundary_kind": self.boundary_kind,
            "source_call_id": self.source_call_id,
            "source_reject": self.source_reject,
            "source_first_cell": self.source_first_cell,
            "source_at_stream_eof": self.source_at_stream_eof,
            "source_last_support_pos": self.source_last_support_pos,
            "wide_left": self.wide_left,
            "support_hint": self.support_hint,
            "support_call_id": self.support_call_id,
            "chronology_positions": list(self.chronology_positions),
            "chronology_groups": [list(group) for group in self.chronology_groups],
            "requires_chronology_guard": self.requires_chronology_guard,
        }


@dataclass
class ReviewRescueOutcome:
    status: str
    reason: str
    call_index: int
    evidence: list[WindowEvidence]
    records: list[dict[str, Any]]
    reports: list[dict[str, Any]]
    start_pos: int | None = None
    onset_kind: str | None = None
    provisional_start: int | None = None
    review_bracket: list[int] | None = None
    verification: dict[str, Any] | None = None


def build_review_rescue_candidates(
    evidence: list[WindowEvidence],
    *,
    limit: int,
    fps: float = 1.0,
    config: WindowProtocolConfig | None = None,
) -> list[ReviewRescueCandidate]:
    """Turn coarse TRANSITION claims into bounded, chronological proposals.

    A rejected or unsupported coarse decision is never accepted here.  It is
    merely allowed to nominate a small region for a new high-resolution
    primary/adversarial check.  This is important when a large contact sheet
    contains both real credits and later story text: the coarse model may get
    the semantics wrong while still landing near the real visual transition.
    """
    if limit < 1:
        return []
    effective_limit = min(int(limit), MAX_REVIEW_RESCUE_CANDIDATES)
    cfg = config or WindowProtocolConfig()
    candidates: list[ReviewRescueCandidate] = []
    seen_right: set[int] = set()
    ordered = sorted(evidence, key=lambda item: item.positions[0])
    for item_index, item in enumerate(ordered):
        previous_coarse = next(
            (
                previous for previous in reversed(ordered[:item_index])
                if previous.stage == "coarse"
            ),
            None,
        )
        transition_candidate = (
            item.stage == "coarse"
            and item.verdict == WindowVerdict.TRANSITION.value
            and item.first_cell >= 1
            and item.first_pos is not None
            and item.kind != BoundaryKind.NONE.value
        )
        active_candidate = (
            item.stage == "coarse"
            and item.verdict == WindowVerdict.ACTIVE_FROM_LEFT.value
            and item.first_cell == 0
            and item.first_pos is not None
            and item.kind != BoundaryKind.NONE.value
            and previous_coarse is not None
            and len(previous_coarse.positions) >= 2
            and len(item.positions) >= 2
        )
        if not transition_candidate and not active_candidate:
            continue
        if transition_candidate:
            left = int(item.positions[item.first_cell - 1])
            right = int(item.positions[item.first_cell])
            provisional = right
            wide_left = int(item.positions[max(0, item.first_cell - 3)])
        else:
            assert previous_coarse is not None
            left = int(previous_coarse.positions[-2])
            right = int(item.positions[1])
            provisional = int(item.positions[0])
            wide_left = int(previous_coarse.positions[max(0, len(previous_coarse.positions) - 3)])
        if left >= right or right in seen_right:
            continue
        unresolved_history = [
            previous for previous in ordered[:item_index]
            if previous.stage == "coarse"
            and (
                previous.verdict == WindowVerdict.AMBIGUOUS.value
                or previous.verdict == WindowVerdict.ACTIVE_FROM_LEFT.value
            )
        ]
        history_groups: list[tuple[int, ...]] = []
        for previous in unresolved_history:
            group = [int(position) for position in previous.positions]
            if previous.verdict == WindowVerdict.ACTIVE_FROM_LEFT.value:
                previous_index = ordered.index(previous)
                context_row = next(
                    (
                        row for row in reversed(ordered[:previous_index])
                        if row.stage == "coarse" and len(row.positions) >= 2
                    ),
                    None,
                )
                if context_row is not None:
                    group.append(int(context_row.positions[-2]))
            group_tuple = tuple(sorted(set(group)))
            if len(group_tuple) >= 3 and group_tuple not in history_groups:
                history_groups.append(group_tuple)
        base_positions = {
            *(
                [int(position) for position in previous_coarse.positions[-2:]]
                if previous_coarse is not None else []
            ),
            *[
                int(position) for position in item.positions[
                    :(
                        min(item.first_cell, cfg.coarse_anchor_count)
                        if transition_candidate else min(2, len(item.positions))
                    )
                ]
            ],
        }
        chronology_positions = tuple(sorted(base_positions))
        chronology_groups = list(history_groups)
        if len(chronology_positions) >= 3 and chronology_positions not in chronology_groups:
            chronology_groups.append(chronology_positions)
        family = _boundary_family(item.kind)
        supporting = item if (
            family == "SUSTAINED_CREDITS"
            and _is_supported(
                item,
                fps=fps,
                min_support_seconds=cfg.min_support_seconds,
                terminal_blank_tail_seconds=cfg.terminal_blank_tail_seconds,
            )
        ) else None
        seen_right.add(right)
        candidates.append(ReviewRescueCandidate(
            bracket=(left, right),
            provisional_start=provisional,
            boundary_kind=item.kind,
            source_call_id=item.call_id,
            source_reject=item.reject,
            source_first_cell=int(item.first_cell),
            source_at_stream_eof=bool(item.at_stream_eof),
            source_last_support_pos=(
                int(item.last_support_pos)
                if item.last_support_pos is not None else None
            ),
            wide_left=wide_left,
            support_hint=(
                int(supporting.last_support_pos)
                if supporting is not None and supporting.last_support_pos is not None
                else None
            ),
            support_call_id=(supporting.call_id if supporting is not None else None),
            chronology_positions=chronology_positions,
            chronology_groups=tuple(chronology_groups),
            requires_chronology_guard=bool(unresolved_history),
        ))
        if len(candidates) >= effective_limit:
            break
    return candidates


def build_shifted_negative_positions(
    positions: list[int],
    *,
    total_frames: int,
) -> list[int]:
    """Add a real, previously unseen context cell for an independent negative.

    The second negative also uses a two-column adversarial prompt.  Keeping all
    primary cells prevents a faint credit from being hidden by the cadence
    shift, while the extra cell makes the transported mosaic genuinely
    different instead of merely replaying the same image with another prompt.
    """
    ordered = sorted({int(position) for position in positions})
    if not ordered or total_frames < 2:
        raise ValueError("shifted negative panel requires at least two frames")
    if ordered[0] < 0 or ordered[-1] >= total_frames:
        raise ValueError("shifted negative positions are outside the frame set")
    used = set(ordered)
    candidates: list[int] = []
    if ordered[0] > 0:
        candidates.append(ordered[0] - 1)
    if ordered[-1] + 1 < total_frames:
        candidates.append(ordered[-1] + 1)
    midpoint = (ordered[0] + ordered[-1]) / 2.0
    candidates.extend(sorted(
        (position for position in range(ordered[0] + 1, ordered[-1])
         if position not in used),
        key=lambda position: (abs(position - midpoint), position),
    ))
    extra = next((position for position in candidates if position not in used), None)
    if extra is None:
        raise ValueError("cannot construct a distinct shifted negative panel")
    return sorted({*ordered, int(extra)})


def _is_clean_pre_only(evidence: WindowEvidence) -> bool:
    return (
        evidence.verdict == WindowVerdict.PRE_ONLY.value
        and evidence.first_cell == -1
        and evidence.first_pos is None
        and evidence.kind == BoundaryKind.NONE.value
        and evidence.continuity == Continuity.NONE.value
    )


def _is_semantic_noncredit(evidence: WindowEvidence) -> bool:
    """True only when a view makes no positive attribution/credit claim.

    Qwen sometimes returns AMBIGUOUS for ordinary footage or diegetic/story
    text while still setting a semantic reject.  That is a usable negative
    only when the structural fields also say there is no onset.  Two
    independent transported views are still required before chronology can be
    discarded.
    """
    return _is_clean_pre_only(evidence) or (
        evidence.verdict == WindowVerdict.AMBIGUOUS.value
        and evidence.first_cell == -1
        and evidence.first_pos is None
        and evidence.kind == BoundaryKind.NONE.value
        and evidence.continuity in {
            Continuity.UNVERIFIABLE.value,
            Continuity.BROKEN.value,
        }
        and evidence.reject != "NONE"
    )


def _is_visually_blank_frame(path: Path) -> bool:
    """Conservative physical veto for frames incapable of containing a glyph."""
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        low, high = rgb.convert("L").getextrema()
        channel_extrema = rgb.getextrema()
    # Keep the veto deliberately narrower than "looks black".  Values 2..4 can
    # already be a real, extremely faint anti-aliased glyph on archival video;
    # the RGB range guard also protects equal-luma chromatic strokes.
    return (
        int(high) <= 1
        and int(high) - int(low) <= 1
        and max(int(top) - int(bottom) for bottom, top in channel_extrema) <= 3
    )


def _micro_backtrack_has_raw_change(
    refs_by_pos: dict[int, FrameRef],
    position: int,
) -> dict[str, Any]:
    """Require a physical change before a micro view may move onset left.

    Exact views can agree on frame N while two denser semantic views claim
    N-1.  That backtrack is valid for a faint fade-in only if N-1 actually
    differs from its predecessor in the decoded pixels.  Repeated near-black
    codec frames otherwise let a VLM hallucinate the blank frame as the first
    credit.  RGB differences preserve very faint or chromatic strokes that a
    luma-only blank test could discard.
    """
    report: dict[str, Any] = {
        "gate_passed": False,
        "position": int(position),
        "reason": "raw predecessor change is unavailable",
    }
    if position <= 0 or position not in refs_by_pos or position - 1 not in refs_by_pos:
        return report

    def interior_rgb(path: Path) -> np.ndarray:
        with Image.open(path) as image:
            array = np.array(image.convert("RGB"), dtype=np.int16)
        height, width = array.shape[:2]
        inset = min(4, max(0, (min(height, width) - 1) // 4))
        if inset and height > 2 * inset and width > 2 * inset:
            array = array[inset:-inset, inset:-inset]
        return array

    previous = interior_rgb(refs_by_pos[position - 1].path)
    current = interior_rgb(refs_by_pos[position].path)
    if previous.shape != current.shape or previous.size == 0:
        report["reason"] = "raw predecessor shapes do not match"
        return report
    difference = np.max(np.abs(current - previous), axis=2)
    max_abs = int(difference.max())
    changed_pixels = int(np.count_nonzero(difference >= 3))
    changed_density = float(changed_pixels / difference.size)
    # Density is resolution-normalized: one real anti-aliased stroke in a tiny
    # unit-test frame still passes, while isolated HD codec speckles do not.
    gate = max_abs >= 4 and changed_density >= 0.0005
    report.update({
        "gate_passed": bool(gate),
        "reason": (
            "decoded RGB change supports the earlier micro claim"
            if gate else "candidate repeats its predecessor without a visible raw change"
        ),
        "max_abs_rgb_delta": max_abs,
        "pixels_with_delta_ge_3": changed_pixels,
        "changed_density": round(changed_density, 8),
    })
    return report


def _earliest_blank_to_visible_transition(
    refs_by_pos: dict[int, FrameRef],
    *,
    left: int,
    right: int,
) -> int | None:
    """Return the first stable physical blank-to-visible edge in a dense gap.

    This is only a proposal for a later two-view semantic audit.  It is never
    credit evidence by itself: a fade from black into ordinary footage has the
    same raw edge and must be rejected by the VLM micro views.
    """
    if right < left:
        return None
    start = max(1, int(left))
    end = min(int(right), max(refs_by_pos))
    for position in range(start, end + 1):
        if not _is_visually_blank_frame(refs_by_pos[position - 1].path):
            continue
        if _is_visually_blank_frame(refs_by_pos[position].path):
            continue
        later = range(position + 1, min(end, position + 2) + 1)
        if position == end or any(
            not _is_visually_blank_frame(refs_by_pos[next_pos].path)
            for next_pos in later
        ):
            return position
    return None


def _persistent_edge_emergence(
    refs_by_pos: dict[int, FrameRef],
    position: int,
    *,
    min_ratio: float = 2.25,
    min_density: float = 0.0005,
) -> dict[str, Any]:
    """Conservative raw proposal for a newly appearing fixed overlay.

    A true faint credit fade introduces small edges that persist at the same
    screen coordinates over the next extracted frames. Moving fire, grain and
    scenery can have many edges, but usually do not create a sharp *new and
    persistent* edge-count jump at the disputed predecessor. This signal never
    authorizes FOUND: it only opens an additional two-view semantic audit.
    """
    result: dict[str, Any] = {
        "gate_passed": False,
        "position": int(position),
        "reason": "insufficient temporal context",
        "min_ratio": float(min_ratio),
        "min_density": float(min_density),
        "thresholds": [],
    }
    required = list(range(int(position) - 2, int(position) + 3))
    if any(value not in refs_by_pos for value in required):
        return result

    frames: list[np.ndarray] = []
    luma_means: list[float] = []
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    for value in required:
        encoded = np.fromfile(str(refs_by_pos[value].path), dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
        if image is None:
            result["reason"] = f"failed to decode frame {value}"
            return result
        height, width = image.shape[:2]
        if width > 720:
            target_height = max(1, int(math.floor(height * 720 / width + 0.5)))
            image = cv2.resize(
                image,
                (720, target_height),
                interpolation=cv2.INTER_AREA,
            )
        luma_means.append(float(np.mean(image)))
        frames.append(clahe.apply(image))

    previous_luma = luma_means[1]
    current_luma = luma_means[2]
    luma_delta = current_luma - previous_luma
    luma_ratio = (current_luma + 1.0) / (previous_luma + 1.0)
    photometric_cut_veto = bool(
        abs(luma_delta) >= 8.0
        and (luma_ratio < 0.72 or luma_ratio > 1.5)
    )
    result.update({
        "previous_luma_mean": round(previous_luma, 4),
        "current_luma_mean": round(current_luma, 4),
        "luma_delta": round(luma_delta, 4),
        "luma_ratio": round(luma_ratio, 4),
        "photometric_cut_veto": photometric_cut_veto,
    })

    pixel_count = int(frames[0].size)
    kernel = np.ones((3, 3), dtype=np.uint8)

    def new_persistent_count(edges: list[np.ndarray], center: int) -> int:
        future = edges[center].astype(bool)
        for offset in (1, 2):
            future &= cv2.dilate(edges[center + offset], kernel).astype(bool)
        previous = cv2.dilate(edges[center - 1], kernel).astype(bool)
        return int(np.count_nonzero(future & ~previous))

    best_ratio = 0.0
    best_row: dict[str, Any] | None = None
    smoothing = max(20.0, pixel_count * 0.00005)
    for threshold in (10, 20, 30, 40):
        edges = [
            cv2.Canny(
                frame,
                threshold,
                threshold * 3,
                L2gradient=True,
            )
            for frame in frames
        ]
        previous_count = new_persistent_count(edges, 1)
        current_count = new_persistent_count(edges, 2)
        ratio = (current_count + smoothing) / (previous_count + smoothing)
        density = current_count / max(1, pixel_count)
        row = {
            "canny_low": threshold,
            "previous_count": previous_count,
            "current_count": current_count,
            "current_density": round(density, 8),
            "ratio": round(ratio, 4),
        }
        result["thresholds"].append(row)
        if ratio > best_ratio:
            best_ratio = ratio
            best_row = row

    gate = bool(
        best_row is not None
        and float(best_row["ratio"]) >= float(min_ratio)
        and float(best_row["current_density"]) >= float(min_density)
        and not photometric_cut_veto
    )
    result.update({
        "gate_passed": gate,
        "best": best_row,
        "reason": (
            "new fixed-edge persistence jump warrants predecessor audit"
            if gate else (
                "global photometric cut/fade vetoed the raw edge proposal"
                if photometric_cut_veto
                else "no conservative fixed-edge emergence jump"
            )
        ),
    })
    return result


def _earliest_dense_gap_edge_emergence(
    refs_by_pos: dict[int, FrameRef],
    *,
    left: int,
    right: int,
) -> dict[str, Any]:
    """Propose the earliest persistent overlay edge inside a disputed dense gap.

    This deliberately trades a lower count-ratio threshold for a much higher
    absolute edge-density floor.  It is used only after two independent sparse
    semantic views have bounded a small credit-family gap, and it can only open
    a fresh primary/adversarial micro audit.  The raw signal never authorizes a
    FOUND result by itself.
    """
    min_ratio = 1.8
    min_density = 0.002
    report: dict[str, Any] = {
        "gate_passed": False,
        "anchor_pos": None,
        "search_range": [int(left), int(right)],
        "min_ratio": min_ratio,
        "min_density": min_density,
        "probes": [],
        "reason": "no conservative dense-gap edge proposal",
    }
    if right < left:
        report["reason"] = "empty dense-gap edge search range"
        return report

    for position in range(max(1, int(left)), int(right) + 1):
        evidence = _persistent_edge_emergence(
            refs_by_pos,
            position,
            min_ratio=min_ratio,
            min_density=min_density,
        )
        report["probes"].append({
            "position": int(position),
            "gate_passed": bool(evidence["gate_passed"]),
            "best": evidence.get("best"),
            "reason": evidence.get("reason"),
        })
        if evidence["gate_passed"]:
            report.update({
                "gate_passed": True,
                "anchor_pos": int(position),
                "anchor_evidence": evidence,
                "reason": (
                    "earliest persistent overlay edge warrants fresh two-view "
                    "semantic audit"
                ),
            })
            break
    return report


def _boundary_family(kind: str) -> str:
    if kind in {
        BoundaryKind.CREDIT_SEQUENCE.value,
        BoundaryKind.END_CARD_THEN_CREDITS.value,
    }:
        return "SUSTAINED_CREDITS"
    if kind == BoundaryKind.TERMINAL_END_CARD.value:
        return "TERMINAL_END_CARD"
    return "NONE"


def adjudicate_candidate_semantic_audits(
    primary: dict[str, Any],
    context: dict[str, Any],
    *,
    allowed_kinds: set[str],
    allow_faint_primary_no_text: bool,
    faint_edge_proof: dict[str, Any],
) -> dict[str, Any]:
    """Fail-closed agreement gate for the two dedicated candidate views."""
    expected: set[str] = set()
    if BoundaryKind.CREDIT_SEQUENCE.value in allowed_kinds:
        expected.add("ATTRIBUTION_CREDIT")
    if BoundaryKind.TERMINAL_END_CARD.value in allowed_kinds:
        expected.add("END_CARD")
    if BoundaryKind.END_CARD_THEN_CREDITS.value in allowed_kinds:
        expected.update({"ATTRIBUTION_CREDIT", "END_CARD"})

    call_ids = [primary.get("call_id"), context.get("call_id")]
    input_hashes = [primary.get("input_sha256"), context.get("input_sha256")]
    prompt_hashes = [primary.get("prompt_sha256"), context.get("prompt_sha256")]
    variants = [primary.get("prompt_variant"), context.get("prompt_variant")]
    candidate_positions = [
        primary.get("candidate_pos"),
        context.get("candidate_pos"),
    ]
    protocols = [
        primary.get("prompt_protocol"),
        context.get("prompt_protocol"),
    ]
    independent = bool(
        all(isinstance(value, str) and value for value in call_ids)
        and call_ids[0] != call_ids[1]
        and all(isinstance(value, str) and len(value) == 64 for value in input_hashes)
        and input_hashes[0] != input_hashes[1]
        and all(isinstance(value, str) and len(value) == 64 for value in prompt_hashes)
        and prompt_hashes[0] != prompt_hashes[1]
        and variants == ["candidate_single", "candidate_context_triplet"]
        and protocols == [
            "candidate_semantic_audit_v1",
            "candidate_semantic_audit_v1",
        ]
        and candidate_positions[0] is not None
        and candidate_positions[0] == candidate_positions[1]
    )

    def strong_positive(view: dict[str, Any]) -> bool:
        decision = view.get("decision")
        inside = view.get("inside_story_screen")
        attribution = view.get("attribution_layout")
        if decision == "ATTRIBUTION_CREDIT":
            return attribution is True and inside is False
        if decision == "END_CARD":
            return inside is False
        return False

    primary_decision = primary.get("decision")
    context_decision = context.get("decision")
    context_positive = bool(
        context_decision in expected and strong_positive(context)
    )
    primary_positive = strong_positive(primary)
    faint_primary = bool(
        allow_faint_primary_no_text
        and faint_edge_proof.get("gate_passed") is True
        and primary_decision == "NO_TEXT"
        and primary.get("attribution_layout") is False
        and primary.get("inside_story_screen") is False
    )
    compatible = bool(
        context_positive
        and (
            (primary_positive and primary_decision == context_decision)
            or faint_primary
        )
    )
    gate = bool(independent and expected and compatible)
    earlier_candidate_invisible = bool(
        independent
        and context_positive
        and primary_decision == "NO_TEXT"
        and primary.get("attribution_layout") is False
        and primary.get("inside_story_screen") is False
        and faint_edge_proof.get("gate_passed") is not True
    )

    explicit_negative = {
        "TITLE_OR_STORY",
        "DIEGETIC_SCREEN",
        "OTHER_TEXT",
        "NO_TEXT",
    }

    def explicit_noncredit(view: dict[str, Any]) -> bool:
        decision = view.get("decision")
        return bool(
            decision in explicit_negative
            and view.get("attribution_layout") is False
            and (
                decision != "DIEGETIC_SCREEN"
                or view.get("inside_story_screen") is True
            )
        )

    definitive_noncredit = bool(
        independent
        and explicit_noncredit(primary)
        and explicit_noncredit(context)
    )
    if gate:
        reason = (
            "context candidate view proved the expected semantic class and the "
            "independent single-frame view agreed or safely reported a faint edge"
        )
    elif definitive_noncredit:
        reason = (
            "independent candidate views both prove explicit non-credit "
            f"semantics: {primary_decision} / {context_decision}"
        )
    elif earlier_candidate_invisible:
        reason = (
            "single-frame view reports NO_TEXT and the candidate lacks a "
            "localized/fixed-edge emergence; contextual positivity begins later"
        )
    elif not independent:
        reason = "candidate semantic views lack independent provenance"
    elif not expected:
        reason = "allowed boundary kinds do not map to a semantic onset class"
    elif not context_positive:
        reason = "context candidate view did not prove the expected semantic class"
    else:
        reason = "single-frame candidate view contradicted the context decision"
    return {
        "gate_passed": gate,
        "definitive_noncredit": definitive_noncredit,
        "earlier_candidate_invisible": earlier_candidate_invisible,
        "reason": reason,
        "expected_decisions": sorted(expected),
        "allowed_kinds": sorted(allowed_kinds),
        "independent_views": independent,
        "allow_faint_primary_no_text": allow_faint_primary_no_text,
        "faint_edge_proof": faint_edge_proof,
        "primary_decision": primary_decision,
        "context_decision": context_decision,
        "views": [primary, context],
        "candidate_pos": candidate_positions[0],
        "input_sha256": input_hashes,
        "prompt_sha256": prompt_hashes,
        "call_ids": call_ids,
    }


def adjudicate_candidate_screen_disproof(
    primary: dict[str, Any],
    context: dict[str, Any],
    screen_view: dict[str, Any],
    *,
    allowed_kinds: set[str],
    faint_edge_proof: dict[str, Any],
    candidate_luma_mean: float,
) -> dict[str, Any]:
    """Override a screen hallucination only with a raw, independent proof."""
    expected_attribution = any(
        kind in {
            BoundaryKind.CREDIT_SEQUENCE.value,
            BoundaryKind.END_CARD_THEN_CREDITS.value,
        }
        for kind in allowed_kinds
    )
    views = [primary, context, screen_view]
    call_ids = [view.get("call_id") for view in views]
    input_hashes = [view.get("input_sha256") for view in views]
    prompt_hashes = [view.get("prompt_sha256") for view in views]
    variants = [view.get("prompt_variant") for view in views]
    positions = [view.get("candidate_pos") for view in views]
    independent = bool(
        all(isinstance(value, str) and value for value in call_ids)
        and len(set(call_ids)) == 3
        and all(isinstance(value, str) and len(value) == 64 for value in input_hashes)
        and len(set(input_hashes)) == 3
        and all(isinstance(value, str) and len(value) == 64 for value in prompt_hashes)
        and len(set(prompt_hashes)) == 3
        and variants == [
            "candidate_single",
            "candidate_context_triplet",
            "candidate_screen_disproof",
        ]
        and positions[0] is not None
        and len(set(positions)) == 1
        and all(
            view.get("prompt_protocol") == "candidate_semantic_audit_v1"
            for view in views
        )
    )

    def attribution(view: dict[str, Any]) -> bool:
        return bool(
            view.get("decision") == "ATTRIBUTION_CREDIT"
            and view.get("attribution_layout") is True
            and view.get("inside_story_screen") is False
        )

    def screen(view: dict[str, Any]) -> bool:
        return bool(
            view.get("decision") == "DIEGETIC_SCREEN"
            and view.get("attribution_layout") is False
            and view.get("inside_story_screen") is True
        )

    raw_disproves_screen = bool(
        attribution(screen_view)
        or (
            screen_view.get("decision") == "NO_TEXT"
            and screen_view.get("attribution_layout") is False
            and screen_view.get("inside_story_screen") is False
        )
    )
    asymmetric_recovery = bool(
        screen(primary) and attribution(context) and raw_disproves_screen
    )
    dark_card_recovery = bool(
        screen(primary)
        and screen(context)
        and raw_disproves_screen
        and faint_edge_proof.get("gate_passed") is True
        and float(candidate_luma_mean) <= 8.0
    )
    gate = bool(
        independent
        and expected_attribution
        and (asymmetric_recovery or dark_card_recovery)
    )
    return {
        "gate_passed": gate,
        "reason": (
            "raw full-frame screen disproof and an independent attribution "
            "witness overruled a layout-induced screen hallucination"
            if gate else
            "raw screen-disproof evidence did not safely overturn the screen vote"
        ),
        "candidate_pos": positions[0],
        "independent_views": independent,
        "expected_attribution": expected_attribution,
        "asymmetric_recovery": asymmetric_recovery,
        "dark_card_recovery": dark_card_recovery,
        "raw_disproves_screen": raw_disproves_screen,
        "candidate_luma_mean": round(float(candidate_luma_mean), 4),
        "dark_card_luma_max": 8.0,
        "faint_edge_proof": faint_edge_proof,
        "views": views,
        "call_ids": call_ids,
        "input_sha256": input_hashes,
        "prompt_sha256": prompt_hashes,
    }


def adjudicate_adjacent_partial_candidate(
    micro: dict[str, Any],
    candidate_audit: dict[str, Any],
    *,
    raw_change: dict[str, Any],
) -> dict[str, Any]:
    """Prove an entering one-frame partial without relaxing wider splits.

    A contextual semantic view can see a glyph cut by the lower image edge
    even when the candidate-only view cannot assign the few visible pixels to
    text.  This exception is deliberately limited to a primary/adversarial
    micro split of exactly one frame, a unanimous exact boundary on the later
    frame, and an independently positive contextual decision about the earlier
    candidate itself.
    """
    first_positions = [
        int(position) for position in (micro.get("first_positions") or [])
        if position is not None
    ]
    exact_positions = [
        int(position)
        for position in (micro.get("exact_first_positions") or [])
        if position is not None
    ]
    earliest = min(first_positions) if len(first_positions) == 2 else None
    later = max(first_positions) if len(first_positions) == 2 else None
    expected = set(candidate_audit.get("expected_decisions") or [])
    context_decision = candidate_audit.get("context_decision")
    gate = bool(
        earliest is not None
        and later == earliest + 1
        and first_positions[0] == earliest
        and len(exact_positions) == 2
        and exact_positions[0] == later
        and exact_positions[1] == later
        and micro.get("independent_transport_views") is True
        and micro.get("kind_compatible") is True
        and candidate_audit.get("independent_views") is True
        and candidate_audit.get("test_double_bypass") is not True
        and candidate_audit.get("candidate_pos") == earliest
        and candidate_audit.get("earlier_candidate_invisible") is True
        and candidate_audit.get("primary_decision") == "NO_TEXT"
        and context_decision in expected
        and context_decision in {"ATTRIBUTION_CREDIT", "END_CARD"}
        and raw_change.get("gate_passed") is True
    )
    return {
        "gate_passed": gate,
        "candidate_pos": earliest,
        "later_pos": later,
        "first_positions": first_positions,
        "exact_first_positions": exact_positions,
        "raw_change": raw_change,
        "reason": (
            "primary micro evidence and the contextual semantic view prove a "
            "one-frame lower-edge partial before the unanimous exact frame"
            if gate else
            "adjacent evidence does not prove a bounded lower-edge partial"
        ),
    }


def adjudicate_later_supported_partial_candidate(
    micro: dict[str, Any],
    candidate_audit: dict[str, Any],
    *,
    later_supports: list[dict[str, Any]],
    allowed_kinds: set[str],
    current_scope: str,
    max_distance_frames: int,
    raw_change: dict[str, Any],
) -> dict[str, Any]:
    """Recover a tiny partial only from a nearby, already proven same run.

    This covers an onset where both candidate semantic views see too few glyph
    pixels, while two micro views agree on the earlier frame, both exact views
    agree one frame later, and a separate chronology audit proves the sustained
    credit run a few frames downstream.  Explicit story/title/screen decisions
    are never eligible.
    """
    chosen = micro.get("chosen_pos")
    try:
        candidate_pos = int(chosen)
    except (TypeError, ValueError):
        candidate_pos = -1
    first_positions = [
        int(position) for position in (micro.get("first_positions") or [])
        if position is not None
    ]
    exact_positions = [
        int(position)
        for position in (micro.get("exact_first_positions") or [])
        if position is not None
    ]
    decisions_are_only_no_text = bool(
        candidate_audit.get("primary_decision") == "NO_TEXT"
        and candidate_audit.get("context_decision") == "NO_TEXT"
    )
    current_families = {
        _boundary_family(kind) for kind in allowed_kinds
        if _boundary_family(kind) != "NONE"
    }
    base_call_ids = {
        value for value in (candidate_audit.get("call_ids") or [])
        if isinstance(value, str) and value
    }
    base_inputs = {
        value for value in (candidate_audit.get("input_sha256") or [])
        if isinstance(value, str) and value
    }
    structural = bool(
        candidate_pos >= 1
        and len(first_positions) == 2
        and first_positions == [candidate_pos, candidate_pos]
        and len(exact_positions) == 2
        and exact_positions == [candidate_pos + 1, candidate_pos + 1]
        and micro.get("independent_transport_views") is True
        and micro.get("kind_compatible") is True
        and candidate_audit.get("independent_views") is True
        and candidate_audit.get("test_double_bypass") is not True
        and candidate_audit.get("candidate_pos") == candidate_pos
        and decisions_are_only_no_text
        and current_families == {"SUSTAINED_CREDITS"}
        and raw_change.get("gate_passed") is True
        and len(base_call_ids) == 2
        and len(base_inputs) == 2
    )
    selected: dict[str, Any] | None = None
    if structural:
        for support in later_supports:
            support_audit = support.get("audit") or {}
            try:
                support_pos = int(support.get("candidate_pos"))
            except (TypeError, ValueError):
                continue
            support_families = {
                _boundary_family(kind)
                for kind in (support.get("allowed_kinds") or [])
                if _boundary_family(kind) != "NONE"
            }
            support_calls = {
                value for value in (support_audit.get("call_ids") or [])
                if isinstance(value, str) and value
            }
            support_inputs = {
                value for value in (support_audit.get("input_sha256") or [])
                if isinstance(value, str) and value
            }
            if bool(
                support.get("scope") == current_scope
                and 0 < support_pos - candidate_pos <= max_distance_frames
                and support_families == current_families
                and support_audit.get("gate_passed") is True
                and support_audit.get("test_double_bypass") is not True
                and support_audit.get("candidate_pos") == support_pos
                and support_audit.get("primary_decision")
                == "ATTRIBUTION_CREDIT"
                and support_audit.get("context_decision")
                == "ATTRIBUTION_CREDIT"
                and len(support_calls) == 2
                and len(support_inputs) == 2
                and base_call_ids.isdisjoint(support_calls)
                and base_inputs.isdisjoint(support_inputs)
            ):
                selected = support
                break
    gate = selected is not None
    return {
        "gate_passed": gate,
        "candidate_pos": candidate_pos if candidate_pos >= 1 else None,
        "max_distance_frames": int(max_distance_frames),
        "raw_change": raw_change,
        "selected_support": selected,
        "reason": (
            "two micro views and a nearby independent same-run attribution "
            "audit prove the tiny entering partial"
            if gate else
            "no bounded independent same-run support proves the tiny partial"
        ),
    }


def _linspace_positions(start: int, end: int, count: int) -> list[int]:
    if end < start:
        raise ValueError("end must be >= start")
    if count < 2 or start == end:
        return [start]
    span = end - start
    positions = {
        start + int(math.floor((span * index / (count - 1)) + 0.5))
        for index in range(count)
    }
    positions.update({start, end})
    return sorted(positions)


def build_coarse_panels(
    total_frames: int,
    *,
    fps: float,
    proposal_positions: list[int] | None = None,
    config: WindowProtocolConfig | None = None,
) -> list[list[int]]:
    """Build <=~5 chronological 120 s panels with one shared boundary anchor."""
    cfg = config or WindowProtocolConfig()
    cfg.validate()
    if total_frames <= 0:
        return []
    if fps <= 0:
        raise ValueError("fps must be > 0")
    proposals = sorted({
        int(position) for position in (proposal_positions or [])
        if 0 <= int(position) < total_frames
    })
    span = max(
        cfg.coarse_anchor_count,
        int(math.floor(cfg.coarse_window_seconds * fps + 0.5)) + 1,
    )
    panels: list[list[int]] = []
    start = 0
    while start < total_frames:
        end = min(total_frames - 1, start + span - 1)
        remaining = total_frames - 1 - end
        if end < total_frames - 1 and remaining < max(2, span // 3):
            end = total_frames - 1
        anchors = _linspace_positions(start, end, cfg.coarse_anchor_count)
        # A short THE END card followed by a bounded black tail can live
        # entirely between the regular ~15 s anchors.  Densely sample the last
        # 15 s in the true final panel.  These cells only nominate a candidate;
        # fine + two exact semantic views are still mandatory for FOUND.
        if end == total_frames - 1:
            dense_start = max(
                start,
                end - int(math.ceil(cfg.terminal_dense_horizon_seconds * fps)),
            )
            dense_count = max(
                2,
                int(math.ceil(
                    cfg.terminal_dense_horizon_seconds
                    / cfg.terminal_dense_step_seconds
                )) + 1,
            )
            terminal_candidates = _linspace_positions(
                dense_start, end, dense_count
            )
            available = [
                position for position in terminal_candidates if position not in anchors
            ]
            room = max(0, cfg.coarse_max_cells - len(set(anchors)))
            if len(available) > room and room > 0:
                selected_indexes = _linspace_positions(0, len(available) - 1, room)
                available = [available[index] for index in selected_indexes]
            else:
                available = available[:room]
            for position in available:
                anchors.append(position)
            anchors = sorted(set(anchors))
        room = max(0, cfg.coarse_max_cells - len(anchors))
        local_proposals = [position for position in proposals if start <= position <= end]
        # Terminal-biased only when an unusually noisy panel has more CV hints
        # than transport cells; CV still cannot decide the semantic class.
        extras = local_proposals[-room:] if room else []
        panel = sorted(set([*anchors, *extras]))
        panels.append(panel)
        if end >= total_frames - 1:
            break
        start = end  # one shared chronological anchor between panels
    return panels


def build_fine_gap_positions(
    bracket: list[int],
    *,
    total_frames: int,
    fps: float,
    config: WindowProtocolConfig | None = None,
) -> list[int]:
    cfg = config or WindowProtocolConfig()
    if len(bracket) != 2 or bracket[0] > bracket[1]:
        raise ValueError(f"invalid bracket: {bracket}")
    pre = int(math.ceil(cfg.fine_pre_seconds * fps))
    post = int(math.ceil(cfg.fine_post_seconds * fps))
    start = max(0, int(bracket[0]) - pre)
    end = min(total_frames - 1, int(bracket[1]) + post)
    return _linspace_positions(start, end, cfg.fine_anchor_count)


def build_terminal_fine_positions(
    bracket: list[int],
    *,
    total_frames: int,
    fps: float,
    config: WindowProtocolConfig | None = None,
) -> list[int]:
    """Densely resolve a short END card while retaining true-EOF context."""
    cfg = config or WindowProtocolConfig()
    if len(bracket) != 2 or bracket[0] >= bracket[1]:
        raise ValueError(f"invalid terminal bracket: {bracket}")
    pre_frames = int(math.ceil(cfg.fine_pre_seconds * fps))
    post_frames = max(cfg.verify_dense_post_frames, int(math.ceil(3.0 * fps)))
    start = max(0, int(bracket[0]) - pre_frames)
    end = min(total_frames - 1, int(bracket[1]) + post_frames)
    base = set(_linspace_positions(start, end, cfg.fine_anchor_count))
    probe_radius = max(2, int(math.ceil(2.0 * fps)))
    mandatory = set(range(
        max(0, int(bracket[1]) - probe_radius),
        min(total_frames - 1, int(bracket[1]) + probe_radius) + 1,
    ))
    mandatory.update({int(bracket[0]), int(bracket[1])})
    eof = total_frames - 1
    for seconds in (0.0, 1.0, 3.0, 5.0, 8.0, cfg.terminal_blank_tail_seconds):
        offset = int(math.floor(seconds * fps + 0.5))
        mandatory.add(max(0, eof - offset))
    if len(mandatory) > cfg.terminal_fine_max_cells:
        raise ValueError(
            "terminal mandatory context exceeds terminal_fine_max_cells"
        )
    optional = sorted(base - mandatory)
    room = max(0, cfg.terminal_fine_max_cells - len(mandatory))
    if len(optional) > room and room > 0:
        keep = _linspace_positions(0, len(optional) - 1, room)
        optional = [optional[index] for index in keep]
    else:
        optional = optional[:room]
    return sorted({*mandatory, *optional})


def build_exact_verification_positions(
    approximate_pos: int,
    *,
    shift: int,
    total_frames: int,
    fps: float,
    pre_pos: int | None = None,
    config: WindowProtocolConfig | None = None,
) -> list[int]:
    cfg = config or WindowProtocolConfig()
    if pre_pos is not None:
        if not 0 <= pre_pos < approximate_pos < total_frames:
            raise ValueError(
                "pre_pos must be a real frame strictly before approximate_pos"
            )
        # Fine localization only proves that the onset is somewhere in
        # (pre_pos, approximate_pos].  Both exact panels must therefore carry
        # every frame in that gap.  Their different extra context makes the
        # sent mosaics independent without creating a coverage hole.
        positions = set(range(pre_pos, approximate_pos + 1))
        positions.update(range(
            approximate_pos + 1,
            min(
                total_frames,
                approximate_pos + cfg.verify_dense_post_frames + 1,
            ),
        ))
        context = (
            pre_pos - 1
            if shift < 0
            else approximate_pos + cfg.verify_dense_post_frames + 1
        )
        positions.add(min(total_frames - 1, max(0, context)))
    else:
        half_pre = max(2, cfg.verify_dense_frames // 2 + 1)
        dense_start = max(0, approximate_pos - half_pre + shift)
        dense_end = min(total_frames - 1, dense_start + cfg.verify_dense_frames - 1)
        positions = set(range(dense_start, dense_end + 1))
    for support_index, seconds in enumerate(cfg.verify_support_seconds):
        # Verification B uses a shifted support cadence as well as a different
        # mosaic layout/prompt.  Both views retain a long future horizon but do
        # not simply replay an almost identical panel.
        if shift >= 0:
            effective_seconds = seconds
        elif support_index == 0:
            effective_seconds = seconds + 1.0
        elif support_index == 1:
            effective_seconds = seconds
        else:
            effective_seconds = max(1.0, seconds - 1.0)
        support = approximate_pos + int(
            math.floor(effective_seconds * fps + 0.5)
        )
        positions.add(min(total_frames - 1, max(0, support)))
    return sorted(positions)


def build_rescue_localization_positions(
    semantic_pre_pos: int,
    right_pos: int,
    *,
    support_pos: int,
    variant: str,
    total_frames: int,
    fps: float,
    config: WindowProtocolConfig | None = None,
    candidate_floor_exclusive: int | None = None,
) -> tuple[list[int], tuple[int, int]]:
    """Build a small high-resolution panel that narrows a coarse gap.

    Unlike the legacy exact panel, this view does not carry every frame in a
    potentially subtitle-heavy gap.  Five or six anchors locate the semantic
    transition first; a later compact panel then examines every nearby frame.
    """
    cfg = config or WindowProtocolConfig()
    if variant not in {"a", "b"}:
        raise ValueError("variant must be 'a' or 'b'")
    if not 0 < semantic_pre_pos < right_pos < total_frames:
        raise ValueError("rescue localization requires PRE < right in bounds")
    if candidate_floor_exclusive is not None and not (
        semantic_pre_pos <= candidate_floor_exclusive < right_pos
    ):
        raise ValueError(
            "exclusive rescue floor must be inside the PRE-to-right gap"
        )
    count = cfg.rescue_localize_anchor_count + (1 if variant == "b" else 0)
    candidate_start = (
        max(semantic_pre_pos, candidate_floor_exclusive + 1)
        if candidate_floor_exclusive is not None else semantic_pre_pos
    )
    candidates = _linspace_positions(candidate_start, right_pos, count)
    if candidate_floor_exclusive is None:
        context = max(0, semantic_pre_pos - (2 if variant == "b" else 1))
        extra_context = context
    else:
        context = max(0, candidate_start - 1)
        extra_context = max(0, context - 1) if variant == "b" else context
    min_support = right_pos + int(math.ceil(cfg.min_support_seconds * fps))
    support = max(int(support_pos), min_support)
    max_support = right_pos + int(math.ceil(max(cfg.verify_support_seconds) * fps))
    support = min(support, max_support)
    if variant == "b" and support - 1 >= min_support:
        support -= 1
    support = min(total_frames - 1, support)
    positions = sorted({extra_context, context, *candidates, support})
    indexes = [positions.index(position) for position in candidates]
    if indexes[0] < 1 or indexes != list(range(indexes[0], indexes[-1] + 1)):
        raise ValueError("rescue localization candidates lack contiguous PRE context")
    return positions, (indexes[0], indexes[-1])


def build_rescue_compact_positions(
    localized_positions: list[int],
    *,
    semantic_pre_pos: int,
    localized_pre_pos: int | None = None,
    support_pos: int,
    variant: str,
    total_frames: int,
    fps: float,
    config: WindowProtocolConfig | None = None,
    candidate_floor_exclusive: int | None = None,
) -> tuple[list[int], tuple[int, int]]:
    """Build the final dense, high-resolution boundary agreement view."""
    cfg = config or WindowProtocolConfig()
    if variant not in {"a", "b"}:
        raise ValueError("variant must be 'a' or 'b'")
    if not localized_positions:
        raise ValueError("localized_positions cannot be empty")
    if candidate_floor_exclusive is not None and not (
        semantic_pre_pos <= candidate_floor_exclusive < total_frames - 1
    ):
        raise ValueError(
            "exclusive compact floor must follow semantic PRE and leave a candidate"
        )
    local_min = min(int(position) for position in localized_positions)
    local_max = max(int(position) for position in localized_positions)
    if localized_pre_pos is not None:
        if not semantic_pre_pos <= localized_pre_pos < local_min:
            raise ValueError(
                "localized_pre_pos must be a proven PRE before localized starts"
            )
        # Each sparse localization view only proves an interval
        # (its_previous_cell, its_first_cell].  Densely inspect the entire
        # intersection interval; looking merely one frame around `first`
        # misses early onsets when sparse anchors are 8-15 frames apart.
        # Include the least-conservative sparse PRE claim as a candidate while
        # keeping its real predecessor as context. A/B sparse views can
        # disagree about a faint fade; final exact + micro adjudication, not a
        # single sparse PRE label, decides that frame.
        candidate_low = max(1, localized_pre_pos)
        candidate_high = min(total_frames - 2, local_max)
    else:
        candidate_low = max(semantic_pre_pos, local_min - 1)
        if variant == "b":
            candidate_low = max(semantic_pre_pos, candidate_low - 1)
        candidate_high = min(total_frames - 2, local_max + 1)
    if candidate_floor_exclusive is not None:
        candidate_low = max(candidate_low, candidate_floor_exclusive + 1)
    if candidate_low > candidate_high:
        raise ValueError("invalid compact rescue candidate range")
    # B already differs through one extra candidate cell and a two-column
    # adversarial layout.  Keep its immediate predecessor adjacent as well;
    # a distant context cell makes faint first-credit text unnecessarily hard
    # to compare at the final frame-level decision.
    context = max(0, candidate_low - 1)
    extra_context = (
        max(0, context - 1)
        if localized_pre_pos is not None and variant == "b"
        else context
    )
    if context >= candidate_low:
        raise ValueError("compact rescue view lacks PRE context")
    candidates = list(range(candidate_low, candidate_high + 1))
    min_support = candidate_high + int(math.ceil(cfg.min_support_seconds * fps))
    support = max(int(support_pos), min_support)
    max_support = candidate_high + int(
        math.ceil(max(cfg.verify_support_seconds) * fps)
    )
    support = min(support, max_support)
    support = min(total_frames - 1, support)
    positions = sorted({extra_context, context, *candidates, support})
    indexes = [positions.index(position) for position in candidates]
    if indexes[0] < 1 or indexes != list(range(indexes[0], indexes[-1] + 1)):
        raise ValueError("compact rescue candidates lack contiguous PRE context")
    return positions, (indexes[0], indexes[-1])


def build_micro_boundary_positions(
    exact_first_positions: list[int],
    *,
    support_pos: int,
    variant: str,
    total_frames: int,
    fps: float,
    at_stream_eof: bool = False,
    config: WindowProtocolConfig | None = None,
) -> tuple[list[int], tuple[int, int]]:
    """Build a tiny raw-frame panel that adjudicates the disputed fade edge."""
    cfg = config or WindowProtocolConfig()
    if variant not in {"a", "b"}:
        raise ValueError("variant must be 'a' or 'b'")
    if len(exact_first_positions) != 2:
        raise ValueError("micro adjudication requires exactly two exact positions")
    first_a, first_b = (int(value) for value in exact_first_positions)
    low = min(first_a, first_b)
    high = max(first_a, first_b)
    if high - low > cfg.micro_max_disagreement_frames:
        raise ValueError("exact disagreement is too wide for micro adjudication")
    # Only a unanimous exact pair may have jointly missed one faint predecessor.
    # When A/B already disagree, neither has claimed the earlier context frame;
    # keep it as PRE context rather than letting one micro view hallucinate a
    # texture/fire edge into an earlier onset (observed on real DRAKULA).
    low = max(1, low - 1 if first_a == first_b else low)
    if not 1 <= low <= high < total_frames:
        raise ValueError("micro candidate range is outside the frame set")
    candidates = list(range(low, high + 1))
    context = low - 1
    short_seconds, long_seconds = ((3.0, 8.0) if variant == "a" else (4.0, 9.0))
    short_support = min(
        total_frames - 1,
        max(
            high + 1,
            high + int(math.floor(short_seconds * fps + 0.5)),
        ),
    )
    long_support = min(
        total_frames - 1,
        max(
            int(support_pos),
            high + int(math.floor(long_seconds * fps + 0.5)),
        ),
    )
    if at_stream_eof:
        long_support = total_frames - 1
    if len(candidates) >= 4:
        if variant == "b" and not at_stream_eof and long_support - 1 > high:
            long_support -= 1
        positions = sorted({context, *candidates, long_support})
    else:
        positions = sorted({context, *candidates, short_support, long_support})
    if variant == "b" and context > 0 and len(positions) < 6:
        positions = sorted({context - 1, *positions})
    indexes = [positions.index(position) for position in candidates]
    if indexes[0] < 1 or indexes != list(range(indexes[0], indexes[-1] + 1)):
        raise ValueError("micro candidates lack a contiguous real predecessor")
    if len(positions) > 6:
        raise ValueError("micro panel exceeds six-cell hard cap")
    return positions, (indexes[0], indexes[-1])


def bounded_verification_tile_width(
    cell_count: int,
    *,
    columns: int,
    config: WindowProtocolConfig | None = None,
) -> int:
    """Keep an exact mosaic below the local VLM's practical context budget.

    Qwen vision tokens grow with the composed mosaic, not just the number of
    source frames.  The detector retains 640 px tiles for small exact views and
    steps down in 32 px increments for larger dense-gap views.  The 16:9
    estimate is the declared 720p input contract; the model call remains
    fail-closed if even the configured minimum cannot satisfy the budget.
    """
    cfg = config or WindowProtocolConfig()
    if cell_count <= 0:
        raise ValueError("cell_count must be > 0")
    if columns <= 0:
        raise ValueError("columns must be > 0")
    rows = int(math.ceil(cell_count / columns))

    def estimated_pixels(tile_width: int) -> int:
        tile_height = int(round(tile_width * 9 / 16))
        cell_height = tile_height + 22
        return columns * tile_width * rows * cell_height

    widths = list(range(
        cfg.verify_tile_width,
        cfg.verify_min_tile_width - 1,
        -32,
    ))
    if not widths or widths[-1] != cfg.verify_min_tile_width:
        widths.append(cfg.verify_min_tile_width)
    for width in widths:
        if estimated_pixels(width) <= cfg.verify_max_mosaic_pixels:
            return width
    raise ValueError(
        "exact verification mosaic exceeds verify_max_mosaic_pixels even at "
        "verify_min_tile_width"
    )


def _is_supported(
    evidence: WindowEvidence,
    *,
    fps: float,
    min_support_seconds: float,
    terminal_blank_tail_seconds: float = 15.0,
) -> bool:
    if evidence.verdict not in {
        WindowVerdict.TRANSITION.value,
        WindowVerdict.ACTIVE_FROM_LEFT.value,
    }:
        return False
    if evidence.continuity != Continuity.CONFIRMED.value:
        return False
    if evidence.reject != "NONE":
        return False
    if evidence.first_pos is None or evidence.last_support_pos is None:
        return False
    if evidence.kind == BoundaryKind.TERMINAL_END_CARD.value:
        return (
            evidence.at_stream_eof
            and evidence.last_support_cell > evidence.first_cell
            and (
                evidence.positions[-1] - evidence.last_support_pos
            ) / fps <= terminal_blank_tail_seconds + 1e-9
        )
    return (
        evidence.last_support_pos - evidence.first_pos
    ) / fps >= min_support_seconds - 1e-9


def decode_coarse_windows(
    evidence: list[WindowEvidence],
    *,
    fps: float,
    config: WindowProtocolConfig | None = None,
) -> CoarseOutcome:
    """Choose a refine bracket without turning a window into fake frame hits."""
    cfg = config or WindowProtocolConfig()
    ordered = sorted(evidence, key=lambda item: item.positions[0])
    if not ordered:
        return CoarseOutcome(DetectionStatus.NOT_FOUND.value, "no coarse windows")
    if any(item.verdict == WindowVerdict.MISSING.value for item in ordered):
        return CoarseOutcome(
            DetectionStatus.MODEL_ERROR.value,
            "one or more coarse VLM windows are missing",
        )

    transitions = [
        item for item in ordered
        if item.verdict == WindowVerdict.TRANSITION.value
        and _is_supported(
            item,
            fps=fps,
            min_support_seconds=cfg.min_support_seconds,
            terminal_blank_tail_seconds=cfg.terminal_blank_tail_seconds,
        )
    ]
    transition_starts = sorted({
        int(item.first_pos) for item in transitions if item.first_pos is not None
    })
    unresolved_positive = [
        item for item in ordered
        if item.verdict in {
            WindowVerdict.TRANSITION.value,
            WindowVerdict.ACTIVE_FROM_LEFT.value,
        }
        and item.reject == "NONE"
        and not _is_supported(
            item,
            fps=fps,
            min_support_seconds=cfg.min_support_seconds,
            terminal_blank_tail_seconds=cfg.terminal_blank_tail_seconds,
        )
    ]
    supported_active = [
        item for item in ordered
        if item.verdict == WindowVerdict.ACTIVE_FROM_LEFT.value
        and _is_supported(
            item,
            fps=fps,
            min_support_seconds=cfg.min_support_seconds,
            terminal_blank_tail_seconds=cfg.terminal_blank_tail_seconds,
        )
    ]
    terminal_probes = [
        item for item in unresolved_positive
        if item.verdict == WindowVerdict.TRANSITION.value
        and item.kind == BoundaryKind.TERMINAL_END_CARD.value
        and item.at_stream_eof
        and item.reject == "NONE"
        and item.first_cell >= 1
        and item.last_support_pos is not None
        and (
            item.positions[-1] - item.last_support_pos
        ) / fps <= cfg.terminal_blank_tail_seconds + 1e-9
    ]
    if (
        len(terminal_probes) == 1
        and not transitions
        and not supported_active
        and len(unresolved_positive) == 1
        and all(
            item is terminal_probes[0]
            or item.verdict == WindowVerdict.PRE_ONLY.value
            for item in ordered
        )
    ):
        probe = terminal_probes[0]
        bracket = [
            probe.positions[probe.first_cell - 1],
            probe.positions[probe.first_cell],
        ]
        return CoarseOutcome(
            "REFINE",
            "single-cell terminal EOF probe requires dense semantic confirmation",
            bracket=bracket,
            candidate_starts=[int(probe.first_pos)],
            provisional_start=int(probe.first_pos),
            boundary_kind=probe.kind,
        )
    seam_pairs: list[tuple[WindowEvidence, WindowEvidence]] = []
    for active_item in supported_active:
        active_index = ordered.index(active_item)
        if active_index == 0:
            continue
        previous = ordered[active_index - 1]
        shared_core_anchor = previous.positions[-1] == active_item.positions[0]
        late_unsupported_transition = (
            previous in unresolved_positive
            and previous.verdict == WindowVerdict.TRANSITION.value
            and previous.first_cell >= max(1, len(previous.positions) - 2)
        )
        seam_ambiguous = previous.verdict == WindowVerdict.AMBIGUOUS.value
        if (
            shared_core_anchor
            and previous.reject == "NONE"
            and (late_unsupported_transition or seam_ambiguous)
        ):
            seam_pairs.append((previous, active_item))
    seam_predecessor_ids = {id(previous) for previous, _active in seam_pairs}
    supported_rows = sorted(
        [*transitions, *supported_active], key=lambda item: ordered.index(item)
    )
    first_supported_index = (
        ordered.index(supported_rows[0]) if supported_rows else None
    )
    rejected_positive = [
        item for item in ordered
        if item.verdict in {
            WindowVerdict.TRANSITION.value,
            WindowVerdict.ACTIVE_FROM_LEFT.value,
        }
        and item.reject != "NONE"
    ]
    if not supported_rows and rejected_positive:
        return CoarseOutcome(
            DetectionStatus.REVIEW.value,
            "rejected positive coarse evidence requires focused semantic rescue",
            candidate_starts=[
                int(item.first_pos)
                if item.first_pos is not None else int(item.positions[0])
                for item in rejected_positive
            ],
        )
    earlier_ambiguous = [
        item for index, item in enumerate(ordered)
        if first_supported_index is not None
        and index < first_supported_index
        and item.verdict == WindowVerdict.AMBIGUOUS.value
    ]
    if earlier_ambiguous:
        return CoarseOutcome(
            DetectionStatus.REVIEW.value,
            "earlier ambiguous evidence requires chronological rescue",
            candidate_starts=[
                *[int(item.positions[0]) for item in earlier_ambiguous],
                *[
                    int(item.first_pos)
                    if item.first_pos is not None else int(item.positions[0])
                    for item in supported_rows
                ],
            ],
            provisional_start=(
                int(supported_rows[0].first_pos)
                if supported_rows[0].first_pos is not None else None
            ),
        )
    # A semantic rejection at the shared seam is not an ordinary weak/missing
    # positive.  If one window calls that seam story-world text and the next
    # calls the same chronology active credits, refining through the conflict
    # would be fail-open.  NO_VISIBLE_ATTRIBUTION is intentionally excluded:
    # the real model can emit it for an all-footage window whose final shared
    # anchor is immediately followed by the actual credit transition.
    hard_rejects = {"DIEGETIC", "STORY_TEXT", "MIXED"}
    for supported in supported_rows:
        supported_index = ordered.index(supported)
        if supported_index == 0:
            continue
        previous = ordered[supported_index - 1]
        if (
            previous.positions[-1] == supported.positions[0]
            and previous.reject in hard_rejects
        ):
            return CoarseOutcome(
                DetectionStatus.REVIEW.value,
                "hard semantic rejection conflicts with credits at a shared coarse seam",
                candidate_starts=[
                    int(previous.first_pos or previous.positions[-1]),
                    int(supported.first_pos or supported.positions[0]),
                ],
            )
    earlier_rejected_positive = [
        item for index, item in enumerate(ordered)
        if first_supported_index is not None
        and index < first_supported_index
        and item in rejected_positive
    ]
    if earlier_rejected_positive:
        return CoarseOutcome(
            DetectionStatus.REVIEW.value,
            "earlier rejected positive evidence requires chronological rescue",
            candidate_starts=[
                *[
                    int(item.first_pos)
                    if item.first_pos is not None else int(item.positions[0])
                    for item in earlier_rejected_positive
                ],
                *[
                    int(item.first_pos)
                    if item.first_pos is not None else int(item.positions[0])
                    for item in supported_rows
                ],
            ],
            provisional_start=(
                int(supported_rows[0].first_pos)
                if supported_rows and supported_rows[0].first_pos is not None
                else None
            ),
        )
    if len({item.kind for item in supported_rows}) > 1:
        return CoarseOutcome(
            DetectionStatus.REVIEW.value,
            "supported coarse positive views disagree on boundary kind",
            candidate_starts=[
                int(item.first_pos if item.first_pos is not None else item.positions[0])
                for item in supported_rows
            ],
        )
    blocking_unresolved: list[WindowEvidence] = []
    for item in unresolved_positive:
        if id(item) in seam_predecessor_ids:
            continue
        item_index = ordered.index(item)
        separated_from_supported = (
            first_supported_index is not None
            and any(
                row.verdict == WindowVerdict.PRE_ONLY.value
                for row in ordered[first_supported_index + 1:item_index]
            )
        )
        if (
            first_supported_index is None
            or item_index < first_supported_index
            or separated_from_supported
        ):
            blocking_unresolved.append(item)
    if blocking_unresolved:
        return CoarseOutcome(
            DetectionStatus.REVIEW.value,
            "coarse scan contains positive but unsupported semantic evidence",
            candidate_starts=[
                int(item.first_pos if item.first_pos is not None else item.positions[0])
                for item in blocking_unresolved
            ],
        )
    if len(seam_pairs) > 1:
        return CoarseOutcome(
            DetectionStatus.REVIEW.value,
            "multiple unresolved coarse seams compete for the onset",
            candidate_starts=[active.positions[0] for _previous, active in seam_pairs],
        )
    positive_segments = 0
    inside_positive_segment = False
    pre_since_positive = False
    for item in ordered:
        is_positive = (
            item.reject == "NONE"
            and item.verdict in {
                WindowVerdict.TRANSITION.value,
                WindowVerdict.ACTIVE_FROM_LEFT.value,
            }
        )
        if is_positive:
            if not inside_positive_segment or pre_since_positive:
                positive_segments += 1
            inside_positive_segment = True
            pre_since_positive = False
        elif item.verdict == WindowVerdict.PRE_ONLY.value and inside_positive_segment:
            pre_since_positive = True
    if positive_segments > 1:
        starts = [
            int(item.first_pos if item.first_pos is not None else item.positions[0])
            for item in ordered
            if item.verdict in {
                WindowVerdict.TRANSITION.value,
                WindowVerdict.ACTIVE_FROM_LEFT.value,
            }
            and item.reject == "NONE"
        ]
        return CoarseOutcome(
            DetectionStatus.REVIEW.value,
            "multiple positive coarse regimes separated by PRE_ONLY evidence",
            candidate_starts=starts,
            provisional_start=starts[-1] if starts else None,
        )
    if supported_rows:
        earliest_supported = supported_rows[0]
        if earliest_supported.verdict == WindowVerdict.TRANSITION.value:
            transitions = [earliest_supported]
            transition_starts = [int(earliest_supported.first_pos)]
        else:
            transitions = []
            transition_starts = []
    clusters: list[list[int]] = []
    max_cluster_gap = max(1, int(math.ceil(30.0 * fps)))
    for position in transition_starts:
        if not clusters or position - clusters[-1][-1] > max_cluster_gap:
            clusters.append([position])
        else:
            clusters[-1].append(position)
    if len(clusters) > 1:
        flat = [item for cluster in clusters for item in cluster]
        return CoarseOutcome(
            DetectionStatus.REVIEW.value,
            "multiple separated coarse transition groups",
            candidate_starts=flat,
            provisional_start=flat[-1],
        )
    if clusters:
        candidate_cluster = clusters[0]
        candidate = min(candidate_cluster)
        source = min(
            (item for item in transitions if item.first_pos in candidate_cluster),
            key=lambda item: int(item.first_pos or 0),
        )
        earlier_broken_group = any(
            item.verdict == WindowVerdict.ACTIVE_FROM_LEFT.value
            and item.positions[-1] < candidate
            and any(
                middle.verdict == WindowVerdict.PRE_ONLY.value
                and item.positions[-1] <= middle.positions[0] < candidate
                for middle in ordered
            )
            for item in ordered
        )
        if earlier_broken_group:
            return CoarseOutcome(
                DetectionStatus.REVIEW.value,
                "earlier ACTIVE_FROM_LEFT group returns to PRE before the later transition",
                candidate_starts=[
                    *[item.positions[0] for item in ordered
                      if item.verdict == WindowVerdict.ACTIVE_FROM_LEFT.value
                      and item.positions[-1] < candidate],
                    *candidate_cluster,
                ],
                provisional_start=candidate,
            )
        if source.first_cell < 1:
            return CoarseOutcome(
                DetectionStatus.REVIEW.value,
                "TRANSITION lacks a local PRE cell",
                provisional_start=candidate,
            )
        bracket = [
            source.positions[source.first_cell - 1],
            source.positions[source.first_cell],
        ]
        if any(
            (
                item.verdict == WindowVerdict.AMBIGUOUS.value
                or item in unresolved_positive
            )
            and item.positions[0] <= bracket[1]
            for item in ordered
        ):
            return CoarseOutcome(
                DetectionStatus.REVIEW.value,
                "unresolved earlier/coincident coarse evidence precedes the transition",
                bracket=bracket,
                candidate_starts=candidate_cluster,
                provisional_start=candidate,
            )
        return CoarseOutcome(
            "REFINE",
            "one supported coarse transition bracket",
            bracket=bracket,
            candidate_starts=candidate_cluster,
            provisional_start=candidate,
            boundary_kind=source.kind,
        )

    active = supported_active
    for item in active:
        index = ordered.index(item)
        seam_previous = next(
            (
                previous for previous, active_item in seam_pairs
                if active_item is item
            ),
            None,
        )
        if seam_previous is not None:
            if (
                seam_previous.verdict == WindowVerdict.TRANSITION.value
                and seam_previous.first_cell >= 1
            ):
                left = seam_previous.positions[seam_previous.first_cell - 1]
            else:
                left = (
                    seam_previous.positions[-2]
                    if len(seam_previous.positions) > 1
                    else seam_previous.positions[-1]
                )
            right = item.positions[1] if len(item.positions) > 1 else item.positions[0]
            return CoarseOutcome(
                "REFINE",
                "late unresolved seam followed by ACTIVE_FROM_LEFT requires dense refinement",
                bracket=[left, right],
                provisional_start=item.positions[0],
                boundary_kind=item.kind,
            )
        earlier = ordered[:index]
        pre = [row for row in earlier if row.verdict == WindowVerdict.PRE_ONLY.value]
        if pre:
            previous = pre[-1]
            previous_index = ordered.index(previous)
            unresolved_between = ordered[previous_index + 1:index]
            if any(
                row.verdict == WindowVerdict.AMBIGUOUS.value
                or row in unresolved_positive
                for row in unresolved_between
            ):
                return CoarseOutcome(
                    DetectionStatus.REVIEW.value,
                    "unresolved coarse evidence lies between PRE_ONLY and ACTIVE_FROM_LEFT",
                    provisional_start=item.positions[0],
                )
            left = previous.positions[-2] if len(previous.positions) > 1 else previous.positions[-1]
            right = item.positions[1] if len(item.positions) > 1 else item.positions[0]
            return CoarseOutcome(
                "REFINE",
                "PRE_ONLY to ACTIVE_FROM_LEFT requires dense refinement",
                bracket=[left, right],
                provisional_start=item.positions[0],
                boundary_kind=item.kind,
            )
    if active:
        return CoarseOutcome(
            DetectionStatus.LEFT_CENSORED.value,
            "credits are active before the first confident PRE context",
            candidate_starts=[item.positions[0] for item in active],
        )
    if any(item.verdict == WindowVerdict.AMBIGUOUS.value for item in ordered):
        return CoarseOutcome(
            DetectionStatus.REVIEW.value,
            "coarse scan contains unresolved semantic evidence",
        )
    return CoarseOutcome(
        DetectionStatus.NOT_FOUND.value,
        "all coarse windows are PRE_ONLY",
    )


def _write_window_timeline(path: Path, evidence: list[WindowEvidence]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "stage", "verdict", "first_pos", "last_support_pos", "kind",
            "continuity", "reject", "at_stream_eof", "positions", "call_id",
        ])
        writer.writeheader()
        for item in evidence:
            writer.writerow({
                "stage": item.stage,
                "verdict": item.verdict,
                "first_pos": item.first_pos,
                "last_support_pos": item.last_support_pos,
                "kind": item.kind,
                "continuity": item.continuity,
                "reject": item.reject,
                "at_stream_eof": item.at_stream_eof,
                "positions": " ".join(str(position) for position in item.positions),
                "call_id": item.call_id,
            })


class WindowClosingCreditOnsetDetector:
    """Fail-closed experimental detector based on corroborating window evidence."""

    def __init__(
        self,
        config: DetectionConfig,
        *,
        protocol: WindowProtocolConfig | None = None,
        locator: Any | None = None,
        score_provider: Callable[..., Any] | None = None,
        allowed_output_root: Path | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.protocol = protocol or WindowProtocolConfig()
        self.protocol.validate()
        self.locator = locator or OllamaFrameClassifier(
            model=config.model,
            host=config.ollama_host,
            timeout_seconds=config.timeout_seconds,
            keep_alive=config.keep_alive,
            image_width=config.image_width,
            mosaic_columns=config.mosaic_columns,
            jpeg_quality=config.jpeg_quality,
            num_ctx=config.num_ctx,
            num_predict=config.num_predict,
            seed=config.seed,
            temperature=config.temperature,
            retry_count=config.retry_count,
        )
        self.score_provider = score_provider or score_frames
        repository_root = Path(__file__).resolve().parents[2]
        self.repository_root = repository_root
        self.allowed_output_root = (
            allowed_output_root
            or repository_root / "outputs" / "closing_credit_onset_vlm"
        ).resolve()

    @staticmethod
    def _validate_call_provenance(
        result: VlmWindowResult,
        *,
        stage: str,
        positions: list[int],
        refs: list[FrameRef],
        capture: Path,
        at_stream_eof: bool,
        boundary_search_cells: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        record = dict(result.call_record)
        evidence = result.evidence
        errors: list[str] = []
        expected_files = [ref.path.name for ref in refs]
        expected_variant = (
            "adversarial_reject"
            if stage == "verify_b" or stage.endswith("_b")
            else "primary_boundary"
        )

        if record.get("ok") is not True:
            errors.append("record.ok is not true")
        if record.get("stage") != stage or evidence.stage != stage:
            errors.append("stage mismatch")
        if record.get("frame_positions") != positions or evidence.positions != positions:
            errors.append("frame positions mismatch")
        if record.get("frame_files") != expected_files or evidence.files != expected_files:
            errors.append("frame files mismatch")
        record_call_id = record.get("call_id")
        if (
            not isinstance(record_call_id, str)
            or not record_call_id
            or evidence.call_id != record_call_id
        ):
            errors.append("record/evidence call_id mismatch")
        if record.get("at_stream_eof") is not at_stream_eof:
            errors.append("at_stream_eof mismatch")
        if evidence.at_stream_eof is not at_stream_eof:
            errors.append("evidence EOF flag mismatch")
        expected_boundary_cells = (
            list(boundary_search_cells)
            if boundary_search_cells is not None else None
        )
        if record.get("boundary_search_cells") != expected_boundary_cells:
            errors.append("boundary search cell range mismatch")
        if evidence.metadata.get("boundary_search_cells") != expected_boundary_cells:
            errors.append("evidence boundary search cell range mismatch")
        positive_verdicts = {
            WindowVerdict.TRANSITION.value,
            WindowVerdict.ACTIVE_FROM_LEFT.value,
        }
        if evidence.verdict in positive_verdicts:
            if not (
                0 <= evidence.first_cell < len(positions)
                and evidence.first_cell <= evidence.last_support_cell < len(positions)
            ):
                errors.append("positive evidence cell indexes are invalid")
            else:
                if positions[evidence.first_cell] != evidence.first_pos:
                    errors.append("first_cell/first_pos mismatch")
                if positions[evidence.last_support_cell] != evidence.last_support_pos:
                    errors.append("last_support_cell/last_support_pos mismatch")
            if (
                evidence.verdict == WindowVerdict.TRANSITION.value
                and evidence.first_cell < 1
            ):
                errors.append("TRANSITION lacks a local PRE cell")
            if (
                evidence.verdict == WindowVerdict.ACTIVE_FROM_LEFT.value
                and evidence.first_cell != 0
            ):
                errors.append("ACTIVE_FROM_LEFT does not begin at cell zero")
            if evidence.kind == BoundaryKind.NONE.value:
                errors.append("positive evidence has NONE boundary kind")
        elif evidence.verdict in {
            WindowVerdict.PRE_ONLY.value,
            WindowVerdict.AMBIGUOUS.value,
        }:
            if (
                evidence.first_cell != -1
                or evidence.last_support_cell != -1
                or evidence.first_pos is not None
                or evidence.last_support_pos is not None
                or evidence.kind != BoundaryKind.NONE.value
            ):
                errors.append("negative/ambiguous evidence carries a fake boundary")
        else:
            errors.append("invalid window verdict")
        if record.get("prompt_protocol") != "window_boundary_v1":
            errors.append("missing or invalid prompt protocol")
        if record.get("prompt_variant") != expected_variant:
            errors.append("missing or invalid prompt variant")

        prompt_hash = record.get("prompt_sha256")
        if not (
            isinstance(prompt_hash, str)
            and len(prompt_hash) == 64
            and all(char in "0123456789abcdefABCDEF" for char in prompt_hash)
        ):
            errors.append("missing or invalid prompt SHA-256")

        recorded_capture = record.get("input_mosaic_path")
        input_hash = record.get("input_sha256")
        if not isinstance(recorded_capture, str) or not recorded_capture:
            errors.append("missing input mosaic path")
        elif Path(recorded_capture).resolve() != capture.resolve():
            errors.append("input mosaic path mismatch")
        if not capture.is_file():
            errors.append("captured input mosaic is missing")
        else:
            actual_hash = hashlib.sha256(capture.read_bytes()).hexdigest()
            if input_hash != actual_hash:
                errors.append("captured input SHA-256 mismatch")

        if errors:
            record["locator_ok"] = record.get("ok")
            record["ok"] = False
            record["detector_validation_ok"] = False
            record["error_kind"] = "provenance_validation"
            record["error"] = "; ".join(errors)
            raise VlmCallError(
                "VLM call provenance failed strict validation", record=record
            )
        record["detector_validation_ok"] = True
        return record

    @staticmethod
    def _validate_candidate_semantic_provenance(
        result: VlmCandidateAuditResult,
        *,
        stage: str,
        variant: str,
        candidate_pos: int,
        refs: list[FrameRef],
        capture: Path,
    ) -> dict[str, Any]:
        record = dict(result.call_record)
        errors: list[str] = []
        expected_positions = [ref.pos for ref in refs]
        expected_files = [ref.path.name for ref in refs]
        expected_prompt_variant = {
            "a": "candidate_single",
            "b": "candidate_context_triplet",
            "s": "candidate_screen_disproof",
        }.get(variant)
        if expected_prompt_variant is None:
            errors.append("unsupported candidate semantic variant")
        if record.get("ok") is not True:
            errors.append("record.ok is not true")
        if record.get("stage") != stage:
            errors.append("stage mismatch")
        if record.get("semantic_variant") != variant:
            errors.append("semantic variant mismatch")
        if record.get("candidate_pos") != candidate_pos:
            errors.append("candidate position mismatch")
        if record.get("frame_positions") != expected_positions:
            errors.append("frame positions mismatch")
        if record.get("frame_files") != expected_files:
            errors.append("frame files mismatch")
        call_id = record.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            errors.append("missing candidate semantic call_id")
        if record.get("prompt_protocol") != "candidate_semantic_audit_v1":
            errors.append("invalid candidate semantic prompt protocol")
        if record.get("prompt_variant") != expected_prompt_variant:
            errors.append("invalid candidate semantic prompt variant")
        parsed = record.get("response_json")
        if not isinstance(parsed, dict):
            errors.append("missing candidate semantic response JSON")
        else:
            if parsed.get("decision") != result.decision:
                errors.append("candidate semantic decision mismatch")
            if parsed.get("attribution_layout") is not result.attribution_layout:
                errors.append("candidate attribution flag mismatch")
            if parsed.get("inside_story_screen") is not result.inside_story_screen:
                errors.append("candidate story-screen flag mismatch")

        prompt_hash = record.get("prompt_sha256")
        if not (
            isinstance(prompt_hash, str)
            and len(prompt_hash) == 64
            and all(char in "0123456789abcdefABCDEF" for char in prompt_hash)
        ):
            errors.append("missing or invalid prompt SHA-256")
        recorded_capture = record.get("input_mosaic_path")
        input_hash = record.get("input_sha256")
        if not isinstance(recorded_capture, str) or not recorded_capture:
            errors.append("missing input mosaic path")
        elif Path(recorded_capture).resolve() != capture.resolve():
            errors.append("input mosaic path mismatch")
        if not capture.is_file():
            errors.append("captured input mosaic is missing")
        else:
            actual_hash = hashlib.sha256(capture.read_bytes()).hexdigest()
            if input_hash != actual_hash:
                errors.append("captured input SHA-256 mismatch")
        if errors:
            record["locator_ok"] = record.get("ok")
            record["ok"] = False
            record["detector_validation_ok"] = False
            record["error_kind"] = "candidate_semantic_provenance_validation"
            record["error"] = "; ".join(errors)
            raise VlmCallError(
                "candidate semantic provenance failed strict validation",
                record=record,
            )
        record["detector_validation_ok"] = True
        return record

    def _audit_candidate_semantics(
        self,
        *,
        candidate_pos: int,
        allowed_kinds: set[str],
        prefix: str,
        refs_by_pos: dict[int, FrameRef],
        total_frames: int,
        call_index: int,
        out: Path,
        calls_path: Path,
        deadline: float,
        record_sinks: tuple[list[dict[str, Any]], ...] = (),
    ) -> tuple[dict[str, Any], int]:
        """Run independent single-frame and triplet semantic sentinels."""
        audit_method = getattr(self.locator, "audit_candidate_semantics", None)
        if not callable(audit_method):
            if self.config.model.startswith("unit-test/"):
                return ({
                    "gate_passed": True,
                    "definitive_noncredit": False,
                    "reason": "explicit unit-test locator bypass",
                    "candidate_pos": candidate_pos,
                    "allowed_kinds": sorted(allowed_kinds),
                    "test_double_bypass": True,
                    "views": [],
                }, call_index)
            record = {
                "call_id": f"{prefix}-candidate-semantic-unavailable",
                "stage": f"{prefix}_candidate_semantic",
                "frame_positions": [candidate_pos],
                "candidate_pos": candidate_pos,
                "ok": False,
                "error_kind": "candidate_semantic_method_missing",
                "error": (
                    "real detector locator does not implement the mandatory "
                    "candidate semantic audit"
                ),
            }
            _append_jsonl(calls_path, record)
            raise VlmCallError(
                "mandatory candidate semantic audit is unavailable", record=record
            )
        if not 1 <= candidate_pos < total_frames - 1:
            record = {
                "call_id": f"{prefix}-candidate-semantic-context-missing",
                "stage": f"{prefix}_candidate_semantic",
                "frame_positions": [candidate_pos],
                "candidate_pos": candidate_pos,
                "ok": False,
                "error_kind": "candidate_semantic_context_missing",
                "error": "candidate lacks a consecutive PRE or POST context frame",
            }
            _append_jsonl(calls_path, record)
            raise VlmCallError(
                "candidate semantic audit lacks adjacent context", record=record
            )
        # Candidate audits measure about 1-2 s per call on the target 3090.
        # Keep the full 10 s safe floor for the second call plus a bounded
        # allowance for the first; each loop iteration rechecks the live floor.
        required = self.protocol.min_call_budget_seconds + 4.0
        remaining = deadline - time.perf_counter()
        if remaining < required:
            record = {
                "call_id": f"{prefix}-candidate-semantic-budget-exhausted",
                "stage": f"{prefix}_candidate_semantic",
                "frame_positions": [candidate_pos],
                "candidate_pos": candidate_pos,
                "ok": False,
                "error_kind": "wall_time_budget",
                "error": (
                    f"remaining={remaining:.3f}s below two-call semantic reserve "
                    f"{required:.3f}s"
                ),
            }
            _append_jsonl(calls_path, record)
            raise VlmCallError(
                "insufficient wall budget for candidate semantic audit",
                record=record,
            )

        views: list[dict[str, Any]] = []
        seen_sink_ids: set[int] = set()

        def emit(record: dict[str, Any]) -> None:
            _append_jsonl(calls_path, record)
            for sink in record_sinks:
                if id(sink) in seen_sink_ids:
                    continue
                sink.append(record)
                seen_sink_ids.add(id(sink))
            seen_sink_ids.clear()

        for variant in ("a", "b"):
            call_index += 1
            stage = f"{prefix}_candidate_semantic_{variant}"
            refs = (
                [refs_by_pos[candidate_pos]]
                if variant == "a" else [
                    refs_by_pos[candidate_pos - 1],
                    refs_by_pos[candidate_pos],
                    refs_by_pos[candidate_pos + 1],
                ]
            )
            capture = out / "panels" / f"{call_index:02d}_{stage}.jpg"
            remaining = deadline - time.perf_counter()
            if remaining < self.protocol.min_call_budget_seconds:
                record = {
                    "call_id": f"{stage}-budget-exhausted",
                    "stage": stage,
                    "frame_positions": [ref.pos for ref in refs],
                    "candidate_pos": candidate_pos,
                    "ok": False,
                    "error_kind": "wall_time_budget",
                    "error": "candidate semantic call lacks safe wall budget",
                }
                emit(record)
                raise VlmCallError(
                    "candidate semantic audit exhausted film wall budget",
                    record=record,
                )
            try:
                result: VlmCandidateAuditResult = audit_method(
                    refs,
                    candidate_pos=candidate_pos,
                    variant=variant,
                    stage=stage,
                    time_budget_seconds=remaining,
                    capture_path=capture,
                )
            except VlmCallError as exc:
                emit(exc.record or {
                    "call_id": f"{stage}-failed",
                    "stage": stage,
                    "frame_positions": [ref.pos for ref in refs],
                    "candidate_pos": candidate_pos,
                    "ok": False,
                    "error": str(exc),
                })
                raise
            try:
                record = self._validate_candidate_semantic_provenance(
                    result,
                    stage=stage,
                    variant=variant,
                    candidate_pos=candidate_pos,
                    refs=refs,
                    capture=capture,
                )
            except VlmCallError as exc:
                emit(exc.record or {})
                raise
            if time.perf_counter() >= deadline:
                record.update({
                    "locator_ok": record.get("ok"),
                    "ok": False,
                    "detector_validation_ok": False,
                    "error_kind": "wall_time_budget_after_call",
                    "error": "candidate semantic evidence returned after deadline",
                })
                emit(record)
                raise VlmCallError(
                    "candidate semantic evidence returned after deadline",
                    record=record,
                )
            emit(record)
            result.call_record = record
            views.append(result.to_dict())

        fixed_edge = _persistent_edge_emergence(refs_by_pos, candidate_pos)
        raw_change = _micro_backtrack_has_raw_change(
            refs_by_pos,
            candidate_pos,
        )
        localized_raw_change = bool(
            raw_change.get("gate_passed")
            and float(raw_change.get("changed_density") or 0.0) <= 0.02
            and not fixed_edge.get("photometric_cut_veto")
        )
        faint_edge_proof = {
            "gate_passed": bool(
                fixed_edge.get("gate_passed") or localized_raw_change
            ),
            "reason": (
                "persistent fixed-edge emergence"
                if fixed_edge.get("gate_passed") else (
                    "localized decoded-pixel emergence"
                    if localized_raw_change else
                    "candidate lacks localized/fixed-edge faint-text emergence"
                )
            ),
            "fixed_edge": fixed_edge,
            "raw_change": raw_change,
            "localized_raw_change_max_density": 0.02,
        }
        gate = adjudicate_candidate_semantic_audits(
            views[0],
            views[1],
            allowed_kinds=allowed_kinds,
            allow_faint_primary_no_text=True,
            faint_edge_proof=faint_edge_proof,
        )
        primary_decision = views[0].get("decision")
        context_decision = views[1].get("decision")
        screen_disproof_eligible = bool(
            not gate.get("gate_passed")
            and primary_decision == "DIEGETIC_SCREEN"
            and context_decision in {
                "DIEGETIC_SCREEN",
                "ATTRIBUTION_CREDIT",
            }
            and any(
                kind in {
                    BoundaryKind.CREDIT_SEQUENCE.value,
                    BoundaryKind.END_CARD_THEN_CREDITS.value,
                }
                for kind in allowed_kinds
            )
        )
        if screen_disproof_eligible:
            screen_report: dict[str, Any] = {
                "gate_passed": False,
                "eligible": True,
                "reason": "raw screen-disproof call was not completed",
            }
            remaining = deadline - time.perf_counter()
            if remaining < self.protocol.min_call_budget_seconds:
                screen_report["reason"] = (
                    "insufficient wall budget for optional raw screen disproof"
                )
                gate["screen_disproof"] = screen_report
            else:
                call_index += 1
                variant = "s"
                stage = f"{prefix}_candidate_semantic_s"
                refs = [refs_by_pos[candidate_pos]]
                capture = out / "panels" / f"{call_index:02d}_{stage}.jpg"
                try:
                    screen_result: VlmCandidateAuditResult = audit_method(
                        refs,
                        candidate_pos=candidate_pos,
                        variant=variant,
                        stage=stage,
                        time_budget_seconds=remaining,
                        capture_path=capture,
                    )
                    record = self._validate_candidate_semantic_provenance(
                        screen_result,
                        stage=stage,
                        variant=variant,
                        candidate_pos=candidate_pos,
                        refs=refs,
                        capture=capture,
                    )
                except VlmCallError as exc:
                    emit(exc.record or {
                        "call_id": f"{stage}-failed",
                        "stage": stage,
                        "frame_positions": [candidate_pos],
                        "candidate_pos": candidate_pos,
                        "ok": False,
                        "error": str(exc),
                    })
                    screen_report["reason"] = (
                        "optional raw screen-disproof call failed closed"
                    )
                    screen_report["error"] = str(exc)
                    gate["screen_disproof"] = screen_report
                else:
                    if time.perf_counter() >= deadline:
                        record.update({
                            "locator_ok": record.get("ok"),
                            "ok": False,
                            "detector_validation_ok": False,
                            "error_kind": "wall_time_budget_after_call",
                            "error": (
                                "raw screen-disproof evidence returned after deadline"
                            ),
                        })
                        emit(record)
                        screen_report["reason"] = (
                            "raw screen-disproof evidence missed the deadline"
                        )
                        gate["screen_disproof"] = screen_report
                    else:
                        emit(record)
                        screen_result.call_record = record
                        screen_view = screen_result.to_dict()
                        with Image.open(refs_by_pos[candidate_pos].path) as image:
                            candidate_luma_mean = float(
                                np.asarray(
                                    image.convert("L"),
                                    dtype=np.float32,
                                ).mean()
                            )
                        screen_report = adjudicate_candidate_screen_disproof(
                            views[0],
                            views[1],
                            screen_view,
                            allowed_kinds=allowed_kinds,
                            faint_edge_proof=faint_edge_proof,
                            candidate_luma_mean=candidate_luma_mean,
                        )
                        gate["screen_disproof"] = screen_report
                        if screen_report.get("gate_passed") is True:
                            gate["base_gate_passed"] = gate.get("gate_passed")
                            gate["base_definitive_noncredit"] = gate.get(
                                "definitive_noncredit"
                            )
                            gate.update({
                                "gate_passed": True,
                                "definitive_noncredit": False,
                                "earlier_candidate_invisible": False,
                                "reason": screen_report.get("reason"),
                                "views": screen_report.get("views"),
                                "call_ids": screen_report.get("call_ids"),
                                "input_sha256": screen_report.get(
                                    "input_sha256"
                                ),
                                "prompt_sha256": screen_report.get(
                                    "prompt_sha256"
                                ),
                            })
        gate["test_double_bypass"] = False
        return gate, call_index

    def _locate(
        self,
        positions: list[int],
        *,
        refs_by_pos: dict[int, FrameRef],
        stage: str,
        call_index: int,
        out: Path,
        calls_path: Path,
        deadline: float,
        tile_width: int,
        columns: int,
        at_stream_eof: bool,
        boundary_search_cells: tuple[int, int] | None = None,
    ) -> tuple[WindowEvidence, dict[str, Any]]:
        remaining = deadline - time.perf_counter()
        if remaining < self.protocol.min_call_budget_seconds:
            record = {
                "call_id": f"{stage}-budget-exhausted",
                "stage": stage,
                "frame_positions": positions,
                "ok": False,
                "error_kind": "wall_time_budget",
                "error": (
                    f"remaining={remaining:.3f}s below safe call floor "
                    f"{self.protocol.min_call_budget_seconds:.3f}s"
                ),
            }
            _append_jsonl(calls_path, record)
            raise VlmCallError("film wall-time budget exhausted", record=record)
        refs = [refs_by_pos[position] for position in positions]
        capture = out / "panels" / f"{call_index:02d}_{stage}.jpg"
        try:
            result: VlmWindowResult = self.locator.locate_window(
                refs,
                stage=stage,
                time_budget_seconds=remaining,
                at_stream_eof=at_stream_eof,
                capture_path=capture,
                tile_width=tile_width,
                jpeg_quality=self.protocol.jpeg_quality,
                mosaic_columns=columns,
                boundary_search_cells=boundary_search_cells,
            )
        except VlmCallError as exc:
            _append_jsonl(calls_path, exc.record or {
                "call_id": f"{stage}-failed",
                "stage": stage,
                "frame_positions": positions,
                "ok": False,
                "error": str(exc),
            })
            raise
        try:
            record = self._validate_call_provenance(
                result,
                stage=stage,
                positions=positions,
                refs=refs,
                capture=capture,
                at_stream_eof=at_stream_eof,
                boundary_search_cells=boundary_search_cells,
            )
        except VlmCallError as exc:
            _append_jsonl(calls_path, exc.record or {})
            raise
        if time.perf_counter() >= deadline:
            record.update({
                "locator_ok": record.get("ok"),
                "ok": False,
                "detector_validation_ok": False,
                "error_kind": "wall_time_budget_after_call",
                "error": "VLM evidence returned after the film wall-time deadline",
            })
            _append_jsonl(calls_path, record)
            raise VlmCallError(
                "film wall-time budget exhausted after VLM call", record=record
            )
        _append_jsonl(calls_path, record)
        result.evidence.metadata.update({
            "input_mosaic_path": record.get("input_mosaic_path"),
            "input_sha256": record.get("input_sha256"),
            "prompt_sha256": record.get("prompt_sha256"),
            "prompt_variant": record.get("prompt_variant"),
            "detector_validation_ok": True,
        })
        return result.evidence, record

    def _adjudicate_micro_boundary(
        self,
        *,
        prefix: str,
        source_views: list[WindowEvidence],
        source_records: list[dict[str, Any]],
        support_pos: int,
        allowed_kinds: set[str],
        refs_by_pos: dict[int, FrameRef],
        total_frames: int,
        deadline: float,
        locate_micro: Callable[..., tuple[WindowEvidence, dict[str, Any]]],
        at_stream_eof: bool = False,
        claim_positions: list[int] | None = None,
        force_two_views: bool = False,
        allow_family_match: bool = False,
        enforce_source_disagreement_cap: bool = True,
    ) -> dict[str, Any]:
        """Adjudicate one dense boundary with fresh high-resolution transport views."""
        source_first = [view.first_pos for view in source_views]
        result: dict[str, Any] = {
            "gate_passed": False,
            "chosen_pos": None,
            # Backward-readable key used by existing rescue artifacts.
            "exact_first_positions": source_first,
            "source_first_positions": source_first,
            "claim_positions": claim_positions,
            "views": [],
            "reason": "micro adjudication was not eligible",
        }
        if len(source_views) != 2 or len(source_records) != 2:
            result["reason"] = "micro adjudication requires two source views"
            return result
        if not all(position is not None for position in source_first):
            return result
        source_positions = [
            int(position) for position in source_first if position is not None
        ]
        if (
            enforce_source_disagreement_cap
            and max(source_positions) - min(source_positions)
            > self.protocol.micro_max_disagreement_frames
        ):
            result["reason"] = "exact disagreement exceeds micro hard cap"
            return result
        boundary_positions = (
            [int(position) for position in claim_positions]
            if claim_positions is not None else source_positions
        )
        if len(boundary_positions) != 2:
            result["reason"] = "micro adjudication requires two boundary claims"
            return result
        if (
            max(boundary_positions) - min(boundary_positions)
            > self.protocol.micro_max_disagreement_frames
        ):
            result["reason"] = "boundary claim disagreement exceeds micro hard cap"
            return result

        candidate_low = max(1, min(boundary_positions) - 1)
        candidate_high = max(boundary_positions)
        raw_candidates = list(range(candidate_low, candidate_high + 1))
        blank_like = [
            position for position in raw_candidates
            if _is_visually_blank_frame(refs_by_pos[position].path)
        ]
        backtrack_checks = [
            _micro_backtrack_has_raw_change(refs_by_pos, position)
            for position in raw_candidates
            if position < min(boundary_positions)
            and position not in blank_like
        ]
        unchanged_backtracks = [
            int(check["position"]) for check in backtrack_checks
            if not check["gate_passed"]
        ]
        raw_veto_positions = set(blank_like) | set(unchanged_backtracks)
        visible_candidates = [
            position for position in raw_candidates
            if position not in raw_veto_positions
        ]
        if not visible_candidates:
            result.update({
                "reason": "every micro candidate failed physical visibility gates",
                "raw_blank_veto_positions": blank_like,
                "raw_unchanged_backtrack_veto_positions": unchanged_backtracks,
                "raw_backtrack_checks": backtrack_checks,
            })
            return result
        visible_floor = min(visible_candidates)
        result["raw_blank_veto_positions"] = blank_like
        result["raw_unchanged_backtrack_veto_positions"] = unchanged_backtracks
        result["raw_backtrack_checks"] = backtrack_checks
        result["visible_candidate_floor"] = visible_floor

        # Reserve the possible primary/adversarial micro pair. The dedicated
        # candidate-semantic method performs its own fresh two-call reserve
        # immediately afterwards; requiring both worst-case reserves here made
        # long chronology paths stop while ample measured runtime remained.
        required_budget = 2 * self.protocol.min_call_budget_seconds + 0.5
        if deadline - time.perf_counter() < required_budget:
            result["reason"] = "insufficient wall budget for two-view micro audit"
            return result

        micro_views: list[WindowEvidence] = []
        micro_records: list[dict[str, Any]] = []
        candidate_sets: list[set[int]] = []

        def run_variant(variant: str) -> None:
            positions, search = build_micro_boundary_positions(
                boundary_positions,
                support_pos=support_pos,
                variant=variant,
                total_frames=total_frames,
                fps=self.config.fps,
                at_stream_eof=at_stream_eof,
                config=self.protocol,
            )
            eligible_indexes = [
                index for index in range(search[0], search[1] + 1)
                if positions[index] >= visible_floor
            ]
            if not eligible_indexes:
                raise ValueError("blank veto removed every micro boundary candidate")
            search = (eligible_indexes[0], eligible_indexes[-1])
            view, record = locate_micro(
                positions,
                stage=f"{prefix}_micro_{variant}",
                tile_width=self.protocol.micro_tile_width,
                columns=2 if variant == "b" else 3,
                boundary_search_cells=search,
                at_stream_eof=at_stream_eof,
            )
            micro_views.append(view)
            micro_records.append(record)
            candidate_sets.append(set(positions[search[0]:search[1] + 1]))

        def valid_view(index: int) -> bool:
            view = micro_views[index]
            return (
                view.verdict == WindowVerdict.TRANSITION.value
                and view.continuity == Continuity.CONFIRMED.value
                and view.reject == "NONE"
                and view.kind in allowed_kinds
                and view.first_cell >= 1
                and view.first_pos is not None
                and int(view.first_pos) in candidate_sets[index]
                and view.positions[view.first_cell]
                - view.positions[view.first_cell - 1] == 1
            )

        run_variant("a")
        source_hashes = {row.get("input_sha256") for row in source_records}
        source_prompts = {row.get("prompt_sha256") for row in source_records}
        source_call_ids = {view.call_id for view in source_views}
        primary_fresh = (
            micro_records[0].get("input_sha256")
            and micro_records[0].get("input_sha256") not in source_hashes
            and micro_records[0].get("prompt_sha256")
            and micro_records[0].get("prompt_sha256") not in source_prompts
            and micro_views[0].call_id not in source_call_ids
        )
        result["views"] = [micro_views[0].to_dict()]
        result["primary_fresh"] = bool(primary_fresh)
        if not primary_fresh or not valid_view(0):
            result["reason"] = "primary micro view did not prove a valid boundary"
            return result
        unanimous_claim = boundary_positions[0] == boundary_positions[1]
        primary_pos = int(micro_views[0].first_pos)
        if (
            not force_two_views
            and unanimous_claim
            and primary_pos == boundary_positions[0]
        ):
            result.update({
                "gate_passed": True,
                "chosen_pos": primary_pos,
                "reason": "unanimous exact boundary survived predecessor micro audit",
                "independent_transport_views": True,
            })
            return result

        run_variant("b")
        result["views"] = [view.to_dict() for view in micro_views]
        hashes = [row.get("input_sha256") for row in micro_records]
        prompts = [row.get("prompt_sha256") for row in micro_records]
        independent = (
            micro_views[0].positions != micro_views[1].positions
            and micro_views[0].call_id != micro_views[1].call_id
            and all(hashes)
            and hashes[0] != hashes[1]
            and not any(value in source_hashes for value in hashes)
            and all(prompts)
            and prompts[0] != prompts[1]
            and not any(value in source_prompts for value in prompts)
            and not any(view.call_id in source_call_ids for view in micro_views)
            and micro_records[0].get("prompt_variant") == "primary_boundary"
            and micro_records[1].get("prompt_variant") == "adversarial_reject"
        )
        chosen = [view.first_pos for view in micro_views]
        kind_compatible = (
            _boundary_family(micro_views[0].kind)
            == _boundary_family(micro_views[1].kind)
            if allow_family_match
            else micro_views[0].kind == micro_views[1].kind
        )
        gate = (
            independent
            and valid_view(0)
            and valid_view(1)
            and chosen[0] is not None
            and chosen[0] == chosen[1]
            and kind_compatible
        )
        result.update({
            "gate_passed": bool(gate),
            "chosen_pos": int(chosen[0]) if gate else None,
            "reason": (
                "primary/adversarial micro views agree at tolerance zero"
                if gate else "micro views did not agree safely"
            ),
            "independent_transport_views": bool(independent),
            "kind_compatible": bool(kind_compatible),
            "first_positions": chosen,
            "input_sha256": hashes,
            "prompt_sha256": prompts,
        })
        if (
            gate
            and claim_positions is None
            and len(set(source_positions)) == 2
            and int(chosen[0]) == min(source_positions)
            and min(source_positions) > 1
        ):
            predecessor = min(source_positions) - 1
            emergence = _persistent_edge_emergence(refs_by_pos, predecessor)
            result["predecessor_emergence"] = emergence
            if emergence["gate_passed"]:
                audit = self._adjudicate_micro_boundary(
                    prefix=f"{prefix}_predecessor",
                    source_views=source_views,
                    source_records=source_records,
                    support_pos=support_pos,
                    allowed_kinds=allowed_kinds,
                    refs_by_pos=refs_by_pos,
                    total_frames=total_frames,
                    deadline=deadline,
                    locate_micro=locate_micro,
                    at_stream_eof=at_stream_eof,
                    claim_positions=[min(source_positions), min(source_positions)],
                    force_two_views=True,
                    allow_family_match=allow_family_match,
                    enforce_source_disagreement_cap=False,
                )
                audit_hashes = set(audit.get("input_sha256") or [])
                audit_prompts = set(audit.get("prompt_sha256") or [])
                audit_fresh = bool(
                    audit_hashes
                    and audit_prompts
                    and audit_hashes.isdisjoint(set(hashes))
                    and audit_prompts.isdisjoint(set(prompts))
                )
                audit["fresh_from_initial_micro"] = audit_fresh
                result["predecessor_audit"] = audit
                audit_chosen = audit.get("chosen_pos")
                if not audit.get("gate_passed") or not audit_fresh:
                    result.update({
                        "gate_passed": False,
                        "chosen_pos": None,
                        "reason": (
                            "fixed-edge predecessor audit did not reach fresh "
                            "two-view consensus"
                        ),
                    })
                elif int(audit_chosen) == predecessor:
                    result.update({
                        "chosen_pos": predecessor,
                        "reason": (
                            "fresh two-view predecessor audit confirmed the "
                            "raw fixed-edge emergence frame"
                        ),
                    })
                elif int(audit_chosen) != min(source_positions):
                    result.update({
                        "gate_passed": False,
                        "chosen_pos": None,
                        "reason": "predecessor audit returned an out-of-scope frame",
                    })
        return result

    def _review_rescue_candidates(
        self,
        candidates: list[ReviewRescueCandidate],
        *,
        refs_by_pos: dict[int, FrameRef],
        total_frames: int,
        call_index: int,
        out: Path,
        calls_path: Path,
        deadline: float,
        evidence_sink: list[WindowEvidence] | None = None,
        record_sink: list[dict[str, Any]] | None = None,
    ) -> ReviewRescueOutcome:
        """Re-check coarse REVIEW proposals from earliest to latest.

        Coarse contact sheets are deliberately cheap and may misread a tiny
        first credit, a subtitle, or a post-credit scene.  This path never
        converts coarse evidence directly into FOUND.  An early proposal must
        first survive a focused fine view, two sparse localization views, and
        two compact frame-level primary/adversarial views.  A clean PRE_ONLY
        fine view safely rejects a false early proposal; any unresolved early
        semantic evidence remains REVIEW and blocks accepting a later onset.
        """
        candidates = sorted(
            candidates,
            key=lambda candidate: (
                candidate.bracket[0],
                candidate.provisional_start,
                candidate.source_call_id,
            ),
        )[:MAX_REVIEW_RESCUE_CANDIDATES]
        emitted: list[WindowEvidence] = []
        records: list[dict[str, Any]] = []
        reports: list[dict[str, Any]] = []
        later_positive_semantic_supports: list[dict[str, Any]] = []
        semantic_rejection_floor: int | None = None

        def remember_semantic_rejection(position: Any) -> int | None:
            """Prevent later rescue candidates from re-opening a proven false edge."""
            nonlocal semantic_rejection_floor
            try:
                rejected = int(position)
            except (TypeError, ValueError):
                return semantic_rejection_floor
            if 1 <= rejected < total_frames - 1:
                semantic_rejection_floor = max(
                    rejected,
                    semantic_rejection_floor or rejected,
                )
            return semantic_rejection_floor

        def locate(
            positions: list[int],
            *,
            stage: str,
            tile_width: int,
            columns: int,
            boundary_search_cells: tuple[int, int] | None = None,
        ) -> WindowEvidence:
            nonlocal call_index
            call_index += 1
            evidence, record = self._locate(
                positions,
                refs_by_pos=refs_by_pos,
                stage=stage,
                call_index=call_index,
                out=out,
                calls_path=calls_path,
                deadline=deadline,
                tile_width=tile_width,
                columns=columns,
                at_stream_eof=positions[-1] == total_frames - 1,
                boundary_search_cells=boundary_search_cells,
            )
            emitted.append(evidence)
            records.append(record)
            if evidence_sink is not None:
                evidence_sink.append(evidence)
            if record_sink is not None:
                record_sink.append(record)
            return evidence

        def micro_adjudicate(
            *,
            prefix: str,
            exact_views: list[WindowEvidence],
            exact_records: list[dict[str, Any]],
            support_pos: int,
            allowed_kinds: set[str],
            at_stream_eof: bool = False,
            claim_positions: list[int] | None = None,
            force_two_views: bool = False,
            allow_family_match: bool = False,
            enforce_source_disagreement_cap: bool = True,
        ) -> dict[str, Any]:
            exact_first = [view.first_pos for view in exact_views]
            result: dict[str, Any] = {
                "gate_passed": False,
                "chosen_pos": None,
                "exact_first_positions": exact_first,
                "claim_positions": claim_positions,
                "views": [],
                "reason": "micro adjudication was not eligible",
            }
            if not all(position is not None for position in exact_first):
                return result
            exact_positions = [int(position) for position in exact_first if position is not None]
            if (
                enforce_source_disagreement_cap
                and (
                    max(exact_positions) - min(exact_positions)
                    > self.protocol.micro_max_disagreement_frames
                )
            ):
                result["reason"] = "exact disagreement exceeds micro hard cap"
                return result
            boundary_positions = (
                [int(position) for position in claim_positions]
                if claim_positions is not None else exact_positions
            )
            if len(boundary_positions) != 2:
                result["reason"] = "micro adjudication requires two boundary claims"
                return result
            if (
                max(boundary_positions) - min(boundary_positions)
                > self.protocol.micro_max_disagreement_frames
            ):
                result["reason"] = "boundary claim disagreement exceeds micro hard cap"
                return result
            # Even an apparently unanimous exact pair may have missed a faint
            # predecessor, so reserve enough budget for a possible adversarial
            # second micro view before starting the primary view. Candidate
            # semantics has its own two-call reserve after micro consensus.
            required_budget = 2 * self.protocol.min_call_budget_seconds + 0.5
            if deadline - time.perf_counter() < required_budget:
                result["reason"] = "insufficient wall budget for two-view micro audit"
                return result

            candidate_low = max(1, min(boundary_positions) - 1)
            candidate_high = max(boundary_positions)
            raw_candidates = list(range(candidate_low, candidate_high + 1))
            blank_like = [
                position for position in raw_candidates
                if _is_visually_blank_frame(refs_by_pos[position].path)
            ]
            backtrack_checks = [
                _micro_backtrack_has_raw_change(refs_by_pos, position)
                for position in raw_candidates
                if position < min(boundary_positions)
                and position not in blank_like
            ]
            unchanged_backtracks = [
                int(check["position"]) for check in backtrack_checks
                if not check["gate_passed"]
            ]
            semantic_floor_veto = [
                position for position in raw_candidates
                if semantic_rejection_floor is not None
                and position <= semantic_rejection_floor
            ]
            raw_veto_positions = (
                set(blank_like)
                | set(unchanged_backtracks)
                | set(semantic_floor_veto)
            )
            visible_candidates = [
                position for position in raw_candidates
                if position not in raw_veto_positions
            ]
            if not visible_candidates:
                result.update({
                    "reason": "every micro candidate failed physical visibility gates",
                    "raw_blank_veto_positions": blank_like,
                    "raw_unchanged_backtrack_veto_positions": unchanged_backtracks,
                    "semantic_rejection_floor_veto_positions": semantic_floor_veto,
                    "raw_backtrack_checks": backtrack_checks,
                })
                return result
            visible_floor = min(visible_candidates)
            result["raw_blank_veto_positions"] = blank_like
            result["raw_unchanged_backtrack_veto_positions"] = unchanged_backtracks
            result["semantic_rejection_floor_veto_positions"] = semantic_floor_veto
            result["raw_backtrack_checks"] = backtrack_checks
            result["visible_candidate_floor"] = visible_floor

            micro_views: list[WindowEvidence] = []
            micro_records: list[dict[str, Any]] = []
            candidate_sets: list[set[int]] = []

            def run_variant(variant: str) -> None:
                positions, search = build_micro_boundary_positions(
                    boundary_positions,
                    support_pos=support_pos,
                    variant=variant,
                    total_frames=total_frames,
                    fps=self.config.fps,
                    at_stream_eof=at_stream_eof,
                    config=self.protocol,
                )
                eligible_indexes = [
                    index for index in range(search[0], search[1] + 1)
                    if positions[index] >= visible_floor
                ]
                if not eligible_indexes:
                    raise ValueError("blank veto removed every micro boundary candidate")
                search = (eligible_indexes[0], eligible_indexes[-1])
                before = len(records)
                view = locate(
                    positions,
                    stage=f"{prefix}_micro_{variant}",
                    tile_width=self.protocol.micro_tile_width,
                    columns=2 if variant == "b" else 3,
                    boundary_search_cells=search,
                )
                micro_views.append(view)
                micro_records.append(records[before])
                candidate_sets.append(set(positions[search[0]:search[1] + 1]))

            def valid_view(index: int) -> bool:
                view = micro_views[index]
                return (
                    view.verdict == WindowVerdict.TRANSITION.value
                    and view.continuity == Continuity.CONFIRMED.value
                    and view.reject == "NONE"
                    and view.kind in allowed_kinds
                    and view.first_cell >= 1
                    and view.first_pos is not None
                    and int(view.first_pos) in candidate_sets[index]
                    and view.positions[view.first_cell]
                    - view.positions[view.first_cell - 1] == 1
                )

            run_variant("a")
            exact_hashes = {row.get("input_sha256") for row in exact_records}
            exact_prompts = {row.get("prompt_sha256") for row in exact_records}
            exact_call_ids = {view.call_id for view in exact_views}
            primary_fresh = (
                micro_records[0].get("input_sha256")
                and micro_records[0].get("input_sha256") not in exact_hashes
                and micro_records[0].get("prompt_sha256")
                and micro_records[0].get("prompt_sha256") not in exact_prompts
                and micro_views[0].call_id not in exact_call_ids
            )
            result["views"] = [micro_views[0].to_dict()]
            result["primary_fresh"] = bool(primary_fresh)
            if not primary_fresh or not valid_view(0):
                result["reason"] = "primary micro view did not prove a valid boundary"
                return result
            unanimous_claim = boundary_positions[0] == boundary_positions[1]
            primary_pos = int(micro_views[0].first_pos)
            if (
                not force_two_views
                and unanimous_claim
                and primary_pos == boundary_positions[0]
            ):
                result.update({
                    "gate_passed": True,
                    "chosen_pos": primary_pos,
                    "reason": "unanimous exact boundary survived predecessor micro audit",
                    "independent_transport_views": True,
                })
                return result

            run_variant("b")
            result["views"] = [view.to_dict() for view in micro_views]
            hashes = [row.get("input_sha256") for row in micro_records]
            prompts = [row.get("prompt_sha256") for row in micro_records]
            independent = (
                micro_views[0].positions != micro_views[1].positions
                and micro_views[0].call_id != micro_views[1].call_id
                and all(hashes)
                and hashes[0] != hashes[1]
                and not any(value in exact_hashes for value in hashes)
                and all(prompts)
                and prompts[0] != prompts[1]
                and not any(value in exact_prompts for value in prompts)
                and not any(view.call_id in exact_call_ids for view in micro_views)
                and micro_records[0].get("prompt_variant") == "primary_boundary"
                and micro_records[1].get("prompt_variant") == "adversarial_reject"
            )
            chosen = [view.first_pos for view in micro_views]
            kind_compatible = (
                _boundary_family(micro_views[0].kind)
                == _boundary_family(micro_views[1].kind)
                if allow_family_match
                else micro_views[0].kind == micro_views[1].kind
            )
            gate = (
                independent
                and valid_view(0)
                and valid_view(1)
                and chosen[0] is not None
                and chosen[0] == chosen[1]
                and kind_compatible
            )
            result.update({
                "gate_passed": bool(gate),
                "chosen_pos": int(chosen[0]) if gate else None,
                "reason": (
                    "primary/adversarial micro views agree at tolerance zero"
                    if gate else "micro views did not agree safely"
                ),
                "independent_transport_views": bool(independent),
                "kind_compatible": bool(kind_compatible),
                "first_positions": chosen,
                "input_sha256": hashes,
                "prompt_sha256": prompts,
            })
            if (
                gate
                and claim_positions is None
                and len(set(exact_positions)) == 2
                and int(chosen[0]) == min(exact_positions)
                and min(exact_positions) > 1
            ):
                predecessor = min(exact_positions) - 1
                emergence = _persistent_edge_emergence(refs_by_pos, predecessor)
                result["predecessor_emergence"] = emergence
                if emergence["gate_passed"]:
                    audit = micro_adjudicate(
                        prefix=f"{prefix}_predecessor",
                        exact_views=exact_views,
                        exact_records=exact_records,
                        support_pos=support_pos,
                        allowed_kinds=allowed_kinds,
                        at_stream_eof=at_stream_eof,
                        claim_positions=[min(exact_positions), min(exact_positions)],
                        force_two_views=True,
                        allow_family_match=allow_family_match,
                        enforce_source_disagreement_cap=False,
                    )
                    audit_hashes = set(audit.get("input_sha256") or [])
                    audit_prompts = set(audit.get("prompt_sha256") or [])
                    audit_fresh = bool(
                        audit_hashes
                        and audit_prompts
                        and audit_hashes.isdisjoint(set(hashes))
                        and audit_prompts.isdisjoint(set(prompts))
                    )
                    audit["fresh_from_initial_micro"] = audit_fresh
                    result["predecessor_audit"] = audit
                    audit_chosen = audit.get("chosen_pos")
                    if not audit.get("gate_passed") or not audit_fresh:
                        result.update({
                            "gate_passed": False,
                            "chosen_pos": None,
                            "reason": (
                                "fixed-edge predecessor audit did not reach "
                                "fresh two-view consensus"
                            ),
                        })
                    elif int(audit_chosen) == predecessor:
                        result.update({
                            "chosen_pos": predecessor,
                            "reason": (
                                "fresh two-view predecessor audit confirmed "
                                "the raw fixed-edge emergence frame"
                            ),
                        })
                    elif int(audit_chosen) != min(exact_positions):
                        result.update({
                            "gate_passed": False,
                            "chosen_pos": None,
                            "reason": (
                                "predecessor audit returned an out-of-scope frame"
                            ),
                        })
            return result

        def apply_candidate_semantic_gate(
            micro: dict[str, Any],
            *,
            prefix: str,
            allowed_kinds: set[str],
        ) -> None:
            nonlocal call_index
            if not micro.get("gate_passed") or micro.get("chosen_pos") is None:
                return
            chosen = int(micro["chosen_pos"])
            existing_audit = micro.get("candidate_semantic_audit") or {}
            if (
                existing_audit.get("gate_passed") is True
                and existing_audit.get("candidate_pos") == chosen
            ):
                return
            sinks: tuple[list[dict[str, Any]], ...] = (
                (records, record_sink)
                if record_sink is not None else (records,)
            )
            audit, call_index = self._audit_candidate_semantics(
                candidate_pos=chosen,
                allowed_kinds=allowed_kinds,
                prefix=prefix,
                refs_by_pos=refs_by_pos,
                total_frames=total_frames,
                call_index=call_index,
                out=out,
                calls_path=calls_path,
                deadline=deadline,
                record_sinks=sinks,
            )
            micro["candidate_semantic_audit"] = audit
            micro["pre_semantic_chosen_pos"] = chosen
            current_scope = "_".join(prefix.split("_")[:2])
            later_support_recovery = (
                adjudicate_later_supported_partial_candidate(
                    micro,
                    audit,
                    later_supports=later_positive_semantic_supports,
                    allowed_kinds=allowed_kinds,
                    current_scope=current_scope,
                    max_distance_frames=max(
                        1,
                        int(math.ceil(
                            self.config.fps
                            * self.protocol.min_support_seconds
                        )),
                    ),
                    raw_change=_micro_backtrack_has_raw_change(
                        refs_by_pos,
                        chosen,
                    ),
                )
            )
            micro["later_support_partial_recovery"] = later_support_recovery
            if later_support_recovery.get("gate_passed") is True:
                audit["base_gate_passed"] = audit.get("gate_passed")
                audit["base_definitive_noncredit"] = audit.get(
                    "definitive_noncredit"
                )
                audit.update({
                    "gate_passed": True,
                    "definitive_noncredit": False,
                    "later_support_recovery": later_support_recovery,
                    "reason": later_support_recovery.get("reason"),
                })
                micro.update({
                    "gate_passed": True,
                    "chosen_pos": chosen,
                    "reason": later_support_recovery.get("reason"),
                })
                return
            if audit.get("earlier_candidate_invisible") is True:
                exact_positions = [
                    int(position) for position in (
                        micro.get("exact_first_positions") or []
                    )
                    if position is not None
                ]
                later = max(exact_positions) if exact_positions else None
                later_edge = (
                    _persistent_edge_emergence(refs_by_pos, later)
                    if later is not None
                    and 1 <= later < total_frames - 1 else None
                )
                can_shift = bool(
                    len(exact_positions) == 2
                    and later == chosen + 1
                    and max(exact_positions) - min(exact_positions) == 1
                    and later_edge is not None
                    and later_edge.get("gate_passed") is True
                    and deadline - time.perf_counter()
                    >= 2 * self.protocol.min_call_budget_seconds + 0.5
                )
                micro["candidate_semantic_shift_check"] = {
                    "eligible": can_shift,
                    "from_pos": chosen,
                    "later_exact_pos": later,
                    "later_edge": later_edge,
                }
                if can_shift:
                    assert later is not None
                    later_audit, call_index = self._audit_candidate_semantics(
                        candidate_pos=later,
                        allowed_kinds=allowed_kinds,
                        prefix=f"{prefix}_later_exact",
                        refs_by_pos=refs_by_pos,
                        total_frames=total_frames,
                        call_index=call_index,
                        out=out,
                        calls_path=calls_path,
                        deadline=deadline,
                        record_sinks=sinks,
                    )
                    micro["candidate_semantic_shift_audit"] = later_audit
                    if later_audit.get("gate_passed"):
                        micro.update({
                            "gate_passed": True,
                            "chosen_pos": later,
                            "reason": (
                                "single-frame and physical evidence rejected the "
                                "earlier adjacent claim; two fresh semantic views "
                                "confirmed the later exact frame"
                            ),
                        })
                        return
            if not audit.get("gate_passed"):
                micro.update({
                    "gate_passed": False,
                    "chosen_pos": None,
                    "reason": (
                        "micro boundary was rejected by the dedicated candidate "
                        f"semantic audit: {audit.get('reason')}"
                    ),
                })

        def resolve_adjacent_micro_disagreement(
            micro: dict[str, Any],
            *,
            prefix: str,
            allowed_kinds: set[str],
        ) -> None:
            """Resolve a one-frame micro split with fresh candidate semantics."""
            nonlocal call_index
            if micro.get("gate_passed"):
                return
            first_positions = [
                int(position) for position in (
                    micro.get("first_positions") or []
                )
                if position is not None
            ]
            exact_positions = [
                int(position) for position in (
                    micro.get("exact_first_positions") or []
                )
                if position is not None
            ]
            eligible = bool(
                len(first_positions) == 2
                and max(first_positions) - min(first_positions) == 1
                and micro.get("independent_transport_views") is True
                and micro.get("kind_compatible") is True
                and len(exact_positions) == 2
                and max(exact_positions) - min(exact_positions) <= 1
            )
            if not eligible:
                return
            sinks: tuple[list[dict[str, Any]], ...] = (
                (records, record_sink)
                if record_sink is not None else (records,)
            )
            earliest = min(first_positions)
            audit, call_index = self._audit_candidate_semantics(
                candidate_pos=earliest,
                allowed_kinds=allowed_kinds,
                prefix=f"{prefix}_adjacent_earliest",
                refs_by_pos=refs_by_pos,
                total_frames=total_frames,
                call_index=call_index,
                out=out,
                calls_path=calls_path,
                deadline=deadline,
                record_sinks=sinks,
            )
            micro["candidate_semantic_audit"] = audit
            micro["pre_semantic_chosen_pos"] = earliest
            micro["adjacent_semantic_resolution"] = {
                "first_positions": first_positions,
                "exact_first_positions": exact_positions,
                "earliest_audit": audit,
            }
            if (
                audit.get("gate_passed")
                and audit.get("test_double_bypass") is not True
            ):
                micro.update({
                    "gate_passed": True,
                    "chosen_pos": earliest,
                    "reason": (
                        "adjacent micro views were resolved to the earliest "
                        "frame by two fresh candidate-semantic views"
                    ),
                })
                return
            later = max(first_positions)
            partial_proof = adjudicate_adjacent_partial_candidate(
                micro,
                audit,
                raw_change=_micro_backtrack_has_raw_change(
                    refs_by_pos,
                    earliest,
                ),
            )
            micro["adjacent_semantic_resolution"][
                "earliest_partial_proof"
            ] = partial_proof
            if partial_proof.get("gate_passed") is True:
                audit["base_gate_passed"] = audit.get("gate_passed")
                audit.update({
                    "gate_passed": True,
                    "earlier_candidate_invisible": False,
                    "adjacent_partial_recovery": partial_proof,
                    "reason": partial_proof.get("reason"),
                })
                micro.update({
                    "gate_passed": True,
                    "chosen_pos": earliest,
                    "reason": partial_proof.get("reason"),
                })
                return
            if (
                audit.get("earlier_candidate_invisible") is True
                and later in exact_positions
                and deadline - time.perf_counter()
                >= self.protocol.min_call_budget_seconds + 4.0
            ):
                later_audit, call_index = self._audit_candidate_semantics(
                    candidate_pos=later,
                    allowed_kinds=allowed_kinds,
                    prefix=f"{prefix}_adjacent_later",
                    refs_by_pos=refs_by_pos,
                    total_frames=total_frames,
                    call_index=call_index,
                    out=out,
                    calls_path=calls_path,
                    deadline=deadline,
                    record_sinks=sinks,
                )
                micro["adjacent_semantic_resolution"][
                    "later_audit"
                ] = later_audit
                if (
                    later_audit.get("gate_passed")
                    and later_audit.get("test_double_bypass") is not True
                ):
                    micro["candidate_semantic_audit"] = later_audit
                    micro.update({
                        "gate_passed": True,
                        "chosen_pos": later,
                        "reason": (
                            "earliest adjacent frame was semantically invisible; "
                            "two fresh views confirmed the later exact frame"
                        ),
                    })

        def refine_semantic_successor(
            *,
            rejected_pos: int,
            later_semantic_pos: int,
            search_right: int,
            prefix: str,
            exact_views: list[WindowEvidence],
            exact_records: list[dict[str, Any]],
            support_pos: int,
            allowed_kinds: set[str],
        ) -> dict[str, Any]:
            """Search a short title-to-credit handoff after a proven false edge."""
            nonlocal call_index
            max_scan_frames = max(2, int(math.ceil(4.0 * self.config.fps)))
            horizon = min(
                total_frames - 2,
                int(search_right),
                int(later_semantic_pos),
                int(rejected_pos) + max_scan_frames,
            )
            report: dict[str, Any] = {
                "gate_passed": False,
                "blocked": False,
                "rejected_pos": int(rejected_pos),
                "later_semantic_pos": int(later_semantic_pos),
                "search_right_pos": int(search_right),
                "scan_horizon_pos": int(horizon),
                "max_scan_frames": max_scan_frames,
                "audits": [],
                "reason": "no bounded semantic successor was eligible",
            }
            allowed_families = {
                _boundary_family(kind) for kind in allowed_kinds
                if _boundary_family(kind) != "NONE"
            }
            if (
                allowed_families != {"SUSTAINED_CREDITS"}
                or horizon <= rejected_pos
            ):
                return report
            sinks: tuple[list[dict[str, Any]], ...] = (
                (records, record_sink)
                if record_sink is not None else (records,)
            )
            for position in range(int(rejected_pos) + 1, int(horizon) + 1):
                # Preserve a full two-view micro reserve after the semantic
                # probe. If it is unavailable, remain REVIEW-capable rather
                # than spending the last seconds on evidence that cannot close.
                required = 2 * self.protocol.min_call_budget_seconds + 4.5
                if deadline - time.perf_counter() < required:
                    report.update({
                        "blocked": True,
                        "reason": (
                            "insufficient wall budget for semantic successor "
                            "plus two-view micro proof"
                        ),
                    })
                    return report
                audit, call_index = self._audit_candidate_semantics(
                    candidate_pos=position,
                    allowed_kinds=allowed_kinds,
                    prefix=f"{prefix}_successor_{position:04d}",
                    refs_by_pos=refs_by_pos,
                    total_frames=total_frames,
                    call_index=call_index,
                    out=out,
                    calls_path=calls_path,
                    deadline=deadline,
                    record_sinks=sinks,
                )
                report["audits"].append(audit)
                if (
                    audit.get("gate_passed") is True
                    and audit.get("test_double_bypass") is not True
                ):
                    successor_micro = micro_adjudicate(
                        prefix=f"{prefix}_successor_{position:04d}",
                        exact_views=exact_views,
                        exact_records=exact_records,
                        support_pos=support_pos,
                        allowed_kinds=allowed_kinds,
                        claim_positions=[position, position],
                        force_two_views=True,
                        allow_family_match=True,
                        enforce_source_disagreement_cap=False,
                    )
                    successor_micro["candidate_semantic_audit"] = audit
                    successor_micro["pre_semantic_chosen_pos"] = position
                    report["successor_pos"] = position
                    report["micro"] = successor_micro
                    if (
                        successor_micro.get("gate_passed") is True
                        and successor_micro.get("chosen_pos") == position
                    ):
                        report.update({
                            "gate_passed": True,
                            "reason": (
                                "sequential candidate audits cleared the title "
                                "frames and fresh micro views proved the first "
                                "later attribution frame"
                            ),
                        })
                    else:
                        report.update({
                            "blocked": True,
                            "reason": (
                                "a later semantic credit was found but fresh "
                                "micro views did not close its exact boundary"
                            ),
                        })
                    return report
                if audit.get("definitive_noncredit") is True:
                    remember_semantic_rejection(position)
                    continue
                report.update({
                    "blocked": True,
                    "reason": (
                        "a successor frame was neither independently positive "
                        "nor definitively non-credit"
                    ),
                })
                return report
            report["reason"] = (
                "every bounded successor frame remained independently non-credit"
            )
            return report

        for ordinal, candidate in enumerate(candidates, start=1):
            prefix = f"rescue_{ordinal:02d}"
            report: dict[str, Any] = {
                **candidate.to_dict(),
                "ordinal": ordinal,
                "status": "STARTED",
            }
            reports.append(report)
            bracket = list(candidate.bracket)
            terminal_candidate = (
                _boundary_family(candidate.boundary_kind) == "TERMINAL_END_CARD"
                and (
                    candidate.source_at_stream_eof
                    or (
                        candidate.source_reject == "NONE"
                        and (total_frames - 1 - candidate.provisional_start)
                        <= int(math.ceil(
                            (
                                self.protocol.terminal_dense_horizon_seconds
                                + self.protocol.terminal_blank_tail_seconds
                            ) * self.config.fps
                        ))
                    )
                )
            )
            if terminal_candidate:
                fine_positions = build_terminal_fine_positions(
                    bracket,
                    total_frames=total_frames,
                    fps=self.config.fps,
                    config=self.protocol,
                )
            elif candidate.source_reject != "NONE":
                # A rejected coarse transition is only an untrusted location
                # hint.  Recheck it at higher resolution with enough forward
                # horizon to prove an 8 s regime if the coarse reject was
                # wrong; this recovers faint/foreign credits without allowing
                # the rejected coarse semantics to authorize FOUND.
                pre = int(math.ceil(self.protocol.fine_pre_seconds * self.config.fps))
                post = int(math.ceil(
                    (
                        self.protocol.fine_post_seconds
                        + self.protocol.min_support_seconds
                        + max(self.protocol.verify_support_seconds)
                    ) * self.config.fps
                ))
                fine_positions = _linspace_positions(
                    max(0, int(bracket[0]) - pre),
                    min(total_frames - 1, int(bracket[1]) + post),
                    max(12, self.protocol.fine_anchor_count),
                )
            else:
                fine_positions = build_fine_gap_positions(
                    bracket,
                    total_frames=total_frames,
                    fps=self.config.fps,
                    config=self.protocol,
                )
            fine_record_index = len(records)
            fine = locate(
                fine_positions,
                stage=f"{prefix}_fine",
                tile_width=self.protocol.fine_tile_width,
                columns=3,
            )
            fine_record = records[fine_record_index]
            report["fine"] = fine.to_dict()
            if _is_semantic_noncredit(fine):
                negative_positions = build_shifted_negative_positions(
                    fine_positions,
                    total_frames=total_frames,
                )
                negative_record_index = len(records)
                negative = locate(
                    negative_positions,
                    stage=f"{prefix}_fine_b",
                    tile_width=self.protocol.fine_tile_width,
                    columns=2,
                )
                negative_record = records[negative_record_index]
                negative_independent = (
                    fine.positions != negative.positions
                    and fine.call_id != negative.call_id
                    and fine_record.get("input_sha256")
                    and negative_record.get("input_sha256")
                    and fine_record.get("input_sha256")
                    != negative_record.get("input_sha256")
                    and fine_record.get("prompt_sha256")
                    and negative_record.get("prompt_sha256")
                    and fine_record.get("prompt_sha256")
                    != negative_record.get("prompt_sha256")
                    and fine_record.get("prompt_variant") == "primary_boundary"
                    and negative_record.get("prompt_variant") == "adversarial_reject"
                )
                report["negative_confirmation"] = {
                    "view": negative.to_dict(),
                    "independent_transport_views": bool(negative_independent),
                    "both_clean_pre_only": bool(
                        _is_clean_pre_only(fine) and _is_clean_pre_only(negative)
                    ),
                    "both_semantic_noncredit": bool(
                        _is_semantic_noncredit(fine)
                        and _is_semantic_noncredit(negative)
                    ),
                }
                if negative_independent and _is_semantic_noncredit(negative):
                    both_clean = (
                        _is_clean_pre_only(fine) and _is_clean_pre_only(negative)
                    )
                    report.update({
                        "status": (
                            "REJECTED_PRE_ONLY_CONFIRMED"
                            if both_clean else "REJECTED_NONCREDIT_CONFIRMED"
                        ),
                        "reason": (
                            "primary and shifted adversarial fine views independently "
                            "contain no credit attribution or credit regime"
                        ),
                    })
                    continue
                report.update({
                    "status": "UNRESOLVED_NEGATIVE_DISAGREEMENT",
                    "reason": "a single negative fine view cannot discard chronology",
                })
                return ReviewRescueOutcome(
                    DetectionStatus.REVIEW.value,
                    "earliest candidate was not independently disproved",
                    call_index,
                    emitted,
                    records,
                    reports,
                    provisional_start=candidate.provisional_start,
                    review_bracket=[negative.positions[0], negative.positions[-1]],
                    verification={"mode": "chronological_review_rescue", "candidates": reports},
                )

            rejected_hint_support = False
            if candidate.source_reject != "NONE":
                recheck_positions = build_shifted_negative_positions(
                    fine_positions,
                    total_frames=total_frames,
                )
                recheck_record_index = len(records)
                recheck = locate(
                    recheck_positions,
                    stage=f"{prefix}_fine_b",
                    tile_width=self.protocol.fine_tile_width,
                    columns=2,
                )
                recheck_record = records[recheck_record_index]
                recheck_independent = (
                    fine.positions != recheck.positions
                    and fine.call_id != recheck.call_id
                    and fine_record.get("input_sha256")
                    and recheck_record.get("input_sha256")
                    and fine_record.get("input_sha256")
                    != recheck_record.get("input_sha256")
                    and fine_record.get("prompt_sha256")
                    and recheck_record.get("prompt_sha256")
                    and fine_record.get("prompt_sha256")
                    != recheck_record.get("prompt_sha256")
                    and fine_record.get("prompt_variant") == "primary_boundary"
                    and recheck_record.get("prompt_variant") == "adversarial_reject"
                )
                positive_states = {
                    WindowVerdict.TRANSITION.value,
                    WindowVerdict.ACTIVE_FROM_LEFT.value,
                }
                recheck_semantic = all(
                    view.verdict in positive_states
                    and view.continuity == Continuity.CONFIRMED.value
                    and view.reject == "NONE"
                    and view.kind != BoundaryKind.NONE.value
                    for view in (fine, recheck)
                )
                recheck_family = _boundary_family(fine.kind)
                recheck_same_family = (
                    recheck_family == _boundary_family(recheck.kind)
                    and recheck_family != "NONE"
                )
                recheck_support_flags = [
                    _is_supported(
                        view,
                        fps=self.config.fps,
                        min_support_seconds=self.protocol.min_support_seconds,
                        terminal_blank_tail_seconds=self.protocol.terminal_blank_tail_seconds,
                    )
                    for view in (fine, recheck)
                ]
                recheck_gate = (
                    recheck_independent
                    and recheck_semantic
                    and recheck_same_family
                    and any(recheck_support_flags)
                )
                report["rejected_hint_recheck"] = {
                    "coarse_reject": candidate.source_reject,
                    "view": recheck.to_dict(),
                    "support_flags": recheck_support_flags,
                    "independent_transport_views": bool(recheck_independent),
                    "same_kind": bool(fine.kind == recheck.kind),
                    "same_boundary_family": bool(recheck_same_family),
                    "gate_passed": bool(recheck_gate),
                }
                rejected_transient = (
                    fine.verdict == WindowVerdict.TRANSITION.value
                    and fine.reject != "NONE"
                    and fine.continuity != Continuity.CONFIRMED.value
                    and fine.first_pos is not None
                    and (
                        fine.last_support_pos is None
                        or (
                            int(fine.last_support_pos) - int(fine.first_pos)
                        ) / self.config.fps
                        < self.protocol.min_support_seconds
                    )
                    and _is_semantic_noncredit(recheck)
                )
                if rejected_transient:
                    transient_pre = int(math.ceil(
                        self.protocol.fine_pre_seconds * self.config.fps
                    ))
                    transient_post = int(math.ceil(
                        (
                            self.protocol.fine_post_seconds
                            + self.protocol.min_support_seconds
                        ) * self.config.fps
                    ))
                    transient_positions = _linspace_positions(
                        max(0, int(fine.first_pos) - transient_pre),
                        min(total_frames - 1, int(fine.first_pos) + transient_post),
                        max(12, self.protocol.fine_anchor_count),
                    )
                    transient_record_index = len(records)
                    transient = locate(
                        transient_positions,
                        stage=f"{prefix}_transient_b",
                        tile_width=self.protocol.fine_tile_width,
                        columns=2,
                    )
                    transient_record = records[transient_record_index]
                    transient_independent = (
                        transient.positions != recheck.positions
                        and transient.call_id != recheck.call_id
                        and transient_record.get("input_sha256")
                        and recheck_record.get("input_sha256")
                        and transient_record.get("input_sha256")
                        != recheck_record.get("input_sha256")
                        and transient_record.get("prompt_sha256")
                        and recheck_record.get("prompt_sha256")
                        and transient_record.get("prompt_sha256")
                        != recheck_record.get("prompt_sha256")
                    )
                    transient_clear = (
                        transient_independent
                        and _is_semantic_noncredit(recheck)
                        and _is_semantic_noncredit(transient)
                    )
                    report["transient_negative_confirmation"] = {
                        "view": transient.to_dict(),
                        "independent_transport_views": bool(transient_independent),
                        "gate_passed": bool(transient_clear),
                    }
                    if transient_clear:
                        report.update({
                            "status": "REJECTED_TRANSIENT_NONCREDIT_CONFIRMED",
                            "reason": (
                                "two shifted adversarial views disprove the primary "
                                "short rejected transient"
                            ),
                        })
                        continue
                if not recheck_gate:
                    semantic_candidate = (
                        int(fine.first_pos)
                        if fine.first_pos is not None else None
                    )
                    if (
                        semantic_candidate is not None
                        and 1 <= semantic_candidate < total_frames - 1
                    ):
                        semantic_kinds = {
                            kind for kind in {
                                candidate.boundary_kind,
                                fine.kind,
                            }
                            if kind != BoundaryKind.NONE.value
                        }
                        sinks: tuple[list[dict[str, Any]], ...] = (
                            (records, record_sink)
                            if record_sink is not None else (records,)
                        )
                        semantic_audit, call_index = (
                            self._audit_candidate_semantics(
                                candidate_pos=semantic_candidate,
                                allowed_kinds=semantic_kinds,
                                prefix=f"{prefix}_rejected_hint",
                                refs_by_pos=refs_by_pos,
                                total_frames=total_frames,
                                call_index=call_index,
                                out=out,
                                calls_path=calls_path,
                                deadline=deadline,
                                record_sinks=sinks,
                            )
                        )
                        report[
                            "rejected_hint_candidate_semantic_audit"
                        ] = semantic_audit
                        if semantic_audit.get("definitive_noncredit") is True:
                            rejection_floor = remember_semantic_rejection(
                                semantic_candidate
                            )
                            report.update({
                                "status": "REJECTED_SEMANTIC_SENTINEL",
                                "reason": semantic_audit.get("reason"),
                                "rejected_candidate_pos": semantic_candidate,
                                "semantic_rejection_floor_after": rejection_floor,
                            })
                            continue
                    report.update({
                        "status": "UNRESOLVED_REJECTED_HINT",
                        "reason": (
                            "rejected coarse hint was not independently confirmed "
                            "or disproved"
                        ),
                    })
                    return ReviewRescueOutcome(
                        DetectionStatus.REVIEW.value,
                        "earliest rejected coarse hint remains semantically unresolved",
                        call_index,
                        emitted,
                        records,
                        reports,
                        provisional_start=int(fine.first_pos or candidate.provisional_start),
                        review_bracket=[fine.positions[0], fine.positions[-1]],
                        verification={"mode": "chronological_review_rescue", "candidates": reports},
                    )
                rejected_hint_support = any(recheck_support_flags)

            fine_supported = _is_supported(
                fine,
                fps=self.config.fps,
                min_support_seconds=self.protocol.min_support_seconds,
                terminal_blank_tail_seconds=self.protocol.terminal_blank_tail_seconds,
            )
            unsupported_positive_supported = False
            unsupported_positive_support_pos: int | None = None

            # A short primary-only positive is a common epilogue failure mode:
            # narrative sentences containing names/dates can look credit-like
            # in one transport even though they are story text.  Never let the
            # primary call authorize its own rejection or acceptance.  Two
            # distinct adversarial transports may jointly disprove it; if they
            # disagree, the ordinary fail-closed path below remains in force.
            unsupported_primary_positive = (
                not terminal_candidate
                and candidate.source_reject == "NONE"
                and fine.verdict in {
                    WindowVerdict.TRANSITION.value,
                    WindowVerdict.ACTIVE_FROM_LEFT.value,
                }
                and fine.continuity == Continuity.CONFIRMED.value
                and fine.reject == "NONE"
                and _boundary_family(fine.kind) == "SUSTAINED_CREDITS"
                and fine.first_pos is not None
                and not fine_supported
            )
            if unsupported_primary_positive:
                unsupported_positions_a = build_shifted_negative_positions(
                    fine.positions,
                    total_frames=total_frames,
                )
                unsupported_positions_b = build_shifted_negative_positions(
                    unsupported_positions_a,
                    total_frames=total_frames,
                )
                unsupported_views: list[WindowEvidence] = []
                unsupported_records: list[dict[str, Any]] = []
                for suffix, positions in (
                    ("a_b", unsupported_positions_a),
                    ("b_b", unsupported_positions_b),
                ):
                    record_index = len(records)
                    view = locate(
                        positions,
                        stage=f"{prefix}_unsupported_{suffix}",
                        tile_width=self.protocol.fine_tile_width,
                        columns=2,
                    )
                    unsupported_views.append(view)
                    unsupported_records.append(records[record_index])
                unsupported_hashes = [
                    row.get("input_sha256") for row in unsupported_records
                ]
                unsupported_prompts = [
                    row.get("prompt_sha256") for row in unsupported_records
                ]
                unsupported_independent = (
                    unsupported_views[0].positions
                    != unsupported_views[1].positions
                    and unsupported_views[0].call_id
                    != unsupported_views[1].call_id
                    and all(unsupported_hashes)
                    and unsupported_hashes[0] != unsupported_hashes[1]
                    and all(unsupported_prompts)
                    and unsupported_prompts[0] != unsupported_prompts[1]
                    and all(
                        row.get("prompt_variant") == "adversarial_reject"
                        for row in unsupported_records
                    )
                )
                unsupported_disproved = (
                    unsupported_independent
                    and all(
                        _is_semantic_noncredit(view)
                        for view in unsupported_views
                    )
                )
                unsupported_support_flags = [
                    _is_supported(
                        view,
                        fps=self.config.fps,
                        min_support_seconds=self.protocol.min_support_seconds,
                        terminal_blank_tail_seconds=(
                            self.protocol.terminal_blank_tail_seconds
                        ),
                    )
                    for view in unsupported_views
                ]
                unsupported_positive_consensus = bool(
                    unsupported_independent
                    and all(unsupported_support_flags)
                    and all(
                        view.verdict == WindowVerdict.TRANSITION.value
                        and view.continuity == Continuity.CONFIRMED.value
                        and view.reject == "NONE"
                        and _boundary_family(view.kind) == "SUSTAINED_CREDITS"
                        and view.first_pos is not None
                        and view.last_support_pos is not None
                        for view in unsupported_views
                    )
                    and max(
                        int(view.first_pos) for view in unsupported_views
                        if view.first_pos is not None
                    )
                    - min(
                        int(view.first_pos) for view in unsupported_views
                        if view.first_pos is not None
                    )
                    <= self.protocol.rescue_compact_max_candidate_frames
                )
                report["unsupported_positive_recheck"] = {
                    "views": [view.to_dict() for view in unsupported_views],
                    "independent_transport_views": bool(unsupported_independent),
                    "support_flags": unsupported_support_flags,
                    "positive_consensus": unsupported_positive_consensus,
                    "both_semantic_noncredit": bool(all(
                        _is_semantic_noncredit(view)
                        for view in unsupported_views
                    )),
                    "gate_passed": bool(unsupported_disproved),
                }
                if unsupported_disproved:
                    report.update({
                        "status": "REJECTED_UNSUPPORTED_POSITIVE_CONFIRMED",
                        "reason": (
                            "two adversarial transports disprove the short "
                            "primary positive as non-credit text"
                        ),
                    })
                    continue
                if unsupported_positive_consensus:
                    semantic_candidate = int(fine.first_pos)
                    semantic_kinds = {
                        kind for kind in {
                            candidate.boundary_kind,
                            fine.kind,
                            *(view.kind for view in unsupported_views),
                        }
                        if kind != BoundaryKind.NONE.value
                    }
                    sinks: tuple[list[dict[str, Any]], ...] = (
                        (records, record_sink)
                        if record_sink is not None else (records,)
                    )
                    semantic_audit, call_index = self._audit_candidate_semantics(
                        candidate_pos=semantic_candidate,
                        allowed_kinds=semantic_kinds,
                        prefix=f"{prefix}_unsupported_positive",
                        refs_by_pos=refs_by_pos,
                        total_frames=total_frames,
                        call_index=call_index,
                        out=out,
                        calls_path=calls_path,
                        deadline=deadline,
                        record_sinks=sinks,
                    )
                    report["unsupported_positive_recheck"][
                        "candidate_semantic_audit"
                    ] = semantic_audit
                    if semantic_audit.get("definitive_noncredit") is True:
                        rejection_floor = remember_semantic_rejection(
                            semantic_candidate
                        )
                        report.update({
                            "status": "REJECTED_SEMANTIC_SENTINEL",
                            "reason": semantic_audit.get("reason"),
                            "rejected_candidate_pos": semantic_candidate,
                            "semantic_rejection_floor_after": rejection_floor,
                        })
                        continue
                    if semantic_audit.get("gate_passed") is True:
                        unsupported_positive_supported = True
                        unsupported_positive_support_pos = max(
                            int(view.last_support_pos)
                            for view in unsupported_views
                            if view.last_support_pos is not None
                        )
                        report["unsupported_positive_recheck"].update({
                            "positive_gate_passed": True,
                            "support_pos": unsupported_positive_support_pos,
                        })

            terminal_compatible_kinds = {
                BoundaryKind.TERMINAL_END_CARD.value,
                BoundaryKind.END_CARD_THEN_CREDITS.value,
            }
            terminal_fine_mode = (
                terminal_candidate and fine.kind in terminal_compatible_kinds
            )
            if terminal_fine_mode:
                terminal_fine_blank_tail = (
                    (total_frames - 1 - int(fine.last_support_pos))
                    / self.config.fps
                    if fine.last_support_pos is not None else None
                )
                terminal_fine_support = bool(
                    fine.at_stream_eof
                    and fine.first_pos is not None
                    and fine.last_support_pos is not None
                    and fine.last_support_cell > fine.first_cell
                    and terminal_fine_blank_tail is not None
                    and terminal_fine_blank_tail
                    <= self.protocol.terminal_blank_tail_seconds
                )
                terminal_fine_gate = (
                    fine.verdict == WindowVerdict.TRANSITION.value
                    and terminal_fine_support
                    and fine.reject == "NONE"
                    and fine.kind in terminal_compatible_kinds
                    and fine.continuity in {
                        Continuity.CONFIRMED.value,
                        Continuity.UNVERIFIABLE.value,
                    }
                    and fine.first_cell >= 1
                    and fine.first_pos is not None
                    and fine.last_support_pos is not None
                )
                report["terminal_fine_localization_only"] = bool(
                    terminal_fine_gate
                    and fine.continuity == Continuity.UNVERIFIABLE.value
                )
                if not terminal_fine_gate:
                    report.update({
                        "status": "UNRESOLVED_TERMINAL_FINE",
                        "reason": (
                            f"{fine.verdict}/{fine.continuity}/{fine.reject}/"
                            f"{fine.kind} did not prove a bounded terminal card"
                        ),
                    })
                    return ReviewRescueOutcome(
                        DetectionStatus.REVIEW.value,
                        "earliest terminal-card proposal remains semantically unresolved",
                        call_index,
                        emitted,
                        records,
                        reports,
                        provisional_start=int(fine.first_pos or candidate.provisional_start),
                        review_bracket=[fine.positions[0], fine.positions[-1]],
                        verification={"mode": "chronological_review_rescue", "candidates": reports},
                    )

                approximate = int(fine.first_pos)
                semantic_pre_pos = int(fine.positions[fine.first_cell - 1])
                exact_pre_pos = max(0, semantic_pre_pos - 1)
                terminal_views: list[WindowEvidence] = []
                terminal_records: list[dict[str, Any]] = []
                boundary_ranges: list[list[int]] = []
                eof = total_frames - 1
                for shift, variant in ((0, "a"), (-1, "b")):
                    exact_positions = build_exact_verification_positions(
                        approximate,
                        shift=shift,
                        total_frames=total_frames,
                        fps=self.config.fps,
                        pre_pos=exact_pre_pos,
                        config=self.protocol,
                    )
                    terminal_context = {eof}
                    for seconds in (
                        1.0,
                        3.0,
                        5.0,
                        8.0,
                        self.protocol.terminal_blank_tail_seconds,
                    ):
                        offset = int(math.floor(seconds * self.config.fps + 0.5))
                        terminal_context.add(max(0, eof - offset))
                    terminal_context.update({
                        max(0, int(fine.last_support_pos) - 1),
                        int(fine.last_support_pos),
                        min(eof, int(fine.last_support_pos) + 1),
                    })
                    exact_positions = sorted({*exact_positions, *terminal_context})
                    boundary_indexes = [
                        index for index, position in enumerate(exact_positions)
                        if exact_pre_pos < position <= approximate
                    ]
                    if (
                        not boundary_indexes
                        or boundary_indexes != list(range(
                            boundary_indexes[0], boundary_indexes[-1] + 1
                        ))
                        or boundary_indexes[0] < 1
                    ):
                        raise ValueError(
                            "terminal exact boundary cells are missing or non-contiguous"
                        )
                    search = (boundary_indexes[0], boundary_indexes[-1])
                    boundary_ranges.append(list(search))
                    columns = 2 if variant == "b" else 3
                    terminal_record_index = len(records)
                    view = locate(
                        exact_positions,
                        stage=f"{prefix}_verify_{variant}",
                        tile_width=bounded_verification_tile_width(
                            len(exact_positions),
                            columns=columns,
                            config=self.protocol,
                        ),
                        columns=columns,
                        boundary_search_cells=search,
                    )
                    terminal_views.append(view)
                    terminal_records.append(records[terminal_record_index])

                terminal_positions = [view.first_pos for view in terminal_views]
                hashes = [row.get("input_sha256") for row in terminal_records]
                prompt_hashes = [row.get("prompt_sha256") for row in terminal_records]
                independent = (
                    terminal_views[0].positions != terminal_views[1].positions
                    and terminal_views[0].call_id != terminal_views[1].call_id
                    and all(hashes)
                    and hashes[0] != hashes[1]
                    and all(prompt_hashes)
                    and prompt_hashes[0] != prompt_hashes[1]
                    and terminal_records[0].get("prompt_variant") == "primary_boundary"
                    and terminal_records[1].get("prompt_variant") == "adversarial_reject"
                )
                adjacent_pre = all(
                    view.first_cell >= 1
                    and view.positions[view.first_cell]
                    - view.positions[view.first_cell - 1] == 1
                    for view in terminal_views
                )
                agree = (
                    all(position is not None for position in terminal_positions)
                    and abs(int(terminal_positions[0]) - int(terminal_positions[1]))
                    <= self.protocol.verification_tolerance_frames
                )
                exact_consensus_kind = (
                    terminal_views[0].kind
                    if terminal_views[0].kind == terminal_views[1].kind
                    else None
                )
                exact_kind = exact_consensus_kind in {
                    BoundaryKind.TERMINAL_END_CARD.value,
                    BoundaryKind.END_CARD_THEN_CREDITS.value,
                }
                terminal_compatible_kind = (
                    fine.kind in terminal_compatible_kinds
                    and exact_kind
                )
                exact_semantic = all(
                    view.verdict == WindowVerdict.TRANSITION.value
                    and view.continuity == Continuity.CONFIRMED.value
                    and view.reject == "NONE"
                    for view in terminal_views
                )
                inside = all(
                    position is not None
                    and exact_pre_pos < int(position) <= approximate
                    for position in terminal_positions
                )
                blank_tails = [
                    round((eof - int(view.last_support_pos)) / self.config.fps, 3)
                    if view.last_support_pos is not None else None
                    for view in terminal_views
                ]
                terminal_support = [
                    bool(
                        view.at_stream_eof
                        and view.first_pos is not None
                        and view.last_support_pos is not None
                        and view.last_support_cell > view.first_cell
                        and blank_tails[index] is not None
                        and float(blank_tails[index])
                        <= self.protocol.terminal_blank_tail_seconds
                    )
                    for index, view in enumerate(terminal_views)
                ]
                terminal_ok = (
                    all(terminal_support)
                    and all(view.at_stream_eof for view in terminal_views)
                    and all(
                        seconds is not None
                        and seconds <= self.protocol.terminal_blank_tail_seconds
                        for seconds in blank_tails
                    )
                )
                exact_structural_gate = (
                    independent
                    and adjacent_pre
                    and terminal_compatible_kind
                    and exact_semantic
                    and inside
                    and terminal_ok
                )
                terminal_micro_support = max(
                    int(view.last_support_pos) for view in terminal_views
                    if view.last_support_pos is not None
                ) if exact_semantic else int(fine.last_support_pos)
                micro = (
                    micro_adjudicate(
                        prefix=prefix,
                        exact_views=terminal_views,
                        exact_records=terminal_records,
                        support_pos=terminal_micro_support,
                        allowed_kinds={
                            BoundaryKind.CREDIT_SEQUENCE.value,
                            BoundaryKind.TERMINAL_END_CARD.value,
                            BoundaryKind.END_CARD_THEN_CREDITS.value,
                        },
                        at_stream_eof=True,
                        allow_family_match=True,
                    )
                    if exact_structural_gate else {
                        "gate_passed": False,
                        "chosen_pos": None,
                        "reason": "terminal exact structural gates failed before micro audit",
                        "views": [],
                    }
                )
                apply_candidate_semantic_gate(
                    micro,
                    prefix=f"{prefix}_terminal",
                    allowed_kinds={
                        BoundaryKind.CREDIT_SEQUENCE.value,
                        BoundaryKind.TERMINAL_END_CARD.value,
                        BoundaryKind.END_CARD_THEN_CREDITS.value,
                    },
                )
                exact_gate = bool(exact_structural_gate and micro["gate_passed"])
                verification = {
                    "mode": "chronological_review_rescue_terminal",
                    "candidates": reports,
                    "independent_transport_views": bool(independent),
                    "independent_calls": bool(independent),
                    "both_supported": bool(all(terminal_support)),
                    "exact_support_flags": terminal_support,
                    "both_exact_semantic": bool(exact_semantic),
                    "support_chain_ok": bool(all(terminal_support)),
                    "adjacent_pre": bool(adjacent_pre),
                    "first_positions": terminal_positions,
                    "tolerance_frames": self.protocol.verification_tolerance_frames,
                    "agree": bool(agree),
                    "inside_exact_search_gap": bool(inside),
                    "exact_search_pre_pos": exact_pre_pos,
                    "fine_semantic_pre_pos": semantic_pre_pos,
                    "fine_approximate_pos": approximate,
                    "boundary_search_cells": boundary_ranges,
                    "same_kind": bool(exact_kind),
                    "same_boundary_family": bool(terminal_compatible_kind),
                    "exact_consensus_kind": exact_consensus_kind,
                    "terminal_ok": bool(terminal_ok),
                    "terminal_blank_tail_seconds": blank_tails,
                    "input_sha256": hashes,
                    "prompt_sha256": prompt_hashes,
                    "exact_structural_gate": bool(exact_structural_gate),
                    "micro_boundary": micro,
                }
                report["exact"] = {
                    "first_positions": terminal_positions,
                    "support_flags": terminal_support,
                    "gate_passed": bool(exact_gate),
                }
                semantic_audit = micro.get("candidate_semantic_audit") or {}
                if (
                    not exact_gate
                    and semantic_audit.get("definitive_noncredit") is True
                ):
                    rejected_position = micro.get("pre_semantic_chosen_pos")
                    rejection_floor = remember_semantic_rejection(
                        rejected_position
                    )
                    report.update({
                        "status": "REJECTED_SEMANTIC_SENTINEL",
                        "reason": semantic_audit.get("reason"),
                        "rejected_candidate_pos": rejected_position,
                        "semantic_rejection_floor_after": rejection_floor,
                    })
                    continue
                if not exact_gate:
                    report.update({
                        "status": "UNRESOLVED_TERMINAL_EXACT",
                        "reason": "terminal primary/adversarial views did not pass all gates",
                    })
                    available = [
                        int(position) for position in terminal_positions
                        if position is not None
                    ]
                    return ReviewRescueOutcome(
                        DetectionStatus.REVIEW.value,
                        "earliest terminal-card candidate failed exact agreement",
                        call_index,
                        emitted,
                        records,
                        reports,
                        provisional_start=(min(available) if available else approximate),
                        review_bracket=(
                            [min(available), max(available)]
                            if available else [semantic_pre_pos, approximate]
                        ),
                        verification=verification,
                    )
                found = int(micro["chosen_pos"])
                report.update({
                    "status": "FOUND",
                    "reason": "terminal exact views passed micro boundary adjudication",
                    "start_pos": found,
                })
                verification["boundary_refinement"] = {
                    "semantic_start_pos": found,
                    "visual_start_pos": found,
                    "backtrack_frames": 0,
                    "method": "dense_terminal_then_micro_primary_adversarial",
                }
                return ReviewRescueOutcome(
                    DetectionStatus.FOUND.value,
                    "terminal THE END card passed dense primary/adversarial verification",
                    call_index,
                    emitted,
                    records,
                    reports,
                    start_pos=found,
                    onset_kind=str(exact_consensus_kind),
                    verification=verification,
                )

            if (
                fine.verdict in {
                    WindowVerdict.ACTIVE_FROM_LEFT.value,
                    WindowVerdict.TRANSITION.value,
                }
                and fine.first_cell <= 1
                and 0 < candidate.wide_left < fine.positions[0]
            ):
                left_positions = _linspace_positions(
                    candidate.wide_left,
                    fine.positions[-1],
                    max(12, self.protocol.fine_anchor_count),
                )
                fine = locate(
                    left_positions,
                    stage=f"{prefix}_fine_left",
                    tile_width=self.protocol.fine_tile_width,
                    columns=3,
                )
                report["fine_left"] = fine.to_dict()
                fine_supported = _is_supported(
                    fine,
                    fps=self.config.fps,
                    min_support_seconds=self.protocol.min_support_seconds,
                    terminal_blank_tail_seconds=self.protocol.terminal_blank_tail_seconds,
                )

            hint_supported = (
                candidate.support_hint is not None
                and candidate.support_call_id == candidate.source_call_id
                and fine.first_pos is not None
                and candidate.support_hint > fine.first_pos
                and (
                    candidate.support_hint - int(fine.first_pos)
                ) / self.config.fps >= self.protocol.min_support_seconds
            )
            fine_effectively_supported = (
                fine_supported
                or rejected_hint_support
                or hint_supported
                or unsupported_positive_supported
            )
            fine_family = _boundary_family(fine.kind)
            fine_gate = (
                fine.verdict == WindowVerdict.TRANSITION.value
                and fine_effectively_supported
                and fine.reject == "NONE"
                and fine_family == "SUSTAINED_CREDITS"
                and fine.continuity == Continuity.CONFIRMED.value
                and fine.first_cell >= 1
                and fine.first_pos is not None
                and fine.last_support_pos is not None
            )

            chronology_views: list[WindowEvidence] = []
            chronology_gap: tuple[int, int] | None = None
            chronology_fallback_group: int | None = None
            chronology_required = (
                candidate.requires_chronology_guard
                or candidate.source_first_cell >= self.protocol.coarse_anchor_count
                or not fine_gate
            )
            chronology_groups = [
                list(group) for group in candidate.chronology_groups
                if len(group) >= 3
            ]
            if not chronology_groups and len(candidate.chronology_positions) >= 3:
                chronology_groups = [list(candidate.chronology_positions)]
            if candidate.requires_chronology_guard and not chronology_groups:
                report.update({
                    "status": "UNRESOLVED_CHRONOLOGY_COVERAGE",
                    "reason": "required earlier chronology has no lossless evidence group",
                })
                return ReviewRescueOutcome(
                    DetectionStatus.REVIEW.value,
                    "required earlier chronology could not be represented safely",
                    call_index,
                    emitted,
                    records,
                    reports,
                    provisional_start=int(fine.first_pos or candidate.provisional_start),
                    review_bracket=list(candidate.bracket),
                    verification={"mode": "chronological_review_rescue", "candidates": reports},
                )
            if (
                chronology_required
                and chronology_groups
                and fine.verdict in {
                    WindowVerdict.TRANSITION.value,
                    WindowVerdict.ACTIVE_FROM_LEFT.value,
                }
            ):
                group_reports: list[dict[str, Any]] = []
                cleared_positions: list[int] = []
                selected_group: int | None = None
                for group_ordinal, chronology_a in enumerate(chronology_groups, start=1):
                    chronology_b = build_shifted_negative_positions(
                        chronology_a,
                        total_frames=total_frames,
                    )
                    group_views: list[WindowEvidence] = []
                    group_records: list[dict[str, Any]] = []
                    single_group = len(chronology_groups) == 1
                    for variant, positions in (("a", chronology_a), ("b", chronology_b)):
                        record_index = len(records)
                        group_token = "" if single_group else f"_{group_ordinal:02d}"
                        view = locate(
                            positions,
                            stage=f"{prefix}_chronology{group_token}_{variant}",
                            tile_width=min(
                                self.protocol.rescue_localize_tile_width,
                                bounded_verification_tile_width(
                                    len(positions),
                                    columns=2 if variant == "b" else 3,
                                    config=self.protocol,
                                ),
                            ),
                            columns=2 if variant == "b" else 3,
                        )
                        group_views.append(view)
                        group_records.append(records[record_index])
                    group_support = [
                        _is_supported(
                            view,
                            fps=self.config.fps,
                            min_support_seconds=self.protocol.min_support_seconds,
                            terminal_blank_tail_seconds=self.protocol.terminal_blank_tail_seconds,
                        )
                        for view in group_views
                    ]
                    group_hashes = [row.get("input_sha256") for row in group_records]
                    group_prompts = [row.get("prompt_sha256") for row in group_records]
                    group_independent = (
                        group_views[0].positions != group_views[1].positions
                        and group_views[0].call_id != group_views[1].call_id
                        and all(group_hashes)
                        and group_hashes[0] != group_hashes[1]
                        and all(group_prompts)
                        and group_prompts[0] != group_prompts[1]
                        and group_records[0].get("prompt_variant") == "primary_boundary"
                        and group_records[1].get("prompt_variant") == "adversarial_reject"
                    )
                    transition_semantic = all(
                        view.verdict == WindowVerdict.TRANSITION.value
                        and view.continuity == Continuity.CONFIRMED.value
                        and view.reject == "NONE"
                        and view.first_cell >= 1
                        and view.first_pos is not None
                        and view.last_support_pos is not None
                        for view in group_views
                    )
                    active_semantic = all(
                        view.verdict == WindowVerdict.ACTIVE_FROM_LEFT.value
                        and view.continuity == Continuity.CONFIRMED.value
                        and view.reject == "NONE"
                        and view.first_cell == 0
                        and view.first_pos is not None
                        and view.last_support_pos is not None
                        for view in group_views
                    )
                    same_kind = (
                        group_views[0].kind == group_views[1].kind
                        != BoundaryKind.NONE.value
                    )
                    group_gap: tuple[int, int] | None = None
                    left_context_widened_from: int | None = None
                    left_context_widened_to: int | None = None
                    if transition_semantic:
                        group_left = min(
                            int(view.positions[view.first_cell - 1])
                            for view in group_views
                        )
                        group_right = max(
                            int(view.first_pos) for view in group_views
                            if view.first_pos is not None
                        )
                        first_spread = max(
                            int(view.first_pos) for view in group_views
                            if view.first_pos is not None
                        ) - min(
                            int(view.first_pos) for view in group_views
                            if view.first_pos is not None
                        )
                        # Sparse chronology transports can legitimately land
                        # one anchor apart on a low-contrast overlay onset.
                        # A wide disagreement is localization evidence only:
                        # retain exactly one earlier source anchor so the true
                        # edge is not excluded, while the later exact, micro,
                        # and candidate-semantic gates remain mandatory.
                        earlier_source_anchors = [
                            int(position) for position in chronology_a
                            if int(position) < group_left
                        ]
                        if (
                            first_spread
                            > self.protocol.rescue_compact_max_candidate_frames
                            and earlier_source_anchors
                        ):
                            left_context_widened_from = group_left
                            group_left = max(earlier_source_anchors)
                            left_context_widened_to = group_left
                        if group_left < group_right:
                            group_gap = (group_left, group_right)
                    elif active_semantic and cleared_positions:
                        first_active = min(
                            int(view.first_pos) for view in group_views
                            if view.first_pos is not None
                        )
                        earlier_pre = [
                            position for position in cleared_positions
                            if position < first_active
                        ]
                        if earlier_pre:
                            group_gap = (max(earlier_pre), first_active)
                    positive_gate = (
                        group_independent
                        and any(group_support)
                        and (transition_semantic or active_semantic)
                        and same_kind
                        and group_gap is not None
                    )
                    negative_clear = (
                        group_independent
                        and all(_is_semantic_noncredit(view) for view in group_views)
                    )
                    group_report = {
                        "ordinal": group_ordinal,
                        "source_positions": chronology_a,
                        "views": [view.to_dict() for view in group_views],
                        "support_flags": group_support,
                        "support_chain_ok": bool(any(group_support)),
                        "independent_transport_views": bool(group_independent),
                        "same_kind": bool(same_kind),
                        "union_gap": list(group_gap) if group_gap is not None else None,
                        "left_context_widened_from": left_context_widened_from,
                        "left_context_widened_to": left_context_widened_to,
                        "gate_passed": bool(positive_gate),
                        "negative_clear": bool(negative_clear),
                        "outcome": (
                            "EARLIER_TRANSITION" if positive_gate else (
                                "EARLIER_NONCREDIT" if negative_clear else "UNRESOLVED"
                            )
                        ),
                    }
                    group_reports.append(group_report)
                    if positive_gate:
                        chronology_views = group_views
                        chronology_gap = group_gap
                        selected_group = group_ordinal
                        break
                    if negative_clear:
                        cleared_positions.extend(chronology_a)
                        continue
                    positive_indexes = [
                        index for index, view in enumerate(group_views)
                        if group_support[index]
                        and view.verdict in {
                            WindowVerdict.TRANSITION.value,
                            WindowVerdict.ACTIVE_FROM_LEFT.value,
                        }
                        and view.continuity == Continuity.CONFIRMED.value
                        and view.reject == "NONE"
                        and _boundary_family(view.kind) == fine_family
                    ]
                    negative_indexes = [
                        index for index, view in enumerate(group_views)
                        if _is_semantic_noncredit(view)
                    ]
                    disputed_boundary_gap: tuple[int, int] | None = None
                    earlier_cleared = (
                        [
                            position for position in cleared_positions
                            if fine.first_pos is not None
                            and position < int(fine.first_pos)
                        ]
                        if cleared_positions else []
                    )
                    active_indexes = [
                        index for index, view in enumerate(group_views)
                        if group_support[index]
                        and view.verdict == WindowVerdict.ACTIVE_FROM_LEFT.value
                        and view.first_cell == 0
                        and view.first_pos is not None
                        and view.continuity == Continuity.CONFIRMED.value
                        and view.reject == "NONE"
                        and _boundary_family(view.kind) == fine_family
                    ]
                    last_cell_indexes = [
                        index for index, view in enumerate(group_views)
                        if view.verdict == WindowVerdict.TRANSITION.value
                        and view.first_cell == len(view.positions) - 1
                        and view.first_pos is not None
                        and view.last_support_cell == view.first_cell
                        and view.last_support_pos == view.first_pos
                        and view.continuity == Continuity.UNVERIFIABLE.value
                        and _boundary_family(view.kind) == fine_family
                    ]
                    active_last_cell_conflict = bool(
                        group_ordinal == len(chronology_groups)
                        and group_independent
                        and fine_gate
                        and earlier_cleared
                        and same_kind
                        and len(active_indexes) == 1
                        and len(last_cell_indexes) == 1
                        and active_indexes[0] != last_cell_indexes[0]
                        and fine.first_pos is not None
                        and fine.first_cell >= 1
                    )
                    if active_last_cell_conflict:
                        active_view = group_views[active_indexes[0]]
                        last_view = group_views[last_cell_indexes[0]]
                        active_pos = int(active_view.first_pos)
                        last_pos = int(last_view.first_pos)
                        last_pre = int(
                            last_view.positions[last_view.first_cell - 1]
                        )
                        fine_pre = int(fine.positions[fine.first_cell - 1])
                        allowed_span = max(
                            1,
                            int(math.ceil(
                                self.config.fps
                                * self.protocol.min_support_seconds
                            )),
                        )
                        bounded_last_cell = bool(
                            1 <= active_pos < total_frames - 1
                            and 1 <= last_pos < total_frames - 1
                            and last_pre < last_pos
                            and fine_pre < last_pos <= int(fine.first_pos)
                            and 0 < int(fine.first_pos) - fine_pre <= allowed_span
                        )
                        if bounded_last_cell:
                            semantic_kinds = {
                                kind for kind in {
                                    fine.kind,
                                    active_view.kind,
                                    last_view.kind,
                                }
                                if kind != BoundaryKind.NONE.value
                            }
                            sinks: tuple[list[dict[str, Any]], ...] = (
                                (records, record_sink)
                                if record_sink is not None else (records,)
                            )
                            active_audit, call_index = (
                                self._audit_candidate_semantics(
                                    candidate_pos=active_pos,
                                    allowed_kinds=semantic_kinds,
                                    prefix=(
                                        f"{prefix}_chronology_"
                                        f"{group_ordinal:02d}_active_disproof"
                                    ),
                                    refs_by_pos=refs_by_pos,
                                    total_frames=total_frames,
                                    call_index=call_index,
                                    out=out,
                                    calls_path=calls_path,
                                    deadline=deadline,
                                    record_sinks=sinks,
                                )
                            )
                            last_audit, call_index = (
                                self._audit_candidate_semantics(
                                    candidate_pos=last_pos,
                                    allowed_kinds=semantic_kinds,
                                    prefix=(
                                        f"{prefix}_chronology_"
                                        f"{group_ordinal:02d}_last_cell"
                                    ),
                                    refs_by_pos=refs_by_pos,
                                    total_frames=total_frames,
                                    call_index=call_index,
                                    out=out,
                                    calls_path=calls_path,
                                    deadline=deadline,
                                    record_sinks=sinks,
                                )
                            )
                            conflict_audit = {
                                "gate_passed": bool(
                                    active_audit.get("definitive_noncredit")
                                    and last_audit.get("gate_passed")
                                ),
                                "active_claim_pos": active_pos,
                                "last_cell_pos": last_pos,
                                "last_cell_pre_pos": last_pre,
                                "fine_pre_pos": fine_pre,
                                "fine_first_pos": int(fine.first_pos),
                                "active_claim_audit": active_audit,
                                "last_cell_audit": last_audit,
                            }
                            group_report[
                                "active_last_cell_conflict_audit"
                            ] = conflict_audit
                            if conflict_audit["gate_passed"]:
                                later_positive_semantic_supports.append({
                                    "scope": prefix,
                                    "candidate_pos": last_pos,
                                    "allowed_kinds": sorted(semantic_kinds),
                                    "audit": last_audit,
                                    "source": (
                                        "active_last_cell_conflict_last_cell"
                                    ),
                                })
                                recovered_gap = (last_pre, last_pos)
                                group_report.update({
                                    "outcome": (
                                        "ACTIVE_LEFT_DISPROVED_LAST_CELL_PROVED"
                                    ),
                                    "active_last_cell_gap": list(recovered_gap),
                                    "gate_passed": False,
                                    "negative_clear": False,
                                })
                                chronology_views = [fine]
                                chronology_gap = recovered_gap
                                chronology_fallback_group = group_ordinal
                                break
                    if (
                        fine_gate
                        and len(positive_indexes) == 1
                        and len(negative_indexes) == 1
                        and positive_indexes[0] != negative_indexes[0]
                        and earlier_cleared
                        and fine.first_pos is not None
                    ):
                        confirmed_pre = max(earlier_cleared)
                        if (
                            confirmed_pre < int(fine.first_pos)
                            and max(chronology_a) > confirmed_pre
                        ):
                            disputed_boundary_gap = (
                                confirmed_pre,
                                int(fine.first_pos),
                            )
                    if disputed_boundary_gap is not None:
                        # The sparse panel is too weak to decide whether its
                        # last cell has already entered credits, but all earlier
                        # chronology was independently cleared and the focused
                        # fine view proves a later sustained regime. Preserve
                        # only that PRE-to-positive bracket and send it through
                        # the ordinary two-view localization + dense exact
                        # gates. Neither disputed sparse answer authorizes FOUND.
                        group_report.update({
                            "outcome": "DISPUTED_BOUNDARY_BRACKET",
                            "disputed_boundary_gap": list(disputed_boundary_gap),
                            "gate_passed": False,
                            "negative_clear": False,
                        })
                        chronology_views = [fine]
                        chronology_gap = disputed_boundary_gap
                        chronology_fallback_group = group_ordinal
                        break
                    # A sparse chronology panel can place the first visible
                    # credit in its final cell yet be unable to prove duration,
                    # because no later cell exists in that panel.  Two shifted
                    # views agreeing on that exact last-cell transition are
                    # useful only as a *bracket*: a supported fine view must
                    # independently prove the same sustained family immediately
                    # afterwards, all earlier chronology groups must already be
                    # clear, and both sparse views must share the same PRE
                    # predecessor.  The sparse answer never authorizes FOUND;
                    # the bracket still goes through localization, dense exact,
                    # and micro adjudication below.
                    sparse_first_positions = [
                        int(view.first_pos) for view in group_views
                        if view.first_pos is not None
                    ]
                    sparse_pre_positions = [
                        int(view.positions[view.first_cell - 1])
                        for view in group_views
                        if view.first_cell >= 1
                    ]
                    fine_sparse_delta = (
                        int(fine.first_pos) - sparse_first_positions[0]
                        if fine.first_pos is not None
                        and sparse_first_positions else None
                    )
                    fine_transition_pre = (
                        int(fine.positions[fine.first_cell - 1])
                        if fine.first_cell >= 1 else None
                    )
                    fine_transition_span = (
                        int(fine.first_pos) - fine_transition_pre
                        if fine.first_pos is not None
                        and fine_transition_pre is not None else None
                    )
                    allowed_fine_transition_span = max(
                        1,
                        int(math.ceil(
                            self.config.fps * self.protocol.min_support_seconds
                        )),
                    )
                    sparse_last_cell_checks = {
                        "final_group": group_ordinal == len(chronology_groups),
                        "independent_views": bool(group_independent),
                        "supported_fine": bool(fine_gate),
                        "earlier_groups_cleared": bool(earlier_cleared),
                        "same_kind": bool(same_kind),
                        "sparse_views_unsupported": all(
                            not supported for supported in group_support
                        ),
                        "same_sparse_first": (
                            len(sparse_first_positions) == 2
                            and len(set(sparse_first_positions)) == 1
                        ),
                        "same_sparse_predecessor": (
                            len(sparse_pre_positions) == 2
                            and len(set(sparse_pre_positions)) == 1
                        ),
                        "last_cell_semantics": all(
                            view.verdict == WindowVerdict.TRANSITION.value
                            and view.continuity == Continuity.UNVERIFIABLE.value
                            and view.reject == "NONE"
                            and view.first_cell == len(view.positions) - 1
                            and view.last_support_cell == view.first_cell
                            and view.last_support_pos == view.first_pos
                            and _boundary_family(view.kind) == fine_family
                            for view in group_views
                        ),
                        "sparse_inside_fine_transition": (
                            fine.first_pos is not None
                            and fine_transition_pre is not None
                            and fine_transition_span is not None
                            and len(sparse_first_positions) == 2
                            and 0 < fine_transition_span
                            <= allowed_fine_transition_span
                            and fine_transition_pre
                            < sparse_first_positions[0]
                            <= int(fine.first_pos)
                        ),
                    }
                    group_report["last_cell_bracket_delta"] = {
                        "fine_first_pos": (
                            int(fine.first_pos)
                            if fine.first_pos is not None else None
                        ),
                        "sparse_first_positions": sparse_first_positions,
                        "fine_minus_sparse_frames": fine_sparse_delta,
                        "fine_transition_pre": fine_transition_pre,
                        "fine_transition_span": fine_transition_span,
                        "allowed_fine_transition_span": (
                            allowed_fine_transition_span
                        ),
                    }
                    group_report["last_cell_bracket_checks"] = (
                        sparse_last_cell_checks
                    )
                    agreed_last_cell_transition = all(
                        sparse_last_cell_checks.values()
                    )
                    if agreed_last_cell_transition:
                        sparse_pre = sparse_pre_positions[0]
                        fine_positive = int(fine.first_pos)
                        if sparse_pre < fine_positive:
                            agreed_sparse_gap = (sparse_pre, fine_positive)
                            group_report.update({
                                "outcome": "AGREED_LAST_CELL_BOUNDARY_BRACKET",
                                "agreed_last_cell_gap": list(agreed_sparse_gap),
                                "gate_passed": False,
                                "negative_clear": False,
                            })
                            chronology_views = [fine]
                            chronology_gap = agreed_sparse_gap
                            chronology_fallback_group = group_ordinal
                            break
                    report["chronology_guard"] = {
                        "groups": group_reports,
                        **group_report,
                        "selected_group": None,
                    }
                    report.update({
                        "status": "UNRESOLVED_CHRONOLOGY",
                        "reason": "an earlier chronology group is semantically unresolved",
                    })
                    return ReviewRescueOutcome(
                        DetectionStatus.REVIEW.value,
                        "earliest visible text chronology could not be resolved safely",
                        call_index,
                        emitted,
                        records,
                        reports,
                        provisional_start=int(fine.first_pos or candidate.provisional_start),
                        review_bracket=[chronology_a[0], chronology_a[-1]],
                        verification={"mode": "chronological_review_rescue", "candidates": reports},
                    )
                all_negative = (
                    selected_group is None and chronology_fallback_group is None
                )
                summary_group = group_reports[-1]
                report["chronology_guard"] = {
                    "groups": group_reports,
                    **summary_group,
                    "selected_group": selected_group,
                    "fallback_group": chronology_fallback_group,
                    "gate_passed": selected_group is not None,
                    "negative_clear": all_negative,
                    "outcome": (
                        "EARLIER_TRANSITION" if selected_group is not None
                        else (
                            str(summary_group.get(
                                "outcome",
                                "DISPUTED_BOUNDARY_BRACKET",
                            ))
                            if chronology_fallback_group is not None
                            else "EARLIER_NONCREDIT"
                        )
                    ),
                }
                if selected_group is not None:
                    fine = chronology_views[0]
                    fine_family = _boundary_family(fine.kind)
                    fine_gate = True

            if not fine_gate:
                report.update({
                    "status": "UNRESOLVED_FINE",
                    "reason": (
                        f"{fine.verdict}/{fine.continuity}/{fine.reject}/"
                        f"{fine.kind} did not pass focused fine gates"
                    ),
                })
                return ReviewRescueOutcome(
                    DetectionStatus.REVIEW.value,
                    "earliest non-PRE coarse proposal remains semantically unresolved",
                    call_index,
                    emitted,
                    records,
                    reports,
                    provisional_start=int(fine.first_pos or candidate.provisional_start),
                    review_bracket=[fine.positions[0], fine.positions[-1]],
                    verification={"mode": "chronological_review_rescue", "candidates": reports},
                )

            if chronology_gap is not None:
                semantic_pre_pos, search_right = chronology_gap
                support_pos = max(
                    int(view.last_support_pos) for view in chronology_views
                    if view.last_support_pos is not None
                )
            else:
                # A sparse fine panel may mistake a later static card change
                # for the onset when earlier cards are separated by black
                # gaps. Preserve the source coarse PRE bracket as the left
                # bound instead of letting the later fine predecessor erase it.
                semantic_pre_pos = min(
                    int(candidate.bracket[0]),
                    int(fine.positions[fine.first_cell - 1]),
                )
                search_right = max(int(candidate.bracket[1]), int(fine.first_pos))
                support_pos = int(fine.last_support_pos)
                if hint_supported and candidate.support_hint is not None:
                    support_pos = max(support_pos, int(candidate.support_hint))
                if unsupported_positive_support_pos is not None:
                    support_pos = max(
                        support_pos,
                        unsupported_positive_support_pos,
                    )
            original_semantic_pre = semantic_pre_pos
            if semantic_rejection_floor is not None:
                if semantic_rejection_floor >= search_right:
                    report.update({
                        "status": "SKIPPED_BELOW_SEMANTIC_REJECTION_FLOOR",
                        "reason": (
                            "candidate search range does not extend beyond the "
                            "previous independently disproved semantic edge"
                        ),
                        "semantic_rejection_floor": semantic_rejection_floor,
                        "search_right_pos": search_right,
                    })
                    continue
                semantic_pre_pos = max(
                    semantic_pre_pos,
                    semantic_rejection_floor,
                )
            report["semantic_rejection_floor"] = {
                "active": semantic_rejection_floor,
                "original_pre_pos": original_semantic_pre,
                "effective_pre_pos": semantic_pre_pos,
                "search_right_pos": search_right,
            }
            exact_pre_pos = max(0, semantic_pre_pos - 1)
            if not 0 < semantic_pre_pos < search_right < total_frames:
                report.update({
                    "status": "UNRESOLVED_RANGE",
                    "reason": "focused fine view did not leave a bounded PRE-to-credit gap",
                })
                return ReviewRescueOutcome(
                    DetectionStatus.REVIEW.value,
                    "review rescue could not construct a bounded localization gap",
                    call_index,
                    emitted,
                    records,
                    reports,
                    provisional_start=int(fine.first_pos),
                    review_bracket=[semantic_pre_pos, search_right],
                    verification={"mode": "chronological_review_rescue", "candidates": reports},
                )

            localization_passes: list[dict[str, Any]] = []
            localization_pre = semantic_pre_pos
            localization_right = search_right
            local_views: list[WindowEvidence] = []
            local_records: list[dict[str, Any]] = []
            local_positions: list[int | None] = []
            local_pre_positions: list[int | None] = []
            local_support: list[bool] = []
            localized_pre: int | None = None
            localized_right: int | None = None
            local_gate = False
            for localization_pass in range(1, 3):
                local_views = []
                local_records = []
                for variant in ("a", "b"):
                    positions, search = build_rescue_localization_positions(
                        localization_pre,
                        localization_right,
                        support_pos=support_pos,
                        variant=variant,
                        total_frames=total_frames,
                        fps=self.config.fps,
                        config=self.protocol,
                        candidate_floor_exclusive=(
                            semantic_rejection_floor
                            if semantic_rejection_floor is not None
                            and localization_pre == semantic_rejection_floor
                            else None
                        ),
                    )
                    before_records = len(records)
                    stage = (
                        f"{prefix}_localize_{variant}"
                        if localization_pass == 1
                        else f"{prefix}_localize_{localization_pass:02d}_{variant}"
                    )
                    view = locate(
                        positions,
                        stage=stage,
                        tile_width=self.protocol.rescue_localize_tile_width,
                        columns=2 if variant == "b" else 3,
                        boundary_search_cells=search,
                    )
                    local_views.append(view)
                    local_records.append(records[before_records])

                local_positions = [item.first_pos for item in local_views]
                local_pre_positions = [
                    int(item.positions[item.first_cell - 1])
                    if item.first_cell >= 1 else None
                    for item in local_views
                ]
                localized_pre = (
                    min(
                        int(position) for position in local_pre_positions
                        if position is not None
                    )
                    if all(position is not None for position in local_pre_positions)
                    else None
                )
                localized_right = (
                    max(
                        int(position) for position in local_positions
                        if position is not None
                    )
                    if all(position is not None for position in local_positions)
                    else None
                )
                local_support = [
                    _is_supported(
                        item,
                        fps=self.config.fps,
                        min_support_seconds=self.protocol.min_support_seconds,
                        terminal_blank_tail_seconds=self.protocol.terminal_blank_tail_seconds,
                    )
                    for item in local_views
                ]
                local_hashes = [record.get("input_sha256") for record in local_records]
                local_prompt_hashes = [
                    record.get("prompt_sha256") for record in local_records
                ]
                local_independent = (
                    local_views[0].positions != local_views[1].positions
                    and local_views[0].call_id != local_views[1].call_id
                    and all(local_hashes)
                    and local_hashes[0] != local_hashes[1]
                    and all(local_prompt_hashes)
                    and local_prompt_hashes[0] != local_prompt_hashes[1]
                    and local_records[0].get("prompt_variant") == "primary_boundary"
                    and local_records[1].get("prompt_variant") == "adversarial_reject"
                )
                # Localization calls answer *where*, while the wider fine call
                # already answers *whether the regime persists*.  One sparse
                # localization cadence may stop last_support at the next card
                # change even though both views visibly identify the same
                # credit family. Once the wider fine chain is supported,
                # localization may remain purely positional: both independent
                # local views still have to report CONFIRMED same-family
                # transitions. Dense exact, micro and candidate-semantic gates
                # remain mandatory before FOUND, so this relaxation cannot
                # publish a transient/diegetic proposal by itself.
                local_support_chain = (
                    all(local_support)
                    or fine_effectively_supported
                )
                localization_floor = localization_pre - (
                    1 if localization_pass > 1 else 0
                )
                local_structural_gate = (
                    local_independent
                    and local_support_chain
                    and all(
                        item.verdict == WindowVerdict.TRANSITION.value
                        and item.continuity == Continuity.CONFIRMED.value
                        and item.reject == "NONE"
                        and _boundary_family(item.kind) == fine_family
                        for item in local_views
                    )
                    and all(position is not None for position in local_positions)
                    and localized_pre is not None
                    and localized_right is not None
                    and localization_floor <= localized_pre < localized_right
                    and localized_right <= localization_right
                )
                dense_span_ok = bool(
                    local_structural_gate
                    and localized_pre is not None
                    and localized_right is not None
                    and localized_right - localized_pre
                    <= self.protocol.rescue_compact_max_candidate_frames
                )
                pass_report = {
                    "ordinal": localization_pass,
                    "input_gap": [localization_pre, localization_right],
                    "first_positions": local_positions,
                    "pre_positions": local_pre_positions,
                    "union_gap": (
                        [localized_pre, localized_right]
                        if local_structural_gate else None
                    ),
                    "support_flags": local_support,
                    "support_chain_ok": bool(local_support_chain),
                    "fine_support_available": bool(fine_effectively_supported),
                    "coarse_support_hint_available": bool(hint_supported),
                    "left_context_tolerance_frames": (
                        localization_pre - localization_floor
                    ),
                    "left_context_disputed": bool(
                        localized_pre is not None
                        and localized_pre < localization_pre
                    ),
                    "independent_transport_views": bool(local_independent),
                    "structural_gate_passed": bool(local_structural_gate),
                    "dense_span_ok": dense_span_ok,
                }
                localization_passes.append(pass_report)
                if not local_structural_gate:
                    break
                if dense_span_ok:
                    local_gate = True
                    break
                if localization_pass == 1:
                    assert localized_pre is not None and localized_right is not None
                    localization_pre = localized_pre
                    localization_right = localized_right

            last_local = localization_passes[-1]
            report["localize"] = {
                **last_local,
                "passes": localization_passes,
                # Compatibility alias for existing diagnostic consumers.
                "intersection_gap": last_local.get("union_gap"),
                "gate_passed": bool(local_gate),
            }
            if not local_gate:
                report.update({
                    "status": "UNRESOLVED_LOCALIZE",
                    "reason": "sparse primary/adversarial localization views did not agree",
                })
                available = [int(value) for value in local_positions if value is not None]
                return ReviewRescueOutcome(
                    DetectionStatus.REVIEW.value,
                    "earliest focused credit candidate could not be localized safely",
                    call_index,
                    emitted,
                    records,
                    reports,
                    provisional_start=min(available) if available else int(fine.first_pos),
                    review_bracket=(
                        [int(localized_pre), int(localized_right)]
                        if localized_pre is not None and localized_right is not None
                        else [semantic_pre_pos, search_right]
                    ),
                    verification={"mode": "chronological_review_rescue", "candidates": reports},
                )

            localized = [int(value) for value in local_positions if value is not None]
            assert localized_pre is not None
            assert localized_right is not None
            blank_transition_anchor = _earliest_blank_to_visible_transition(
                refs_by_pos,
                left=localized_pre + 1,
                right=localized_right,
            )
            blank_anchor_eligible = bool(
                fine_family == "SUSTAINED_CREDITS"
                and blank_transition_anchor is not None
                and int(blank_transition_anchor) < min(localized)
                and min(localized) - int(blank_transition_anchor)
                <= int(math.ceil(8.0 * self.config.fps))
                and localized_right - localized_pre
                <= self.protocol.rescue_compact_max_candidate_frames
            )
            if blank_anchor_eligible:
                assert blank_transition_anchor is not None
                sustained_kinds = {
                    BoundaryKind.CREDIT_SEQUENCE.value,
                    BoundaryKind.END_CARD_THEN_CREDITS.value,
                }
                blank_micro = micro_adjudicate(
                    prefix=f"{prefix}_blank",
                    exact_views=local_views,
                    exact_records=local_records,
                    support_pos=support_pos,
                    allowed_kinds=sustained_kinds,
                    claim_positions=[
                        int(blank_transition_anchor),
                        int(blank_transition_anchor),
                    ],
                    force_two_views=True,
                    allow_family_match=True,
                    enforce_source_disagreement_cap=False,
                )
                apply_candidate_semantic_gate(
                    blank_micro,
                    prefix=f"{prefix}_blank",
                    allowed_kinds=sustained_kinds,
                )
                report["blank_transition_rescue"] = {
                    "anchor_pos": int(blank_transition_anchor),
                    "source_first_positions": local_positions,
                    "source_union_gap": [localized_pre, localized_right],
                    "micro": blank_micro,
                    "gate_passed": bool(blank_micro["gate_passed"]),
                }
                blank_verification = {
                    "mode": "chronological_review_rescue",
                    "candidates": reports,
                    "independent_transport_views": bool(local_independent),
                    "independent_calls": bool(local_independent),
                    "first_positions": local_positions,
                    "support_chain_ok": bool(all(local_support)),
                    "same_kind": bool(all(item.kind == fine.kind for item in local_views)),
                    "same_boundary_family": bool(all(
                        _boundary_family(item.kind) == fine_family
                        for item in local_views
                    )),
                    "blank_transition_anchor": int(blank_transition_anchor),
                    "blank_anchor_needs_rescue": True,
                    "localized_union_gap": [localized_pre, localized_right],
                    "micro_boundary": blank_micro,
                }
                if not blank_micro["gate_passed"]:
                    semantic_audit = (
                        blank_micro.get("candidate_semantic_audit") or {}
                    )
                    if semantic_audit.get("definitive_noncredit") is True:
                        rejected_position = blank_micro.get(
                            "pre_semantic_chosen_pos"
                        )
                        rejection_floor = remember_semantic_rejection(
                            rejected_position
                        )
                        report.update({
                            "status": "REJECTED_SEMANTIC_SENTINEL",
                            "reason": semantic_audit.get("reason"),
                            "rejected_candidate_pos": rejected_position,
                            "semantic_rejection_floor_after": rejection_floor,
                        })
                        continue
                    report.update({
                        "status": "UNRESOLVED_BLANK_TRANSITION",
                        "reason": (
                            "earliest physical blank-to-visible edge did not pass "
                            "two-view semantic credit proof"
                        ),
                    })
                    return ReviewRescueOutcome(
                        DetectionStatus.REVIEW.value,
                        "earliest blank-to-visible edge remains semantically unresolved",
                        call_index,
                        emitted,
                        records,
                        reports,
                        provisional_start=min(localized),
                        review_bracket=[int(blank_transition_anchor), localized_right],
                        verification=blank_verification,
                    )
                found = int(blank_micro["chosen_pos"])
                report.update({
                    "status": "FOUND",
                    "reason": (
                        "earliest blank-to-visible edge passed independent "
                        "primary/adversarial semantic micro proof"
                    ),
                    "start_pos": found,
                })
                blank_verification["boundary_refinement"] = {
                    "semantic_start_pos": found,
                    "visual_start_pos": found,
                    "backtrack_frames": min(localized) - found,
                    "method": "blank_transition_two_view_micro_vlm",
                }
                return ReviewRescueOutcome(
                    DetectionStatus.FOUND.value,
                    "earliest static/RTL credit edge passed two-view micro proof",
                    call_index,
                    emitted,
                    records,
                    reports,
                    start_pos=found,
                    onset_kind=fine.kind,
                    verification=blank_verification,
                )

            exact_views: list[WindowEvidence] = []
            exact_records: list[dict[str, Any]] = []
            exact_pre_pos = (
                semantic_rejection_floor
                if semantic_rejection_floor is not None
                and localized_pre <= semantic_rejection_floor
                else max(0, localized_pre - 1)
            )
            exact_search_right = localized_right
            compact_semantic_pre_pos = min(semantic_pre_pos, localized_pre)
            for variant in ("a", "b"):
                positions, search = build_rescue_compact_positions(
                    localized,
                    semantic_pre_pos=compact_semantic_pre_pos,
                    localized_pre_pos=localized_pre,
                    support_pos=support_pos,
                    variant=variant,
                    total_frames=total_frames,
                    fps=self.config.fps,
                    config=self.protocol,
                    candidate_floor_exclusive=(
                        semantic_rejection_floor
                        if semantic_rejection_floor is not None
                        and localized_pre <= semantic_rejection_floor
                        else None
                    ),
                )
                columns = 2 if variant == "b" else 3
                before_records = len(records)
                view = locate(
                    positions,
                    stage=f"{prefix}_verify_{variant}",
                    tile_width=min(
                        self.protocol.rescue_compact_tile_width,
                        bounded_verification_tile_width(
                            len(positions),
                            columns=columns,
                            config=self.protocol,
                        ),
                    ),
                    columns=columns,
                    boundary_search_cells=search,
                )
                exact_views.append(view)
                exact_records.append(records[before_records])

            exact_positions = [item.first_pos for item in exact_views]
            exact_support = [
                _is_supported(
                    item,
                    fps=self.config.fps,
                    min_support_seconds=self.protocol.min_support_seconds,
                    terminal_blank_tail_seconds=self.protocol.terminal_blank_tail_seconds,
                )
                for item in exact_views
            ]
            hashes = [record.get("input_sha256") for record in exact_records]
            prompt_hashes = [record.get("prompt_sha256") for record in exact_records]
            calls_independent = (
                exact_views[0].positions != exact_views[1].positions
                and exact_views[0].call_id != exact_views[1].call_id
                and all(hashes)
                and hashes[0] != hashes[1]
                and all(prompt_hashes)
                and prompt_hashes[0] != prompt_hashes[1]
                and exact_records[0].get("prompt_variant") == "primary_boundary"
                and exact_records[1].get("prompt_variant") == "adversarial_reject"
            )
            adjacent_pre = all(
                item.first_cell >= 1
                and item.positions[item.first_cell]
                - item.positions[item.first_cell - 1] == 1
                for item in exact_views
            )
            support_chain_ok = local_support_chain and any(exact_support)
            compatible_fine_kinds = {fine.kind}
            if fine_family == "SUSTAINED_CREDITS":
                compatible_fine_kinds.update({
                    BoundaryKind.CREDIT_SEQUENCE.value,
                    BoundaryKind.END_CARD_THEN_CREDITS.value,
                })
            exact_localization_gate = (
                calls_independent
                and support_chain_ok
                and all(
                    item.verdict == WindowVerdict.TRANSITION.value
                    and item.continuity in {
                        Continuity.CONFIRMED.value,
                        Continuity.UNVERIFIABLE.value,
                    }
                    and item.reject == "NONE"
                    and _boundary_family(item.kind) == fine_family
                    for item in exact_views
                )
                and any(
                    item.continuity == Continuity.CONFIRMED.value
                    for item in exact_views
                )
                and adjacent_pre
                and all(position is not None for position in exact_positions)
                and all(
                    exact_pre_pos < int(position) <= exact_search_right
                    for position in exact_positions
                    if position is not None
                )
            )
            # A source view with UNVERIFIABLE continuity is permitted only as a
            # localization witness.  It can never authorize FOUND: the branch
            # below forces two fresh, independently transported micro views,
            # both of which must return CONFIRMED continuity at tolerance zero.
            exact_family_gate = bool(
                exact_localization_gate
                and all(
                    item.continuity == Continuity.CONFIRMED.value
                    for item in exact_views
                )
            )
            blank_transition_anchor = (
                _earliest_blank_to_visible_transition(
                    refs_by_pos,
                    left=exact_pre_pos + 1,
                    right=exact_search_right,
                )
                if exact_localization_gate else None
            )
            blank_anchor_needs_rescue = bool(
                blank_transition_anchor is not None
                and all(position is not None for position in exact_positions)
                and int(blank_transition_anchor) < min(
                    int(position) for position in exact_positions
                    if position is not None
                )
            )
            dense_edge_probe: dict[str, Any] = {
                "gate_passed": False,
                "anchor_pos": None,
                "reason": "dense-gap edge audit was not eligible",
                "probes": [],
            }
            if (
                exact_localization_gate
                and all(position is not None for position in exact_positions)
                and len(localized) == 2
                and max(localized) - min(localized) >= 2
            ):
                earliest_exact = min(
                    int(position) for position in exact_positions
                    if position is not None
                )
                # Leave at least one later candidate cell between the raw
                # proposal and the exact consensus. One-frame misses are
                # already handled by the stricter predecessor audit.
                dense_edge_left = max(localized_pre + 1, min(localized))
                dense_edge_right = earliest_exact - 2
                dense_edge_probe = _earliest_dense_gap_edge_emergence(
                    refs_by_pos,
                    left=dense_edge_left,
                    right=dense_edge_right,
                )
            dense_edge_anchor = (
                int(dense_edge_probe["anchor_pos"])
                if dense_edge_probe.get("gate_passed")
                and dense_edge_probe.get("anchor_pos") is not None
                else None
            )
            exact_consensus_kind = (
                exact_views[0].kind
                if exact_views[0].kind == exact_views[1].kind
                else None
            )
            exact_kind_consensus = bool(
                exact_consensus_kind is not None
                and (
                    exact_consensus_kind == fine.kind
                    or (
                        fine_family == "SUSTAINED_CREDITS"
                        and _boundary_family(exact_consensus_kind) == fine_family
                    )
                )
            )
            exact_structural_gate = bool(exact_localization_gate)
            source_needs_two_view_audit = bool(
                not exact_family_gate or not exact_kind_consensus
            )
            micro_claim_positions: list[int] | None = None
            if blank_anchor_needs_rescue:
                assert blank_transition_anchor is not None
                micro_claim_positions = [
                    int(blank_transition_anchor),
                    int(blank_transition_anchor),
                ]
            elif dense_edge_anchor is not None:
                # A disagreement pair keeps anchor-1 as context-only; the raw
                # signal itself is the earliest answer the VLM may select.
                micro_claim_positions = [
                    int(dense_edge_anchor),
                    int(dense_edge_anchor) + 1,
                ]
            micro_uses_family = bool(
                micro_claim_positions is not None or source_needs_two_view_audit
            )
            micro_allowed_kinds = (
                compatible_fine_kinds
                if micro_uses_family else {str(exact_consensus_kind)}
            )
            micro = (
                micro_adjudicate(
                    prefix=(
                        f"{prefix}_dense_edge"
                        if dense_edge_anchor is not None else prefix
                    ),
                    exact_views=exact_views,
                    exact_records=exact_records,
                    support_pos=support_pos,
                    allowed_kinds=micro_allowed_kinds,
                    claim_positions=micro_claim_positions,
                    force_two_views=bool(
                        micro_claim_positions is not None
                        or source_needs_two_view_audit
                    ),
                    allow_family_match=micro_uses_family,
                )
                if exact_structural_gate else {
                    "gate_passed": False,
                    "chosen_pos": None,
                    "reason": "exact structural gates failed before micro audit",
                    "views": [],
                }
            )
            if (
                dense_edge_anchor is not None
                and micro.get("gate_passed")
                and micro.get("chosen_pos") != dense_edge_anchor
            ):
                micro.update({
                    "gate_passed": False,
                    "chosen_pos": None,
                    "reason": (
                        "dense-gap micro views did not confirm the earliest raw "
                        "edge proposal"
                    ),
                })
            resolve_adjacent_micro_disagreement(
                micro,
                prefix=(
                    f"{prefix}_dense_edge"
                    if dense_edge_anchor is not None else prefix
                ),
                allowed_kinds=micro_allowed_kinds,
            )
            apply_candidate_semantic_gate(
                micro,
                prefix=(
                    f"{prefix}_dense_edge"
                    if dense_edge_anchor is not None else prefix
                ),
                allowed_kinds=micro_allowed_kinds,
            )
            exact_gate = bool(exact_structural_gate and micro["gate_passed"])
            if (
                not exact_gate
                and exact_localization_gate
                and "candidate_semantic_audit" not in micro
                and (
                    dense_edge_anchor is not None
                    or fine.first_pos is not None
                )
                and 1 <= int(
                    dense_edge_anchor
                    if dense_edge_anchor is not None else fine.first_pos
                ) < total_frames - 1
            ):
                # When a dense raw edge exists, audit that earliest proposal,
                # not the later/easier fine cell. This lets a title card or
                # story-screen edge be disproved before a later true credit in
                # the same fine window can bias the contextual semantic view.
                semantic_candidate = int(
                    dense_edge_anchor
                    if dense_edge_anchor is not None else fine.first_pos
                )
                sinks: tuple[list[dict[str, Any]], ...] = (
                    (records, record_sink)
                    if record_sink is not None else (records,)
                )
                semantic_audit, call_index = self._audit_candidate_semantics(
                    candidate_pos=semantic_candidate,
                    allowed_kinds=compatible_fine_kinds,
                    prefix=f"{prefix}_exact_disagreement",
                    refs_by_pos=refs_by_pos,
                    total_frames=total_frames,
                    call_index=call_index,
                    out=out,
                    calls_path=calls_path,
                    deadline=deadline,
                    record_sinks=sinks,
                )
                micro["candidate_semantic_audit"] = semantic_audit
                micro["pre_semantic_chosen_pos"] = semantic_candidate
                if not semantic_audit.get("gate_passed"):
                    micro["reason"] = (
                        f"{micro.get('reason')}; candidate semantic audit: "
                        f"{semantic_audit.get('reason')}"
                    )
                if semantic_audit.get("definitive_noncredit") is True:
                    remember_semantic_rejection(semantic_candidate)
                    later_semantic_pos = int(
                        fine.first_pos
                        if fine.first_pos is not None else search_right
                    )
                    successor = refine_semantic_successor(
                        rejected_pos=semantic_candidate,
                        later_semantic_pos=later_semantic_pos,
                        search_right=search_right,
                        prefix=f"{prefix}_exact_disagreement",
                        exact_views=exact_views,
                        exact_records=exact_records,
                        support_pos=support_pos,
                        allowed_kinds=compatible_fine_kinds,
                    )
                    if successor.get("gate_passed") is True:
                        successor_micro = successor.pop("micro")
                        successor["initial_micro"] = micro
                        successor_micro[
                            "semantic_successor_refinement"
                        ] = successor
                        micro = successor_micro
                        exact_gate = bool(
                            exact_structural_gate
                            and micro.get("gate_passed")
                        )
                    else:
                        micro["semantic_successor_refinement"] = successor
                        if successor.get("blocked") is True:
                            semantic_audit["base_definitive_noncredit"] = (
                                semantic_audit.get("definitive_noncredit")
                            )
                            semantic_audit["definitive_noncredit"] = False
                            semantic_audit["reason"] = successor.get("reason")
            verification = {
                "mode": "chronological_review_rescue",
                "candidates": reports,
                "independent_transport_views": bool(calls_independent),
                "independent_calls": bool(calls_independent),
                "both_supported": bool(all(exact_support)),
                "exact_support_flags": exact_support,
                "both_exact_semantic": bool(all(
                    item.verdict == WindowVerdict.TRANSITION.value
                    and item.continuity == Continuity.CONFIRMED.value
                    and item.reject == "NONE"
                    for item in exact_views
                )),
                "support_chain_ok": bool(support_chain_ok),
                "adjacent_pre": bool(adjacent_pre),
                "first_positions": exact_positions,
                "tolerance_frames": self.protocol.verification_tolerance_frames,
                "agree": bool(
                    all(position is not None for position in exact_positions)
                    and abs(int(exact_positions[0]) - int(exact_positions[1]))
                    <= self.protocol.verification_tolerance_frames
                ),
                "inside_exact_search_gap": bool(all(
                    position is not None
                    and exact_pre_pos < int(position) <= exact_search_right
                    for position in exact_positions
                )),
                "exact_search_pre_pos": exact_pre_pos,
                "fine_semantic_pre_pos": semantic_pre_pos,
                "compact_semantic_pre_pos": compact_semantic_pre_pos,
                "fine_approximate_pos": int(fine.first_pos),
                "rescue_search_right_pos": search_right,
                "localized_search_right_pos": localized_right,
                "blank_transition_anchor": blank_transition_anchor,
                "blank_anchor_needs_rescue": blank_anchor_needs_rescue,
                "same_kind": bool(all(item.kind == fine.kind for item in exact_views)),
                "same_boundary_family": bool(all(
                    _boundary_family(item.kind) == fine_family for item in exact_views
                )),
                "terminal_ok": True,
                "input_sha256": hashes,
                "prompt_sha256": prompt_hashes,
                "exact_structural_gate": bool(exact_structural_gate),
                "exact_family_gate": bool(exact_family_gate),
                "exact_localization_gate": bool(exact_localization_gate),
                "exact_kind_consensus": exact_kind_consensus,
                "exact_consensus_kind": exact_consensus_kind,
                "source_needs_two_view_audit": source_needs_two_view_audit,
                "dense_edge_probe": dense_edge_probe,
                "dense_edge_anchor": dense_edge_anchor,
                "micro_boundary": micro,
            }
            report["exact"] = {
                "first_positions": exact_positions,
                "support_flags": exact_support,
                "independent_transport_views": bool(calls_independent),
                "gate_passed": bool(exact_gate),
            }
            semantic_audit = micro.get("candidate_semantic_audit") or {}
            if (
                not exact_gate
                and semantic_audit.get("definitive_noncredit") is True
            ):
                rejected_position = micro.get("pre_semantic_chosen_pos")
                rejection_floor = remember_semantic_rejection(
                    rejected_position
                )
                report.update({
                    "status": "REJECTED_SEMANTIC_SENTINEL",
                    "reason": semantic_audit.get("reason"),
                    "rejected_candidate_pos": rejected_position,
                    "semantic_rejection_floor_after": rejection_floor,
                })
                continue
            if not exact_gate:
                report.update({
                    "status": "UNRESOLVED_EXACT",
                    "reason": "compact primary/adversarial frame views did not agree",
                })
                available = [int(value) for value in exact_positions if value is not None]
                return ReviewRescueOutcome(
                    DetectionStatus.REVIEW.value,
                    "earliest focused credit candidate failed exact boundary agreement",
                    call_index,
                    emitted,
                    records,
                    reports,
                    provisional_start=min(available) if available else min(localized),
                    review_bracket=(
                        [min(available), max(available)]
                        if available else [min(localized), max(localized)]
                    ),
                    verification=verification,
                )

            found = int(micro["chosen_pos"])
            report.update({
                "status": "FOUND",
                "reason": "compact exact views passed micro boundary adjudication",
                "start_pos": found,
            })
            verification["boundary_refinement"] = {
                "semantic_start_pos": found,
                "visual_start_pos": found,
                "backtrack_frames": 0,
                "method": "chronological_sparse_compact_then_micro_vlm",
            }
            return ReviewRescueOutcome(
                DetectionStatus.FOUND.value,
                "earlier coarse false positives were rejected; exact and micro views agree",
                call_index,
                emitted,
                records,
                reports,
                start_pos=found,
                onset_kind=exact_views[0].kind,
                verification=verification,
            )

        return ReviewRescueOutcome(
            DetectionStatus.REVIEW.value,
            "focused review rescue rejected every coarse proposal as PRE_ONLY",
            call_index,
            emitted,
            records,
            reports,
            verification={"mode": "chronological_review_rescue", "candidates": reports},
        )

    def _safe_output(self, frame_dir: Path, out: Path) -> None:
        frames_root = frame_dir.parent
        if (
            out == frame_dir
            or frame_dir in out.parents
            or out == frames_root
            or frames_root in out.parents
            or out.name.lower() == "cikis_jenerik"
            or _inside_any_protected_frames_tree(out)
        ):
            raise ValueError(
                "output directory must be outside every protected frames tree; "
                f"refusing unsafe path: {out}"
            )
        if out != self.allowed_output_root and self.allowed_output_root not in out.parents:
            raise ValueError(
                "output directory must stay inside the experiment output root "
                f"{self.allowed_output_root}; refusing: {out}"
            )

    def run(self, frame_dir: Path, output_dir: Path | None = None) -> DetectionResult:
        started = time.perf_counter()
        deadline = started + self.config.max_wall_seconds
        frame_dir = frame_dir.resolve()
        if not frame_dir.is_dir():
            raise FileNotFoundError(f"frame directory does not exist: {frame_dir}")
        refs = build_frame_refs(frame_dir, self.config.fps)
        if not refs:
            raise ValueError(f"no supported images in: {frame_dir}")
        refs_by_pos = {ref.pos: ref for ref in refs}
        if output_dir is None:
            default_root = (
                self.repository_root / "outputs" / "closing_credit_onset_vlm"
            ).resolve()
            default_candidate = default_output_dir(
                frame_dir, root=self.repository_root
            ).resolve()
            if self.allowed_output_root == default_root:
                out = default_candidate
            else:
                out = (
                    self.allowed_output_root
                    / default_candidate.relative_to(default_root)
                ).resolve()
        else:
            out = output_dir.resolve()
        self._safe_output(frame_dir, out)
        out.mkdir(parents=True, exist_ok=False)
        calls_path = out / "calls.jsonl"
        signature_before = frame_source_signature(frame_dir, refs)
        all_evidence: list[WindowEvidence] = []
        call_records: list[dict[str, Any]] = []
        call_index = 0
        model_identity: dict[str, Any] = {"requested_name": self.config.model}
        cv_seconds = 0.0
        scores: list[FrameScore] = []
        proposals: list[int] = []
        coarse_panels: list[list[int]] = []
        coarse_outcome = CoarseOutcome(DetectionStatus.MODEL_ERROR.value, "not run")
        verification_meta: dict[str, Any] = {}
        status = DetectionStatus.MODEL_ERROR.value
        reason = "window detector did not finish"
        start_pos: int | None = None
        onset_kind: str | None = None
        provisional_start: int | None = None
        review_bracket: list[int] | None = None
        candidate_starts: list[int] = []

        try:
            identity_fn = getattr(self.locator, "model_identity", None)
            if callable(identity_fn):
                model_identity = identity_fn()
            capabilities = model_identity.get("capabilities") or []
            if capabilities and "vision" not in capabilities:
                raise ValueError(
                    f"model has no vision capability: {self.config.model} ({capabilities})"
                )

            cv_started = time.perf_counter()
            cv_config = CvDetectorConfig(max_width=self.config.cv_width, ocr_mode="none")
            cv_paths, scores, masks = self.score_provider(frame_dir, cv_config)
            del masks
            if [path.resolve() for path in cv_paths] != [ref.path.resolve() for ref in refs]:
                raise RuntimeError("CV scanner and canonical frame enumerator disagree")
            cv_seconds = time.perf_counter() - cv_started
            _write_features(out / "features.csv", scores)
            proposals = select_cv_proposals(
                scores,
                fps=self.config.fps,
                limit=self.config.max_cv_proposals,
                min_distance_seconds=self.config.proposal_min_distance_seconds,
            )
            coarse_panels = build_coarse_panels(
                len(refs),
                fps=self.config.fps,
                proposal_positions=proposals,
                config=self.protocol,
            )
            for positions in coarse_panels:
                call_index += 1
                evidence, record = self._locate(
                    positions,
                    refs_by_pos=refs_by_pos,
                    stage="coarse",
                    call_index=call_index,
                    out=out,
                    calls_path=calls_path,
                    deadline=deadline,
                    tile_width=self.protocol.coarse_tile_width,
                    columns=3,
                    at_stream_eof=positions[-1] == len(refs) - 1,
                )
                all_evidence.append(evidence)
                call_records.append(record)

            coarse_outcome = decode_coarse_windows(
                all_evidence,
                fps=self.config.fps,
                config=self.protocol,
            )
            status = coarse_outcome.status
            reason = coarse_outcome.reason
            provisional_start = coarse_outcome.provisional_start
            review_bracket = coarse_outcome.bracket
            candidate_starts = list(coarse_outcome.candidate_starts or [])

            if coarse_outcome.status == DetectionStatus.REVIEW.value:
                rescue_candidates = build_review_rescue_candidates(
                    all_evidence,
                    limit=self.protocol.review_rescue_max_candidates,
                    fps=self.config.fps,
                    config=self.protocol,
                )
                if rescue_candidates:
                    candidate_starts = sorted({
                        *candidate_starts,
                        *[item.provisional_start for item in rescue_candidates],
                    })
                    rescue = self._review_rescue_candidates(
                        rescue_candidates,
                        refs_by_pos=refs_by_pos,
                        total_frames=len(refs),
                        call_index=call_index,
                        out=out,
                        calls_path=calls_path,
                        deadline=deadline,
                        evidence_sink=all_evidence,
                        record_sink=call_records,
                    )
                    call_index = rescue.call_index
                    status = rescue.status
                    reason = rescue.reason
                    start_pos = rescue.start_pos
                    onset_kind = rescue.onset_kind
                    provisional_start = rescue.provisional_start
                    review_bracket = rescue.review_bracket
                    verification_meta = rescue.verification or {}
                    if start_pos is not None:
                        candidate_starts = [start_pos]
            if coarse_outcome.status == "REFINE" and coarse_outcome.bracket:
                if (
                    coarse_outcome.boundary_kind
                    == BoundaryKind.TERMINAL_END_CARD.value
                ):
                    fine_positions = build_terminal_fine_positions(
                        coarse_outcome.bracket,
                        total_frames=len(refs),
                        fps=self.config.fps,
                        config=self.protocol,
                    )
                else:
                    fine_positions = build_fine_gap_positions(
                        coarse_outcome.bracket,
                        total_frames=len(refs),
                        fps=self.config.fps,
                        config=self.protocol,
                    )
                call_index += 1
                fine, record = self._locate(
                    fine_positions,
                    refs_by_pos=refs_by_pos,
                    stage="fine_gap",
                    call_index=call_index,
                    out=out,
                    calls_path=calls_path,
                    deadline=deadline,
                    tile_width=self.protocol.fine_tile_width,
                    columns=3,
                    at_stream_eof=fine_positions[-1] == len(refs) - 1,
                )
                all_evidence.append(fine)
                call_records.append(record)

                fine_ok = _is_supported(
                    fine,
                    fps=self.config.fps,
                    min_support_seconds=self.protocol.min_support_seconds,
                    terminal_blank_tail_seconds=(
                        self.protocol.terminal_blank_tail_seconds
                    ),
                )
                fine_kind_matches = (
                    fine.kind == coarse_outcome.boundary_kind
                )
                if (
                    fine.verdict != WindowVerdict.TRANSITION.value
                    or not fine_ok
                    or not fine_kind_matches
                ):
                    status = DetectionStatus.REVIEW.value
                    reason = (
                        "fine gap did not return a supported TRANSITION: "
                        f"{fine.verdict}/{fine.continuity}/{fine.reject}/"
                        f"kind={fine.kind}, expected={coarse_outcome.boundary_kind}"
                    )
                    provisional_start = fine.first_pos or provisional_start
                    review_bracket = [fine.positions[0], fine.positions[-1]]
                else:
                    approximate = int(fine.first_pos)
                    semantic_pre_pos = fine.positions[fine.first_cell - 1]
                    # Fine cells are sparse.  A model can overlook a faint first
                    # credit in the sampled predecessor and call the next cell
                    # the transition (observed on the real 13. SAVASCI tail).
                    # Include one real frame left of that semantic predecessor,
                    # then constrain exact `first` to the dense gap ending at
                    # `approximate`.  Starting at the whole fine panel would
                    # needlessly create a huge exact mosaic.
                    exact_pre_pos = max(0, semantic_pre_pos - 1)
                    exact_evidence: list[WindowEvidence] = []
                    exact_records: list[dict[str, Any]] = []
                    exact_boundary_ranges: list[list[int]] = []
                    for shift, stage in ((0, "verify_a"), (-1, "verify_b")):
                        exact_positions = build_exact_verification_positions(
                            approximate,
                            shift=shift,
                            total_frames=len(refs),
                            fps=self.config.fps,
                            pre_pos=exact_pre_pos,
                            config=self.protocol,
                        )
                        if (
                            fine.kind == BoundaryKind.TERMINAL_END_CARD.value
                        ):
                            eof = len(refs) - 1
                            terminal_context = {eof}
                            for seconds in (
                                1.0,
                                3.0,
                                5.0,
                                8.0,
                                self.protocol.terminal_blank_tail_seconds,
                            ):
                                offset = int(math.floor(
                                    seconds * self.config.fps + 0.5
                                ))
                                terminal_context.add(max(0, eof - offset))
                            if fine.last_support_pos is not None:
                                terminal_context.update({
                                    max(0, int(fine.last_support_pos) - 1),
                                    int(fine.last_support_pos),
                                    min(eof, int(fine.last_support_pos) + 1),
                                })
                            exact_positions = sorted({
                                *exact_positions,
                                *terminal_context,
                            })
                        boundary_indexes = [
                            index for index, position in enumerate(exact_positions)
                            if exact_pre_pos < position <= approximate
                        ]
                        if (
                            not boundary_indexes
                            or boundary_indexes != list(range(
                                boundary_indexes[0], boundary_indexes[-1] + 1
                            ))
                            or boundary_indexes[0] < 1
                        ):
                            raise ValueError(
                                "exact boundary candidate cells are missing, "
                                "non-contiguous, or lack PRE/context"
                            )
                        boundary_search_cells = (
                            boundary_indexes[0], boundary_indexes[-1]
                        )
                        exact_boundary_ranges.append(list(boundary_search_cells))
                        exact_columns = 2 if stage == "verify_b" else 3
                        exact_tile_width = bounded_verification_tile_width(
                            len(exact_positions),
                            columns=exact_columns,
                            config=self.protocol,
                        )
                        call_index += 1
                        exact, exact_record = self._locate(
                            exact_positions,
                            refs_by_pos=refs_by_pos,
                            stage=stage,
                            call_index=call_index,
                            out=out,
                            calls_path=calls_path,
                            deadline=deadline,
                            tile_width=exact_tile_width,
                            columns=exact_columns,
                            at_stream_eof=exact_positions[-1] == len(refs) - 1,
                            boundary_search_cells=boundary_search_cells,
                        )
                        all_evidence.append(exact)
                        call_records.append(exact_record)
                        exact_evidence.append(exact)
                        exact_records.append(exact_record)

                    a, b = exact_evidence
                    positions_differ = a.positions != b.positions
                    hashes = [record.get("input_sha256") for record in exact_records]
                    prompt_hashes = [
                        record.get("prompt_sha256") for record in exact_records
                    ]
                    calls_independent = (
                        positions_differ
                        and a.call_id != b.call_id
                        and hashes[0]
                        and hashes[1]
                        and hashes[0] != hashes[1]
                        and prompt_hashes[0]
                        and prompt_hashes[1]
                        and prompt_hashes[0] != prompt_hashes[1]
                        and exact_records[0].get("prompt_variant") == "primary_boundary"
                        and exact_records[1].get("prompt_variant") == "adversarial_reject"
                    )
                    exact_support_flags = [
                        _is_supported(
                            item,
                            fps=self.config.fps,
                            min_support_seconds=self.protocol.min_support_seconds,
                            terminal_blank_tail_seconds=(
                                self.protocol.terminal_blank_tail_seconds
                            ),
                        )
                        for item in exact_evidence
                    ]
                    both_supported = all(exact_support_flags)
                    both_exact_semantic = all(
                        item.verdict == WindowVerdict.TRANSITION.value
                        and item.continuity == Continuity.CONFIRMED.value
                        and item.reject == "NONE"
                        for item in exact_evidence
                    )
                    adjacent_pre = all(
                        item.first_cell >= 1
                        and item.positions[item.first_cell]
                        - item.positions[item.first_cell - 1] == 1
                        for item in exact_evidence
                    )
                    exact_positions_found = [item.first_pos for item in exact_evidence]
                    inside_coarse_bracket = all(
                        position is not None
                        and coarse_outcome.bracket[0] < int(position) <= coarse_outcome.bracket[1]
                        for position in exact_positions_found
                    )
                    inside_exact_search_gap = all(
                        position is not None
                        and exact_pre_pos < int(position) <= approximate
                        for position in exact_positions_found
                    )
                    agree = (
                        all(position is not None for position in exact_positions_found)
                        and abs(int(exact_positions_found[0]) - int(exact_positions_found[1]))
                        <= self.protocol.verification_tolerance_frames
                    )
                    same_kind = (
                        a.kind == b.kind == fine.kind == coarse_outcome.boundary_kind
                    )
                    terminal_kind = a.kind == BoundaryKind.TERMINAL_END_CARD.value
                    # Exact A is the primary dense boundary view and can focus
                    # on the local candidate cells even after the prompt asks
                    # for a distant support anchor (observed on real Qwen v4/v5).
                    # Continuity is already supported by fine, coarse, and at
                    # least one exact transport view.  Do not require redundant
                    # 8s support from both same-model exact views.  The terminal
                    # end-card exception stays stricter because it relies on the
                    # two-card-cell and bounded-blank-tail proof in each view.
                    support_chain_ok = (
                        both_supported
                        if terminal_kind
                        else fine_ok and any(exact_support_flags)
                    )
                    terminal_blank_tails = [
                        round(
                            (len(refs) - 1 - int(item.last_support_pos))
                            / self.config.fps,
                            3,
                        )
                        if item.last_support_pos is not None else None
                        for item in exact_evidence
                    ]
                    terminal_ok = (
                        not terminal_kind
                        or (
                            a.at_stream_eof
                            and b.at_stream_eof
                            and a.last_support_cell > a.first_cell
                            and b.last_support_cell > b.first_cell
                            and all(
                                seconds is not None
                                and seconds
                                <= self.protocol.terminal_blank_tail_seconds
                                for seconds in terminal_blank_tails
                            )
                        )
                    )
                    exact_structural_gate = bool(
                        calls_independent
                        and both_exact_semantic
                        and support_chain_ok
                        and adjacent_pre
                        and inside_exact_search_gap
                        and same_kind
                        and terminal_ok
                    )

                    def locate_refine_micro(
                        positions: list[int],
                        *,
                        stage: str,
                        tile_width: int,
                        columns: int,
                        boundary_search_cells: tuple[int, int],
                        at_stream_eof: bool,
                    ) -> tuple[WindowEvidence, dict[str, Any]]:
                        nonlocal call_index
                        call_index += 1
                        view, call_record = self._locate(
                            positions,
                            refs_by_pos=refs_by_pos,
                            stage=stage,
                            call_index=call_index,
                            out=out,
                            calls_path=calls_path,
                            deadline=deadline,
                            tile_width=tile_width,
                            columns=columns,
                            at_stream_eof=at_stream_eof,
                            boundary_search_cells=boundary_search_cells,
                        )
                        all_evidence.append(view)
                        call_records.append(call_record)
                        return view, call_record

                    micro_support_positions = [
                        int(position) for position in [
                            fine.last_support_pos,
                            *[item.last_support_pos for item in exact_evidence],
                        ]
                        if position is not None
                    ]
                    micro = (
                        self._adjudicate_micro_boundary(
                            prefix="refine",
                            source_views=exact_evidence,
                            source_records=exact_records,
                            support_pos=max(micro_support_positions),
                            allowed_kinds={a.kind},
                            refs_by_pos=refs_by_pos,
                            total_frames=len(refs),
                            deadline=deadline,
                            locate_micro=locate_refine_micro,
                            at_stream_eof=terminal_kind,
                        )
                        if exact_structural_gate else {
                            "gate_passed": False,
                            "chosen_pos": None,
                            "reason": "exact structural gates failed before micro audit",
                            "views": [],
                        }
                    )
                    if (
                        micro.get("gate_passed")
                        and micro.get("chosen_pos") is not None
                    ):
                        semantic_candidate = int(micro["chosen_pos"])
                        semantic_audit, call_index = (
                            self._audit_candidate_semantics(
                                candidate_pos=semantic_candidate,
                                allowed_kinds={a.kind},
                                prefix="refine",
                                refs_by_pos=refs_by_pos,
                                total_frames=len(refs),
                                call_index=call_index,
                                out=out,
                                calls_path=calls_path,
                                deadline=deadline,
                                record_sinks=(call_records,),
                            )
                        )
                        micro["candidate_semantic_audit"] = semantic_audit
                        micro["pre_semantic_chosen_pos"] = semantic_candidate
                        if not semantic_audit.get("gate_passed"):
                            micro.update({
                                "gate_passed": False,
                                "chosen_pos": None,
                                "reason": (
                                    "micro boundary was rejected by the dedicated "
                                    "candidate semantic audit: "
                                    f"{semantic_audit.get('reason')}"
                                ),
                            })
                    verification_meta = {
                        "independent_transport_views": bool(calls_independent),
                        # Backward-readable alias. This is transport/context
                        # independence, not independent-model probability.
                        "independent_calls": bool(calls_independent),
                        "both_supported": both_supported,
                        "exact_support_flags": exact_support_flags,
                        "both_exact_semantic": both_exact_semantic,
                        "support_chain_ok": support_chain_ok,
                        "adjacent_pre": adjacent_pre,
                        "first_positions": exact_positions_found,
                        "tolerance_frames": self.protocol.verification_tolerance_frames,
                        "agree": bool(agree),
                        "inside_coarse_bracket": inside_coarse_bracket,
                        "inside_exact_search_gap": inside_exact_search_gap,
                        "exact_search_pre_pos": exact_pre_pos,
                        "fine_semantic_pre_pos": semantic_pre_pos,
                        "fine_approximate_pos": approximate,
                        "boundary_search_cells": exact_boundary_ranges,
                        "same_kind": same_kind,
                        "terminal_ok": terminal_ok,
                        "terminal_blank_tail_seconds": terminal_blank_tails,
                        "input_sha256": hashes,
                        "prompt_sha256": prompt_hashes,
                        "exact_structural_gate": exact_structural_gate,
                        "micro_boundary": micro,
                    }
                    if not (
                        exact_structural_gate
                        and micro["gate_passed"]
                    ):
                        status = DetectionStatus.REVIEW.value
                        reason = (
                            "shifted primary/adversarial exact views did not pass "
                            "all boundary gates"
                        )
                        available = [int(pos) for pos in exact_positions_found if pos is not None]
                        provisional_start = min(available) if available else approximate
                        review_bracket = (
                            [min(available), max(available)] if available
                            else [fine.positions[0], fine.positions[-1]]
                        )
                    else:
                        localized = int(micro["chosen_pos"])
                        verification_meta["boundary_refinement"] = {
                            "semantic_start_pos": localized,
                            "visual_start_pos": localized,
                            "backtrack_frames": 0,
                            "method": "exact_then_micro_vlm",
                        }
                        status = DetectionStatus.FOUND.value
                        start_pos = localized
                        onset_kind = a.kind
                        provisional_start = None
                        review_bracket = None
                        candidate_starts = [localized]
                        reason = (
                            "exact structural gates and micro boundary audit agree; "
                            "future support confirmed"
                        )
        except VlmCallError as exc:
            status = DetectionStatus.MODEL_ERROR.value
            reason = f"VLM window evidence missing: {exc}"
            if exc.record and not any(
                row.get("call_id") == exc.record.get("call_id") for row in call_records
            ):
                call_records.append(exc.record)
        except Exception as exc:  # noqa: BLE001
            status = DetectionStatus.MODEL_ERROR.value
            reason = f"{type(exc).__name__}: {exc}"

        refs_after = build_frame_refs(frame_dir, self.config.fps)
        signature_after = frame_source_signature(frame_dir, refs_after)
        source_drift = signature_before["sig_sha256"] != signature_after["sig_sha256"]
        if source_drift:
            status = DetectionStatus.REVIEW.value
            provisional_start = start_pos or provisional_start
            start_pos = None
            reason = "source frame set changed while detector was running"

        _atomic_write_json(
            out / "window_evidence.json",
            [item.to_dict() for item in all_evidence],
        )
        _write_window_timeline(out / "window_timeline.csv", all_evidence)
        finalization_reserve = min(0.5, self.config.max_wall_seconds * 0.05)
        remaining_for_publication = deadline - time.perf_counter()
        final_gate_triggered = (
            status == DetectionStatus.FOUND.value
            and remaining_for_publication < finalization_reserve
        )
        if final_gate_triggered:
            final_gate_record = {
                "call_id": "final-wall-time-gate",
                "stage": "finalize",
                "frame_positions": [],
                "frame_files": [],
                "ok": False,
                "detector_validation_ok": False,
                "error_kind": "wall_time_budget_final_gate",
                "error": (
                    "detector reached FOUND evidence without enough reserved "
                    "time for atomic result/manifest publication"
                ),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "remaining_seconds": round(remaining_for_publication, 3),
                "publication_reserve_seconds": finalization_reserve,
                "max_wall_seconds": self.config.max_wall_seconds,
            }
            _append_jsonl(calls_path, final_gate_record)
            call_records.append(final_gate_record)
            provisional_start = start_pos or provisional_start
            start_pos = None
            onset_kind = None
            status = DetectionStatus.MODEL_ERROR.value
            reason = "film wall-time budget exhausted before final decision publication"
        decision_finished = time.perf_counter()
        start_ref = refs_by_pos.get(start_pos) if start_pos is not None else None
        if status != DetectionStatus.FOUND.value:
            agreement_score = 0.0
        elif (
            verification_meta.get("first_positions")
            and len(set(verification_meta["first_positions"])) == 1
        ):
            agreement_score = 1.0
        else:
            agreement_score = 0.9
        artifacts = {
            "result": str(out / "result.json"),
            "manifest": str(out / "run_manifest.json"),
            "calls": str(calls_path),
            "features": str(out / "features.csv"),
            "window_evidence": str(out / "window_evidence.json"),
            "window_timeline": str(out / "window_timeline.csv"),
            "panels": str(out / "panels"),
        }
        result = DetectionResult(
            schema_version=WINDOW_SCHEMA_VERSION,
            status=status,
            frame_dir=str(frame_dir),
            output_dir=str(out),
            total_frames=len(refs),
            fps=self.config.fps,
            start_pos=start_pos,
            start_frame_no=(start_ref.frame_no if start_ref else None),
            start_file=(start_ref.path.name if start_ref else None),
            start_time_seconds=(start_ref.timestamp_seconds if start_ref else None),
            onset_kind=onset_kind,
            confidence=agreement_score,
            publishable=False,
            pool_may_be_replaced=False,
            needs_more_context=status == DetectionStatus.LEFT_CENSORED.value,
            provisional_start=provisional_start,
            review_bracket=review_bracket,
            candidate_starts=candidate_starts,
            reason=reason,
            source_signature=signature_after,
            config={
                **self.config.to_dict(),
                "semantic_protocol": WINDOW_PROTOCOL,
                "window_protocol": self.protocol.to_dict(),
            },
            metrics={
                "model_identity": model_identity,
                "cv_seconds": round(cv_seconds, 3),
                "cv_proposal_count": len(proposals),
                "coarse_panel_count": len(coarse_panels),
                "vlm_call_count": len(call_records),
                "verification": verification_meta,
                "source_drift": source_drift,
                "max_wall_seconds": self.config.max_wall_seconds,
                "wall_budget_exhausted": bool(
                    final_gate_triggered or decision_finished >= deadline
                ),
                "total_wall_seconds": round(decision_finished - started, 3),
                "confidence_meaning": (
                    "exact-boundary view agreement; not VLM probability or an "
                    "independent-model score"
                ),
            },
            artifacts=artifacts,
        )
        _atomic_write_json(out / "result.json", result.to_dict())
        _atomic_write_json(out / "run_manifest.json", {
            "schema_version": WINDOW_SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "semantic_protocol": WINDOW_PROTOCOL,
            "pool_may_be_replaced": False,
            "frame_source_before": signature_before,
            "frame_source_after": signature_after,
            "model": model_identity,
            "config": result.config,
            "cv_proposals": proposals,
            "coarse_panels": coarse_panels,
            "coarse_outcome": {
                "status": coarse_outcome.status,
                "reason": coarse_outcome.reason,
                "bracket": coarse_outcome.bracket,
                "candidate_starts": coarse_outcome.candidate_starts,
                "boundary_kind": coarse_outcome.boundary_kind,
            },
            "window_evidence": [item.to_dict() for item in all_evidence],
            "verification": verification_meta,
            "decision": result.to_dict(),
            "result_path": str(out / "result.json"),
        })
        return result


__all__ = [
    "WindowClosingCreditOnsetDetector",
    "WindowProtocolConfig",
    "build_coarse_panels",
    "build_exact_verification_positions",
    "bounded_verification_tile_width",
    "build_fine_gap_positions",
    "build_terminal_fine_positions",
    "decode_coarse_windows",
]
