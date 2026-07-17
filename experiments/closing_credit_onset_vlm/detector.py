from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Iterable
import uuid

from PIL import Image, ImageDraw, ImageOps

from core.pipelines.ocr.jenerik_frame_pool_detector import (
    DetectorConfig as CvDetectorConfig,
    FrameScore,
    list_images,
    natural_frame_no,
    score_frames,
)

from .models import (
    DetectionConfig,
    DetectionResult,
    DetectionStatus,
    FrameRef,
    Label,
    Observation,
    TemporalDecision,
)
from .ollama_client import OllamaFrameClassifier, VlmBatchResult, VlmCallError
from .temporal import decode_timeline, make_overlapping_batches, sample_positions


SCHEMA_VERSION = "closing-credit-onset-vlm-test/1.0"
_POSITIVE = {Label.CREDIT, Label.END_CARD}
_HARD_NEGATIVE = {Label.FOOTAGE, Label.DIEGETIC_TEXT, Label.STORY_TEXT}


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-zÀ-ž_-]+", "_", value, flags=re.UNICODE).strip("_-")
    return (slug or "film")[:100]


def default_output_dir(frame_dir: Path, root: Path | None = None) -> Path:
    resolved = frame_dir.resolve()
    if resolved.name.lower() == "cikis" and resolved.parent.name.lower() == "frames":
        film_name = resolved.parent.parent.name
    else:
        film_name = resolved.parent.name or resolved.name
    base = (root or Path.cwd()) / "outputs" / "closing_credit_onset_vlm" / _safe_slug(film_name)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = base / stamp
    if candidate.exists():
        candidate = base / f"{stamp}_{uuid.uuid4().hex[:6]}"
    return candidate


def _inside_any_protected_frames_tree(path: Path) -> bool:
    protected_names = {"giris", "cikis", "giris_jenerik", "cikis_jenerik"}
    for candidate in (path, *path.parents):
        if (
            candidate.name.lower() in protected_names
            and candidate.parent.name.lower() == "frames"
        ):
            return True
    return False


def build_frame_refs(frame_dir: Path, fps: float) -> list[FrameRef]:
    paths = list_images(frame_dir)
    return [
        FrameRef(
            pos=position,
            frame_no=natural_frame_no(path),
            path=path,
            timestamp_seconds=position / fps,
        )
        for position, path in enumerate(paths)
    ]


