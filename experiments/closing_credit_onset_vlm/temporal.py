from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Iterable, Sequence

from .models import DecoderConfig, DetectionStatus, Label, Observation, TemporalDecision


_PRE_LABELS = {Label.FOOTAGE, Label.DIEGETIC_TEXT, Label.STORY_TEXT}
_AMBIGUOUS_LABELS = {Label.UNCERTAIN, Label.MISSING}


def _round_half_up(value: float) -> int:
    """Round a non-negative frame coordinate without Python's bankers rounding."""

    if value < 0:
        raise ValueError("frame coordinate must be non-negative")
    return int(math.floor(value + 0.5))


def sample_positions(
    total_frames: int,
    *,
    fps: float = 1.5,
    base_stride_seconds: float = 15.0,
    dense_tail_seconds: float = 90.0,
    dense_stride_seconds: float = 4.0,
    proposal_positions: Iterable[int] | None = None,
    proposals: Iterable[int] | None = None,
) -> list[int]:
    """Build the deterministic coarse VLM schedule.

    Sampling is a union, never a CV gate: the global cadence and dense terminal
    cadence remain present when there are no text proposals.  The logical
    window duration is ``total_frames / fps``; this preserves the requested
    600-second contract for 900 frames extracted at 1.5 fps.

    ``proposals`` is accepted as an integration-friendly alias for
    ``proposal_positions``.
    """

    if total_frames < 0:
        raise ValueError("total_frames must be >= 0")
    if total_frames == 0:
        return []
    if fps <= 0:
        raise ValueError("fps must be > 0")
    if base_stride_seconds <= 0:
        raise ValueError("base_stride_seconds must be > 0")
    if dense_tail_seconds < 0:
        raise ValueError("dense_tail_seconds must be >= 0")
    if dense_tail_seconds > 0 and dense_stride_seconds <= 0:
        raise ValueError("dense_stride_seconds must be > 0 when dense tail sampling is enabled")

    duration_seconds = total_frames / fps
    selected = {0, total_frames - 1}

    def add_schedule(start_seconds: float, stride_seconds: float) -> None:
        # Integer loop counters avoid cumulative floating-point drift.
        step = 0
        while True:
            target_seconds = max(0.0, start_seconds) + step * stride_seconds
            if target_seconds >= duration_seconds - 1e-12:
                break
            position = _round_half_up(target_seconds * fps)
            selected.add(min(total_frames - 1, position))
            step += 1

    add_schedule(0.0, base_stride_seconds)
    if dense_tail_seconds > 0:
        add_schedule(max(0.0, duration_seconds - dense_tail_seconds), dense_stride_seconds)

    for source in (proposal_positions, proposals):
        if source is None:
            continue
        for raw_position in source:
            try:
                position = int(raw_position)
            except (TypeError, ValueError):
                continue
            if 0 <= position < total_frames:
                selected.add(position)

    return sorted(selected)


def make_overlapping_batches(
    positions: Sequence[int],
    *,
    batch_size: int = 8,
    overlap: int = 2,
) -> list[list[int]]:
    """Split positions into bounded batches while retaining temporal overlap."""

    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    if overlap < 0 or overlap >= batch_size:
        raise ValueError("overlap must satisfy 0 <= overlap < batch_size")
    if not positions:
        return []

    step = batch_size - overlap
    values = list(positions)
    batches: list[list[int]] = []
    start = 0
    while start < len(values):
        batches.append(values[start : start + batch_size])
        if start + batch_size >= len(values):
            break
        start += step
    return batches


@dataclass
class _Regime:
    start_idx: int
    end_idx: int
    credit_indices: list[int]
    valid: bool


@dataclass
class _Candidate:
    start_idx: int
    end_idx: int
    credit_indices: list[int]
    onset_kind: str = "credit"
    terminal_end_card: bool = False


