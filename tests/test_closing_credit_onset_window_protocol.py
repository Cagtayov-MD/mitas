from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import time
from types import SimpleNamespace
from typing import Any

from PIL import Image
import pytest

import experiments.closing_credit_onset_vlm.window_detector as window_module
from experiments.closing_credit_onset_vlm.cli import build_parser
from experiments.closing_credit_onset_vlm.models import (
    BoundaryKind,
    Continuity,
    DetectionConfig,
    FrameRef,
    WindowEvidence,
    WindowVerdict,
)
from experiments.closing_credit_onset_vlm.ollama_client import (
    OllamaFrameClassifier,
    VlmCallError,
    VlmCandidateAuditResult,
    _candidate_audit_prompt,
    _candidate_audit_schema,
    _prompt,
    _schema,
)
from experiments.closing_credit_onset_vlm.window_detector import (
    ReviewRescueCandidate,
    WindowClosingCreditOnsetDetector,
    WindowProtocolConfig,
    adjudicate_adjacent_partial_candidate,
    adjudicate_candidate_screen_disproof,
    adjudicate_candidate_semantic_audits,
    adjudicate_later_supported_partial_candidate,
    build_coarse_panels,
    build_exact_verification_positions,
    build_fine_gap_positions,
    build_micro_boundary_positions,
    build_rescue_compact_positions,
    build_rescue_localization_positions,
    build_review_rescue_candidates,
    build_terminal_fine_positions,
    bounded_verification_tile_width,
    decode_coarse_windows,
)


@dataclass
class _FakeScore:
    pos: int
    frame_no: int = 0
    text_score: float = 0.0
    line_count: int = 0
    vertical_coverage: float = 0.0
    text_dy: float = 0.0
    bottom_only: bool = False
    mask_density: float = 0.0
    component_count: int = 0
    dark_ratio: float = 0.0
    luma_mean: float = 100.0

    def __init__(self, pos: int) -> None:
        self.pos = pos
        self.frame_no = pos + 1


