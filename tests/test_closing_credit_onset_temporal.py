from __future__ import annotations

import pytest

from experiments.closing_credit_onset_vlm.models import DecoderConfig, Label, Observation
from experiments.closing_credit_onset_vlm.temporal import (
    decode_timeline,
    make_overlapping_batches,
    sample_positions,
)


CFG = DecoderConfig(
    fps=1.5,
    confirm_window_seconds=12.0,
    min_credit_hits=6,
    min_long_credit_seconds=8.0,
    max_gap_seconds=4.0,
    end_card_min_frames=2,
    end_card_follow_seconds=15.0,
    uncertain_review_seconds=4.0,
)


def _sequence(*parts: tuple[Label, int], proposal_labels: set[Label] | None = None) -> list[Observation]:
    observations: list[Observation] = []
    proposal_labels = proposal_labels or set()
    for label, count in parts:
        for _ in range(count):
            pos = len(observations)
            metadata: dict[str, object] = {}
            if label == Label.DIEGETIC_TEXT:
                metadata = {"cv_text_score": 0.99, "name_like_count": 8}
            observations.append(
                Observation(
                    pos=pos,
                    frame_no=pos + 1,
                    file=f"c_{pos + 1:04d}.png",
                    label=label,
                    confidence=0.48 if label == Label.UNCERTAIN else 0.95,
                    proposal=label in proposal_labels,
                    metadata=metadata,
                )
            )
    return observations


def _states(decision) -> list[str]:
    return [str(item["state"]) for item in decision.timeline_states]


def _assert_fail_closed(decision) -> None:
    assert decision.start_pos is None
    assert decision.publishable is False
    assert decision.pool_may_be_replaced is False


def test_sample_positions_unions_global_dense_and_proposals() -> None:
    result = sample_positions(
        20,
        fps=1.0,
        base_stride_seconds=5.0,
        dense_tail_seconds=6.0,
        dense_stride_seconds=2.0,
        proposal_positions=[-1, 3, 15, 15, 20],
    )

    assert result == [0, 3, 5, 10, 14, 15, 16, 18, 19]


def test_sample_positions_900_frame_default_plan_is_exact_and_bounded() -> None:
    result = sample_positions(
        900,
        fps=1.5,
        base_stride_seconds=15.0,
        dense_tail_seconds=90.0,
        dense_stride_seconds=4.0,
    )

    assert result == [
        0, 23, 45, 68, 90, 113, 135, 158, 180, 203, 225, 248,
        270, 293, 315, 338, 360, 383, 405, 428, 450, 473, 495,
        518, 540, 563, 585, 608, 630, 653, 675, 698, 720, 743,
        765, 771, 777, 783, 788, 789, 795, 801, 807, 810, 813,
        819, 825, 831, 833, 837, 843, 849, 855, 861, 867, 873,
        878, 879, 885, 891, 897, 899,
    ]
    assert len(result) == 62
    assert len(make_overlapping_batches(result, batch_size=8, overlap=0)) == 8


def test_sample_positions_is_not_disabled_by_empty_cv_proposals() -> None:
    result = sample_positions(
        900,
        fps=1.5,
        base_stride_seconds=15.0,
        dense_tail_seconds=90.0,
        dense_stride_seconds=4.0,
        proposal_positions=[],
    )

    assert 879 in result
    assert 885 in result
    assert result[-1] == 899


@pytest.mark.parametrize(
    "observations",
    [
        [Observation(pos=0, label=Label.FOOTAGE)] + [
            Observation(pos=position, label=Label.CREDIT)
            for position in range(100, 1300, 100)
        ],
        [
            Observation(pos=0, label=Label.FOOTAGE),
            Observation(pos=100, label=Label.END_CARD),
            Observation(pos=500, label=Label.END_CARD),
        ],
    ],
)
def test_sparse_observations_can_never_fake_duration_or_adjacency(
    observations: list[Observation],
) -> None:
    decision = decode_timeline(observations, CFG)

    assert decision.status == "MODEL_ERROR"
    _assert_fail_closed(decision)


def test_make_overlapping_batches_has_two_frame_overlap() -> None:
    assert make_overlapping_batches(list(range(18)), batch_size=8, overlap=2) == [
        [0, 1, 2, 3, 4, 5, 6, 7],
        [6, 7, 8, 9, 10, 11, 12, 13],
        [12, 13, 14, 15, 16, 17],
    ]


def test_make_overlapping_batches_does_not_add_redundant_terminal_batch() -> None:
    assert make_overlapping_batches(list(range(14)), batch_size=8, overlap=2) == [
        [0, 1, 2, 3, 4, 5, 6, 7],
        [6, 7, 8, 9, 10, 11, 12, 13],
    ]


def test_decode_bridges_exact_four_second_blank_gap() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.CREDIT, 9),
        (Label.BLANK, 6),
        (Label.CREDIT, 15),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 10
    assert decision.start_frame_no == 11
    assert _states(decision) == ["PRE"] * 10 + ["CREDIT"] * 9 + ["GAP"] * 6 + ["CREDIT"] * 15