def _normalise_observations(observations: Iterable[Observation]) -> list[Observation]:
    """Sort observations and collapse overlapping-query duplicates safely."""

    grouped: dict[int, list[Observation]] = {}
    for observation in observations:
        if observation.pos < 0:
            raise ValueError("observation positions must be >= 0")
        grouped.setdefault(observation.pos, []).append(observation)

    result: list[Observation] = []
    for position in sorted(grouped):
        group = grouped[position]
        usable = [item for item in group if item.label != Label.MISSING]
        labels = {item.label for item in usable}
        if not usable:
            result.append(max(group, key=lambda item: item.confidence))
            continue
        if len(labels) == 1:
            result.append(max(usable, key=lambda item: item.confidence))
            continue

        best = max(usable, key=lambda item: item.confidence)
        metadata = dict(best.metadata)
        metadata.update(
            {
                "overlap_disagreement": True,
                "overlap_labels": sorted(label.value for label in labels),
            }
        )
        result.append(
            Observation(
                pos=position,
                label=Label.UNCERTAIN,
                confidence=min(item.confidence for item in usable),
                frame_no=best.frame_no,
                file=best.file,
                stage=best.stage,
                # An overlap disagreement is itself a boundary proposal: if
                # it persists, the decoder must surface REVIEW rather than
                # silently treating it as footage.
                proposal=True,
                text_plane=best.text_plane,
                cue=best.cue,
                call_id=best.call_id,
                metadata=metadata,
            )
        )
    return result


def _apply_confidence_floor(
    observations: list[Observation], config: DecoderConfig
) -> list[Observation]:
    """Turn low-confidence categorical claims into explicit uncertainty."""
    result: list[Observation] = []
    for item in observations:
        if item.label in {Label.MISSING, Label.UNCERTAIN}:
            result.append(item)
            continue
        if item.label == Label.CREDIT:
            threshold = config.min_credit_confidence
        elif item.label == Label.END_CARD:
            threshold = config.min_end_card_confidence
        else:
            threshold = config.min_other_confidence
        if item.confidence >= threshold:
            result.append(item)
            continue
        metadata = dict(item.metadata)
        metadata.update({
            "low_confidence_original_label": item.label.value,
            "low_confidence_threshold": threshold,
        })
        result.append(replace(
            item,
            label=Label.UNCERTAIN,
            proposal=True,
            metadata=metadata,
        ))
    return result


def _build_regimes(observations: list[Observation], config: DecoderConfig) -> list[_Regime]:
    max_gap_frames = max(0, int(math.floor(config.max_gap_seconds * config.fps + 1e-9)))
    confirm_frames = max(1, int(math.ceil(config.confirm_window_seconds * config.fps)))
    long_credit_frames = max(1, int(math.ceil(config.min_long_credit_seconds * config.fps)))
    regimes: list[_Regime] = []

    index = 0
    while index < len(observations):
        if observations[index].label != Label.CREDIT:
            index += 1
            continue

        start_idx = index
        cursor = index
        end_idx = index
        credit_indices: list[int] = []

        while cursor < len(observations):
            label = observations[cursor].label
            if label == Label.CREDIT:
                credit_indices.append(cursor)
                end_idx = cursor
                cursor += 1
                continue
            if label == Label.END_CARD:
                # END_CARD within an established regime is credit-state evidence,
                # but does not count toward the visible-name duration threshold.
                end_idx = cursor
                cursor += 1
                continue
            if label != Label.BLANK:
                break

            gap_start = cursor
            while cursor < len(observations) and observations[cursor].label == Label.BLANK:
                cursor += 1
            gap_length = cursor - gap_start
            if (
                gap_length <= max_gap_frames
                and cursor < len(observations)
                and observations[cursor].label in {Label.CREDIT, Label.END_CARD}
            ):
                continue
            break

        confirm_end = min(len(observations), start_idx + confirm_frames)
        confirm_hits = sum(
            1 for item in observations[start_idx:confirm_end] if item.label == Label.CREDIT
        )
        valid = len(credit_indices) >= long_credit_frames and confirm_hits >= config.min_credit_hits
        regimes.append(
            _Regime(
                start_idx=start_idx,
                end_idx=end_idx,
                credit_indices=credit_indices,
                valid=valid,
            )
        )
        index = max(start_idx + 1, cursor)

    return regimes