def _make_frames(directory: Path, count: int) -> list[Path]:
    directory.mkdir(parents=True)
    paths: list[Path] = []
    for index in range(count):
        path = directory / f"c_{index + 1:04d}.png"
        Image.new("RGB", (32, 20), (index % 255, 20, 40)).save(path)
        paths.append(path)
    return paths


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _patch_fast_cv(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_score_frames(frame_dir: Path, _config: object):
        paths = window_module.build_frame_refs(Path(frame_dir), 1.0)
        return (
            [ref.path for ref in paths],
            [_FakeScore(index) for index in range(len(paths))],
            [],
        )

    monkeypatch.setattr(window_module, "score_frames", fake_score_frames)


def _config(*, fps: float = 1.0) -> DetectionConfig:
    return DetectionConfig(
        fps=fps,
        model="unit-test/window-vlm",
        image_width=128,
        mosaic_columns=3,
        batch_size=9,
        fine_overlap=4,
        max_cv_proposals=0,
        max_wall_seconds=30.0,
        num_ctx=1024,
        num_predict=64,
        retry_count=1,
    )


def _evidence(
    positions: list[int],
    verdict: WindowVerdict,
    *,
    first_cell: int = -1,
    kind: BoundaryKind = BoundaryKind.NONE,
    continuity: Continuity = Continuity.NONE,
    reject: str = "NONE",
    stage: str = "coarse",
) -> WindowEvidence:
    last_support = len(positions) - 1 if first_cell >= 0 else -1
    return WindowEvidence(
        stage=stage,
        positions=positions,
        files=[f"c_{position + 1:04d}.png" for position in positions],
        verdict=verdict.value,
        first_cell=first_cell,
        last_support_cell=last_support,
        first_pos=(positions[first_cell] if first_cell >= 0 else None),
        last_support_pos=(positions[last_support] if last_support >= 0 else None),
        kind=kind.value,
        continuity=continuity.value,
        reject=reject,
        call_id=f"{stage}-fake",
    )


class _FakeWindowLocator:
    def __init__(
        self,
        onset: int,
        *,
        kind: BoundaryKind = BoundaryKind.CREDIT_SEQUENCE,
        kind_by_stage: dict[str, BoundaryKind] | None = None,
        fail_stages: set[str] | None = None,
        ambiguous_stages: set[str] | None = None,
        verify_b_shift: int = 0,
        support_end: int | None = None,
        support_end_by_stage: dict[str, int] | None = None,
        onset_by_stage: dict[str, int] | None = None,
        continuity_by_stage: dict[str, Continuity] | None = None,
        reject_by_stage: dict[str, str] | None = None,
        reject_stages: set[str] | None = None,
        reuse_verification_call_id: bool = False,
        evidence_id_mismatch_stages: set[str] | None = None,
        evidence_position_mismatch_stages: set[str] | None = None,
        record_position_mismatch_stages: set[str] | None = None,
        corrupt_capture_hash_stages: set[str] | None = None,
        missing_prompt_stages: set[str] | None = None,
        equal_verification_images: bool = False,
        mutate_path: Path | None = None,
    ) -> None:
        self.onset = onset
        self.kind = kind
        self.kind_by_stage = kind_by_stage or {}
        self.fail_stages = fail_stages or set()
        self.ambiguous_stages = ambiguous_stages or set()
        self.verify_b_shift = verify_b_shift
        self.support_end = support_end
        self.support_end_by_stage = support_end_by_stage or {}
        self.onset_by_stage = onset_by_stage or {}
        self.continuity_by_stage = continuity_by_stage or {}
        self.reject_by_stage = reject_by_stage or {}
        self.reject_stages = reject_stages or set()
        self.reuse_verification_call_id = reuse_verification_call_id
        self.evidence_id_mismatch_stages = evidence_id_mismatch_stages or set()
        self.evidence_position_mismatch_stages = (
            evidence_position_mismatch_stages or set()
        )
        self.record_position_mismatch_stages = record_position_mismatch_stages or set()
        self.corrupt_capture_hash_stages = corrupt_capture_hash_stages or set()
        self.missing_prompt_stages = missing_prompt_stages or set()
        self.equal_verification_images = equal_verification_images
        self.mutate_path = mutate_path
        self.calls: list[tuple[str, list[int]]] = []

    def model_identity(self) -> dict[str, Any]:
        return {
            "requested_name": "unit-test/window-vlm",
            "architecture": "fake-window",
            "capabilities": ["vision"],
        }

    def locate_window(
        self,
        refs: list[FrameRef],
        *,
        stage: str,
        time_budget_seconds: float | None = None,
        at_stream_eof: bool = False,
        capture_path: Path | None = None,
        tile_width: int | None = None,
        jpeg_quality: int | None = None,
        mosaic_columns: int | None = None,
        boundary_search_cells: tuple[int, int] | None = None,
    ) -> SimpleNamespace:
        del time_budget_seconds, tile_width, jpeg_quality
        assert mosaic_columns == (2 if stage == "verify_b" or stage.endswith("_b") else 3)
        positions = [ref.pos for ref in refs]
        self.calls.append((stage, positions))
        call_id = f"fake-{stage}-{len(self.calls):02d}"
        if self.reuse_verification_call_id and stage in {"verify_a", "verify_b"}:
            call_id = "fake-shared-verification-call"
        if stage in self.fail_stages or "*" in self.fail_stages:
            raise VlmCallError(
                "injected missing window",
                record={
                    "call_id": call_id,
                    "stage": stage,
                    "frame_positions": positions,
                    "ok": False,
                    "error": "injected missing window",
                },
            )

        payload = (
            b"same-exact-mosaic"
            if self.equal_verification_images
            and stage in {"verify_a", "verify_b"}
            else f"mosaic:{stage}:{positions}".encode("utf-8")
        )
        if capture_path is not None:
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            capture_path.write_bytes(payload)
        record = {
            "call_id": call_id,
            "stage": stage,
            "frame_positions": positions,
            "frame_files": [ref.path.name for ref in refs],
            "ok": True,
            "at_stream_eof": at_stream_eof,
            "boundary_search_cells": (
                list(boundary_search_cells)
                if boundary_search_cells is not None else None
            ),
            "input_mosaic_path": str(capture_path.resolve()) if capture_path else None,
            "input_sha256": hashlib.sha256(payload).hexdigest(),
            "prompt_protocol": "window_boundary_v1",
            "prompt_variant": (
                "adversarial_reject"
                if stage == "verify_b" or stage.endswith("_b")
                else "primary_boundary"
            ),
            "prompt_sha256": hashlib.sha256(
                f"fake-prompt:{stage}:{positions}".encode("utf-8")
            ).hexdigest(),
        }
        if stage in self.record_position_mismatch_stages:
            record["frame_positions"] = [*positions[:-1], positions[-1] + 1]
        if stage in self.corrupt_capture_hash_stages:
            record["input_sha256"] = "0" * 64
        if stage in self.missing_prompt_stages:
            record.pop("prompt_sha256")

        if stage in self.ambiguous_stages:
            evidence = _evidence(
                positions,
                WindowVerdict.AMBIGUOUS,
                continuity=Continuity.UNVERIFIABLE,
                stage=stage,
            )
        else:
            target = self.onset_by_stage.get(stage, self.onset)
            target += self.verify_b_shift if stage == "verify_b" else 0
            stage_kind = self.kind_by_stage.get(stage, self.kind)
            stage_support_end = self.support_end_by_stage.get(stage, self.support_end)
            active_cells = [
                index for index, position in enumerate(positions)
                if position >= target
                and (stage_support_end is None or position <= stage_support_end)
            ]
            if not active_cells:
                evidence = _evidence(positions, WindowVerdict.PRE_ONLY, stage=stage)
            elif active_cells[0] == 0:
                evidence = _evidence(
                    positions,
                    WindowVerdict.ACTIVE_FROM_LEFT,
                    first_cell=0,
                    kind=stage_kind,
                    continuity=Continuity.CONFIRMED,
                    stage=stage,
                )
            else:
                first_cell = active_cells[0]
                evidence = _evidence(
                    positions,
                    WindowVerdict.TRANSITION,
                    first_cell=first_cell,
                    kind=stage_kind,
                    continuity=Continuity.CONFIRMED,
                    stage=stage,
                )
            if active_cells:
                evidence.last_support_cell = active_cells[-1]
                evidence.last_support_pos = positions[active_cells[-1]]
        if stage in self.continuity_by_stage:
            evidence.continuity = self.continuity_by_stage[stage].value
        if stage in self.reject_by_stage:
            evidence.reject = self.reject_by_stage[stage]
        if stage in self.reject_stages:
            evidence.reject = "DIEGETIC"
        evidence.at_stream_eof = at_stream_eof
        evidence.call_id = call_id
        evidence.metadata["boundary_search_cells"] = (
            list(boundary_search_cells)
            if boundary_search_cells is not None else None
        )
        if stage in self.evidence_id_mismatch_stages:
            evidence.call_id = f"mismatched-{call_id}"
        if stage in self.evidence_position_mismatch_stages:
            evidence.first_pos = positions[evidence.first_cell] + 1
        if stage == "verify_b" and self.mutate_path is not None:
            self.mutate_path.write_bytes(self.mutate_path.read_bytes() + b"drift")
        return SimpleNamespace(evidence=evidence, call_record=record)


def test_coarse_panels_share_core_seams_and_densely_cover_true_eof() -> None:
    panels = build_coarse_panels(
        900,
        fps=1.5,
        proposal_positions=[77, 78, 257, 888],
    )

    assert len(panels) == 5
    assert all(9 <= len(panel) <= 24 for panel in panels)
    assert panels[0][0] == 0
    assert panels[-1][-1] == 899
    assert all(right[0] in left for left, right in zip(panels, panels[1:]))
    assert {77, 78}.issubset(set(panels[0]))
    dense_tail = [position for position in panels[-1] if position >= 876]
    assert len(dense_tail) >= 16
    assert max(right - left for left, right in zip(dense_tail, dense_tail[1:])) <= 2


def test_cli_default_keeps_full_24_cell_terminal_tail_capacity() -> None:
    args = build_parser().parse_args(["--frames", "X:/fake/frames/cikis"])

    assert args.coarse_max_cells == 24


def test_strict_bracket_uses_transition_predecessor_and_never_active_cell_zero() -> None:
    first = list(range(0, 81, 10))
    second = list(range(80, 161, 10))
    transition = decode_coarse_windows([
        _evidence(first, WindowVerdict.PRE_ONLY),
        _evidence(
            second,
            WindowVerdict.TRANSITION,
            first_cell=3,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
    ], fps=1.0)
    active_left = decode_coarse_windows([
        _evidence(
            first,
            WindowVerdict.ACTIVE_FROM_LEFT,
            first_cell=0,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        )
    ], fps=1.0)

    assert transition.bracket == [100, 110]
    assert active_left.bracket is None
    assert active_left.status == "LEFT_CENSORED"


def test_pre_then_active_shared_anchor_forms_bounded_candidate_not_fake_onset() -> None:
    first = list(range(0, 81, 10))
    second = list(range(80, 161, 10))
    plan = decode_coarse_windows([
        _evidence(first, WindowVerdict.PRE_ONLY),
        _evidence(
            second,
            WindowVerdict.ACTIVE_FROM_LEFT,
            first_cell=0,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
    ], fps=1.0)

    assert plan.bracket == [70, 90]
    assert plan.provisional_start == second[0]


@pytest.mark.parametrize(
    ("previous", "expected_status"),
    [
        (
            _evidence(
                list(range(0, 81, 10)),
                WindowVerdict.TRANSITION,
                first_cell=8,
                kind=BoundaryKind.CREDIT_SEQUENCE,
                continuity=Continuity.UNVERIFIABLE,
            ),
            "REFINE",
        ),
        (
            _evidence(
                list(range(0, 81, 10)),
                WindowVerdict.AMBIGUOUS,
                continuity=Continuity.UNVERIFIABLE,
            ),
            "REVIEW",
        ),
    ],
)
def test_late_unresolved_shared_seam_then_active_is_fail_closed_when_ambiguous(
    previous: WindowEvidence,
    expected_status: str,
) -> None:
    active = _evidence(
        list(range(80, 161, 10)),
        WindowVerdict.ACTIVE_FROM_LEFT,
        first_cell=0,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.CONFIRMED,
    )

    outcome = decode_coarse_windows([previous, active], fps=1.0)

    assert outcome.status == expected_status
    if expected_status == "REFINE":
        assert outcome.bracket == [70, 90]


def test_diegetic_reject_cannot_use_the_shared_seam_exception() -> None:
    first = list(range(0, 81, 10))
    rejected = _evidence(
        first,
        WindowVerdict.TRANSITION,
        first_cell=8,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.UNVERIFIABLE,
        reject="DIEGETIC",
    )
    active = _evidence(
        list(range(80, 161, 10)),
        WindowVerdict.ACTIVE_FROM_LEFT,
        first_cell=0,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.CONFIRMED,
    )

    outcome = decode_coarse_windows([rejected, active], fps=1.0)

    assert outcome.status == "REVIEW"


@pytest.mark.parametrize(
    "reject",
    ["NO_VISIBLE_ATTRIBUTION", "DIEGETIC", "STORY_TEXT", "MIXED"],
)
def test_rejected_positive_before_real_transition_forces_chronological_rescue(
    reject: str,
) -> None:
    rejected_footage = _evidence(
        list(range(0, 81, 10)),
        WindowVerdict.TRANSITION,
        first_cell=8,
        kind=BoundaryKind.TERMINAL_END_CARD,
        continuity=Continuity.UNVERIFIABLE,
        reject=reject,
    )
    intervening_pre = _evidence(
        list(range(80, 161, 10)),
        WindowVerdict.PRE_ONLY,
    )
    transition = _evidence(
        list(range(160, 241, 10)),
        WindowVerdict.TRANSITION,
        first_cell=3,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.CONFIRMED,
    )

    outcome = decode_coarse_windows(
        [rejected_footage, intervening_pre, transition],
        fps=1.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.reason == (
        "earlier rejected positive evidence requires chronological rescue"
    )
    assert outcome.candidate_starts == [80, 190]


def test_review_rescue_candidates_keep_rejected_rows_as_untrusted_hints() -> None:
    first = _evidence(
        list(range(0, 81, 10)),
        WindowVerdict.TRANSITION,
        first_cell=8,
        kind=BoundaryKind.END_CARD_THEN_CREDITS,
        continuity=Continuity.UNVERIFIABLE,
    )
    second = _evidence(
        list(range(80, 161, 10)),
        WindowVerdict.TRANSITION,
        first_cell=6,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.UNVERIFIABLE,
        reject="DIEGETIC",
    )
    active = _evidence(
        list(range(160, 241, 10)),
        WindowVerdict.ACTIVE_FROM_LEFT,
        first_cell=0,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.CONFIRMED,
    )

    candidates = build_review_rescue_candidates(
        [active, second, first],
        limit=4,
    )

    assert [item.bracket for item in candidates] == [
        (70, 80),
        (130, 140),
        (150, 170),
    ]
    assert candidates[1].source_reject == "DIEGETIC"


def test_review_rescue_candidate_preserves_earlier_unresolved_chronology() -> None:
    ambiguous = _evidence(
        list(range(0, 81, 10)),
        WindowVerdict.AMBIGUOUS,
        continuity=Continuity.UNVERIFIABLE,
    )
    transition = _evidence(
        list(range(80, 161, 10)),
        WindowVerdict.TRANSITION,
        first_cell=7,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.CONFIRMED,
    )

    candidates = build_review_rescue_candidates(
        [ambiguous, transition],
        limit=5,
        fps=1.0,
    )

    assert len(candidates) == 1
    assert candidates[0].requires_chronology_guard is True
    assert tuple(range(0, 81, 10)) in candidates[0].chronology_groups


def test_ambiguous_semantic_reject_is_negative_only_without_positive_fields() -> None:
    semantic_negative = _evidence(
        [10, 20, 30],
        WindowVerdict.AMBIGUOUS,
        continuity=Continuity.UNVERIFIABLE,
        reject="DIEGETIC",
        stage="fine",
    )
    unresolved = _evidence(
        [10, 20, 30],
        WindowVerdict.AMBIGUOUS,
        continuity=Continuity.UNVERIFIABLE,
        stage="fine",
    )

    assert window_module._is_semantic_noncredit(semantic_negative) is True
    assert window_module._is_semantic_noncredit(unresolved) is False


def test_review_rescue_panels_are_sparse_then_compact_and_keep_pre_context() -> None:
    cfg = WindowProtocolConfig()
    local_a, search_a = build_rescue_localization_positions(
        532,
        540,
        support_pos=563,
        variant="a",
        total_frames=900,
        fps=1.5,
        config=cfg,
    )
    local_b, search_b = build_rescue_localization_positions(
        532,
        540,
        support_pos=563,
        variant="b",
        total_frames=900,
        fps=1.5,
        config=cfg,
    )
    compact_a, compact_search_a = build_rescue_compact_positions(
        [540, 540],
        semantic_pre_pos=532,
        support_pos=563,
        variant="a",
        total_frames=900,
        fps=1.5,
        config=cfg,
    )
    compact_b, compact_search_b = build_rescue_compact_positions(
        [540, 540],
        semantic_pre_pos=532,
        support_pos=563,
        variant="b",
        total_frames=900,
        fps=1.5,
        config=cfg,
    )

    assert local_a != local_b
    assert local_a[search_a[0] - 1] < local_a[search_a[0]]
    assert local_b[search_b[0] - 1] < local_b[search_b[0]]
    assert compact_a == [538, 539, 540, 541, 563]
    assert compact_b == [537, 538, 539, 540, 541, 563]
    assert compact_a[compact_search_a[0]] == 539
    assert compact_b[compact_search_b[0]] == 538


def test_rescue_localization_keeps_semantic_rejection_floor_as_pre_only() -> None:
    positions_a, search_a = build_rescue_localization_positions(
        731,
        765,
        support_pos=790,
        variant="a",
        total_frames=900,
        fps=1.5,
        candidate_floor_exclusive=731,
    )
    positions_b, search_b = build_rescue_localization_positions(
        731,
        765,
        support_pos=790,
        variant="b",
        total_frames=900,
        fps=1.5,
        candidate_floor_exclusive=731,
    )

    assert positions_a[search_a[0] - 1] == 731
    assert positions_a[search_a[0]] == 732
    assert positions_b[search_b[0] - 1] == 731
    assert positions_b[search_b[0]] == 732
    assert 730 in positions_b[:search_b[0]]
    assert 731 not in positions_a[search_a[0]:search_a[1] + 1]

    compact_a, compact_search_a = build_rescue_compact_positions(
        [732, 732],
        semantic_pre_pos=731,
        localized_pre_pos=731,
        support_pos=790,
        variant="a",
        total_frames=900,
        fps=1.5,
        candidate_floor_exclusive=731,
    )
    compact_b, compact_search_b = build_rescue_compact_positions(
        [732, 732],
        semantic_pre_pos=731,
        localized_pre_pos=731,
        support_pos=790,
        variant="b",
        total_frames=900,
        fps=1.5,
        candidate_floor_exclusive=731,
    )
    assert compact_a[compact_search_a[0] - 1] == 731
    assert compact_a[compact_search_a[0]] == 732
    assert compact_b[compact_search_b[0] - 1] == 731
    assert compact_b[compact_search_b[0]] == 732


def test_review_rescue_rejects_earlier_false_probe_then_finds_exact_boundary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 600)
    refs = window_module.build_frame_refs(source, 1.5)
    refs_by_pos = {ref.pos: ref for ref in refs}
    locator = _FakeWindowLocator(
        onset=539,
        onset_by_stage={
            "rescue_01_fine": 1000,
            "rescue_01_fine_b": 1000,
            "rescue_02_fine": 537,
            "rescue_02_localize_a": 540,
            "rescue_02_localize_b": 540,
            "rescue_02_verify_a": 539,
            "rescue_02_verify_b": 539,
        },
    )
    output_root = tmp_path / "window-runs"
    output = output_root / "review-rescue"
    output.mkdir(parents=True)
    detector = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=output_root,
    )
    candidates = [
        ReviewRescueCandidate(
            bracket=(338, 360),
            provisional_start=360,
            boundary_kind=BoundaryKind.END_CARD_THEN_CREDITS.value,
            source_call_id="coarse-false",
            source_reject="NONE",
        ),
        ReviewRescueCandidate(
            bracket=(527, 540),
            provisional_start=540,
            boundary_kind=BoundaryKind.END_CARD_THEN_CREDITS.value,
            source_call_id="coarse-real",
            source_reject="NONE",
        ),
    ]

    outcome = detector._review_rescue_candidates(
        candidates,
        refs_by_pos=refs_by_pos,
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 539
    assert outcome.reports[0]["status"] == "REJECTED_PRE_ONLY_CONFIRMED"
    assert outcome.reports[1]["status"] == "FOUND"
    assert outcome.verification is not None
    assert outcome.verification["first_positions"] == [539, 539]
    stages = [stage for stage, _positions in locator.calls]
    assert stages == [
        "rescue_01_fine",
        "rescue_01_fine_b",
        "rescue_02_fine",
        "rescue_02_localize_a",
        "rescue_02_localize_b",
        "rescue_02_verify_a",
        "rescue_02_verify_b",
        "rescue_02_micro_a",
    ]


def test_two_independent_semantic_noncredit_views_clear_rejected_hint(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 600)
    refs = window_module.build_frame_refs(source, 1.5)
    locator = _FakeWindowLocator(
        onset=539,
        ambiguous_stages={"rescue_01_fine"},
        reject_stages={"rescue_01_fine"},
    )
    output_root = tmp_path / "window-runs"
    output = output_root / "semantic-negative-clear"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=output_root,
    )._review_rescue_candidates(
        [
            ReviewRescueCandidate(
                bracket=(338, 360),
                provisional_start=360,
                boundary_kind=BoundaryKind.TERMINAL_END_CARD.value,
                source_call_id="coarse-false",
                source_reject="NO_VISIBLE_ATTRIBUTION",
            ),
            ReviewRescueCandidate(
                bracket=(527, 540),
                provisional_start=540,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-real",
                source_reject="NONE",
            ),
        ],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 539
    assert outcome.reports[0]["status"] == "REJECTED_NONCREDIT_CONFIRMED"
    assert outcome.reports[0]["negative_confirmation"][
        "both_semantic_noncredit"
    ] is True


def test_two_adversarial_views_disprove_short_epilogue_positive_before_credits(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 700)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "epilogue-then-credits"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=585,
        onset_by_stage={
            "rescue_01_fine": 539,
            "rescue_01_unsupported_a_b": 1000,
            "rescue_01_unsupported_b_b": 1000,
        },
        support_end_by_stage={"rescue_01_fine": 548},
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [
            ReviewRescueCandidate(
                bracket=(529, 540),
                provisional_start=540,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-epilogue",
                source_reject="NONE",
            ),
            ReviewRescueCandidate(
                bracket=(580, 590),
                provisional_start=590,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-real-credits",
                source_reject="NONE",
            ),
        ],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 585
    first = outcome.reports[0]
    assert first["status"] == "REJECTED_UNSUPPORTED_POSITIVE_CONFIRMED"
    assert first["unsupported_positive_recheck"]["gate_passed"] is True
    assert [stage for stage, _positions in locator.calls][:3] == [
        "rescue_01_fine",
        "rescue_01_unsupported_a_b",
        "rescue_01_unsupported_b_b",
    ]


def test_supported_epilogue_text_is_semantically_rejected_before_real_credit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 700)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "supported-epilogue-then-credits"
    output.mkdir(parents=True)

    class SemanticLocator(_FakeWindowLocator):
        def __init__(self) -> None:
            super().__init__(
                onset=585,
                onset_by_stage={
                    "rescue_01_fine": 539,
                    "rescue_01_unsupported_a_b": 539,
                    "rescue_01_unsupported_b_b": 544,
                },
                support_end_by_stage={
                    "rescue_01_fine": 548,
                    "rescue_01_unsupported_a_b": 563,
                    "rescue_01_unsupported_b_b": 558,
                },
            )
            self.semantic_calls: list[tuple[str, int, str]] = []

        def audit_candidate_semantics(
            self,
            refs: list[FrameRef],
            *,
            candidate_pos: int,
            variant: str,
            stage: str,
            time_budget_seconds: float | None = None,
            capture_path: Path | None = None,
        ) -> VlmCandidateAuditResult:
            del time_budget_seconds
            assert capture_path is not None
            decision = (
                "TITLE_OR_STORY"
                if candidate_pos == 539 else "ATTRIBUTION_CREDIT"
            )
            attribution = decision == "ATTRIBUTION_CREDIT"
            payload = f"candidate:{variant}:{candidate_pos}:{stage}".encode()
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            capture_path.write_bytes(payload)
            response_json = {
                "decision": decision,
                "attribution_layout": attribution,
                "inside_story_screen": False,
            }
            record = {
                "call_id": f"fake-{stage}-{variant}",
                "stage": stage,
                "frame_positions": [ref.pos for ref in refs],
                "frame_files": [ref.path.name for ref in refs],
                "candidate_pos": candidate_pos,
                "semantic_variant": variant,
                "ok": True,
                "input_mosaic_path": str(capture_path.resolve()),
                "input_sha256": hashlib.sha256(payload).hexdigest(),
                "prompt_protocol": "candidate_semantic_audit_v1",
                "prompt_variant": (
                    "candidate_single"
                    if variant == "a" else "candidate_context_triplet"
                ),
                "prompt_sha256": hashlib.sha256(
                    f"prompt:{stage}:{variant}".encode()
                ).hexdigest(),
                "response_json": response_json,
            }
            self.semantic_calls.append((variant, candidate_pos, decision))
            return VlmCandidateAuditResult(
                decision=decision,
                attribution_layout=attribution,
                inside_story_screen=False,
                call_record=record,
            )

    locator = SemanticLocator()
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [
            ReviewRescueCandidate(
                bracket=(529, 540),
                provisional_start=540,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-epilogue",
                source_reject="NONE",
            ),
            ReviewRescueCandidate(
                bracket=(580, 590),
                provisional_start=590,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-real-credits",
                source_reject="NONE",
            ),
        ],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 120.0,
    )

    assert outcome.status == "FOUND", (outcome.reason, outcome.reports)
    assert outcome.start_pos == 585
    first = outcome.reports[0]
    assert first["status"] == "REJECTED_SEMANTIC_SENTINEL"
    recheck = first["unsupported_positive_recheck"]
    assert recheck["positive_consensus"] is True
    assert recheck["candidate_semantic_audit"]["definitive_noncredit"] is True
    assert locator.semantic_calls[:2] == [
        ("a", 539, "TITLE_OR_STORY"),
        ("b", 539, "TITLE_OR_STORY"),
    ]


def test_review_rescue_hard_caps_all_chronological_hints_at_five() -> None:
    rows: list[WindowEvidence] = []
    for index in range(8):
        start = index * 100
        rows.append(_evidence(
            list(range(start, start + 81, 10)),
            WindowVerdict.TRANSITION,
            first_cell=4,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.UNVERIFIABLE,
            reject="DIEGETIC" if index == 0 else "NONE",
        ))

    candidates = build_review_rescue_candidates(rows, limit=99, fps=1.0)

    assert WindowProtocolConfig().review_rescue_max_candidates == 5
    with pytest.raises(ValueError, match="between 1 and 5"):
        WindowProtocolConfig(review_rescue_max_candidates=6).validate()
    assert len(candidates) == 5
    assert [item.bracket for item in candidates] == [
        (30, 40),
        (130, 140),
        (230, 240),
        (330, 340),
        (430, 440),
    ]


def test_shifted_negative_panel_keeps_primary_cells_and_changes_transport() -> None:
    primary = [20, 25, 30, 35, 40]

    shifted = window_module.build_shifted_negative_positions(
        primary,
        total_frames=100,
    )

    assert set(primary).issubset(shifted)
    assert shifted != primary
    assert len(shifted) == len(primary) + 1


def test_one_negative_view_cannot_discard_an_earlier_candidate(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 600)
    refs = window_module.build_frame_refs(source, 1.5)
    locator = _FakeWindowLocator(
        onset=539,
        onset_by_stage={"rescue_01_fine": 1000},
        ambiguous_stages={"rescue_01_fine_b"},
    )
    output = tmp_path / "window-runs" / "negative-disagreement"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [
            ReviewRescueCandidate(
                bracket=(338, 360),
                provisional_start=360,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-early",
                source_reject="NONE",
            ),
            ReviewRescueCandidate(
                bracket=(527, 540),
                provisional_start=540,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-late",
                source_reject="NONE",
            ),
        ],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.reports[0]["status"] == "UNRESOLVED_NEGATIVE_DISAGREEMENT"
    assert [stage for stage, _positions in locator.calls] == [
        "rescue_01_fine",
        "rescue_01_fine_b",
    ]


def test_rejected_coarse_hint_needs_positive_adversarial_recheck(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "rejected-positive-recheck"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(onset=130)
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.TERMINAL_END_CARD.value,
            source_call_id="coarse-rejected",
            source_reject="NO_VISIBLE_ATTRIBUTION",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 130
    assert outcome.reports[0]["rejected_hint_recheck"]["gate_passed"] is True
    assert [stage for stage, _positions in locator.calls][:2] == [
        "rescue_01_fine",
        "rescue_01_fine_b",
    ]


def test_rejected_hint_accepts_sustained_credit_family_and_longer_support_horizon(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 600)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "rejected-family-recheck"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=379,
        kind_by_stage={
            "rescue_01_fine": BoundaryKind.END_CARD_THEN_CREDITS,
            "rescue_01_fine_b": BoundaryKind.CREDIT_SEQUENCE,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(338, 360),
            provisional_start=360,
            boundary_kind=BoundaryKind.TERMINAL_END_CARD.value,
            source_call_id="coarse-rejected-near-real-credits",
            source_reject="NO_VISIBLE_ATTRIBUTION",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 379
    recheck = outcome.reports[0]["rejected_hint_recheck"]
    assert recheck["same_kind"] is False
    assert recheck["same_boundary_family"] is True
    assert recheck["gate_passed"] is True
    first_fine_positions = locator.calls[0][1]
    assert first_fine_positions[-1] >= 417


def test_rejected_positive_hint_disagreement_blocks_later_found(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "rejected-positive-disagreement"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=130,
            ambiguous_stages={"rescue_01_fine_b"},
        ),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-rejected",
            source_reject="STORY_TEXT",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.reports[0]["status"] == "UNRESOLVED_REJECTED_HINT"


def test_short_rejected_transition_needs_two_adversarial_negatives_before_later_credit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "short-rejected-transient"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=726,
        onset_by_stage={
            "rescue_01_fine": 409,
            "rescue_01_fine_b": 850,
            "rescue_01_transient_b": 850,
        },
        support_end_by_stage={"rescue_01_fine": 417},
        continuity_by_stage={
            "rescue_01_fine": Continuity.UNVERIFIABLE,
        },
        reject_by_stage={
            "rescue_01_fine": "NO_VISIBLE_ATTRIBUTION",
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [
            ReviewRescueCandidate(
                bracket=(338, 360),
                provisional_start=360,
                boundary_kind=BoundaryKind.TERMINAL_END_CARD.value,
                source_call_id="coarse-rejected-short",
                source_reject="NO_VISIBLE_ATTRIBUTION",
            ),
            ReviewRescueCandidate(
                bracket=(698, 720),
                provisional_start=720,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-real-later-credit",
                source_reject="NONE",
                source_last_support_pos=800,
                support_hint=800,
                support_call_id="coarse-real-later-credit",
            ),
        ],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 726
    assert outcome.reports[0]["status"] == (
        "REJECTED_TRANSIENT_NONCREDIT_CONFIRMED"
    )
    assert outcome.reports[0]["transient_negative_confirmation"]["gate_passed"] is True
    assert outcome.reports[1]["status"] == "FOUND"
    stages = [stage for stage, _positions in locator.calls]
    assert stages[:3] == [
        "rescue_01_fine",
        "rescue_01_fine_b",
        "rescue_01_transient_b",
    ]


def test_terminal_review_candidate_has_dense_exact_rescue(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 600)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "terminal-rescue"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=_FakeWindowLocator(
            onset=587,
            kind=BoundaryKind.TERMINAL_END_CARD,
        ),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(586, 588),
            provisional_start=588,
            boundary_kind=BoundaryKind.TERMINAL_END_CARD.value,
            source_call_id="coarse-terminal",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 587
    assert outcome.onset_kind == BoundaryKind.TERMINAL_END_CARD.value
    assert outcome.verification is not None
    assert outcome.verification["terminal_ok"] is True


def test_unverifiable_terminal_fine_is_localization_only_before_exact(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 600)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "terminal-fine-localization-only"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=_FakeWindowLocator(
            onset=587,
            kind=BoundaryKind.TERMINAL_END_CARD,
            continuity_by_stage={
                "rescue_01_fine": Continuity.UNVERIFIABLE,
            },
        ),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(586, 588),
            provisional_start=588,
            boundary_kind=BoundaryKind.TERMINAL_END_CARD.value,
            source_call_id="coarse-terminal-unverifiable-fine",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 587
    assert outcome.reports[0]["terminal_fine_localization_only"] is True
    assert outcome.verification is not None
    assert outcome.verification["both_exact_semantic"] is True
    assert outcome.verification["micro_boundary"]["gate_passed"] is True


def test_terminal_candidate_accepts_ending_card_family_at_real_eof(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 600)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "terminal-ending-family"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=_FakeWindowLocator(
            onset=587,
            kind=BoundaryKind.END_CARD_THEN_CREDITS,
        ),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(586, 588),
            provisional_start=588,
            boundary_kind=BoundaryKind.TERMINAL_END_CARD.value,
            source_call_id="coarse-terminal-family",
            source_reject="NONE",
            source_at_stream_eof=True,
            source_last_support_pos=599,
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 587
    assert outcome.onset_kind == BoundaryKind.END_CARD_THEN_CREDITS.value
    assert outcome.verification is not None
    assert outcome.verification["terminal_ok"] is True
    assert outcome.verification["exact_consensus_kind"] == (
        BoundaryKind.END_CARD_THEN_CREDITS.value
    )


def test_far_from_eof_terminal_hint_can_be_reinterpreted_as_credits(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 300)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "terminal-type-recheck"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.TERMINAL_END_CARD.value,
            source_call_id="coarse-wrong-terminal",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 130
    assert outcome.onset_kind == BoundaryKind.CREDIT_SEQUENCE.value


@pytest.mark.parametrize("variant", ["a", "b"])
def test_micro_exact_disagreement_keeps_unclaimed_predecessor_context_only(
    variant: str,
) -> None:
    positions, search = build_micro_boundary_positions(
        [859, 860],
        support_pos=880,
        variant=variant,
        total_frames=900,
        fps=1.5,
    )

    assert positions[search[0] : search[1] + 1] == [859, 860]
    assert positions[search[0] - 1] == 858
    assert 858 not in positions[search[0] : search[1] + 1]


@pytest.mark.parametrize("variant", ["a", "b"])
def test_micro_unanimous_exact_retains_one_predecessor_candidate(
    variant: str,
) -> None:
    positions, search = build_micro_boundary_positions(
        [888, 888],
        support_pos=899,
        variant=variant,
        total_frames=900,
        fps=1.5,
        at_stream_eof=True,
    )

    assert positions[search[0] : search[1] + 1] == [887, 888]
    assert positions[search[0] - 1] == 886


@pytest.mark.parametrize(
    ("micro_a", "micro_b", "expected_status", "expected_start"),
    [
        (130, 130, "FOUND", 130),
        (131, 131, "FOUND", 131),
        (130, 131, "REVIEW", None),
    ],
)
def test_rescue_one_frame_exact_disagreement_requires_two_view_micro_consensus(
    tmp_path: Path,
    micro_a: int,
    micro_b: int,
    expected_status: str,
    expected_start: int | None,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "one-frame-fade"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        onset_by_stage={
            "rescue_01_verify_b": 131,
            "rescue_01_micro_a": micro_a,
            "rescue_01_micro_b": micro_b,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-fade",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == expected_status
    assert outcome.start_pos == expected_start
    assert outcome.verification is not None
    assert outcome.verification["first_positions"][0] == 130
    assert outcome.verification["first_positions"][1] != 130
    micro = outcome.verification["micro_boundary"]
    assert micro["first_positions"] == [micro_a, micro_b]
    assert micro["gate_passed"] is (expected_status == "FOUND")


def test_definitive_candidate_semantic_rejection_continues_to_later_credit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 280)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "semantic-continue"
    output.mkdir(parents=True)

    class SemanticLocator(_FakeWindowLocator):
        def __init__(self) -> None:
            super().__init__(onset=130)
            self.semantic_calls: list[tuple[str, int, str]] = []

        def locate_window(self, refs: list[FrameRef], **kwargs: Any) -> SimpleNamespace:
            original = self.onset
            if str(kwargs.get("stage", "")).startswith("rescue_02"):
                self.onset = 200
            try:
                return super().locate_window(refs, **kwargs)
            finally:
                self.onset = original

        def audit_candidate_semantics(
            self,
            refs: list[FrameRef],
            *,
            candidate_pos: int,
            variant: str,
            stage: str,
            time_budget_seconds: float | None = None,
            capture_path: Path | None = None,
        ) -> VlmCandidateAuditResult:
            del time_budget_seconds
            assert capture_path is not None
            decision = (
                "TITLE_OR_STORY"
                if candidate_pos < 180 else "ATTRIBUTION_CREDIT"
            )
            attribution = decision == "ATTRIBUTION_CREDIT"
            payload = f"candidate:{variant}:{candidate_pos}:{stage}".encode("utf-8")
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            capture_path.write_bytes(payload)
            response_json = {
                "decision": decision,
                "attribution_layout": attribution,
                "inside_story_screen": False,
            }
            record = {
                "call_id": f"fake-{stage}-{variant}",
                "stage": stage,
                "frame_positions": [ref.pos for ref in refs],
                "frame_files": [ref.path.name for ref in refs],
                "candidate_pos": candidate_pos,
                "semantic_variant": variant,
                "ok": True,
                "input_mosaic_path": str(capture_path.resolve()),
                "input_sha256": hashlib.sha256(payload).hexdigest(),
                "prompt_protocol": "candidate_semantic_audit_v1",
                "prompt_variant": (
                    "candidate_single"
                    if variant == "a" else "candidate_context_triplet"
                ),
                "prompt_sha256": hashlib.sha256(
                    f"prompt:{stage}:{variant}".encode("utf-8")
                ).hexdigest(),
                "response_json": response_json,
            }
            self.semantic_calls.append((variant, candidate_pos, decision))
            return VlmCandidateAuditResult(
                decision=decision,
                attribution_layout=attribution,
                inside_story_screen=False,
                call_record=record,
            )

    locator = SemanticLocator()
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [
            ReviewRescueCandidate(
                bracket=(120, 140),
                provisional_start=140,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-title",
                source_reject="NONE",
            ),
            ReviewRescueCandidate(
                # Deliberately overlap the earlier false title bracket. The
                # second rescue must retain chronology but may not re-open
                # frame 130 or anything earlier as a fresh onset candidate.
                bracket=(120, 210),
                provisional_start=210,
                boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
                source_call_id="coarse-real-credit",
                source_reject="NONE",
            ),
        ],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 120.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 200
    assert outcome.reports[0]["status"] == "REJECTED_SEMANTIC_SENTINEL"
    assert outcome.reports[0]["rejected_candidate_pos"] == 130
    assert outcome.reports[0]["semantic_rejection_floor_after"] == 130
    assert outcome.reports[1]["status"] == "FOUND"
    floor = outcome.reports[1]["semantic_rejection_floor"]
    assert floor["active"] == 130
    assert floor["original_pre_pos"] == 120
    assert floor["effective_pre_pos"] == 130
    assert floor["search_right_pos"] > floor["effective_pre_pos"]
    assert locator.semantic_calls == [
        ("a", 130, "TITLE_OR_STORY"),
        ("b", 130, "TITLE_OR_STORY"),
        ("a", 200, "ATTRIBUTION_CREDIT"),
        ("b", 200, "ATTRIBUTION_CREDIT"),
    ]


def test_fixed_edge_emergence_opens_fresh_two_view_predecessor_audit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    paths = _make_frames(source, 260)
    for position, path in enumerate(paths):
        image = Image.new("RGB", (320, 180), (35 + position % 30, 40, 55))
        if position >= 129:
            for y in (72, 96):
                for x in range(84, 244, 12):
                    for yy in range(y, y + 11):
                        image.putpixel((x, yy), (225, 225, 225))
                    for xx in range(x, x + 7):
                        image.putpixel((xx, y), (225, 225, 225))
                        image.putpixel((xx, y + 5), (225, 225, 225))
        image.save(path)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "faint-predecessor-emergence"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        onset_by_stage={
            "rescue_01_verify_b": 131,
            "rescue_01_predecessor_micro_a": 129,
            "rescue_01_predecessor_micro_b": 129,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-faint-predecessor-emergence",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 129
    assert outcome.verification is not None
    micro = outcome.verification["micro_boundary"]
    assert micro["predecessor_emergence"]["gate_passed"] is True
    assert micro["predecessor_audit"]["chosen_pos"] == 129
    assert micro["predecessor_audit"]["fresh_from_initial_micro"] is True
    assert [stage for stage, _positions in locator.calls][-2:] == [
        "rescue_01_predecessor_micro_a",
        "rescue_01_predecessor_micro_b",
    ]


def test_rescue_two_frame_exact_disagreement_never_reaches_micro(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "two-frame-exact-gap"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        onset_by_stage={"rescue_01_verify_b": 132},
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-wide-exact-gap",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.start_pos is None
    assert outcome.verification is not None
    micro = outcome.verification["micro_boundary"]
    assert micro["gate_passed"] is False
    assert micro["reason"] == "exact disagreement exceeds micro hard cap"
    assert not any("_micro_" in stage for stage, _ in locator.calls)


def test_unanimous_exact_backtracks_only_with_two_micro_views(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    paths = _make_frames(source, 260)
    # The production micro gate permits a one-frame backtrack only when the
    # candidate contains a decoded-pixel change relative to its predecessor.
    # Give this consensus test a real faint credit-like emergence at pos 130.
    for position, path in enumerate(paths):
        image = Image.new("RGB", (320, 180), (28, 31, 36))
        if position >= 130:
            for y in (76, 98):
                for x in range(126, 194):
                    if (x // 5) % 2 == 0:
                        image.putpixel((x, y), (118, 122, 128))
        image.save(path)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "unanimous-exact-backtrack"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=131,
        onset_by_stage={
            "rescue_01_micro_a": 130,
            "rescue_01_micro_b": 130,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-faint-predecessor",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 130
    assert outcome.verification is not None
    assert outcome.verification["first_positions"] == [131, 131]
    micro = outcome.verification["micro_boundary"]
    assert micro["first_positions"] == [130, 130]
    assert micro["chosen_pos"] == 130
    assert micro["gate_passed"] is True


def test_micro_blank_veto_excludes_physically_blank_predecessor(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    paths = _make_frames(source, 260)
    Image.new("RGB", (32, 20), (0, 0, 0)).save(paths[129])
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "blank-predecessor-veto"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-blank-predecessor",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 130
    assert outcome.verification is not None
    micro = outcome.verification["micro_boundary"]
    assert micro["raw_blank_veto_positions"] == [129]
    assert micro["visible_candidate_floor"] == 130
    assert micro["chosen_pos"] == 130


def test_micro_veto_excludes_unchanged_nonblank_predecessor(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    paths = _make_frames(source, 260)
    repeated_codec_black = Image.new("RGB", (32, 20), (0, 0, 0))
    # A value-4 pixel remains auditable under the blank policy, but because it
    # is already present in the preceding frame it cannot be a new onset.
    repeated_codec_black.putpixel((16, 10), (4, 4, 4))
    repeated_codec_black.save(paths[128])
    faint_new_stroke = repeated_codec_black.copy()
    faint_new_stroke.putpixel((17, 10), (4, 4, 4))
    faint_new_stroke.save(paths[129])
    refs = window_module.build_frame_refs(source, 1.0)
    refs_by_pos = {ref.pos: ref for ref in refs}
    faint_check = window_module._micro_backtrack_has_raw_change(
        refs_by_pos,
        129,
    )
    assert faint_check["gate_passed"] is True

    repeated_codec_black.save(paths[129])
    assert window_module._is_visually_blank_frame(paths[129]) is False
    raw_check = window_module._micro_backtrack_has_raw_change(
        refs_by_pos,
        129,
    )
    assert raw_check["gate_passed"] is False
    assert raw_check["max_abs_rgb_delta"] == 0

    output = tmp_path / "window-runs" / "unchanged-predecessor-veto"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-unchanged-predecessor",
            source_reject="NONE",
        )],
        refs_by_pos=refs_by_pos,
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 130
    assert outcome.verification is not None
    micro = outcome.verification["micro_boundary"]
    assert micro["raw_blank_veto_positions"] == []
    assert micro["raw_unchanged_backtrack_veto_positions"] == [129]
    assert micro["visible_candidate_floor"] == 130
    assert micro["chosen_pos"] == 130


def test_blank_veto_keeps_faint_or_chromatic_strokes_auditable(
    tmp_path: Path,
) -> None:
    black = tmp_path / "black.png"
    faint = tmp_path / "faint.png"
    chromatic = tmp_path / "chromatic.png"
    Image.new("RGB", (32, 20), (0, 0, 0)).save(black)
    faint_image = Image.new("RGB", (32, 20), (0, 0, 0))
    faint_image.putpixel((16, 10), (4, 4, 4))
    faint_image.save(faint)
    chromatic_image = Image.new("RGB", (32, 20), (0, 0, 0))
    chromatic_image.putpixel((16, 10), (5, 0, 0))
    chromatic_image.save(chromatic)

    assert window_module._is_visually_blank_frame(black) is True
    assert window_module._is_visually_blank_frame(faint) is False
    assert window_module._is_visually_blank_frame(chromatic) is False


def test_persistent_edge_emergence_only_proposes_new_fixed_overlay(
    tmp_path: Path,
) -> None:
    source = tmp_path / "edge-emergence" / "frames" / "cikis"
    paths = _make_frames(source, 12)
    for position, path in enumerate(paths):
        image = Image.new("RGB", (320, 180), (35 + position, 40, 55))
        # Moving scene structure should not look like a newly fixed overlay.
        for y in range(30, 150, 12):
            x = 20 + position * 3 + (y % 17)
            for dx in range(4):
                image.putpixel((min(319, x + dx), y), (120, 100, 70))
        if position >= 6:
            # A stable two-line glyph-like overlay appears at frame 6.
            for y in (72, 96):
                for x in range(84, 244, 12):
                    for yy in range(y, y + 11):
                        image.putpixel((x, yy), (225, 225, 225))
                    for xx in range(x, x + 7):
                        image.putpixel((xx, y), (225, 225, 225))
                        image.putpixel((xx, y + 5), (225, 225, 225))
        image.save(path)
    refs = window_module.build_frame_refs(source, 1.5)
    refs_by_pos = {ref.pos: ref for ref in refs}

    before = window_module._persistent_edge_emergence(refs_by_pos, 4)
    onset = window_module._persistent_edge_emergence(refs_by_pos, 6)

    assert before["gate_passed"] is False
    assert onset["gate_passed"] is True
    assert onset["best"]["ratio"] >= 2.25
    assert onset["photometric_cut_veto"] is False


def test_global_fade_to_dark_cannot_open_fixed_overlay_predecessor_audit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "global-fade" / "frames" / "cikis"
    paths = _make_frames(source, 10)
    for position, path in enumerate(paths):
        level = 105 if position < 5 else 18
        image = Image.new("RGB", (320, 180), (level, level, level))
        # Preserve a stable film-border/noise structure on both sides so this
        # is specifically a global photometric transition, not a blank image.
        for x in range(0, 320, 8):
            value = min(255, level + (28 if x % 16 == 0 else 12))
            for y in range(4):
                image.putpixel((x, y), (value, value, value))
        image.save(path)
    refs = window_module.build_frame_refs(source, 1.5)

    result = window_module._persistent_edge_emergence(
        {ref.pos: ref for ref in refs},
        5,
    )

    assert result["photometric_cut_veto"] is True
    assert result["gate_passed"] is False
    assert result["luma_ratio"] < 0.72
    assert "photometric cut/fade" in result["reason"]


def test_multi_frame_exact_miss_uses_earliest_dense_edge_only_after_two_micro_views(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    paths = _make_frames(source, 260)
    for position in range(126, 138):
        image = Image.new("RGB", (320, 180), (35, 40, 55))
        if position >= 130:
            for y in (72, 96):
                for x in range(84, 244, 12):
                    for yy in range(y, y + 11):
                        image.putpixel((x, yy), (225, 225, 225))
                    for xx in range(x, x + 7):
                        image.putpixel((xx, y), (225, 225, 225))
                        image.putpixel((xx, y + 5), (225, 225, 225))
        image.save(paths[position])
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "multi-frame-dense-edge"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        onset_by_stage={
            "rescue_01_localize_a": 129,
            "rescue_01_localize_b": 134,
            "rescue_01_verify_a": 134,
            "rescue_01_verify_b": 134,
        },
        kind_by_stage={
            "rescue_01_verify_b": BoundaryKind.END_CARD_THEN_CREDITS,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-multi-frame-fade",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 130
    assert outcome.verification is not None
    probe = outcome.verification["dense_edge_probe"]
    assert probe["gate_passed"] is True
    assert probe["anchor_pos"] == 130
    assert probe["min_ratio"] == 1.8
    assert probe["min_density"] == 0.002
    micro = outcome.verification["micro_boundary"]
    assert micro["claim_positions"] == [130, 131]
    assert micro["first_positions"] == [130, 130]
    assert micro["gate_passed"] is True
    assert [stage for stage, _positions in locator.calls][-2:] == [
        "rescue_01_dense_edge_micro_a",
        "rescue_01_dense_edge_micro_b",
    ]


def test_dense_edge_candidate_cannot_promote_a_later_micro_answer(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    paths = _make_frames(source, 260)
    for position in range(126, 138):
        image = Image.new("RGB", (320, 180), (35, 40, 55))
        if position >= 130:
            for y in (72, 96):
                for x in range(84, 244, 12):
                    for yy in range(y, y + 11):
                        image.putpixel((x, yy), (225, 225, 225))
                    for xx in range(x, x + 7):
                        image.putpixel((xx, y), (225, 225, 225))
                        image.putpixel((xx, y + 5), (225, 225, 225))
        image.save(paths[position])
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "dense-edge-later-answer"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        onset_by_stage={
            "rescue_01_localize_a": 129,
            "rescue_01_localize_b": 134,
            "rescue_01_verify_a": 134,
            "rescue_01_verify_b": 134,
            "rescue_01_dense_edge_micro_a": 131,
            "rescue_01_dense_edge_micro_b": 131,
        },
        kind_by_stage={
            "rescue_01_verify_b": BoundaryKind.END_CARD_THEN_CREDITS,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-dense-edge-later-answer",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.start_pos is None
    assert outcome.verification is not None
    micro = outcome.verification["micro_boundary"]
    assert micro["gate_passed"] is False
    assert micro["chosen_pos"] is None
    assert "earliest raw edge proposal" in micro["reason"]


def test_title_edge_refines_sequentially_to_first_later_attribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "semantic-successor"
    output.mkdir(parents=True)

    class SuccessorLocator(_FakeWindowLocator):
        def audit_candidate_semantics(
            self,
            refs: list[FrameRef],
            *,
            candidate_pos: int,
            variant: str,
            stage: str,
            time_budget_seconds: float | None = None,
            capture_path: Path | None = None,
        ) -> VlmCandidateAuditResult:
            del time_budget_seconds
            assert capture_path is not None
            if candidate_pos >= 134:
                decision = "ATTRIBUTION_CREDIT"
            else:
                decision = "TITLE_OR_STORY" if variant == "a" else "OTHER_TEXT"
            attribution = decision == "ATTRIBUTION_CREDIT"
            payload = f"semantic:{stage}:{variant}:{candidate_pos}".encode()
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            capture_path.write_bytes(payload)
            response_json = {
                "decision": decision,
                "attribution_layout": attribution,
                "inside_story_screen": False,
            }
            record = {
                "call_id": f"fake-{stage}-{variant}",
                "stage": stage,
                "frame_positions": [ref.pos for ref in refs],
                "frame_files": [ref.path.name for ref in refs],
                "candidate_pos": candidate_pos,
                "semantic_variant": variant,
                "ok": True,
                "input_mosaic_path": str(capture_path.resolve()),
                "input_sha256": hashlib.sha256(payload).hexdigest(),
                "prompt_protocol": "candidate_semantic_audit_v1",
                "prompt_variant": (
                    "candidate_single"
                    if variant == "a" else "candidate_context_triplet"
                ),
                "prompt_sha256": hashlib.sha256(
                    f"prompt:{stage}:{variant}".encode()
                ).hexdigest(),
                "response_json": response_json,
            }
            return VlmCandidateAuditResult(
                decision=decision,
                attribution_layout=attribution,
                inside_story_screen=False,
                call_record=record,
            )

    successor_prefix = "rescue_01_exact_disagreement_successor_0134"
    locator = SuccessorLocator(
        onset=136,
        onset_by_stage={
            "rescue_01_localize_a": 129,
            "rescue_01_localize_b": 136,
            "rescue_01_verify_a": 133,
            "rescue_01_verify_b": 135,
            f"{successor_prefix}_micro_a": 134,
            f"{successor_prefix}_micro_b": 134,
        },
    )
    monkeypatch.setattr(
        window_module,
        "_earliest_dense_gap_edge_emergence",
        lambda *_args, **_kwargs: {
            "gate_passed": True,
            "anchor_pos": 130,
            "search_range": [130, 131],
            "probes": [],
            "reason": "injected title edge",
        },
    )

    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-title-then-credit",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 134
    assert outcome.verification is not None
    micro = outcome.verification["micro_boundary"]
    refinement = micro["semantic_successor_refinement"]
    assert [audit["candidate_pos"] for audit in refinement["audits"]] == [
        131, 132, 133, 134
    ]
    assert refinement["successor_pos"] == 134
    assert micro["first_positions"] == [134, 134]
    assert micro["semantic_rejection_floor_veto_positions"] == [133]


def test_blank_transition_rescue_recovers_earliest_static_credit_card(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    paths = _make_frames(source, 520)
    for position in (412, 413, 414, 423):
        Image.new("RGB", (32, 20), (0, 0, 0)).save(paths[position])
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "static-card-blank-anchor"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=415,
        onset_by_stage={
            "rescue_01_fine": 438,
            "rescue_01_localize_a": 422,
            "rescue_01_localize_b": 425,
            "rescue_01_verify_a": 424,
            "rescue_01_verify_b": 423,
            "rescue_01_blank_micro_a": 415,
            "rescue_01_blank_micro_b": 415,
        },
        kind_by_stage={
            "rescue_01_localize_b": BoundaryKind.END_CARD_THEN_CREDITS,
            "rescue_01_verify_b": BoundaryKind.END_CARD_THEN_CREDITS,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(405, 428),
            provisional_start=428,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-static-cards",
            source_reject="NONE",
            source_last_support_pos=500,
            support_hint=500,
            support_call_id="coarse-static-cards",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 415
    assert outcome.verification is not None
    assert outcome.verification["first_positions"] == [422, 425]
    assert outcome.verification["same_kind"] is False
    assert outcome.verification["same_boundary_family"] is True
    assert outcome.verification["blank_transition_anchor"] == 415
    assert outcome.verification["blank_anchor_needs_rescue"] is True
    micro = outcome.verification["micro_boundary"]
    assert micro["claim_positions"] == [415, 415]
    assert micro["first_positions"] == [415, 415]
    assert micro["gate_passed"] is True
    assert [stage for stage, _ in locator.calls][-2:] == [
        "rescue_01_blank_micro_a",
        "rescue_01_blank_micro_b",
    ]
    assert not any("_verify_" in stage for stage, _ in locator.calls)


def test_blank_transition_rescue_recovers_rtl_card_after_near_black_frame(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    paths = _make_frames(source, 900)
    near_black = Image.new("RGB", (32, 20), (0, 0, 0))
    near_black.putpixel((16, 10), (3, 0, 0))
    near_black.save(paths[725])
    assert window_module._is_visually_blank_frame(paths[725]) is True
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "rtl-near-black-anchor"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=726,
        onset_by_stage={
            "rescue_01_fine": 727,
            "rescue_01_localize_a": 727,
            "rescue_01_localize_b": 727,
            "rescue_01_blank_micro_a": 726,
            "rescue_01_blank_micro_b": 726,
        },
        kind_by_stage={
            "rescue_01_localize_a": BoundaryKind.END_CARD_THEN_CREDITS,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(698, 720),
            provisional_start=720,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-rtl-card",
            source_reject="NONE",
            source_last_support_pos=800,
            support_hint=800,
            support_call_id="coarse-rtl-card",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 726
    assert outcome.verification is not None
    assert all(position > 726 for position in outcome.verification["first_positions"])
    assert outcome.verification["blank_transition_anchor"] == 726
    assert outcome.verification["same_kind"] is False
    assert outcome.verification["same_boundary_family"] is True
    assert outcome.verification["micro_boundary"]["first_positions"] == [726, 726]
    assert not any("_verify_" in stage for stage, _ in locator.calls)


def test_rescue_exact_same_family_kind_mismatch_requires_fresh_micro_consensus(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "rescue-kind-mismatch"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=130,
            kind_by_stage={
                "rescue_01_verify_b": BoundaryKind.END_CARD_THEN_CREDITS,
            },
        ),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-kind",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 130
    assert outcome.verification is not None
    assert outcome.verification["same_kind"] is False
    assert outcome.verification["same_boundary_family"] is True
    assert outcome.verification["source_needs_two_view_audit"] is True
    micro = outcome.verification["micro_boundary"]
    assert micro["gate_passed"] is True
    assert len(micro["views"]) == 2


def test_rescue_exact_cross_family_kind_mismatch_is_review(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "rescue-cross-family-mismatch"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        kind_by_stage={
            "rescue_01_verify_b": BoundaryKind.TERMINAL_END_CARD,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-cross-family-kind",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.start_pos is None
    assert outcome.verification is not None
    assert outcome.verification["same_boundary_family"] is False
    assert outcome.verification["exact_localization_gate"] is False
    assert outcome.verification["micro_boundary"]["views"] == []


@pytest.mark.parametrize(
    ("ambiguous_micro_b", "expected_status"),
    [(False, "FOUND"), (True, "REVIEW")],
)
def test_one_unverifiable_exact_view_is_only_a_localizer_until_two_fresh_micro_views(
    tmp_path: Path,
    ambiguous_micro_b: bool,
    expected_status: str,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / f"one-unverifiable-{ambiguous_micro_b}"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        kind_by_stage={
            "rescue_01_verify_a": BoundaryKind.END_CARD_THEN_CREDITS,
        },
        continuity_by_stage={
            "rescue_01_verify_a": Continuity.UNVERIFIABLE,
        },
        ambiguous_stages=(
            {"rescue_01_micro_b"} if ambiguous_micro_b else set()
        ),
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-unverifiable-localizer",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == expected_status
    assert outcome.start_pos == (130 if expected_status == "FOUND" else None)
    assert outcome.verification is not None
    assert outcome.verification["exact_family_gate"] is False
    assert outcome.verification["exact_localization_gate"] is True
    assert outcome.verification["source_needs_two_view_audit"] is True
    micro = outcome.verification["micro_boundary"]
    assert len(micro["views"]) == 2
    assert micro["gate_passed"] is (expected_status == "FOUND")


def test_two_unverifiable_exact_views_cannot_open_micro_audit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "two-unverifiable"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        continuity_by_stage={
            "rescue_01_verify_a": Continuity.UNVERIFIABLE,
            "rescue_01_verify_b": Continuity.UNVERIFIABLE,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-both-unverifiable",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.verification is not None
    assert outcome.verification["exact_localization_gate"] is False
    assert outcome.verification["micro_boundary"]["views"] == []


def test_wide_chronology_guard_recovers_onset_before_late_candidate(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 600)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "chronology-guard"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=379),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(500, 520),
            provisional_start=520,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-late",
            source_reject="NONE",
            source_first_cell=12,
            wide_left=473,
            chronology_positions=(360, 380, 400, 420, 440, 460, 480, 500, 510),
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 379
    assert outcome.reports[0]["chronology_guard"]["gate_passed"] is True


def test_wide_sparse_chronology_disagreement_keeps_one_earlier_anchor(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "chronology-one-anchor-left"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=804,
        onset_by_stage={
            "rescue_01_fine": 897,
            "rescue_01_chronology_05_a": 832,
            "rescue_01_chronology_05_b": 854,
        },
        kind_by_stage={
            "rescue_01_fine": BoundaryKind.TERMINAL_END_CARD,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(885, 887),
            provisional_start=887,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-terminal-after-credits",
            source_reject="NONE",
            source_first_cell=7,
            source_at_stream_eof=True,
            source_last_support_pos=899,
            wide_left=698,
            support_hint=899,
            support_call_id="coarse-terminal-after-credits",
            chronology_positions=(698, 720, 742, 765, 787, 810, 832, 854, 876, 877),
            chronology_groups=(
                (0, 23, 45, 68, 90, 113, 135, 158, 180),
                (180, 203, 225, 248, 270, 293, 315, 338, 360),
                (360, 383, 405, 428, 450, 473, 495, 518, 540),
                (540, 563, 585, 608, 630, 653, 675, 698, 720),
                (698, 720, 742, 765, 787, 810, 832, 854, 876, 877),
            ),
            requires_chronology_guard=True,
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND", (outcome.reason, outcome.reports)
    assert outcome.start_pos == 804
    guard = outcome.reports[0]["chronology_guard"]
    selected = guard["groups"][guard["selected_group"] - 1]
    assert selected["union_gap"] == [787, 854]
    assert selected["left_context_widened_from"] == 810
    assert selected["left_context_widened_to"] == 787
    assert any(
        stage == "rescue_01_localize_a" and 787 in positions
        for stage, positions in locator.calls
    )


def test_late_candidate_runs_chronology_guard_even_when_fine_passes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 600)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "mandatory-chronology"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=379,
        onset_by_stage={"rescue_01_fine": 510},
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(500, 520),
            provisional_start=520,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-late-pass",
            source_reject="NONE",
            source_first_cell=12,
            wide_left=473,
            chronology_positions=(360, 380, 400, 420, 440, 460, 480, 500, 510),
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 379
    assert outcome.reports[0]["chronology_guard"]["gate_passed"] is True


def test_two_clean_chronology_views_clear_history_and_keep_current_fine(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 700)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "chronology-negative-clear"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(onset=510)
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(500, 520),
            provisional_start=520,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-after-ambiguous",
            source_reject="NONE",
            source_first_cell=7,
            chronology_positions=(360, 380, 400, 420, 440, 460, 480, 500),
            requires_chronology_guard=True,
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 510
    guard = outcome.reports[0]["chronology_guard"]
    assert guard["negative_clear"] is True
    assert guard["outcome"] == "EARLIER_NONCREDIT"
    assert guard["gate_passed"] is False
    assert [stage for stage, _positions in locator.calls][1:3] == [
        "rescue_01_chronology_a",
        "rescue_01_chronology_b",
    ]


def test_sparse_final_chronology_disagreement_only_opens_bounded_localization(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "chronology-disputed-boundary"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=759,
        onset_by_stage={
            "rescue_01_fine": 773,
            "rescue_01_chronology_01_a": 899,
            "rescue_01_chronology_01_b": 899,
            "rescue_01_chronology_02_a": 700,
            "rescue_01_chronology_02_b": 899,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(765, 787),
            provisional_start=787,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-late-rolling-credit",
            source_reject="NONE",
            source_first_cell=3,
            source_at_stream_eof=True,
            source_last_support_pos=885,
            wide_left=720,
            support_hint=885,
            support_call_id="coarse-late-rolling-credit",
            chronology_positions=(720, 742, 765),
            chronology_groups=(
                (600, 650, 700, 720),
                (720, 742, 765),
            ),
            requires_chronology_guard=True,
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 759
    guard = outcome.reports[0]["chronology_guard"]
    assert guard["selected_group"] is None
    assert guard["fallback_group"] == 2
    assert guard["outcome"] == "DISPUTED_BOUNDARY_BRACKET"
    assert guard["disputed_boundary_gap"] == [720, 773]
    assert guard["gate_passed"] is False
    assert outcome.reports[0]["localize"]["gate_passed"] is True
    assert any("_localize_" in stage for stage, _positions in locator.calls)
    assert any("_verify_" in stage for stage, _positions in locator.calls)


def test_sparse_chronology_fallback_requires_one_semantic_noncredit_view(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "chronology-unresolved-no-negative"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=759,
        onset_by_stage={
            "rescue_01_fine": 773,
            "rescue_01_chronology_01_a": 899,
            "rescue_01_chronology_01_b": 899,
            "rescue_01_chronology_02_a": 700,
        },
        ambiguous_stages={"rescue_01_chronology_02_b"},
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(765, 787),
            provisional_start=787,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-unresolved-last-group",
            source_reject="NONE",
            source_first_cell=3,
            source_at_stream_eof=True,
            source_last_support_pos=885,
            wide_left=720,
            support_hint=885,
            support_call_id="coarse-unresolved-last-group",
            chronology_positions=(720, 742, 765),
            chronology_groups=(
                (600, 650, 700, 720),
                (720, 742, 765),
            ),
            requires_chronology_guard=True,
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.reports[0]["status"] == "UNRESOLVED_CHRONOLOGY"
    assert not any("_localize_" in stage for stage, _positions in locator.calls)


def test_agreed_sparse_last_cell_only_opens_exact_boundary_pipeline(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "chronology-agreed-last-cell"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=826,
        onset_by_stage={
            "rescue_01_fine": 833,
            "rescue_01_fine_left": 836,
            "rescue_01_chronology_01_a": 899,
            "rescue_01_chronology_01_b": 899,
            "rescue_01_chronology_02_a": 832,
            "rescue_01_chronology_02_b": 832,
        },
        continuity_by_stage={
            "rescue_01_chronology_02_a": Continuity.UNVERIFIABLE,
            "rescue_01_chronology_02_b": Continuity.UNVERIFIABLE,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(832, 854),
            provisional_start=854,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-late-overlay-credit",
            source_reject="NONE",
            source_first_cell=7,
            source_last_support_pos=877,
            wide_left=787,
            support_hint=877,
            support_call_id="coarse-late-overlay-credit",
            chronology_positions=(712, 720, 742, 765, 787, 810, 832),
            chronology_groups=(
                (540, 585, 630, 675, 720),
                (712, 720, 742, 765, 787, 810, 832),
            ),
            requires_chronology_guard=True,
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND", (outcome.reason, outcome.reports)
    assert outcome.start_pos == 826
    guard = outcome.reports[0]["chronology_guard"]
    assert guard["selected_group"] is None
    assert guard["fallback_group"] == 2
    assert guard["outcome"] == "AGREED_LAST_CELL_BOUNDARY_BRACKET"
    assert guard["agreed_last_cell_gap"] == [810, 836]
    assert guard["gate_passed"] is False
    assert outcome.reports[0]["localize"]["gate_passed"] is True
    assert any("_verify_" in stage for stage, _positions in locator.calls)
    assert any("_micro_" in stage for stage, _positions in locator.calls)


@pytest.mark.parametrize("failure_mode", ["different_first", "rejected_view"])
def test_sparse_last_cell_bracket_rejects_nonmatching_views(
    tmp_path: Path,
    failure_mode: str,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / f"chronology-last-cell-{failure_mode}"
    output.mkdir(parents=True)
    onset_by_stage = {
        "rescue_01_fine": 833,
        "rescue_01_fine_left": 836,
        "rescue_01_chronology_01_a": 899,
        "rescue_01_chronology_01_b": 899,
        "rescue_01_chronology_02_a": 832,
        "rescue_01_chronology_02_b": (
            810 if failure_mode == "different_first" else 832
        ),
    }
    reject_by_stage = (
        {"rescue_01_chronology_02_b": "DIEGETIC"}
        if failure_mode == "rejected_view" else {}
    )
    locator = _FakeWindowLocator(
        onset=826,
        onset_by_stage=onset_by_stage,
        continuity_by_stage={
            "rescue_01_chronology_02_a": Continuity.UNVERIFIABLE,
            "rescue_01_chronology_02_b": Continuity.UNVERIFIABLE,
        },
        reject_by_stage=reject_by_stage,
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(832, 854),
            provisional_start=854,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-unresolved-last-cell",
            source_reject="NONE",
            source_first_cell=7,
            source_last_support_pos=877,
            wide_left=787,
            support_hint=877,
            support_call_id="coarse-unresolved-last-cell",
            chronology_positions=(712, 720, 742, 765, 787, 810, 832),
            chronology_groups=(
                (540, 585, 630, 675, 720),
                (712, 720, 742, 765, 787, 810, 832),
            ),
            requires_chronology_guard=True,
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.reports[0]["status"] == "UNRESOLVED_CHRONOLOGY"
    assert not any("_localize_" in stage for stage, _positions in locator.calls)


def test_left_expansion_and_sparse_gap_intersection_recover_early_overlay(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "left-expand"
    output.mkdir(parents=True)
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=_FakeWindowLocator(onset=804),
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(832, 854),
            provisional_start=854,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-overlay",
            source_reject="NONE",
            source_first_cell=6,
            wide_left=787,
            support_hint=882,
            support_call_id="coarse-overlay",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 804
    assert "fine_left" in outcome.reports[0]
    assert outcome.reports[0]["localize"]["intersection_gap"][0] < 804


def test_supported_fine_chain_allows_one_short_sparse_localization_view(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    refs = window_module.build_frame_refs(source, 1.5)
    output = tmp_path / "window-runs" / "localize-support-chain"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=804,
        onset_by_stage={
            "rescue_01_localize_a": 829,
            "rescue_01_localize_b": 813,
            "rescue_01_localize_02_a": 803,
            "rescue_01_localize_02_b": 808,
        },
        support_end_by_stage={
            "rescue_01_localize_b": 823,
            "rescue_01_localize_02_b": 813,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(832, 854),
            provisional_start=854,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-overlay-short-local-support",
            source_reject="NONE",
            source_first_cell=6,
            wide_left=787,
            support_hint=882,
            support_call_id="coarse-overlay-short-local-support",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=5,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 804
    passes = outcome.reports[0]["localize"]["passes"]
    assert passes[0]["support_flags"] == [True, False]
    assert passes[0]["support_chain_ok"] is True
    assert passes[0]["fine_support_available"] is True
    assert len(passes) == 2
    assert passes[1]["left_context_disputed"] is True
    assert passes[1]["left_context_tolerance_frames"] == 1
    assert passes[1]["structural_gate_passed"] is True


def test_coarse_and_fine_support_allow_two_positional_localization_views(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "localize-two-short-with-hint"
    output.mkdir(parents=True)
    source_call = "coarse-supported-same-candidate"
    locator = _FakeWindowLocator(
        onset=130,
        support_end_by_stage={
            "rescue_01_localize_a": 135,
            "rescue_01_localize_b": 135,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id=source_call,
            source_reject="NONE",
            support_hint=180,
            support_call_id=source_call,
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "FOUND"
    assert outcome.start_pos == 130
    first_pass = outcome.reports[0]["localize"]["passes"][0]
    assert first_pass["support_flags"] == [False, False]
    assert first_pass["fine_support_available"] is True
    assert first_pass["coarse_support_hint_available"] is True
    assert first_pass["support_chain_ok"] is True


def test_sparse_union_keeps_disputed_cell_but_micro_fails_closed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "exact-escape"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        onset_by_stage={
            "rescue_01_localize_a": 134,
            "rescue_01_localize_b": 135,
            "rescue_01_verify_a": 136,
            "rescue_01_verify_b": 136,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-gap",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.verification is not None
    assert outcome.verification["inside_exact_search_gap"] is True
    assert outcome.verification["exact_structural_gate"] is True
    assert outcome.verification["micro_boundary"]["gate_passed"] is False


def test_dense_exact_cannot_escape_sparse_union_gap(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    refs = window_module.build_frame_refs(source, 1.0)
    output = tmp_path / "window-runs" / "exact-union-escape"
    output.mkdir(parents=True)
    locator = _FakeWindowLocator(
        onset=130,
        onset_by_stage={
            "rescue_01_localize_a": 134,
            "rescue_01_localize_b": 135,
            "rescue_01_verify_a": 137,
            "rescue_01_verify_b": 137,
        },
    )
    outcome = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    )._review_rescue_candidates(
        [ReviewRescueCandidate(
            bracket=(120, 140),
            provisional_start=140,
            boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
            source_call_id="coarse-union-escape",
            source_reject="NONE",
        )],
        refs_by_pos={ref.pos: ref for ref in refs},
        total_frames=len(refs),
        call_index=2,
        out=output,
        calls_path=output / "calls.jsonl",
        deadline=time.perf_counter() + 30.0,
    )

    assert outcome.status == "REVIEW"
    assert outcome.verification is not None
    assert outcome.verification["inside_exact_search_gap"] is False
    assert outcome.verification["exact_structural_gate"] is False
    assert outcome.verification["micro_boundary"]["views"] == []


def test_mid_rescue_failure_keeps_successful_trace_in_final_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    candidate = ReviewRescueCandidate(
        bracket=(120, 140),
        provisional_start=140,
        boundary_kind=BoundaryKind.CREDIT_SEQUENCE.value,
        source_call_id="coarse-forced-review",
        source_reject="NONE",
    )
    monkeypatch.setattr(
        window_module,
        "decode_coarse_windows",
        lambda *_args, **_kwargs: window_module.CoarseOutcome(
            "REVIEW", "forced rescue for trace test"
        ),
    )
    monkeypatch.setattr(
        window_module,
        "build_review_rescue_candidates",
        lambda *_args, **_kwargs: [candidate],
    )
    output = tmp_path / "window-runs" / "rescue-trace-failure"
    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=130,
            fail_stages={"rescue_01_localize_a"},
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, output)

    calls = [
        json.loads(line)
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    evidence = json.loads((output / "window_evidence.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert result.status == "MODEL_ERROR"
    assert any(row["stage"] == "rescue_01_fine" for row in evidence)
    assert any(row["stage"] == "rescue_01_localize_a" and not row["ok"] for row in calls)
    assert result.metrics["vlm_call_count"] == len(calls)
    assert len(manifest["window_evidence"]) == len(evidence)


def test_found_is_revoked_if_artifact_write_crosses_wall_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    original_atomic = window_module._atomic_write_json
    state = {"expired": False}

    def atomic(path: Path, payload: Any) -> None:
        original_atomic(path, payload)
        if path.name == "window_evidence.json":
            state["expired"] = True

    monkeypatch.setattr(window_module, "_atomic_write_json", atomic)
    monkeypatch.setattr(
        window_module.time,
        "perf_counter",
        lambda: 31.0 if state["expired"] else 0.0,
    )
    output = tmp_path / "window-runs" / "final-wall-gate"
    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, output)

    calls = [
        json.loads(line)
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert result.status == "MODEL_ERROR"
    assert result.start_pos is None
    assert calls[-1]["error_kind"] == "wall_time_budget_final_gate"


def test_chronology_prompt_is_explicitly_script_agnostic() -> None:
    prompt = _prompt(
        list(range(9)),
        3,
        stage="rescue_01_chronology_a",
    )

    assert "EARLIEST-CHRONOLOGY GUARD" in prompt
    assert "Arabic/Persian RTL" in prompt
    assert "terminal logo" in prompt


def test_real_onset_near_a_coarse_seam_is_not_left_censored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=115),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "coarse-seam")

    assert result.status == "FOUND"
    assert result.start_pos == 115


def test_unsupported_positive_coarse_evidence_is_review_not_not_found() -> None:
    positions = list(range(0, 81, 10))
    unsupported = _evidence(
        positions,
        WindowVerdict.TRANSITION,
        first_cell=4,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.UNVERIFIABLE,
    )

    outcome = decode_coarse_windows([unsupported], fps=1.0)

    assert outcome.status == "REVIEW"
    assert "unsupported" in outcome.reason


def test_active_pre_active_is_multiple_regimes_and_never_refined() -> None:
    first = list(range(0, 81, 10))
    second = list(range(80, 161, 10))
    third = list(range(160, 241, 10))
    outcome = decode_coarse_windows([
        _evidence(
            first,
            WindowVerdict.ACTIVE_FROM_LEFT,
            first_cell=0,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
        _evidence(second, WindowVerdict.PRE_ONLY),
        _evidence(
            third,
            WindowVerdict.ACTIVE_FROM_LEFT,
            first_cell=0,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
    ], fps=1.0)

    assert outcome.status == "REVIEW"
    assert "PRE_ONLY" in outcome.reason


def test_ambiguous_window_between_pre_and_active_blocks_refinement() -> None:
    first = list(range(0, 81, 10))
    middle = list(range(80, 161, 10))
    third = list(range(170, 251, 10))
    outcome = decode_coarse_windows([
        _evidence(first, WindowVerdict.PRE_ONLY),
        _evidence(
            middle,
            WindowVerdict.AMBIGUOUS,
            continuity=Continuity.UNVERIFIABLE,
        ),
        _evidence(
            third,
            WindowVerdict.ACTIVE_FROM_LEFT,
            first_cell=0,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
    ], fps=1.0)

    assert outcome.status == "REVIEW"
    assert "ambiguous" in outcome.reason


@pytest.mark.parametrize(
    "rows",
    [
        [
            (WindowVerdict.TRANSITION, 3, Continuity.CONFIRMED),
            (WindowVerdict.PRE_ONLY, -1, Continuity.NONE),
        ],
        [
            (WindowVerdict.PRE_ONLY, -1, Continuity.NONE),
            (WindowVerdict.ACTIVE_FROM_LEFT, 0, Continuity.CONFIRMED),
            (WindowVerdict.PRE_ONLY, -1, Continuity.NONE),
        ],
        [
            (WindowVerdict.TRANSITION, 3, Continuity.CONFIRMED),
            (WindowVerdict.AMBIGUOUS, -1, Continuity.UNVERIFIABLE),
        ],
    ],
)
def test_post_credit_pre_or_ambiguity_does_not_require_credits_to_reach_eof(
    rows: list[tuple[WindowVerdict, int, Continuity]],
) -> None:
    evidence: list[WindowEvidence] = []
    for index, (verdict, first_cell, continuity) in enumerate(rows):
        positions = list(range(index * 80, index * 80 + 81, 10))
        evidence.append(_evidence(
            positions,
            verdict,
            first_cell=first_cell,
            kind=(
                BoundaryKind.CREDIT_SEQUENCE
                if first_cell >= 0 else BoundaryKind.NONE
            ),
            continuity=continuity,
        ))

    outcome = decode_coarse_windows(evidence, fps=1.0)

    assert outcome.status == "REFINE"
    assert outcome.bracket is not None


def test_repeated_transition_claims_in_one_continuous_regime_use_earliest() -> None:
    first = list(range(0, 81, 10))
    second = list(range(80, 161, 10))
    outcome = decode_coarse_windows([
        _evidence(
            first,
            WindowVerdict.TRANSITION,
            first_cell=6,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
        _evidence(
            second,
            WindowVerdict.TRANSITION,
            first_cell=1,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
    ], fps=1.0)

    assert outcome.status == "REFINE"
    assert outcome.bracket == [50, 60]


def test_overlapping_transition_brackets_are_one_coarse_candidate() -> None:
    first = list(range(0, 101, 10))
    second = list(range(70, 171, 10))
    outcome = decode_coarse_windows([
        _evidence(
            first,
            WindowVerdict.TRANSITION,
            first_cell=8,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
        _evidence(
            second,
            WindowVerdict.TRANSITION,
            first_cell=1,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
    ], fps=1.0)

    assert outcome.status == "REFINE"
    assert outcome.bracket == [70, 80]


def test_active_before_later_transition_remains_left_censored() -> None:
    first = list(range(0, 81, 10))
    second = list(range(80, 161, 10))
    outcome = decode_coarse_windows([
        _evidence(
            first,
            WindowVerdict.ACTIVE_FROM_LEFT,
            first_cell=0,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
        _evidence(
            second,
            WindowVerdict.TRANSITION,
            first_cell=3,
            kind=BoundaryKind.CREDIT_SEQUENCE,
            continuity=Continuity.CONFIRMED,
        ),
    ], fps=1.0)

    assert outcome.status == "LEFT_CENSORED"
    assert outcome.bracket is None


def test_supported_transition_and_active_views_must_agree_on_kind() -> None:
    transition = _evidence(
        list(range(0, 81, 10)),
        WindowVerdict.TRANSITION,
        first_cell=3,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.CONFIRMED,
    )
    active = _evidence(
        list(range(80, 161, 10)),
        WindowVerdict.ACTIVE_FROM_LEFT,
        first_cell=0,
        kind=BoundaryKind.END_CARD_THEN_CREDITS,
        continuity=Continuity.CONFIRMED,
    )

    outcome = decode_coarse_windows([transition, active], fps=1.0)

    assert outcome.status == "REVIEW"
    assert "kind" in outcome.reason


def test_multiple_supported_active_views_must_agree_on_kind() -> None:
    pre = _evidence(list(range(0, 81, 10)), WindowVerdict.PRE_ONLY)
    active_credit = _evidence(
        list(range(80, 161, 10)),
        WindowVerdict.ACTIVE_FROM_LEFT,
        first_cell=0,
        kind=BoundaryKind.CREDIT_SEQUENCE,
        continuity=Continuity.CONFIRMED,
    )
    active_end_then_credit = _evidence(
        list(range(160, 241, 10)),
        WindowVerdict.ACTIVE_FROM_LEFT,
        first_cell=0,
        kind=BoundaryKind.END_CARD_THEN_CREDITS,
        continuity=Continuity.CONFIRMED,
    )

    outcome = decode_coarse_windows(
        [pre, active_credit, active_end_then_credit], fps=1.0
    )

    assert outcome.status == "REVIEW"
    assert "kind" in outcome.reason


def test_fine_gap_and_shifted_panels_keep_exact_pre_and_long_support() -> None:
    fine = build_fine_gap_positions([120, 135], total_frames=260, fps=1.0)
    verify_a = build_exact_verification_positions(
        130, shift=0, total_frames=260, fps=1.0
    )
    verify_b = build_exact_verification_positions(
        130, shift=-1, total_frames=260, fps=1.0
    )

    assert len(fine) == 9
    assert fine[0] == 117 and fine[-1] == 150
    assert 130 in verify_a and 130 in verify_b
    assert 129 in verify_a and 129 in verify_b
    assert verify_a[-1] - 130 >= 12
    assert verify_b[-1] - 130 >= 11


def test_terminal_fine_panel_is_bounded_and_keeps_dense_probe_and_eof_context() -> None:
    positions = build_terminal_fine_positions(
        [787, 810], total_frames=900, fps=1.5
    )

    assert len(positions) <= WindowProtocolConfig().terminal_fine_max_cells
    assert {787, 807, 808, 809, 810, 811, 812, 813}.issubset(positions)
    assert {876, 887, 891, 894, 897, 899}.issubset(positions)


def test_dense_exact_mosaic_adapts_tile_width_to_context_pixel_budget() -> None:
    cfg = WindowProtocolConfig()

    assert bounded_verification_tile_width(9, columns=3, config=cfg) == 640
    assert bounded_verification_tile_width(13, columns=3, config=cfg) == 512
    assert bounded_verification_tile_width(13, columns=2, config=cfg) == 512


def test_exact_panels_cover_every_frame_in_the_fine_gap() -> None:
    verify_a = build_exact_verification_positions(
        108, shift=0, pre_pos=101, total_frames=260, fps=1.5
    )
    verify_b = build_exact_verification_positions(
        108, shift=-1, pre_pos=101, total_frames=260, fps=1.5
    )

    required_gap = set(range(101, 109))
    assert required_gap.issubset(verify_a)
    assert required_gap.issubset(verify_b)
    assert verify_a != verify_b
    overlap = len(set(verify_a) & set(verify_b))
    union = len(set(verify_a) | set(verify_b))
    assert overlap / union <= 0.8


def test_prompt_allows_short_terminal_eof_and_uses_adversarial_verify_b() -> None:
    primary = _prompt(
        [0, 1, 2],
        3,
        relative_seconds=[0.0, 1.0, 3.0],
        at_stream_eof=True,
        stage="verify_a",
    )
    adversarial = _prompt(
        [0, 1, 2],
        2,
        relative_seconds=[0.0, 1.0, 3.0],
        at_stream_eof=True,
        stage="verify_b",
    )

    assert "at least two dense cells total" in primary
    assert "under 8 seconds" in primary
    assert "fade only to blank/black" in primary
    assert "exactly one plausible" in primary
    assert "last_support=first" in primary
    assert "ADVERSARIAL REJECTION AUDIT" in adversarial
    assert "Persistent text is not enough" in adversarial


def test_semantic_sentinel_prompt_rejects_tv_chyrons_and_title_cards() -> None:
    prompt = _prompt(
        [0, 1, 2, 3, 4, 5],
        2,
        relative_seconds=[0.0, 0.7, 3.0, 8.0, 15.0, 30.0],
        stage="semantic_sentinel_b",
        boundary_search_cells=(1, 1),
    )

    assert "SEMANTIC FALSE-POSITIVE SENTINEL" in prompt
    assert "broadcast logo" in prompt
    assert "interview name strap" in prompt
    assert "film title" in prompt
    assert "later genuine credits cannot" in prompt
    assert "Credits over footage remain valid" in prompt
    assert "ADVERSARIAL REJECTION AUDIT" in prompt


def _candidate_semantic_view(
    decision: str,
    variant: str,
    *,
    token: str,
) -> dict[str, Any]:
    return {
        "decision": decision,
        "attribution_layout": decision == "ATTRIBUTION_CREDIT",
        "inside_story_screen": decision == "DIEGETIC_SCREEN",
        "call_id": f"semantic-{variant}-{token}",
        "candidate_pos": 130,
        "input_sha256": token * 64,
        "prompt_sha256": {
            "a": "c",
            "b": "d",
            "s": "e",
        }.get(variant, "f") * 64,
        "prompt_protocol": "candidate_semantic_audit_v1",
        "prompt_variant": {
            "a": "candidate_single",
            "b": "candidate_context_triplet",
            "s": "candidate_screen_disproof",
        }[variant],
    }


def test_candidate_semantic_schema_and_prompts_are_candidate_only() -> None:
    schema = _candidate_audit_schema()
    single = _candidate_audit_prompt(variant="a", candidate_cell=0)
    context = _candidate_audit_prompt(variant="b", candidate_cell=1)
    screen = _candidate_audit_prompt(variant="s", candidate_cell=0)

    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "decision", "attribution_layout", "inside_story_screen"
    ]
    assert "DIEGETIC_SCREEN" in schema["properties"]["decision"]["enum"]
    assert "SAME candidate frame" in single
    assert "All five panes" in single
    assert "center zoom" in single
    assert "lower-edge zoom" in single
    assert "Judge only CELL 01" in context
    assert "retroactively" in single
    assert "Arabic/Persian RTL" in context
    assert "SCREEN DISPROOF AUDIT" in screen
    assert "visible physical evidence" in screen
    assert "scan lines" in screen
    assert "MUST NOT return DIEGETIC_SCREEN" in screen
    assert "IN MEMORY OF" in single
    assert "AVEC/WITH" in single


def test_raw_screen_disproof_recovers_only_bounded_credit_patterns() -> None:
    primary_screen = _candidate_semantic_view(
        "DIEGETIC_SCREEN", "a", token="a"
    )
    context_credit = _candidate_semantic_view(
        "ATTRIBUTION_CREDIT", "b", token="b"
    )
    context_screen = _candidate_semantic_view(
        "DIEGETIC_SCREEN", "b", token="b"
    )
    raw_credit = _candidate_semantic_view(
        "ATTRIBUTION_CREDIT", "s", token="e"
    )
    raw_screen = _candidate_semantic_view(
        "DIEGETIC_SCREEN", "s", token="e"
    )
    raw_no_text = _candidate_semantic_view(
        "NO_TEXT", "s", token="f"
    )

    asymmetric = adjudicate_candidate_screen_disproof(
        primary_screen,
        context_credit,
        raw_credit,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        faint_edge_proof={"gate_passed": False},
        candidate_luma_mean=45.0,
    )
    dark_card = adjudicate_candidate_screen_disproof(
        primary_screen,
        context_screen,
        raw_credit,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        faint_edge_proof={"gate_passed": True},
        candidate_luma_mean=0.4,
    )
    real_screen = adjudicate_candidate_screen_disproof(
        primary_screen,
        context_screen,
        raw_screen,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        faint_edge_proof={"gate_passed": True},
        candidate_luma_mean=0.4,
    )
    bright_double_screen = adjudicate_candidate_screen_disproof(
        primary_screen,
        context_screen,
        raw_credit,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        faint_edge_proof={"gate_passed": True},
        candidate_luma_mean=45.0,
    )
    asymmetric_raw_no_text = adjudicate_candidate_screen_disproof(
        primary_screen,
        context_credit,
        raw_no_text,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        faint_edge_proof={"gate_passed": False},
        candidate_luma_mean=45.0,
    )
    dark_raw_no_text = adjudicate_candidate_screen_disproof(
        primary_screen,
        context_screen,
        raw_no_text,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        faint_edge_proof={"gate_passed": True},
        candidate_luma_mean=0.4,
    )

    assert asymmetric["gate_passed"] is True
    assert asymmetric["asymmetric_recovery"] is True
    assert dark_card["gate_passed"] is True
    assert dark_card["dark_card_recovery"] is True
    assert real_screen["gate_passed"] is False
    assert bright_double_screen["gate_passed"] is False
    assert asymmetric_raw_no_text["gate_passed"] is True
    assert dark_raw_no_text["gate_passed"] is True


def test_candidate_semantic_gate_accepts_two_attribution_views() -> None:
    gate = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view("ATTRIBUTION_CREDIT", "a", token="a"),
        _candidate_semantic_view("ATTRIBUTION_CREDIT", "b", token="b"),
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )

    assert gate["gate_passed"] is True
    assert gate["definitive_noncredit"] is False
    assert gate["independent_views"] is True


def test_candidate_semantic_gate_accepts_faint_single_view_only_with_context_proof() -> None:
    gate = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view("NO_TEXT", "a", token="a"),
        _candidate_semantic_view("ATTRIBUTION_CREDIT", "b", token="b"),
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )
    blocked = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view("NO_TEXT", "a", token="a"),
        _candidate_semantic_view("ATTRIBUTION_CREDIT", "b", token="b"),
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=False,
        faint_edge_proof={"gate_passed": True},
    )
    physically_blocked = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view("NO_TEXT", "a", token="a"),
        _candidate_semantic_view("ATTRIBUTION_CREDIT", "b", token="b"),
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": False},
    )

    assert gate["gate_passed"] is True
    assert blocked["gate_passed"] is False
    assert physically_blocked["gate_passed"] is False


def test_candidate_semantic_gate_accepts_end_card_for_terminal_family() -> None:
    gate = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view("END_CARD", "a", token="a"),
        _candidate_semantic_view("END_CARD", "b", token="b"),
        allowed_kinds={BoundaryKind.TERMINAL_END_CARD.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )

    assert gate["gate_passed"] is True


@pytest.mark.parametrize("decision", ["TITLE_OR_STORY", "DIEGETIC_SCREEN"])
def test_candidate_semantic_gate_definitively_rejects_story_false_positives(
    decision: str,
) -> None:
    gate = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view(decision, "a", token="a"),
        _candidate_semantic_view(decision, "b", token="b"),
        allowed_kinds={BoundaryKind.END_CARD_THEN_CREDITS.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )

    assert gate["gate_passed"] is False
    assert gate["definitive_noncredit"] is True
    assert decision in gate["reason"]


def test_candidate_semantic_gate_accepts_cross_class_noncredit_consensus() -> None:
    gate = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view("TITLE_OR_STORY", "a", token="a"),
        _candidate_semantic_view("OTHER_TEXT", "b", token="b"),
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )
    uncertain = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view("TITLE_OR_STORY", "a", token="a"),
        _candidate_semantic_view("UNCERTAIN", "b", token="b"),
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )

    assert gate["gate_passed"] is False
    assert gate["definitive_noncredit"] is True
    assert uncertain["definitive_noncredit"] is False


@pytest.mark.parametrize("decision", ["NO_TEXT", "UNCERTAIN"])
def test_candidate_semantic_context_must_be_strongly_positive(
    decision: str,
) -> None:
    gate = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view("ATTRIBUTION_CREDIT", "a", token="a"),
        _candidate_semantic_view(decision, "b", token="b"),
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )

    assert gate["gate_passed"] is False


@pytest.mark.parametrize("collision", ["call_id", "input_sha256", "prompt_sha256"])
def test_candidate_semantic_gate_requires_independent_provenance(
    collision: str,
) -> None:
    primary = _candidate_semantic_view("ATTRIBUTION_CREDIT", "a", token="a")
    context = _candidate_semantic_view("ATTRIBUTION_CREDIT", "b", token="b")
    context[collision] = primary[collision]
    gate = adjudicate_candidate_semantic_audits(
        primary,
        context,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )

    assert gate["gate_passed"] is False
    assert gate["independent_views"] is False


def test_candidate_semantic_gate_rejects_kind_incompatible_positive() -> None:
    gate = adjudicate_candidate_semantic_audits(
        _candidate_semantic_view("END_CARD", "a", token="a"),
        _candidate_semantic_view("END_CARD", "b", token="b"),
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )

    assert gate["gate_passed"] is False


def test_adjacent_partial_candidate_requires_primary_early_and_exact_later() -> None:
    primary = _candidate_semantic_view("NO_TEXT", "a", token="a")
    context = _candidate_semantic_view("END_CARD", "b", token="b")
    primary["candidate_pos"] = 759
    context["candidate_pos"] = 759
    audit = adjudicate_candidate_semantic_audits(
        primary,
        context,
        allowed_kinds={BoundaryKind.TERMINAL_END_CARD.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": False},
    )
    micro = {
        "first_positions": [759, 760],
        "exact_first_positions": [760, 760],
        "independent_transport_views": True,
        "kind_compatible": True,
    }

    proof = adjudicate_adjacent_partial_candidate(
        micro,
        audit,
        raw_change={"gate_passed": True},
    )
    reversed_primary = adjudicate_adjacent_partial_candidate(
        {**micro, "first_positions": [760, 759]},
        audit,
        raw_change={"gate_passed": True},
    )
    no_physical_change = adjudicate_adjacent_partial_candidate(
        micro,
        audit,
        raw_change={"gate_passed": False},
    )

    assert proof["gate_passed"] is True
    assert proof["candidate_pos"] == 759
    assert reversed_primary["gate_passed"] is False
    assert no_physical_change["gate_passed"] is False


def test_no_text_partial_requires_nearby_independent_same_run_support() -> None:
    primary = _candidate_semantic_view("NO_TEXT", "a", token="a")
    context = _candidate_semantic_view("NO_TEXT", "b", token="b")
    candidate_audit = adjudicate_candidate_semantic_audits(
        primary,
        context,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": False},
    )
    support_primary = _candidate_semantic_view(
        "ATTRIBUTION_CREDIT", "a", token="a"
    )
    support_context = _candidate_semantic_view(
        "ATTRIBUTION_CREDIT", "b", token="b"
    )
    for index, view in enumerate((support_primary, support_context), start=1):
        view["candidate_pos"] = 136
        view["call_id"] = f"support-{index}"
        view["input_sha256"] = ("e" if index == 1 else "f") * 64
    support_audit = adjudicate_candidate_semantic_audits(
        support_primary,
        support_context,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        allow_faint_primary_no_text=True,
        faint_edge_proof={"gate_passed": True},
    )
    micro = {
        "gate_passed": True,
        "chosen_pos": 130,
        "first_positions": [130, 130],
        "exact_first_positions": [131, 131],
        "independent_transport_views": True,
        "kind_compatible": True,
    }
    supports = [{
        "scope": "rescue_01",
        "candidate_pos": 136,
        "allowed_kinds": [BoundaryKind.CREDIT_SEQUENCE.value],
        "audit": support_audit,
    }]

    proof = adjudicate_later_supported_partial_candidate(
        micro,
        candidate_audit,
        later_supports=supports,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        current_scope="rescue_01",
        max_distance_frames=12,
        raw_change={"gate_passed": True},
    )
    wrong_scope = adjudicate_later_supported_partial_candidate(
        micro,
        candidate_audit,
        later_supports=supports,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        current_scope="rescue_02",
        max_distance_frames=12,
        raw_change={"gate_passed": True},
    )
    no_micro_consensus = adjudicate_later_supported_partial_candidate(
        {**micro, "first_positions": [130, 131]},
        candidate_audit,
        later_supports=supports,
        allowed_kinds={BoundaryKind.CREDIT_SEQUENCE.value},
        current_scope="rescue_01",
        max_distance_frames=12,
        raw_change={"gate_passed": True},
    )

    assert proof["gate_passed"] is True
    assert proof["selected_support"]["candidate_pos"] == 136
    assert wrong_scope["gate_passed"] is False
    assert no_micro_consensus["gate_passed"] is False


def test_exact_schema_prompt_and_parser_forbid_support_only_first() -> None:
    search = (2, 7)
    schema = _schema(14, search)
    prompt = _prompt(
        list(range(14)),
        2,
        stage="verify_b",
        boundary_search_cells=search,
    )
    refs = [
        FrameRef(index, index + 1, Path(f"c_{index + 1:04d}.png"), float(index))
        for index in range(14)
    ]
    support_only_first = {
        "state": "TRANSITION",
        "first": 13,
        "last_support": 13,
        "kind": "CREDIT_SEQUENCE",
        "continuity": "CONFIRMED",
        "reject": "NONE",
    }

    assert schema["properties"]["first"]["maximum"] == 7
    assert schema["properties"]["first"]["enum"] == [-1, 0, 2, 3, 4, 5, 6, 7]
    assert "CELL 02..CELL 07" in prompt
    assert "SUPPORT ONLY" in prompt
    with pytest.raises(ValueError, match="outside exact boundary candidate"):
        OllamaFrameClassifier._parse_window_evidence(
            support_only_first,
            refs,
            "verify_b",
            "fake-call",
            boundary_search_cells=search,
        )

    accepted = dict(support_only_first, first=2)
    evidence = OllamaFrameClassifier._parse_window_evidence(
        accepted,
        refs,
        "verify_b",
        "fake-call",
        boundary_search_cells=search,
    )
    assert evidence.first_pos == 2
    assert evidence.last_support_pos == 13


def test_end_to_end_found_uses_only_direct_window_evidence_and_writes_audit_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    before = _snapshot(source)
    output = tmp_path / "window-runs" / "found"
    _patch_fast_cv(monkeypatch)
    locator = _FakeWindowLocator(onset=130)

    result = WindowClosingCreditOnsetDetector(
        _config(), locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, output)

    assert result.status == "FOUND"
    assert result.start_pos == 130
    assert result.start_frame_no == 131
    assert result.start_file == "c_0131.png"
    assert result.pool_may_be_replaced is False
    assert _snapshot(source) == before
    assert any(stage == "fine_gap" for stage, _ in locator.calls)
    assert [stage for stage, _ in locator.calls][-3:] == [
        "verify_a",
        "verify_b",
        "refine_micro_a",
    ]

    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    result_json = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert manifest["pool_may_be_replaced"] is False
    assert manifest["decision"]["pool_may_be_replaced"] is False
    assert result_json["pool_may_be_replaced"] is False
    evidence = manifest["window_evidence"]
    assert evidence
    assert all(row["metadata"]["input_sha256"] for row in evidence)
    assert all(Path(row["metadata"]["input_mosaic_path"]).is_file() for row in evidence)
    assert (output / "window_evidence.json").is_file()
    assert (output / "window_timeline.csv").is_file()


def test_fps_1_5_sparse_fine_anchor_still_localizes_every_gap_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=_FakeWindowLocator(onset=102),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "fps-1-5-gap")

    assert result.status == "FOUND"
    assert result.start_pos == 102
    assert result.metrics["verification"]["first_positions"] == [102, 102]


def test_real_like_fine_one_cell_drift_expands_left_and_binds_exact_search(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 720)
    _patch_fast_cv(monkeypatch)
    locator = _FakeWindowLocator(
        onset=318,
        onset_by_stage={"fine_gap": 323},
    )
    output = tmp_path / "window-runs" / "real-like-fine-drift"

    result = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, output)

    assert result.status == "FOUND"
    assert result.start_pos == 318
    verification = result.metrics["verification"]
    assert verification["first_positions"] == [318, 318]
    assert verification["exact_search_pre_pos"] == (
        verification["fine_semantic_pre_pos"] - 1
    )
    assert verification["inside_exact_search_gap"] is True
    call_rows = [
        json.loads(line)
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    exact_calls = [row for row in call_rows if row["stage"].startswith("verify_")]
    assert len(exact_calls) == 2
    assert all(call["boundary_search_cells"] for call in exact_calls)
    exact_evidence = [
        row for row in json.loads(
            (output / "window_evidence.json").read_text(encoding="utf-8")
        )
        if row["stage"].startswith("verify_")
    ]
    assert [
        row["metadata"]["boundary_search_cells"] for row in exact_evidence
    ] == [call["boundary_search_cells"] for call in exact_calls]


def test_exact_eight_second_credit_support_passes_both_distinct_cadences(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=130,
            support_end_by_stage={"verify_a": 138, "verify_b": 138},
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "ten-second-support")

    assert result.status == "FOUND"
    assert result.start_pos == 130
    assert result.metrics["verification"]["both_supported"] is True


def test_credit_support_chain_allows_one_exact_view_to_focus_on_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=130,
            support_end_by_stage={"verify_a": 133},
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "one-exact-short-support")

    assert result.status == "FOUND"
    assert result.start_pos == 130
    assert result.metrics["verification"]["exact_support_flags"] == [False, True]
    assert result.metrics["verification"]["both_exact_semantic"] is True
    assert result.metrics["verification"]["support_chain_ok"] is True


def test_credit_support_chain_rejects_when_both_exact_views_lack_long_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=130,
            support_end_by_stage={"verify_a": 133, "verify_b": 133},
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "both-exact-short-support")

    assert result.status == "REVIEW"
    assert result.start_pos is None
    assert result.metrics["verification"]["exact_support_flags"] == [False, False]
    assert result.metrics["verification"]["support_chain_ok"] is False


def test_active_from_first_coarse_panel_is_left_censored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 80)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(), locator=_FakeWindowLocator(onset=0),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "left")

    assert result.status == "LEFT_CENSORED"
    assert result.start_pos is None
    assert result.needs_more_context is True
    assert result.pool_may_be_replaced is False


def test_any_missing_coarse_window_suppresses_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130, fail_stages={"coarse"}),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "missing")

    assert result.status == "MODEL_ERROR"
    assert result.start_pos is None
    assert result.pool_may_be_replaced is False


def test_shifted_verification_disagreement_is_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130, verify_b_shift=3),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "disagree")

    assert result.status == "REVIEW"
    assert result.start_pos is None
    assert "boundary gates" in result.reason
    assert result.pool_may_be_replaced is False


@pytest.mark.parametrize(
    ("micro_a", "micro_b", "expected_status", "expected_start"),
    [
        (130, 130, "FOUND", 130),
        (131, 131, "FOUND", 131),
        (130, 131, "REVIEW", None),
    ],
)
def test_normal_refine_one_frame_exact_disagreement_requires_micro_consensus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    micro_a: int,
    micro_b: int,
    expected_status: str,
    expected_start: int | None,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    locator = _FakeWindowLocator(
        onset=130,
        onset_by_stage={
            "fine_gap": 131,
            "verify_b": 131,
            "refine_micro_a": micro_a,
            "refine_micro_b": micro_b,
        },
    )
    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / f"normal-micro-{micro_a}-{micro_b}")

    assert result.status == expected_status
    assert result.start_pos == expected_start
    verification = result.metrics["verification"]
    assert verification["first_positions"] == [130, 131]
    assert verification["exact_structural_gate"] is True
    assert verification["micro_boundary"]["first_positions"] == [micro_a, micro_b]
    assert verification["micro_boundary"]["gate_passed"] is (
        expected_status == "FOUND"
    )


def test_diegetic_reject_on_exact_verification_suppresses_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130, reject_stages={"verify_b"}),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "diegetic-reject")

    assert result.status == "REVIEW"
    assert result.start_pos is None
    assert result.metrics["verification"]["both_supported"] is False
    assert result.confidence == 0.0
    assert result.pool_may_be_replaced is False


def test_fine_diegetic_reject_stops_before_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    locator = _FakeWindowLocator(onset=130, reject_stages={"fine_gap"})

    result = WindowClosingCreditOnsetDetector(
        _config(), locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "fine-diegetic")

    assert result.status == "REVIEW"
    assert result.start_pos is None
    assert locator.calls[-1][0] == "fine_gap"
    assert not any(stage.startswith("verify_") for stage, _ in locator.calls)


def test_boundary_kind_must_remain_consistent_through_fine_and_exact_views(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    locator = _FakeWindowLocator(
        onset=130,
        kind_by_stage={"fine_gap": BoundaryKind.END_CARD_THEN_CREDITS},
    )

    result = WindowClosingCreditOnsetDetector(
        _config(), locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "kind-mismatch")

    assert result.status == "REVIEW"
    assert result.start_pos is None
    assert "expected=CREDIT_SEQUENCE" in result.reason
    assert locator.calls[-1][0] == "fine_gap"


def test_reused_exact_call_identity_suppresses_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130, reuse_verification_call_id=True),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "reused-call")

    assert result.status == "REVIEW"
    assert result.start_pos is None
    assert result.metrics["verification"]["independent_calls"] is False
    assert result.confidence == 0.0


@pytest.mark.parametrize(
    "locator_kwargs",
    [
        {"evidence_id_mismatch_stages": {"verify_b"}},
        {"evidence_position_mismatch_stages": {"verify_b"}},
        {"record_position_mismatch_stages": {"verify_b"}},
        {"corrupt_capture_hash_stages": {"verify_b"}},
        {"missing_prompt_stages": {"verify_b"}},
    ],
)
def test_call_record_provenance_mismatch_is_model_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    locator_kwargs: dict[str, Any],
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    output = tmp_path / "window-runs" / "bad-provenance"

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130, **locator_kwargs),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, output)

    assert result.status == "MODEL_ERROR"
    assert result.start_pos is None
    records = [
        json.loads(line)
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert records[-1]["error_kind"] == "provenance_validation"
    assert records[-1]["detector_validation_ok"] is False


def test_equal_exact_mosaic_hashes_suppress_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130, equal_verification_images=True),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "equal-exact-images")

    assert result.status == "REVIEW"
    assert result.start_pos is None
    assert result.metrics["verification"]["independent_transport_views"] is False


def test_verify_b_failure_persists_partial_audit_and_suppresses_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    output = tmp_path / "window-runs" / "verify-b-failure"

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130, fail_stages={"verify_b"}),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, output)

    assert result.status == "MODEL_ERROR"
    assert result.start_pos is None
    records = [
        json.loads(line)
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(row["stage"] == "verify_a" and row["ok"] for row in records)
    assert records[-1]["stage"] == "verify_b"
    assert records[-1]["ok"] is False


def test_cv_trace_cannot_move_an_exact_semantic_boundary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)

    def score_with_false_early_trace(frame_dir: Path, _config: object):
        refs = window_module.build_frame_refs(Path(frame_dir), 1.0)
        scores = [_FakeScore(index) for index in range(len(refs))]
        for position in (127, 128, 129):
            scores[position].text_score = 1.0
            scores[position].line_count = 4
            scores[position].vertical_coverage = 0.5
            scores[position].mask_density = 0.2
            scores[position].component_count = 8
            scores[position].dark_ratio = 0.9
            scores[position].luma_mean = 10.0
        return [ref.path for ref in refs], scores, []

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130),
        score_provider=score_with_false_early_trace,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "cv-cannot-move")

    assert result.status == "FOUND"
    assert result.start_pos == 130
    assert result.metrics["verification"]["boundary_refinement"] == {
        "semantic_start_pos": 130,
        "visual_start_pos": 130,
        "backtrack_frames": 0,
        "method": "exact_then_micro_vlm",
    }


def test_terminal_end_card_requires_real_eof_but_can_pass_at_real_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_fast_cv(monkeypatch)
    source_early = tmp_path / "early" / "frames" / "cikis"
    source_eof = tmp_path / "eof" / "frames" / "cikis"
    _make_frames(source_early, 260)
    _make_frames(source_eof, 260)

    early = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=130,
            support_end=170,
            kind=BoundaryKind.TERMINAL_END_CARD,
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source_early, tmp_path / "window-runs" / "terminal-early")
    eof = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=242, kind=BoundaryKind.TERMINAL_END_CARD
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source_eof, tmp_path / "window-runs" / "terminal-eof")

    assert early.status == "REVIEW"
    assert early.start_pos is None
    assert eof.status == "FOUND"
    assert eof.start_pos == 242
    assert eof.pool_may_be_replaced is False


def test_long_terminal_end_card_exact_panels_include_true_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    locator = _FakeWindowLocator(
        onset=230, kind=BoundaryKind.TERMINAL_END_CARD
    )

    result = WindowClosingCreditOnsetDetector(
        _config(), locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "terminal-long")

    assert result.status == "FOUND"
    assert result.start_pos == 230
    exact_calls = [positions for stage, positions in locator.calls if stage.startswith("verify_")]
    assert len(exact_calls) == 2
    assert all(positions[-1] == 259 for positions in exact_calls)


def test_terminal_end_card_allows_only_a_bounded_blank_tail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_fast_cv(monkeypatch)
    source_short = tmp_path / "short" / "frames" / "cikis"
    source_long = tmp_path / "long" / "frames" / "cikis"
    _make_frames(source_short, 260)
    _make_frames(source_long, 260)

    short_blank = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=230,
            support_end=253,
            kind=BoundaryKind.TERMINAL_END_CARD,
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source_short, tmp_path / "window-runs" / "terminal-short-blank")
    long_blank = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=230,
            support_end=238,
            kind=BoundaryKind.TERMINAL_END_CARD,
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source_long, tmp_path / "window-runs" / "terminal-long-blank")

    assert short_blank.status == "FOUND"
    assert short_blank.start_pos == 230
    assert long_blank.status in {"REVIEW", "NOT_FOUND"}
    assert long_blank.start_pos is None


def test_two_frame_terminal_card_plus_bounded_black_tail_is_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=244,
            support_end=245,
            kind=BoundaryKind.TERMINAL_END_CARD,
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "two-frame-terminal")

    assert result.status == "FOUND"
    assert result.start_pos == 244
    assert result.metrics["verification"]["terminal_ok"] is True


def test_single_coarse_terminal_probe_recovers_exact_fifteen_second_blank_tail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(
            onset=243,
            support_end=244,
            kind=BoundaryKind.TERMINAL_END_CARD,
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "terminal-cap-boundary")

    assert result.status == "FOUND"
    assert result.start_pos == 243
    assert result.metrics["verification"]["terminal_blank_tail_seconds"] == [
        15.0,
        15.0,
    ]


def test_long_terminal_card_ending_at_blank_tail_limit_keeps_true_last_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    locator = _FakeWindowLocator(
        onset=200,
        support_end=244,
        kind=BoundaryKind.TERMINAL_END_CARD,
    )
    protocol = WindowProtocolConfig(coarse_window_seconds=300.0)

    result = WindowClosingCreditOnsetDetector(
        _config(),
        protocol=protocol,
        locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "terminal-long-card-limit")

    assert result.status == "FOUND"
    assert result.start_pos == 200
    assert result.metrics["verification"]["terminal_blank_tail_seconds"] == [
        15.0,
        15.0,
    ]


def test_fps_1_5_terminal_probe_fine_panel_keeps_the_two_card_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    _patch_fast_cv(monkeypatch)

    result = WindowClosingCreditOnsetDetector(
        _config(fps=1.5),
        locator=_FakeWindowLocator(
            onset=876,
            support_end=877,
            kind=BoundaryKind.TERMINAL_END_CARD,
        ),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "terminal-probe-fps-1-5")

    assert result.status == "FOUND"
    assert result.start_pos == 876
    assert result.metrics["verification"]["terminal_ok"] is True


def test_short_terminal_end_card_at_real_eof_enters_dense_refinement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 900)
    _patch_fast_cv(monkeypatch)
    locator = _FakeWindowLocator(
        onset=892, kind=BoundaryKind.TERMINAL_END_CARD
    )

    result = WindowClosingCreditOnsetDetector(
        _config(fps=1.5), locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "terminal-short")

    assert result.status == "FOUND"
    assert result.start_pos == 892
    assert any(stage == "fine_gap" for stage, _positions in locator.calls)
    assert [stage for stage, _positions in locator.calls][-3:] == [
        "verify_a",
        "verify_b",
        "refine_micro_a",
    ]


def test_source_drift_after_verification_suppresses_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    paths = _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    locator = _FakeWindowLocator(onset=130, mutate_path=paths[-1])

    result = WindowClosingCreditOnsetDetector(
        _config(), locator=locator,
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, tmp_path / "window-runs" / "drift")

    assert result.status == "REVIEW"
    assert result.start_pos is None
    assert result.provisional_start == 130
    assert result.metrics["source_drift"] is True
    assert result.pool_may_be_replaced is False


def test_output_inside_any_frames_tree_is_rejected_before_write(tmp_path: Path) -> None:
    source = tmp_path / "film-a" / "frames" / "cikis"
    _make_frames(source, 8)
    forbidden = tmp_path / "film-b" / "frames" / "cikis_jenerik" / "debug"

    with pytest.raises(ValueError, match="protected frames tree"):
        WindowClosingCreditOnsetDetector(
            _config(), locator=_FakeWindowLocator(onset=4),
            allowed_output_root=tmp_path / "window-runs",
        ).run(source, forbidden)

    assert not forbidden.exists()


def test_output_outside_experiment_allowlist_is_rejected_before_write(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 8)
    forbidden = tmp_path / "some-other-output" / "run"

    with pytest.raises(ValueError, match="experiment output root"):
        WindowClosingCreditOnsetDetector(
            _config(), locator=_FakeWindowLocator(onset=4),
            allowed_output_root=tmp_path / "window-runs",
        ).run(source, forbidden)

    assert not forbidden.exists()


def test_wall_budget_below_safe_call_floor_fails_closed_with_audit_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 20)
    _patch_fast_cv(monkeypatch)
    config = _config()
    config.max_wall_seconds = 0.1
    output = tmp_path / "window-runs" / "deadline"

    result = WindowClosingCreditOnsetDetector(
        config,
        locator=_FakeWindowLocator(onset=10),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, output)

    assert result.status == "MODEL_ERROR"
    assert result.start_pos is None
    assert "budget exhausted" in result.reason
    call = json.loads((output / "calls.jsonl").read_text(encoding="utf-8"))
    assert call["error_kind"] == "wall_time_budget"


def test_final_verification_returning_at_deadline_cannot_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    clock = SimpleNamespace(value=0.0)
    monkeypatch.setattr(
        window_module,
        "time",
        SimpleNamespace(perf_counter=lambda: clock.value),
    )

    class LateVerifyB(_FakeWindowLocator):
        def locate_window(self, refs: list[FrameRef], **kwargs: Any) -> SimpleNamespace:
            result = super().locate_window(refs, **kwargs)
            if kwargs["stage"] == "verify_b":
                clock.value = 30.0
            return result

    config = _config()
    config.max_wall_seconds = 30.0
    output = tmp_path / "window-runs" / "late-verify-b"
    result = WindowClosingCreditOnsetDetector(
        config,
        locator=LateVerifyB(onset=130),
        allowed_output_root=tmp_path / "window-runs",
    ).run(source, output)

    assert result.status == "MODEL_ERROR"
    assert result.start_pos is None
    records = [
        json.loads(line)
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert records[-1]["error_kind"] == "wall_time_budget_after_call"


def test_preexisting_output_is_never_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 8)
    output = tmp_path / "window-runs" / "already-there"
    output.mkdir(parents=True)
    marker = output / "owned-by-user.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        WindowClosingCreditOnsetDetector(
            _config(), locator=_FakeWindowLocator(onset=4),
            allowed_output_root=tmp_path / "window-runs",
        ).run(source, output)

    assert marker.read_text(encoding="utf-8") == "keep"
    assert sorted(path.name for path in output.iterdir()) == ["owned-by-user.txt"]


def test_default_output_uses_allowlist_independent_of_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, 260)
    _patch_fast_cv(monkeypatch)
    elsewhere = tmp_path / "unrelated-cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    allowed = tmp_path / "window-runs"

    result = WindowClosingCreditOnsetDetector(
        _config(),
        locator=_FakeWindowLocator(onset=130),
        allowed_output_root=allowed,
    ).run(source)

    assert result.status == "FOUND"
    assert Path(result.output_dir).is_relative_to(allowed.resolve())
    assert not (elsewhere / "outputs").exists()