@pytest.mark.parametrize("label,count", [(Label.CREDIT, 18), (Label.END_CARD, 2)])
def test_low_confidence_positive_labels_can_never_publish(label: Label, count: int) -> None:
    observations = _sequence((Label.FOOTAGE, 10), (label, count))
    for item in observations[-count:]:
        item.confidence = 0.0

    decision = decode_timeline(observations, CFG)

    assert decision.status != "FOUND"
    _assert_fail_closed(decision)


def test_unresolved_earlier_island_forces_review_even_with_later_valid_credit() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.UNCERTAIN, 8),
        (Label.FOOTAGE, 3),
        (Label.CREDIT, 18),
        proposal_labels={Label.UNCERTAIN},
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "REVIEW"
    assert decision.provisional_start == 21
    assert decision.review_bracket == [10, 17]
    _assert_fail_closed(decision)


def test_low_confidence_later_island_forces_review_of_earlier_valid_credit() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.CREDIT, 12),
        (Label.FOOTAGE, 10),
        (Label.CREDIT, 8),
    )
    for item in observations[-8:]:
        item.confidence = 0.10

    decision = decode_timeline(observations, CFG)

    assert decision.status == "REVIEW"
    assert decision.provisional_start == 10
    assert decision.review_bracket == [32, 39]
    _assert_fail_closed(decision)


def test_decode_does_not_bridge_gap_longer_than_four_seconds() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.CREDIT, 9),
        (Label.BLANK, 7),
        (Label.CREDIT, 15),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 26
    assert _states(decision) == ["PRE"] * 26 + ["CREDIT"] * 15


def test_decode_marks_terminal_footage_as_post() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.CREDIT, 15),
        (Label.BLANK, 3),
        (Label.CREDIT, 15),
        (Label.FOOTAGE, 10),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 10
    assert _states(decision)[43:] == ["POST"] * 10


def test_high_text_diegetic_run_cannot_seed_onset() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 8),
        (Label.DIEGETIC_TEXT, 10),
        (Label.FOOTAGE, 8),
        (Label.CREDIT, 18),
    )

    decision = decode_timeline(observations, CFG)

    assert observations[8].metadata["cv_text_score"] == 0.99
    assert decision.status == "FOUND"
    assert decision.start_pos == 26


def test_single_credit_error_inside_diegetic_run_is_not_an_onset() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 8),
        (Label.DIEGETIC_TEXT, 4),
        (Label.CREDIT, 1),
        (Label.DIEGETIC_TEXT, 5),
        (Label.FOOTAGE, 5),
        (Label.CREDIT, 18),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 23
    assert decision.earliest_credit_pos == 12


def test_end_card_is_promoted_when_credits_follow() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.END_CARD, 2),
        (Label.BLANK, 6),
        (Label.CREDIT, 15),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 10
    assert decision.onset_kind == "end_card"
    assert _states(decision) == ["PRE"] * 10 + ["CREDIT"] * 2 + ["GAP"] * 6 + ["CREDIT"] * 15


def test_single_end_card_frame_is_not_promoted() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.END_CARD, 1),
        (Label.BLANK, 2),
        (Label.CREDIT, 15),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 13
    assert decision.onset_kind == "credit"


def test_end_card_is_not_promoted_when_credits_are_more_than_fifteen_seconds_away() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.END_CARD, 2),
        (Label.FOOTAGE, 24),
        (Label.CREDIT, 15),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 36
    assert decision.onset_kind == "credit"


def test_terminal_end_card_followed_only_by_blank_is_an_onset() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.END_CARD, 2),
        (Label.BLANK, 10),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 10
    assert decision.onset_kind == "end_card"
    assert _states(decision) == ["PRE"] * 10 + ["CREDIT"] * 2 + ["GAP"] * 10


def test_terminal_end_card_exception_requires_real_stream_eof() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.END_CARD, 2),
        (Label.BLANK, 3),
    )

    decision = decode_timeline(observations, CFG, at_stream_eof=False)

    assert decision.status == "NOT_FOUND"
    _assert_fail_closed(decision)


def test_terminal_end_card_after_sustained_credits_does_not_create_second_candidate() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.CREDIT, 15),
        (Label.BLANK, 3),
        (Label.END_CARD, 2),
        (Label.BLANK, 5),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 10
    assert decision.candidate_starts == [10]


def test_diegetic_the_end_text_does_not_override_semantic_label() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.DIEGETIC_TEXT, 3),
        (Label.FOOTAGE, 5),
        (Label.CREDIT, 15),
    )
    for observation in observations[10:13]:
        observation.metadata["raw_text"] = "THE END"

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 18
    assert decision.onset_kind == "credit"


@pytest.mark.parametrize(
    ("parts", "earliest"),
    [
        (((Label.CREDIT, 30),), 0),
        (((Label.BLANK, 4), (Label.CREDIT, 20)), 4),
    ],
)
def test_credit_without_observed_pre_context_is_left_censored(parts, earliest: int) -> None:
    decision = decode_timeline(_sequence(*parts), CFG)

    assert decision.status == "LEFT_CENSORED"
    assert decision.earliest_credit_pos == earliest
    assert decision.needs_more_context is True
    _assert_fail_closed(decision)