def _end_card_runs(observations: list[Observation]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(observations):
        if observations[index].label != Label.END_CARD:
            index += 1
            continue
        end = index
        while end + 1 < len(observations) and observations[end + 1].label == Label.END_CARD:
            end += 1
        runs.append((index, end))
        index = end + 1
    return runs


def _build_candidates(
    observations: list[Observation],
    regimes: list[_Regime],
    config: DecoderConfig,
    *,
    at_stream_eof: bool,
) -> list[_Candidate]:
    candidates = [
        _Candidate(item.start_idx, item.end_idx, list(item.credit_indices))
        for item in regimes
        if item.valid
    ]
    end_runs = [
        run
        for run in _end_card_runs(observations)
        if run[1] - run[0] + 1 >= config.end_card_min_frames
    ]
    used_end_runs: set[tuple[int, int]] = set()

    # Promote a qualifying THE END card to the onset of the following credit
    # regime.  Compare real timestamps rather than rounding 15 seconds to an
    # ambiguous integer frame count.
    for candidate in candidates:
        eligible = []
        for run in end_runs:
            if run[1] >= candidate.start_idx:
                continue
            between = observations[run[1] + 1 : candidate.start_idx]
            if any(item.label not in {Label.BLANK, Label.UNCERTAIN} for item in between):
                # A THE END sign/card followed by real footage must not pull a
                # later credit sequence backwards merely because it is close.
                continue
            elapsed = (
                observations[candidate.start_idx].pos - observations[run[1]].pos
            ) / config.fps
            if elapsed <= config.end_card_follow_seconds + 1e-9:
                eligible.append(run)
        if eligible:
            chosen = eligible[-1]
            candidate.start_idx = chosen[0]
            candidate.onset_kind = "end_card"
            used_end_runs.add(chosen)

    # A terminal END_CARD followed only by blank/end-card frames is valid even
    # without a conventional name list, provided the observed tail ends soon.
    for run in end_runs:
        if run in used_end_runs:
            continue
        # END_CARD-at-EOF is an exception for tails with no conventional
        # credit regime.  When credits were already sustained, a later end
        # card belongs to that closing regime and must not create candidate #2.
        if candidates:
            continue
        tail = observations[run[1] + 1 :]
        terminal_tail = all(item.label in {Label.BLANK, Label.END_CARD} for item in tail)
        elapsed_to_eof = (
            0.0
            if not tail
            else (observations[-1].pos - observations[run[1]].pos) / config.fps
        )
        if (
            at_stream_eof
            and terminal_tail
            and elapsed_to_eof <= config.end_card_follow_seconds + 1e-9
        ):
            candidates.append(
                _Candidate(
                    start_idx=run[0],
                    end_idx=len(observations) - 1,
                    credit_indices=[],
                    onset_kind="end_card",
                    terminal_end_card=True,
                )
            )

    candidates.sort(key=lambda item: observations[item.start_idx].pos)
    return candidates


def _timeline(
    observations: list[Observation],
    candidates: list[_Candidate],
) -> list[dict[str, object]]:
    states = ["PRE"] * len(observations)
    for candidate in candidates:
        for index in range(candidate.start_idx, candidate.end_idx + 1):
            if observations[index].label in {Label.CREDIT, Label.END_CARD}:
                states[index] = "CREDIT"
            else:
                states[index] = "GAP"

        post_started = False
        for index in range(candidate.end_idx + 1, len(observations)):
            if observations[index].label in _PRE_LABELS:
                post_started = True
            if post_started:
                states[index] = "POST"
            elif observations[index].label in {Label.BLANK, Label.END_CARD}:
                states[index] = "GAP"

    return [
        {
            "pos": observation.pos,
            "label": observation.label.value,
            "state": states[index],
        }
        for index, observation in enumerate(observations)
    ]


def _first_credit_position(observations: list[Observation]) -> int | None:
    for observation in observations:
        if observation.label == Label.CREDIT:
            return observation.pos
    return None


def _ambiguous_prefix(
    observations: list[Observation],
    candidate: _Candidate,
    config: DecoderConfig,
) -> tuple[bool, list[int] | None, str | None]:
    end = candidate.start_idx - 1
    if end < 0 or observations[end].label not in _AMBIGUOUS_LABELS:
        return False, None, None
    start = end
    while start > 0 and observations[start - 1].label in _AMBIGUOUS_LABELS:
        start -= 1
    run = observations[start : end + 1]
    if any(item.label == Label.MISSING for item in run):
        return True, [observations[start].pos, observations[candidate.start_idx].pos], "missing VLM evidence at boundary"

    review_frames = max(1, int(math.ceil(config.uncertain_review_seconds * config.fps)))
    if len(run) >= review_frames and any(item.proposal for item in run):
        return True, [observations[start].pos, observations[candidate.start_idx].pos], "uncertain proposal touches boundary"
    return False, None, None


def _unresolved_run(
    observations: list[Observation], config: DecoderConfig
) -> tuple[list[int] | None, str | None]:
    review_frames = max(1, int(math.ceil(config.uncertain_review_seconds * config.fps)))
    index = 0
    while index < len(observations):
        if observations[index].label not in _AMBIGUOUS_LABELS:
            index += 1
            continue
        end = index
        while end + 1 < len(observations) and observations[end + 1].label in _AMBIGUOUS_LABELS:
            end += 1
        run = observations[index : end + 1]
        if any(item.label == Label.MISSING for item in run):
            return [observations[index].pos, observations[end].pos], "missing VLM evidence"
        if len(run) >= review_frames and any(item.proposal for item in run):
            return [observations[index].pos, observations[end].pos], "unresolved uncertain text proposal"
        index = end + 1
    return None, None


def decode_timeline(
    observations: Iterable[Observation],
    config: DecoderConfig | None = None,
    *,
    at_stream_eof: bool = True,
) -> TemporalDecision:
    """Decode refined semantic observations into a fail-closed onset decision.

    The decoder deliberately avoids binary-search monotonicity assumptions.
    It accepts persistent CREDIT regimes, bridges bounded BLANK gaps, rejects
    diegetic/story text regardless of CV/OCR density, and makes ambiguity
    explicit through LEFT_CENSORED/REVIEW/MODEL_ERROR statuses.
    """

    cfg = config or DecoderConfig()
    cfg.validate()
    ordered = _apply_confidence_floor(_normalise_observations(observations), cfg)
    if not ordered:
        return TemporalDecision(
            status=DetectionStatus.NOT_FOUND.value,
            reason="no observations",
            timeline_states=[],
        )

    if any(right.pos != left.pos + 1 for left, right in zip(ordered, ordered[1:])):
        return TemporalDecision(
            status=DetectionStatus.MODEL_ERROR.value,
            reason="temporal decoder requires a dense consecutive frame window",
            timeline_states=_timeline(ordered, []),
        )

    if all(item.label == Label.MISSING for item in ordered):
        return TemporalDecision(
            status=DetectionStatus.MODEL_ERROR.value,
            reason="all semantic observations are missing",
            timeline_states=_timeline(ordered, []),
        )

    regimes = _build_regimes(ordered, cfg)
    candidates = _build_candidates(
        ordered,
        regimes,
        cfg,
        at_stream_eof=at_stream_eof,
    )
    earliest_credit_pos = _first_credit_position(ordered)
    timeline = _timeline(ordered, candidates)

    if len(candidates) > 1:
        starts = [ordered[item.start_idx].pos for item in candidates]
        return TemporalDecision(
            status=DetectionStatus.REVIEW.value,
            earliest_credit_pos=earliest_credit_pos,
            candidate_starts=starts,
            review_bracket=[starts[0], starts[-1]],
            reason="multiple sustained credit regimes separated beyond the gap budget",
            timeline_states=timeline,
        )

    if not candidates:
        bracket, unresolved_reason = _unresolved_run(ordered, cfg)
        if bracket is not None:
            status = (
                DetectionStatus.MODEL_ERROR.value
                if unresolved_reason == "missing VLM evidence"
                else DetectionStatus.REVIEW.value
            )
            return TemporalDecision(
                status=status,
                earliest_credit_pos=earliest_credit_pos,
                review_bracket=bracket,
                reason=unresolved_reason or "unresolved semantic evidence",
                timeline_states=timeline,
            )
        return TemporalDecision(
            status=DetectionStatus.NOT_FOUND.value,
            earliest_credit_pos=earliest_credit_pos,
            reason="no sustained semantic credit regime",
            timeline_states=timeline,
        )

    candidate = candidates[0]
    candidate_start = ordered[candidate.start_idx].pos
    ambiguous, review_bracket, ambiguous_reason = _ambiguous_prefix(ordered, candidate, cfg)
    if ambiguous:
        return TemporalDecision(
            status=DetectionStatus.REVIEW.value,
            provisional_start=candidate_start,
            earliest_credit_pos=earliest_credit_pos,
            onset_kind=candidate.onset_kind,
            candidate_starts=[candidate_start],
            review_bracket=review_bracket,
            reason=ambiguous_reason or "ambiguous semantic boundary",
            timeline_states=timeline,
        )

    # Also reject a separate unresolved semantic island elsewhere in the
    # refined window. The boundary-adjacent case above has priority because it
    # includes the candidate edge in its review bracket and remains REVIEW for
    # a recoverable local MISSING run.
    unresolved_bracket, unresolved_reason = _unresolved_run(ordered, cfg)
    if unresolved_bracket is not None:
        status = (
            DetectionStatus.MODEL_ERROR.value
            if unresolved_reason == "missing VLM evidence"
            else DetectionStatus.REVIEW.value
        )
        return TemporalDecision(
            status=status,
            provisional_start=candidate_start,
            earliest_credit_pos=earliest_credit_pos,
            onset_kind=candidate.onset_kind,
            candidate_starts=[candidate_start],
            review_bracket=unresolved_bracket,
            reason=(
                (unresolved_reason or "unresolved semantic evidence")
                + " coexists with a sustained credit regime"
            ),
            timeline_states=timeline,
        )

    # BLANK/END_CARD does not prove that the input contains pre-credit context.
    confident_pre = any(
        item.label in _PRE_LABELS and item.confidence >= 0.5
        for item in ordered[: candidate.start_idx]
    )
    if not confident_pre:
        if earliest_credit_pos is None and candidate.onset_kind == "end_card":
            earliest_credit_pos = candidate_start
        return TemporalDecision(
            status=DetectionStatus.LEFT_CENSORED.value,
            earliest_credit_pos=earliest_credit_pos,
            onset_kind=candidate.onset_kind,
            needs_more_context=True,
            candidate_starts=[candidate_start],
            reason="credit regime begins before any confident PRE evidence",
            timeline_states=timeline,
        )

    start_observation = ordered[candidate.start_idx]
    start_frame_no = (
        start_observation.frame_no
        if start_observation.frame_no is not None
        else start_observation.pos + 1
    )
    return TemporalDecision(
        status=DetectionStatus.FOUND.value,
        start_pos=candidate_start,
        start_frame_no=start_frame_no,
        earliest_credit_pos=earliest_credit_pos,
        onset_kind=candidate.onset_kind,
        publishable=True,
        pool_may_be_replaced=True,
        candidate_starts=[candidate_start],
        reason="persistent semantic credit regime confirmed",
        timeline_states=timeline,
    )


__all__ = ["decode_timeline", "make_overlapping_batches", "sample_positions"]