def frame_source_signature(frame_dir: Path, refs: list[FrameRef]) -> dict[str, Any]:
    """Bounded content signature plus complete ordered inventory."""
    resolved = frame_dir.resolve()
    digest = hashlib.sha256()
    total_bytes = 0
    for ref in refs:
        stat = ref.path.stat()
        total_bytes += stat.st_size
        relative = ref.path.relative_to(resolved).as_posix()
        digest.update(f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8"))
    for ref in ([refs[0], refs[-1]] if len(refs) > 1 else refs):
        digest.update(ref.path.name.encode("utf-8"))
        with ref.path.open("rb") as stream:
            digest.update(stream.read())
    return {
        "frame_dir": str(resolved),
        "file_count": len(refs),
        "size_bytes": total_bytes,
        "sig_sha256": digest.hexdigest(),
        "edge_content_hashed": True,
    }


def select_cv_proposals(
    scores: list[FrameScore],
    *,
    fps: float,
    limit: int,
    min_distance_seconds: float,
) -> list[int]:
    """Rank text-change hints; these positions never decide the class."""
    if limit <= 0 or not scores:
        return []
    ranked: list[tuple[float, int]] = []
    previous = 0.0
    for score in scores:
        rise = max(0.0, score.text_score - previous)
        structure = min(1.0, score.line_count / 5.0) * 0.10
        coverage = min(1.0, score.vertical_coverage / 0.35) * 0.08
        motion = min(1.0, abs(score.text_dy) / 8.0) * 0.04
        rank = score.text_score + 0.70 * rise + structure + coverage + motion
        if score.bottom_only:
            rank *= 0.70
        ranked.append((rank, score.pos))
        previous = score.text_score

    minimum_distance = max(1, int(math.floor(fps * min_distance_seconds + 0.5)))
    selected: list[int] = []
    for _rank, position in sorted(ranked, key=lambda item: (-item[0], -item[1])):
        if all(abs(position - existing) >= minimum_distance for existing in selected):
            selected.append(position)
            if len(selected) >= limit:
                break
    return sorted(selected)


def _coarse_groups(
    observations: list[Observation],
    *,
    fps: float,
    total_frames: int,
    min_credit_confidence: float,
    min_end_card_confidence: float,
) -> list[list[Observation]]:
    ordered = sorted(observations, key=lambda item: item.pos)
    positives = [
        item for item in ordered
        if (
            item.label == Label.CREDIT
            and item.confidence >= min_credit_confidence
        ) or (
            item.label == Label.END_CARD
            and item.confidence >= min_end_card_confidence
        )
    ]
    if not positives:
        return []
    max_positive_gap = max(1, int(math.ceil(30.0 * fps)))
    groups: list[list[Observation]] = [[positives[0]]]
    for item in positives[1:]:
        previous = groups[-1][-1]
        between = [
            row for row in ordered
            if previous.pos < row.pos < item.pos and row.label in _HARD_NEGATIVE
        ]
        if item.pos - previous.pos <= max_positive_gap and len(between) <= 1:
            groups[-1].append(item)
        else:
            groups.append([item])

    valid: list[list[Observation]] = []
    eof_distance = max(1, int(math.ceil(12.0 * fps)))
    for group in groups:
        credit_count = sum(item.label == Label.CREDIT for item in group)
        end_count = sum(item.label == Label.END_CARD for item in group)
        high_confidence_tail = (
            group[-1].pos >= total_frames - 1 - eof_distance
            and max(item.confidence for item in group) >= 0.75
        )
        if credit_count >= 2 or end_count >= 1 or high_confidence_tail:
            valid.append(group)
    return valid


def find_coarse_bracket(
    observations: list[Observation],
    *,
    fps: float,
    total_frames: int,
    decoder_config: Any | None = None,
) -> dict[str, Any] | None:
    """Find a *window* for dense scanning, never a final boundary."""
    ordered = sorted(observations, key=lambda item: item.pos)
    min_credit_confidence = float(
        getattr(decoder_config, "min_credit_confidence", 0.60)
    )
    min_end_card_confidence = float(
        getattr(decoder_config, "min_end_card_confidence", 0.65)
    )
    groups = _coarse_groups(
        ordered,
        fps=fps,
        total_frames=total_frames,
        min_credit_confidence=min_credit_confidence,
        min_end_card_confidence=min_end_card_confidence,
    )
    if groups:
        strong_groups = [
            group for group in groups
            if sum(item.label == Label.CREDIT for item in group) >= 2
            or sum(item.label == Label.END_CARD for item in group) >= 2
        ]
        # A lone END_CARD sampled after an already sustained credit group is
        # part of the tail, not a later alternative onset.
        chosen = strong_groups[-1] if strong_groups else groups[-1]
        first = chosen[0]
        report_groups = strong_groups or groups
        prior = [item for item in ordered if item.pos < first.pos]
        left = prior[-1].pos if prior else 0
        return {
            "left": left,
            "right": first.pos,
            "kind": "positive",
            "coarse_candidate_starts": [group[0].pos for group in report_groups],
            # One isolated coarse END_CARD is a refine hint, not evidence for
            # a competing sustained credit island.
            "ambiguous_groups": len(strong_groups) > 1,
        }

    uncertain = [
        item for item in ordered
        if (
            item.label in {Label.UNCERTAIN, Label.MISSING}
            and (item.proposal or item.label == Label.MISSING)
        )
        or (
            item.label == Label.CREDIT
            and item.confidence < min_credit_confidence
        )
        or (
            item.label == Label.END_CARD
            and item.confidence < min_end_card_confidence
        )
    ]
    if uncertain:
        chosen = uncertain[-1]
        prior = [item for item in ordered if item.pos < chosen.pos]
        return {
            "left": prior[-1].pos if prior else 0,
            "right": chosen.pos,
            "kind": "uncertain",
            "coarse_candidate_starts": [],
            "ambiguous_groups": False,
        }
    return None


def refine_positions(
    bracket: dict[str, Any],
    *,
    total_frames: int,
    config: DetectionConfig,
) -> list[int]:
    assert config.decoder is not None
    pre = int(math.ceil(config.fine_pre_seconds * config.fps))
    # Observe enough future to distinguish a short false island from a real
    # credit regime after the allowed blank gap.
    post_seconds = max(
        config.fine_post_seconds,
        config.decoder.confirm_window_seconds
        + config.decoder.max_gap_seconds
        + config.decoder.min_long_credit_seconds,
    )
    post = int(math.ceil(post_seconds * config.fps))
    start = max(0, int(bracket["left"]) - pre)
    end = min(total_frames - 1, int(bracket["right"]) + post)
    values = list(range(start, end + 1))
    if len(values) > config.max_fine_frames:
        values = values[: config.max_fine_frames]
    return values


def merge_observations(
    observations: Iterable[Observation],
    refs_by_pos: dict[int, FrameRef],
    proposal_positions: set[int],
) -> list[Observation]:
    grouped: dict[int, list[Observation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.pos].append(observation)
    merged: list[Observation] = []
    for position in sorted(grouped):
        rows = grouped[position]
        usable = [item for item in rows if item.label != Label.MISSING]
        ref = refs_by_pos[position]
        if not usable:
            merged.append(Observation(
                pos=position,
                frame_no=ref.frame_no,
                file=ref.path.name,
                label=Label.MISSING,
                confidence=0.0,
                stage=rows[0].stage,
                proposal=position in proposal_positions,
                metadata={"votes": [item.to_dict() for item in rows]},
            ))
            continue

        weight: dict[Label, float] = defaultdict(float)
        count: dict[Label, int] = defaultdict(int)
        for item in usable:
            weight[item.label] += max(0.05, item.confidence)
            count[item.label] += 1
        ranking = sorted(weight, key=lambda label: (-weight[label], label.value))
        winner = ranking[0]
        second_weight = weight[ranking[1]] if len(ranking) > 1 else 0.0
        disagreement = len(ranking) > 1
        if disagreement and not (
            count[winner] >= 2 and weight[winner] - second_weight >= 0.35
        ):
            label = Label.UNCERTAIN
            confidence = min(item.confidence for item in usable)
        else:
            label = winner
            winner_rows = [item for item in usable if item.label == winner]
            confidence = sum(item.confidence for item in winner_rows) / len(winner_rows)
        best = max(usable, key=lambda item: item.confidence)
        merged.append(Observation(
            pos=position,
            frame_no=ref.frame_no,
            file=ref.path.name,
            label=label,
            confidence=round(float(confidence), 4),
            stage=best.stage,
            # Semantic uncertainty is itself a refine/review proposal, even
            # when low contrast prevented the cheap CV mask from firing.
            proposal=position in proposal_positions or label == Label.UNCERTAIN,
            text_plane=best.text_plane,
            cue=best.cue,
            call_id=best.call_id,
            metadata={
                "overlap_disagreement": disagreement,
                "vote_labels": [item.label.value for item in rows],
                "missing_votes": sum(item.label == Label.MISSING for item in rows),
            },
        ))
    return merged


def conservative_visual_backtrack(
    decision: TemporalDecision,
    observations: list[Observation],
    scores: list[FrameScore],
    *,
    max_frames: int = 3,
) -> tuple[TemporalDecision, dict[str, Any]]:
    """Recover the first faint/single-line fade-in before semantic certainty.

    CV is allowed to move an already-confirmed semantic boundary by at most
    three extracted frames. It may cross only BLANK/UNCERTAIN observations and
    stops at footage, story text, diegetic text or missing model evidence.
    """
    semantic_start = decision.start_pos
    meta = {
        "semantic_start_pos": semantic_start,
        "visual_start_pos": semantic_start,
        "backtrack_frames": 0,
        "method": "none",
    }
    if decision.status != DetectionStatus.FOUND.value or semantic_start is None:
        return decision, meta
    by_pos = {item.pos: item for item in observations}
    earliest = semantic_start
    for position in range(semantic_start - 1, max(-1, semantic_start - max_frames - 1), -1):
        observation = by_pos.get(position)
        if observation is None or observation.label != Label.UNCERTAIN:
            break
        if not 0 <= position < len(scores):
            break
        score = scores[position]
        previous_density = (
            scores[position - 1].mask_density if position > 0 else 0.0
        )
        structural_trace = (
            score.component_count >= 1
            and score.line_count >= 1
            and score.mask_density >= 0.006
            and score.vertical_coverage >= 0.025
            and (
                score.mask_density - previous_density >= 0.004
                or score.text_score >= 0.14
            )
        )
        visible_in_field = (
            (
                (score.dark_ratio >= 0.70 or score.luma_mean <= 50.0)
                and (
                    score.text_score >= 0.025
                    or score.component_count >= 2
                    or score.mask_density >= 0.010
                )
            )
            or score.text_score >= 0.14
            or (
                observation.label == Label.UNCERTAIN
                and score.mask_density >= 0.010
                and score.vertical_coverage >= 0.035
            )
        )
        if not (structural_trace and visible_in_field):
            break
        earliest = position

    if earliest == semantic_start:
        return decision, meta
    decision.start_pos = earliest
    decision.start_frame_no = scores[earliest].frame_no or earliest + 1
    decision.candidate_starts = [
        earliest if item == semantic_start else item for item in decision.candidate_starts
    ]
    decision.reason += (
        f"; first visible text trace begins {semantic_start - earliest} frame(s) earlier"
    )
    for row in decision.timeline_states:
        if earliest <= int(row.get("pos", -1)) < semantic_start:
            row["state"] = "CREDIT_FADE_IN"
    meta.update({
        "visual_start_pos": earliest,
        "backtrack_frames": semantic_start - earliest,
        "method": "bounded_cv_trace_after_semantic_confirmation",
    })
    return decision, meta


def _write_features(path: Path, scores: list[FrameScore]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    rows = [asdict(score) for score in scores]
    fieldnames = list(rows[0]) if rows else ["pos"]
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_timeline(
    path: Path,
    observations: list[Observation],
    decision: TemporalDecision | None,
) -> None:
    states = {
        int(row["pos"]): str(row["state"])
        for row in ((decision.timeline_states if decision else []) or [])
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "pos", "frame_no", "file", "label", "confidence", "state",
            "text_plane", "cue", "proposal", "stage", "call_id",
        ])
        writer.writeheader()
        for item in observations:
            writer.writerow({
                "pos": item.pos,
                "frame_no": item.frame_no,
                "file": item.file,
                "label": item.label.value,
                "confidence": item.confidence,
                "state": states.get(item.pos, ""),
                "text_plane": item.text_plane,
                "cue": item.cue,
                "proposal": item.proposal,
                "stage": item.stage,
                "call_id": item.call_id,
            })
    temporary.replace(path)


def _write_contact_sheet(
    path: Path,
    refs_by_pos: dict[int, FrameRef],
    observations: list[Observation],
    *,
    columns: int = 4,
) -> None:
    if not observations:
        return
    thumb_width, image_height, label_height = 256, 144, 34
    cell_height = image_height + label_height
    rows = math.ceil(len(observations) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    colors = {
        Label.CREDIT: "#d9f8d9",
        Label.END_CARD: "#fff0a6",
        Label.DIEGETIC_TEXT: "#ffd9d9",
        Label.STORY_TEXT: "#ffe8c4",
        Label.UNCERTAIN: "#e4d9ff",
        Label.MISSING: "#ff78a5",
        Label.BLANK: "#e4e4e4",
        Label.FOOTAGE: "#d9eaff",
    }
    for index, observation in enumerate(observations):
        ref = refs_by_pos[observation.pos]
        x = (index % columns) * thumb_width
        y = (index // columns) * cell_height
        try:
            with Image.open(ref.path) as source:
                image = ImageOps.fit(
                    ImageOps.exif_transpose(source).convert("RGB"),
                    (thumb_width, image_height),
                    method=Image.Resampling.LANCZOS,
                )
            sheet.paste(image, (x, y))
        except Exception:  # noqa: BLE001
            draw.rectangle((x, y, x + thumb_width - 1, y + image_height - 1), fill="#333333")
        draw.rectangle(
            (x, y + image_height, x + thumb_width - 1, y + cell_height - 1),
            fill=colors.get(observation.label, "white"),
        )
        draw.text(
            (x + 4, y + image_height + 3),
            f"pos={observation.pos} frame={observation.frame_no} {observation.label.value}",
            fill="black",
        )
        draw.text(
            (x + 4, y + image_height + 18),
            f"conf={observation.confidence:.2f} {observation.text_plane}",
            fill="black",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="JPEG", quality=88)


class ClosingCreditOnsetDetector:
    """Experimental semantic coarse-to-fine detector.

    It has no method that writes or replaces ``frames/cikis_jenerik``.
    """

    def __init__(
        self,
        config: DetectionConfig,
        *,
        classifier: OllamaFrameClassifier | Any | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.classifier = classifier or OllamaFrameClassifier(
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

    def _classify_positions(
        self,
        positions: list[int],
        *,
        refs_by_pos: dict[int, FrameRef],
        stage: str,
        overlap: int,
        calls_path: Path,
        proposal_positions: set[int],
        deadline: float,
    ) -> tuple[list[Observation], int]:
        raw: list[Observation] = []
        failures = 0
        for batch in make_overlapping_batches(
            positions,
            batch_size=self.config.batch_size,
            overlap=overlap,
        ):
            refs = [refs_by_pos[position] for position in batch]
            try:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    raise VlmCallError(
                        "film wall-time budget exhausted before VLM batch",
                        record={
                            "call_id": f"{stage}-budget-exhausted",
                            "stage": stage,
                            "frame_positions": batch,
                            "ok": False,
                            "error_kind": "wall_time_budget",
                            "error": "film wall-time budget exhausted",
                        },
                    )
                if isinstance(self.classifier, OllamaFrameClassifier):
                    result = self.classifier.classify(
                        refs,
                        stage=stage,
                        time_budget_seconds=remaining,
                    )
                else:
                    result = self.classifier.classify(refs, stage=stage)
                _append_jsonl(calls_path, result.call_record)
                raw.extend(result.observations)
            except VlmCallError as exc:
                failures += 1
                _append_jsonl(calls_path, exc.record or {
                    "stage": stage,
                    "frame_positions": batch,
                    "ok": False,
                    "error": str(exc),
                })
                for ref in refs:
                    raw.append(Observation(
                        pos=ref.pos,
                        frame_no=ref.frame_no,
                        file=ref.path.name,
                        label=Label.MISSING,
                        confidence=0.0,
                        stage=stage,
                        proposal=ref.pos in proposal_positions,
                        metadata={"error": str(exc)},
                    ))
        return merge_observations(raw, refs_by_pos, proposal_positions), failures

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
        out = (output_dir or default_output_dir(frame_dir)).resolve()
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
                "output directory must be outside the source frames tree; "
                f"refusing unsafe path: {out}"
            )
        out.mkdir(parents=True, exist_ok=False)
        calls_path = out / "calls.jsonl"
        signature_before = frame_source_signature(frame_dir, refs)

        model_identity: dict[str, Any]
        try:
            identity_fn = getattr(self.classifier, "model_identity", None)
            model_identity = identity_fn() if callable(identity_fn) else {"requested_name": self.config.model}
            capabilities = model_identity.get("capabilities") or []
            if capabilities and "vision" not in capabilities:
                raise ValueError(
                    f"model has no vision capability: {self.config.model} ({capabilities})"
                )
        except Exception as exc:  # noqa: BLE001
            preflight_error = f"{type(exc).__name__}: {exc}"
            manifest_path = out / "run_manifest.json"
            result = DetectionResult(
                schema_version=SCHEMA_VERSION,
                status=DetectionStatus.MODEL_ERROR.value,
                frame_dir=str(frame_dir),
                output_dir=str(out),
                total_frames=len(refs),
                fps=self.config.fps,
                reason=f"Ollama/model preflight failed: {preflight_error}",
                source_signature=signature_before,
                config=self.config.to_dict(),
                metrics={"total_wall_seconds": round(time.perf_counter() - started, 3)},
                artifacts={
                    "result": str(out / "result.json"),
                    "manifest": str(manifest_path),
                },
            )
            _atomic_write_json(manifest_path, {
                "schema_version": SCHEMA_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "frame_source_before": signature_before,
                "model": {"requested_name": self.config.model},
                "model_preflight_error": preflight_error,
                "config": self.config.to_dict(),
                "result_path": str(out / "result.json"),
            })
            _atomic_write_json(out / "result.json", result.to_dict())
            return result

        cv_started = time.perf_counter()
        cv_config = CvDetectorConfig(max_width=self.config.cv_width, ocr_mode="none")
        cv_paths, scores, masks = score_frames(frame_dir, cv_config)
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
        proposal_set = set(proposals)
        coarse_positions = sample_positions(
            len(refs),
            fps=self.config.fps,
            base_stride_seconds=self.config.base_stride_seconds,
            dense_tail_seconds=self.config.dense_tail_seconds,
            dense_stride_seconds=self.config.dense_stride_seconds,
            proposal_positions=proposals,
        )
        coarse, coarse_failures = self._classify_positions(
            coarse_positions,
            refs_by_pos=refs_by_pos,
            stage="coarse",
            overlap=0,
            calls_path=calls_path,
            proposal_positions=proposal_set,
            deadline=deadline,
        )
        _atomic_write_json(out / "coarse_observations.json", [item.to_dict() for item in coarse])
        _write_contact_sheet(out / "coarse_contact_sheet.jpg", refs_by_pos, coarse)

        bracket = find_coarse_bracket(
            coarse,
            fps=self.config.fps,
            total_frames=len(refs),
            decoder_config=self.config.decoder,
        )
        fine: list[Observation] = []
        fine_failures = 0
        boundary_refinement: dict[str, Any] = {
            "semantic_start_pos": None,
            "visual_start_pos": None,
            "backtrack_frames": 0,
            "method": "none",
        }
        decision: TemporalDecision
        if bracket is None:
            missing_count = sum(item.label == Label.MISSING for item in coarse)
            status = (
                DetectionStatus.MODEL_ERROR.value
                if missing_count
                else DetectionStatus.NOT_FOUND.value
            )
            decision = TemporalDecision(
                status=status,
                reason=(
                    "coarse VLM evidence incomplete"
                    if missing_count
                    else "coarse semantic scan found no credit or unresolved proposal"
                ),
            )
        else:
            dense_positions = refine_positions(
                bracket,
                total_frames=len(refs),
                config=self.config,
            )
            fine, fine_failures = self._classify_positions(
                dense_positions,
                refs_by_pos=refs_by_pos,
                stage="fine",
                overlap=self.config.fine_overlap,
                calls_path=calls_path,
                proposal_positions=proposal_set,
                deadline=deadline,
            )
            assert self.config.decoder is not None
            decision = decode_timeline(
                fine,
                self.config.decoder,
                at_stream_eof=dense_positions[-1] == len(refs) - 1,
            )
            # A false early coarse positive can leave fewer than the required
            # 8 seconds of the real terminal credit regime at the right edge.
            # Extend linearly (never binary-search) only while the refined tail
            # still contains credit/uncertain evidence, under a hard cap.
            initial_fine_start = dense_positions[0]
            max_fine_end = min(
                len(refs) - 1,
                initial_fine_start + self.config.max_fine_frames - 1,
            )
            extension_frames = max(
                self.config.batch_size,
                int(math.ceil(self.config.fine_extension_seconds * self.config.fps)),
            )
            while (
                decision.status == DetectionStatus.NOT_FOUND.value
                and dense_positions[-1] < max_fine_end
                and any(
                    item.label in {Label.CREDIT, Label.END_CARD, Label.UNCERTAIN, Label.MISSING}
                    for item in fine[-max(1, int(math.ceil(
                        self.config.decoder.min_long_credit_seconds * self.config.fps
                    ))) :]
                )
            ):
                new_start = dense_positions[-1] + 1
                new_end = min(max_fine_end, new_start + extension_frames - 1)
                new_positions = list(range(new_start, new_end + 1))
                query_positions = dense_positions[-self.config.fine_overlap :] + new_positions
                extension, extension_failures = self._classify_positions(
                    query_positions,
                    refs_by_pos=refs_by_pos,
                    stage="fine_extension",
                    overlap=self.config.fine_overlap,
                    calls_path=calls_path,
                    proposal_positions=proposal_set,
                    deadline=deadline,
                )
                fine_failures += extension_failures
                fine = merge_observations(
                    [*fine, *extension], refs_by_pos, proposal_set
                )
                dense_positions.extend(new_positions)
                decision = decode_timeline(
                    fine,
                    self.config.decoder,
                    at_stream_eof=dense_positions[-1] == len(refs) - 1,
                )
            if bracket.get("kind") == "uncertain" and decision.status == DetectionStatus.NOT_FOUND.value:
                decision = TemporalDecision(
                    status=DetectionStatus.REVIEW.value,
                    provisional_start=int(bracket["right"]),
                    review_bracket=[int(bracket["left"]), int(bracket["right"])],
                    reason="coarse unresolved proposal was not confirmed in dense scan",
                    timeline_states=decision.timeline_states,
                )
            if (
                bracket.get("ambiguous_groups")
                and decision.status != DetectionStatus.MODEL_ERROR.value
            ):
                coarse_starts = list(bracket.get("coarse_candidate_starts") or [])
                decision = TemporalDecision(
                    status=DetectionStatus.REVIEW.value,
                    provisional_start=(
                        decision.start_pos
                        or decision.provisional_start
                        or int(bracket["right"])
                    ),
                    earliest_credit_pos=decision.earliest_credit_pos,
                    onset_kind=decision.onset_kind,
                    candidate_starts=coarse_starts,
                    review_bracket=[
                        int((coarse_starts or [bracket["left"]])[0]),
                        int((coarse_starts or [bracket["right"]])[-1]),
                    ],
                    reason=(
                        "multiple separated coarse credit groups require review; "
                        f"dense_status={decision.status}"
                    ),
                    timeline_states=decision.timeline_states,
                )
            if (coarse_failures or fine_failures) and decision.status == DetectionStatus.FOUND.value:
                missing_positions = sorted({
                    item.pos for item in coarse + fine if item.label == Label.MISSING
                })
                decision = TemporalDecision(
                    status=DetectionStatus.REVIEW.value,
                    provisional_start=decision.start_pos,
                    earliest_credit_pos=decision.earliest_credit_pos,
                    onset_kind=decision.onset_kind,
                    candidate_starts=decision.candidate_starts,
                    review_bracket=(
                        [missing_positions[0], missing_positions[-1]]
                        if missing_positions else decision.review_bracket
                    ),
                    reason="one or more VLM batches failed; FOUND suppressed fail-closed",
                    timeline_states=decision.timeline_states,
                )

            decision, boundary_refinement = conservative_visual_backtrack(
                decision,
                fine,
                scores,
            )

        _atomic_write_json(out / "fine_observations.json", [item.to_dict() for item in fine])
        _write_timeline(out / "timeline.csv", fine or coarse, decision)
        if fine:
            _write_contact_sheet(out / "fine_contact_sheet.jpg", refs_by_pos, fine)

        refs_after = build_frame_refs(frame_dir, self.config.fps)
        signature_after = frame_source_signature(frame_dir, refs_after)
        source_drift = signature_before["sig_sha256"] != signature_after["sig_sha256"]
        if source_drift:
            provisional = decision.start_pos or decision.provisional_start
            decision = TemporalDecision(
                status=DetectionStatus.REVIEW.value,
                provisional_start=provisional,
                reason="source frame set changed while detector was running",
                timeline_states=decision.timeline_states,
            )

        # A pure temporal FOUND is publishable evidence, but this experiment
        # never has authority to mutate the production pool. Keep the same
        # value in result.json *and* run_manifest.json.
        decision.pool_may_be_replaced = False

        start_ref = refs_by_pos.get(decision.start_pos) if decision.start_pos is not None else None
        start_confidences = [
            item.confidence for item in fine
            if decision.start_pos is not None
            and decision.start_pos <= item.pos <= decision.start_pos + int(self.config.fps * 12)
            and item.label in {Label.CREDIT, Label.END_CARD}
        ]
        confidence = (
            sum(start_confidences) / len(start_confidences)
            if start_confidences else 0.0
        )
        artifacts = {
            "result": str(out / "result.json"),
            "calls": str(calls_path),
            "features": str(out / "features.csv"),
            "coarse_observations": str(out / "coarse_observations.json"),
            "fine_observations": str(out / "fine_observations.json"),
            "timeline": str(out / "timeline.csv"),
            "coarse_contact_sheet": str(out / "coarse_contact_sheet.jpg"),
        }
        if fine:
            artifacts["fine_contact_sheet"] = str(out / "fine_contact_sheet.jpg")
        result = DetectionResult(
            schema_version=SCHEMA_VERSION,
            status=decision.status,
            frame_dir=str(frame_dir),
            output_dir=str(out),
            total_frames=len(refs),
            fps=self.config.fps,
            start_pos=decision.start_pos,
            start_frame_no=(start_ref.frame_no if start_ref else None),
            start_file=(start_ref.path.name if start_ref else None),
            start_time_seconds=(start_ref.timestamp_seconds if start_ref else None),
            onset_kind=decision.onset_kind,
            confidence=round(confidence, 4),
            publishable=decision.publishable,
            # Deliberately false: this test package has no production authority.
            pool_may_be_replaced=False,
            needs_more_context=decision.needs_more_context,
            provisional_start=decision.provisional_start,
            review_bracket=decision.review_bracket,
            candidate_starts=decision.candidate_starts,
            reason=decision.reason,
            source_signature=signature_after,
            config=self.config.to_dict(),
            metrics={
                "model_identity": model_identity,
                "cv_seconds": round(cv_seconds, 3),
                "coarse_sample_count": len(coarse_positions),
                "fine_sample_count": len(fine),
                "cv_proposal_count": len(proposals),
                "coarse_failed_batches": coarse_failures,
                "fine_failed_batches": fine_failures,
                "source_drift": source_drift,
                "boundary_refinement": boundary_refinement,
                "max_wall_seconds": self.config.max_wall_seconds,
                "wall_budget_exhausted": time.perf_counter() >= deadline,
                "total_wall_seconds": round(time.perf_counter() - started, 3),
            },
            artifacts=artifacts,
        )
        _atomic_write_json(out / "result.json", result.to_dict())
        _atomic_write_json(out / "run_manifest.json", {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "frame_source_before": signature_before,
            "frame_source_after": signature_after,
            "model": model_identity,
            "config": self.config.to_dict(),
            "cv_proposals": proposals,
            "coarse_positions": coarse_positions,
            "coarse_bracket": bracket,
            "decision": decision.to_dict(),
            "result_path": str(out / "result.json"),
        })
        result.artifacts["manifest"] = str(out / "run_manifest.json")
        _atomic_write_json(out / "result.json", result.to_dict())
        return result


__all__ = [
    "ClosingCreditOnsetDetector",
    "build_frame_refs",
    "conservative_visual_backtrack",
    "default_output_dir",
    "find_coarse_bracket",
    "frame_source_signature",
    "merge_observations",
    "refine_positions",
    "select_cv_proposals",
]