@pytest.mark.parametrize(
    "parts",
    [
        ((Label.FOOTAGE, 30),),
        ((Label.FOOTAGE, 10), (Label.DIEGETIC_TEXT, 8), (Label.FOOTAGE, 12)),
        ((Label.BLANK, 30),),
    ],
)
def test_no_credit_evidence_returns_not_found(parts) -> None:
    decision = decode_timeline(_sequence(*parts), CFG)

    assert decision.status == "NOT_FOUND"
    _assert_fail_closed(decision)


def test_uncertain_proposal_touching_onset_returns_review() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.UNCERTAIN, 8),
        (Label.CREDIT, 18),
        proposal_labels={Label.UNCERTAIN},
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "REVIEW"
    assert decision.provisional_start == 18
    assert decision.review_bracket == [10, 18]
    _assert_fail_closed(decision)


def test_persistent_overlap_disagreement_at_onset_returns_review() -> None:
    observations = _sequence((Label.FOOTAGE, 10), (Label.CREDIT, 30))
    for pos in range(10, 18):
        observations.append(
            Observation(
                pos=pos,
                frame_no=pos + 1,
                label=Label.DIEGETIC_TEXT,
                confidence=0.95,
                call_id="overlap-query-b",
            )
        )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "REVIEW"
    assert decision.provisional_start == 18
    assert decision.review_bracket == [10, 18]
    _assert_fail_closed(decision)


def test_missing_vlm_results_at_onset_return_review() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.MISSING, 3),
        (Label.CREDIT, 18),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "REVIEW"
    assert decision.provisional_start == 13
    assert decision.review_bracket == [10, 13]
    _assert_fail_closed(decision)


def test_two_sustained_regimes_beyond_gap_budget_return_review() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.CREDIT, 12),
        (Label.FOOTAGE, 8),
        (Label.CREDIT, 15),
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "REVIEW"
    assert decision.candidate_starts == [10, 30]
    assert decision.review_bracket == [10, 30]
    _assert_fail_closed(decision)


def test_unresolved_terminal_text_proposal_without_credit_returns_review() -> None:
    observations = _sequence(
        (Label.FOOTAGE, 10),
        (Label.UNCERTAIN, 8),
        (Label.FOOTAGE, 10),
        proposal_labels={Label.UNCERTAIN},
    )

    decision = decode_timeline(observations, CFG)

    assert decision.status == "REVIEW"
    assert decision.review_bracket == [10, 17]
    _assert_fail_closed(decision)


def test_all_missing_semantic_results_return_model_error() -> None:
    decision = decode_timeline(_sequence((Label.MISSING, 12)), CFG)

    assert decision.status == "MODEL_ERROR"
    _assert_fail_closed(decision)


@pytest.mark.parametrize(
    "style",
    ["scroll", "overlay", "static_card", "two_column", "rtl", "low_contrast"],
)
@pytest.mark.parametrize("script", ["latin", "arabic", "cyrillic"])
def test_temporal_decoder_is_style_and_script_agnostic(style: str, script: str) -> None:
    observations = _sequence((Label.FOOTAGE, 10), (Label.CREDIT, 18))
    for observation in observations[10:]:
        observation.metadata.update({"style": style, "script": script})

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 10


def test_dense_refinement_handles_non_monotonic_credit_blank_credit_sequence() -> None:
    # Coarse bracket is [50, 70].  Frame 60 is BLANK; a raw binary search
    # would move right and report 64.  Dense temporal decoding must retain 51.
    observations = _sequence(
        (Label.FOOTAGE, 51),
        (Label.CREDIT, 9),
        (Label.BLANK, 4),
        (Label.CREDIT, 17),
    )

    decision = decode_timeline(observations, CFG)

    assert observations[50].label == Label.FOOTAGE
    assert observations[60].label == Label.BLANK
    assert observations[70].label == Label.CREDIT
    assert decision.status == "FOUND"
    assert decision.start_pos == 51


def test_late_terminal_onset_maps_zero_based_position_to_one_based_frame_number() -> None:
    observations = _sequence((Label.FOOTAGE, 883), (Label.CREDIT, 17))

    decision = decode_timeline(observations, CFG)

    assert decision.status == "FOUND"
    assert decision.start_pos == 883
    assert decision.start_frame_no == 884


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"total_frames": -1}, "total_frames"),
        ({"total_frames": 10, "fps": 0}, "fps"),
        ({"total_frames": 10, "base_stride_seconds": 0}, "base_stride"),
        (
            {"total_frames": 10, "dense_tail_seconds": 1, "dense_stride_seconds": 0},
            "dense_stride",
        ),
    ],
)
def test_sample_positions_rejects_invalid_configuration(kwargs, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        sample_positions(**kwargs)


def test_make_overlapping_batches_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        make_overlapping_batches([1, 2, 3], batch_size=2, overlap=2)
