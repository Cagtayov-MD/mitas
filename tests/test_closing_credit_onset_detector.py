from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PIL import Image
import pytest

import experiments.closing_credit_onset_vlm.detector as detector_module
import experiments.closing_credit_onset_vlm.ollama_client as ollama_module
import experiments.closing_credit_onset_vlm.cli as cli_module
from experiments.closing_credit_onset_vlm.detector import (
    ClosingCreditOnsetDetector,
    conservative_visual_backtrack,
    find_coarse_bracket,
    merge_observations,
    refine_positions,
)
from experiments.closing_credit_onset_vlm.models import (
    DecoderConfig,
    DetectionConfig,
    FrameRef,
    Label,
    Observation,
    TemporalDecision,
)
from experiments.closing_credit_onset_vlm.ollama_client import (
    OllamaFrameClassifier,
    VlmBatchResult,
    VlmCallError,
)


@dataclass
class _FakeScore:
    """Minimum score shape needed when CV proposals are disabled."""

    pos: int


class _SemanticFakeClassifier:
    """Deterministic classifier used without an Ollama process or socket."""

    def __init__(self, onset: int = 12, *, fail_all: bool = False) -> None:
        self.onset = onset
        self.fail_all = fail_all
        self.calls: list[tuple[str, list[int]]] = []

    def model_identity(self) -> dict[str, Any]:
        return {
            "requested_name": "unit-test/fake-vlm",
            "architecture": "fake",
            "capabilities": ["vision"],
        }

    def classify(self, refs: list[FrameRef], *, stage: str) -> VlmBatchResult:
        positions = [ref.pos for ref in refs]
        self.calls.append((stage, positions))
        if self.fail_all:
            raise VlmCallError(
                "injected test failure",
                record={
                    "call_id": f"fake-{stage}-{len(self.calls)}",
                    "stage": stage,
                    "frame_positions": positions,
                    "ok": False,
                    "error": "injected test failure",
                },
            )

        observations = []
        for ref in refs:
            label = Label.CREDIT if ref.pos >= self.onset else Label.FOOTAGE
            observations.append(
                Observation(
                    pos=ref.pos,
                    frame_no=ref.frame_no,
                    file=ref.path.name,
                    label=label,
                    confidence=0.96,
                    stage=stage,
                    text_plane=(
                        "SCREEN_OVERLAY" if label == Label.CREDIT else "NONE"
                    ),
                    cue=(
                        "CAST_CREW_LIST" if label == Label.CREDIT else "NO_TEXT"
                    ),
                    call_id=f"fake-{stage}-{len(self.calls)}",
                )
            )
        return VlmBatchResult(
            observations=observations,
            call_record={
                "call_id": f"fake-{stage}-{len(self.calls)}",
                "stage": stage,
                "frame_positions": positions,
                "ok": True,
            },
        )


class _ExtensionFakeClassifier(_SemanticFakeClassifier):
    """Coarse onset is early; dense evidence becomes valid after extension."""

    def classify(self, refs: list[FrameRef], *, stage: str) -> VlmBatchResult:
        positions = [ref.pos for ref in refs]
        self.calls.append((stage, positions))
        observations: list[Observation] = []
        for ref in refs:
            if stage == "coarse":
                label = Label.CREDIT if ref.pos >= 40 else Label.FOOTAGE
            else:
                label = (
                    Label.CREDIT
                    if 60 <= ref.pos <= 64 or ref.pos >= 70
                    else Label.FOOTAGE
                )
            observations.append(Observation(
                pos=ref.pos,
                frame_no=ref.frame_no,
                file=ref.path.name,
                label=label,
                confidence=0.96,
                stage=stage,
                call_id=f"extension-{stage}-{len(self.calls)}",
            ))
        return VlmBatchResult(
            observations=observations,
            call_record={
                "call_id": f"extension-{stage}-{len(self.calls)}",
                "stage": stage,
                "frame_positions": positions,
                "ok": True,
            },
        )


class _EndCardWindowFakeClassifier(_SemanticFakeClassifier):
    def classify(self, refs: list[FrameRef], *, stage: str) -> VlmBatchResult:
        positions = [ref.pos for ref in refs]
        self.calls.append((stage, positions))
        observations: list[Observation] = []
        for ref in refs:
            if ref.pos < 100:
                label = Label.FOOTAGE
            elif ref.pos <= 101:
                label = Label.END_CARD
            else:
                label = Label.BLANK
            observations.append(Observation(
                pos=ref.pos,
                frame_no=ref.frame_no,
                file=ref.path.name,
                label=label,
                confidence=0.96,
                stage=stage,
                call_id=f"end-window-{stage}-{len(self.calls)}",
            ))
        return VlmBatchResult(
            observations=observations,
            call_record={
                "call_id": f"end-window-{stage}-{len(self.calls)}",
                "stage": stage,
                "frame_positions": positions,
                "ok": True,
            },
        )


class _AmbiguousCoarseFakeClassifier(_SemanticFakeClassifier):
    def classify(self, refs: list[FrameRef], *, stage: str) -> VlmBatchResult:
        positions = [ref.pos for ref in refs]
        self.calls.append((stage, positions))
        observations: list[Observation] = []
        for ref in refs:
            label = (
                Label.CREDIT
                if stage == "coarse" and ref.pos in {40, 45, 100, 105}
                else Label.FOOTAGE
            )
            observations.append(Observation(
                pos=ref.pos,
                frame_no=ref.frame_no,
                file=ref.path.name,
                label=label,
                confidence=0.96,
                stage=stage,
                call_id=f"ambiguous-{stage}-{len(self.calls)}",
            ))
        return VlmBatchResult(
            observations=observations,
            call_record={
                "call_id": f"ambiguous-{stage}-{len(self.calls)}",
                "stage": stage,
                "frame_positions": positions,
                "ok": True,
            },
        )


class _PreflightFailClassifier(_SemanticFakeClassifier):
    def model_identity(self) -> dict[str, Any]:
        raise RuntimeError("injected preflight failure")


class _HttpResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_HttpResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _make_frames(directory: Path, count: int = 40) -> list[Path]:
    directory.mkdir(parents=True)
    paths: list[Path] = []
    for position in range(count):
        path = directory / f"c_{position + 1:04d}.png"
        Image.new(
            "RGB",
            (48, 32),
            (position % 255, (position * 3) % 255, (position * 7) % 255),
        ).save(path)
        paths.append(path)
    return paths


def _source_snapshot(directory: Path) -> dict[str, tuple[str, bytes]]:
    """Include both directory topology and complete file bytes."""

    snapshot: dict[str, tuple[str, bytes]] = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        snapshot[relative] = (
            "directory" if path.is_dir() else "file",
            b"" if path.is_dir() else path.read_bytes(),
        )
    return snapshot


def _patch_fast_cv(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_score_frames(frame_dir: Path, _config: object):
        paths = detector_module.list_images(Path(frame_dir))
        return paths, [_FakeScore(pos=index) for index in range(len(paths))], []

    monkeypatch.setattr(detector_module, "score_frames", fake_score_frames)


def _test_config() -> DetectionConfig:
    return DetectionConfig(
        fps=1.0,
        model="unit-test/fake-vlm",
        image_width=128,
        batch_size=8,
        fine_overlap=2,
        base_stride_seconds=5.0,
        dense_tail_seconds=20.0,
        dense_stride_seconds=5.0,
        max_cv_proposals=0,
        fine_pre_seconds=4.0,
        fine_post_seconds=10.0,
        max_fine_frames=48,
    )


def _client() -> OllamaFrameClassifier:
    return OllamaFrameClassifier(
        model="unit-test/fake-vlm",
        host="http://ollama.invalid",
        timeout_seconds=1.0,
        keep_alive="0",
        image_width=128,
        jpeg_quality=80,
        num_ctx=1024,
        num_predict=128,
        seed=42,
        temperature=0.0,
        retry_count=1,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"base_stride_seconds": 0.0},
        {"dense_tail_seconds": -1.0},
        {"fine_pre_seconds": -100.0},
        {"cv_width": 0},
        {"timeout_seconds": 0.0},
        {"max_wall_seconds": 0.0},
    ],
)
def test_detection_config_rejects_invalid_runtime_bounds(overrides: dict[str, Any]) -> None:
    config = DetectionConfig(**overrides)
    with pytest.raises(ValueError):
        config.validate()


def test_detection_config_does_not_mutate_shared_decoder() -> None:
    shared = DecoderConfig(fps=9.0)
    first = DetectionConfig(fps=30.0, decoder=shared)
    second = DetectionConfig(fps=1.5, decoder=shared)

    assert shared.fps == 9.0
    assert first.decoder is not None and first.decoder.fps == 30.0
    assert second.decoder is not None and second.decoder.fps == 1.5


def test_cli_reports_invalid_config_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_module.main([
        "--frames", str(tmp_path / "does-not-matter"),
        "--fps", "0",
    ])
    captured = capsys.readouterr()

    assert exit_code == 10
    assert "fps must be > 0" in captured.err
    assert "Traceback" not in captured.err


def test_late_coarse_bracket_and_refinement_cover_870_through_899() -> None:
    # F*883+C*17: the default 900-frame schedule observes F at 879 and C at
    # 885.  Refinement must scan the whole local interval, not binary-search a
    # false monotonic boundary.
    bracket = find_coarse_bracket(
        [
            Observation(pos=879, label=Label.FOOTAGE, confidence=0.97),
            Observation(pos=885, label=Label.CREDIT, confidence=0.96),
        ],
        fps=1.5,
        total_frames=900,
    )

    assert bracket == {
        "left": 879,
        "right": 885,
        "kind": "positive",
        "coarse_candidate_starts": [885],
        "ambiguous_groups": False,
    }
    assert refine_positions(
        bracket,
        total_frames=900,
        config=DetectionConfig(fps=1.5),
    ) == list(range(870, 900))


def test_isolated_terminal_end_card_cannot_replace_earlier_strong_credit_group() -> None:
    bracket = find_coarse_bracket(
        [
            Observation(pos=90, label=Label.FOOTAGE, confidence=0.95),
            Observation(pos=100, label=Label.CREDIT, confidence=0.95),
            Observation(pos=115, label=Label.CREDIT, confidence=0.95),
            Observation(pos=145, label=Label.FOOTAGE, confidence=0.95),
            Observation(pos=180, label=Label.END_CARD, confidence=0.95),
        ],
        fps=1.0,
        total_frames=195,
    )

    assert bracket == {
        "left": 90,
        "right": 100,
        "kind": "positive",
        "coarse_candidate_starts": [100],
        "ambiguous_groups": False,
    }


def test_low_confidence_coarse_credit_cannot_hide_high_confidence_terminal_end() -> None:
    bracket = find_coarse_bracket(
        [
            Observation(pos=90, label=Label.FOOTAGE, confidence=0.95),
            Observation(pos=100, label=Label.CREDIT, confidence=0.10),
            Observation(pos=115, label=Label.CREDIT, confidence=0.10),
            Observation(pos=145, label=Label.FOOTAGE, confidence=0.95),
            Observation(pos=180, label=Label.END_CARD, confidence=0.95),
        ],
        fps=1.0,
        total_frames=195,
    )

    assert bracket == {
        "left": 145,
        "right": 180,
        "kind": "positive",
        "coarse_candidate_starts": [180],
        "ambiguous_groups": False,
    }


def test_low_confidence_coarse_positive_becomes_dense_review_candidate() -> None:
    bracket = find_coarse_bracket(
        [
            Observation(pos=90, label=Label.FOOTAGE, confidence=0.95),
            Observation(pos=100, label=Label.CREDIT, confidence=0.20),
        ],
        fps=1.0,
        total_frames=150,
    )

    assert bracket is not None
    assert bracket["left"] == 90
    assert bracket["right"] == 100
    assert bracket["kind"] == "uncertain"


def test_overlap_label_disagreement_merges_to_uncertain(tmp_path: Path) -> None:
    ref = FrameRef(
        pos=10,
        frame_no=11,
        path=tmp_path / "c_0011.png",
        timestamp_seconds=10.0,
    )
    merged = merge_observations(
        [
            Observation(pos=10, label=Label.CREDIT, confidence=0.95, call_id="a"),
            Observation(
                pos=10,
                label=Label.DIEGETIC_TEXT,
                confidence=0.95,
                call_id="b",
            ),
        ],
        refs_by_pos={10: ref},
        proposal_positions=set(),
    )

    assert len(merged) == 1
    assert merged[0].label == Label.UNCERTAIN
    assert merged[0].metadata["overlap_disagreement"] is True
    assert set(merged[0].metadata["vote_labels"]) == {
        Label.CREDIT.value,
        Label.DIEGETIC_TEXT.value,
    }


def test_visual_backtrack_recovers_faint_first_line_but_never_crosses_diegetic() -> None:
    scores = [
        SimpleNamespace(
            component_count=0,
            line_count=0,
            mask_density=0.0,
            vertical_coverage=0.0,
            dark_ratio=1.0,
            luma_mean=0.0,
            text_score=0.0,
            frame_no=position + 1,
        )
        for position in range(12)
    ]
    scores[8] = SimpleNamespace(
        component_count=1,
        line_count=1,
        mask_density=0.011,
        vertical_coverage=0.04,
        dark_ratio=0.99,
        luma_mean=0.8,
        text_score=0.04,
        frame_no=9,
    )
    decision = TemporalDecision(
        status="FOUND",
        start_pos=9,
        start_frame_no=10,
        publishable=True,
        candidate_starts=[9],
        reason="semantic confirmation",
        timeline_states=[{"pos": pos, "state": "PRE"} for pos in range(12)],
    )
    observations = [
        Observation(pos=pos, label=(Label.UNCERTAIN if pos == 8 else Label.CREDIT))
        for pos in range(8, 12)
    ]

    refined, meta = conservative_visual_backtrack(decision, observations, scores)

    assert refined.start_pos == 8
    assert refined.start_frame_no == 9
    assert meta["backtrack_frames"] == 1
    assert refined.timeline_states[8]["state"] == "CREDIT_FADE_IN"

    blocked = TemporalDecision(status="FOUND", start_pos=9, start_frame_no=10)
    diegetic = [
        Observation(pos=8, label=Label.DIEGETIC_TEXT),
        Observation(pos=9, label=Label.CREDIT),
    ]
    blocked, blocked_meta = conservative_visual_backtrack(blocked, diegetic, scores)
    assert blocked.start_pos == 9
    assert blocked_meta["backtrack_frames"] == 0

    noise_scores = list(scores)
    noise_scores[8] = SimpleNamespace(
        component_count=1,
        line_count=1,
        mask_density=0.002,
        vertical_coverage=0.015,
        dark_ratio=0.90,
        luma_mean=10.0,
        text_score=0.0,
        frame_no=9,
    )
    noise_decision = TemporalDecision(status="FOUND", start_pos=9, start_frame_no=10)
    noise_observations = [
        Observation(pos=8, label=Label.UNCERTAIN),
        Observation(pos=9, label=Label.CREDIT),
    ]
    noise_decision, noise_meta = conservative_visual_backtrack(
        noise_decision, noise_observations, noise_scores
    )
    assert noise_decision.start_pos == 9
    assert noise_meta["backtrack_frames"] == 0

    blank_decision = TemporalDecision(status="FOUND", start_pos=9, start_frame_no=10)
    blank_observations = [
        Observation(pos=8, label=Label.BLANK),
        Observation(pos=9, label=Label.CREDIT),
    ]
    blank_decision, blank_meta = conservative_visual_backtrack(
        blank_decision, blank_observations, scores
    )
    assert blank_decision.start_pos == 9
    assert blank_meta["backtrack_frames"] == 0


def test_detector_end_to_end_keeps_source_immutable_and_never_authorizes_pool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source)
    before = _source_snapshot(source)
    output = tmp_path / "detector-output" / "run-001"
    _patch_fast_cv(monkeypatch)

    result = ClosingCreditOnsetDetector(
        _test_config(),
        classifier=_SemanticFakeClassifier(onset=12),
    ).run(source, output)

    assert result.status == "FOUND"
    assert result.start_pos == 12
    assert result.start_frame_no == 13
    assert result.start_file == "c_0013.png"
    assert result.publishable is True
    # Even a confident detector result is observational in this experiment.
    assert result.pool_may_be_replaced is False
    assert Path(result.output_dir) == output.resolve()
    assert output.is_dir()
    assert not output.is_relative_to(source.resolve())
    assert _source_snapshot(source) == before
    assert not (source / "cikis_jenerik").exists()

    result_json = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert result_json["status"] == "FOUND"
    assert result_json["pool_may_be_replaced"] is False
    assert (output / "run_manifest.json").is_file()
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"]["pool_may_be_replaced"] is False
    assert (output / "calls.jsonl").is_file()


def test_vlm_call_error_is_fail_closed_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source)
    before = _source_snapshot(source)
    output = tmp_path / "detector-output" / "failed-run"
    _patch_fast_cv(monkeypatch)

    result = ClosingCreditOnsetDetector(
        _test_config(),
        classifier=_SemanticFakeClassifier(fail_all=True),
    ).run(source, output)

    assert result.status == "MODEL_ERROR"
    assert result.start_pos is None
    assert result.start_file is None
    assert result.publishable is False
    assert result.pool_may_be_replaced is False
    assert result.metrics["coarse_failed_batches"] > 0
    assert result.metrics["fine_failed_batches"] > 0
    assert _source_snapshot(source) == before
    call_rows = [
        json.loads(line)
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert call_rows
    assert all(row["ok"] is False for row in call_rows)


def test_preflight_model_error_still_writes_result_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, count=8)
    output = tmp_path / "detector-output" / "preflight-failure"

    result = ClosingCreditOnsetDetector(
        _test_config(),
        classifier=_PreflightFailClassifier(),
    ).run(source, output)

    assert result.status == "MODEL_ERROR"
    assert (output / "result.json").is_file()
    assert (output / "run_manifest.json").is_file()
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert "injected preflight failure" in manifest["model_preflight_error"]


def test_film_wall_budget_exhaustion_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, count=40)
    output = tmp_path / "detector-output" / "deadline"
    _patch_fast_cv(monkeypatch)
    config = _test_config()
    config.max_wall_seconds = 1e-9
    classifier = _SemanticFakeClassifier(onset=12)

    result = ClosingCreditOnsetDetector(config, classifier=classifier).run(source, output)

    assert result.status == "MODEL_ERROR"
    assert result.start_pos is None
    assert result.pool_may_be_replaced is False
    assert result.metrics["wall_budget_exhausted"] is True
    assert classifier.calls == []


def test_dense_scan_extends_when_credit_evidence_is_cut_at_right_edge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, count=100)
    output = tmp_path / "detector-output" / "extended-run"
    _patch_fast_cv(monkeypatch)
    config = _test_config()
    config.max_fine_frames = 80
    config.fine_extension_seconds = 20.0
    classifier = _ExtensionFakeClassifier()

    result = ClosingCreditOnsetDetector(config, classifier=classifier).run(source, output)

    assert result.status == "FOUND"
    assert result.start_pos == 70
    assert any(stage == "fine_extension" for stage, _positions in classifier.calls)
    assert result.metrics["fine_sample_count"] > 34


def test_capped_fine_window_is_never_mistaken_for_real_video_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, count=200)
    output = tmp_path / "detector-output" / "capped-end-card"
    _patch_fast_cv(monkeypatch)
    config = _test_config()
    config.fine_pre_seconds = 6.0
    config.max_fine_frames = 16

    result = ClosingCreditOnsetDetector(
        config,
        classifier=_EndCardWindowFakeClassifier(),
    ).run(source, output)

    assert result.status == "NOT_FOUND"
    assert result.start_pos is None
    assert result.publishable is False
    assert result.pool_may_be_replaced is False


def test_two_strong_coarse_groups_remain_review_when_dense_scan_finds_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, count=150)
    output = tmp_path / "detector-output" / "ambiguous-coarse"
    _patch_fast_cv(monkeypatch)
    config = _test_config()

    result = ClosingCreditOnsetDetector(
        config,
        classifier=_AmbiguousCoarseFakeClassifier(),
    ).run(source, output)

    assert result.status == "REVIEW"
    assert result.start_pos is None
    assert result.candidate_starts == [40, 100]
    assert result.publishable is False
    assert result.pool_may_be_replaced is False


def test_detector_rejects_output_inside_frame_source_before_any_write(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, count=8)
    before = _source_snapshot(source)
    forbidden = source / "detector-output"

    with pytest.raises(ValueError, match="output.*frame|source|inside"):
        ClosingCreditOnsetDetector(
            _test_config(),
            classifier=_SemanticFakeClassifier(),
        ).run(source, forbidden)

    assert not forbidden.exists()
    assert _source_snapshot(source) == before


def test_detector_rejects_production_pool_sibling_before_any_write(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film" / "frames" / "cikis"
    _make_frames(source, count=8)
    before = _source_snapshot(source)
    forbidden = source.parent / "cikis_jenerik"

    with pytest.raises(ValueError, match="frames tree|unsafe"):
        ClosingCreditOnsetDetector(
            _test_config(),
            classifier=_SemanticFakeClassifier(),
        ).run(source, forbidden)

    assert not forbidden.exists()
    assert _source_snapshot(source) == before


def test_detector_rejects_output_inside_another_films_frames_tree(
    tmp_path: Path,
) -> None:
    source = tmp_path / "film-a" / "frames" / "cikis"
    _make_frames(source, count=8)
    forbidden = tmp_path / "film-b" / "frames" / "cikis_jenerik" / "debug-run"

    with pytest.raises(ValueError, match="frames tree|unsafe"):
        ClosingCreditOnsetDetector(
            _test_config(),
            classifier=_SemanticFakeClassifier(),
        ).run(source, forbidden)

    assert not forbidden.exists()


def test_ollama_client_accepts_structured_json_from_message_thinking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = _make_frames(tmp_path / "frames", count=1)[0]
    ref = FrameRef(pos=7, frame_no=8, path=image_path, timestamp_seconds=7.0)
    structured = {
        "frames": [{
            "id": 7,
            "label": "CREDIT",
            "text_plane": "SCREEN_OVERLAY",
            "cue": "ROLE_NAME_LAYOUT",
            "confidence": 0.93,
        }]
    }

    def fake_urlopen(_request: object, timeout: float):
        assert timeout == 1.0
        return _HttpResponse({
            "message": {"content": "", "thinking": json.dumps(structured)},
            "done_reason": "stop",
            "eval_count": 12,
        })

    monkeypatch.setattr(ollama_module.urllib.request, "urlopen", fake_urlopen)
    result = _client().classify([ref], stage="fine")

    assert result.call_record["response_field"] == "message.thinking"
    assert result.call_record["ok"] is True
    assert [item.pos for item in result.observations] == [7]
    assert result.observations[0].label == Label.CREDIT


def test_candidate_semantic_client_uses_dedicated_triplet_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _make_frames(tmp_path / "frames", count=3)
    refs = [
        FrameRef(
            pos=129 + index,
            frame_no=130 + index,
            path=path,
            timestamp_seconds=float(129 + index),
        )
        for index, path in enumerate(paths)
    ]
    captured: dict[str, Any] = {}

    def fake_urlopen(request: object, timeout: float):
        assert timeout == 1.0
        captured.update(json.loads(request.data.decode("utf-8")))
        return _HttpResponse({
            "message": {
                "content": "",
                "thinking": json.dumps({
                    "decision": "DIEGETIC_SCREEN",
                    "attribution_layout": False,
                    "inside_story_screen": True,
                }),
            },
            "done_reason": "stop",
            "eval_count": 8,
        })

    monkeypatch.setattr(ollama_module.urllib.request, "urlopen", fake_urlopen)
    capture = tmp_path / "candidate-b.jpg"
    result = _client().audit_candidate_semantics(
        refs,
        candidate_pos=130,
        variant="b",
        stage="refine_candidate_semantic_b",
        capture_path=capture,
    )

    assert result.decision == "DIEGETIC_SCREEN"
    assert result.attribution_layout is False
    assert result.inside_story_screen is True
    assert captured["format"]["required"] == [
        "decision", "attribution_layout", "inside_story_screen"
    ]
    assert "Judge only CELL 01" in captured["messages"][0]["content"]
    assert len(captured["messages"][0]["images"]) == 1
    assert capture.is_file()
    assert result.call_record["prompt_protocol"] == "candidate_semantic_audit_v1"
    assert result.call_record["prompt_variant"] == "candidate_context_triplet"


def test_candidate_single_transport_has_center_and_full_enhancement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = tmp_path / "frames" / "c_0131.png"
    image_path.parent.mkdir(parents=True)
    image = Image.new("RGB", (1280, 720), (5, 5, 5))
    for x in range(600, 680):
        for y in range(650, 666):
            image.putpixel((x, y), (110, 8, 18))
    image.save(image_path)
    ref = FrameRef(
        pos=130,
        frame_no=131,
        path=image_path,
        timestamp_seconds=130.0,
    )
    captured: dict[str, Any] = {}

    def fake_urlopen(request: object, timeout: float):
        assert timeout == 1.0
        captured.update(json.loads(request.data.decode("utf-8")))
        return _HttpResponse({
            "message": {
                "content": "",
                "thinking": json.dumps({
                    "decision": "ATTRIBUTION_CREDIT",
                    "attribution_layout": True,
                    "inside_story_screen": False,
                }),
            },
            "done_reason": "stop",
            "eval_count": 8,
        })

    monkeypatch.setattr(ollama_module.urllib.request, "urlopen", fake_urlopen)
    capture = tmp_path / "candidate-a.jpg"
    result = _client().audit_candidate_semantics(
        [ref],
        candidate_pos=130,
        variant="a",
        stage="refine_candidate_semantic_a",
        capture_path=capture,
    )

    assert result.decision == "ATTRIBUTION_CREDIT"
    assert "All five panes" in captured["messages"][0]["content"]
    mosaic = result.call_record["mosaic"]
    assert mosaic["columns"] == 3
    assert mosaic["rows"] == 2
    assert mosaic["candidate_detail_views"] == [
        "CANDIDATE FULL",
        "CANDIDATE FULL ENHANCED",
        "CANDIDATE CENTER ZOOM",
        "CANDIDATE LOWER ZOOM",
        "CANDIDATE BOTTOM EDGE",
    ]
    assert mosaic["center_crop_margins_ratio"] == [0.2, 0.2]
    assert mosaic["full_enhancement"]["color"] == 2.0
    with Image.open(capture) as transported:
        assert transported.size == (2160, 858)


def test_candidate_screen_disproof_transports_headerless_raw_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = tmp_path / "frames" / "c_0131.png"
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (1280, 720), (17, 29, 43)).save(image_path)
    ref = FrameRef(
        pos=130,
        frame_no=131,
        path=image_path,
        timestamp_seconds=130.0,
    )
    captured: dict[str, Any] = {}

    def fake_urlopen(request: object, timeout: float):
        assert timeout == 1.0
        captured.update(json.loads(request.data.decode("utf-8")))
        return _HttpResponse({
            "message": {
                "content": "",
                "thinking": json.dumps({
                    "decision": "NO_TEXT",
                    "attribution_layout": False,
                    "inside_story_screen": False,
                }),
            },
            "done_reason": "stop",
            "eval_count": 8,
        })

    monkeypatch.setattr(ollama_module.urllib.request, "urlopen", fake_urlopen)
    capture = tmp_path / "candidate-s.jpg"
    result = _client().audit_candidate_semantics(
        [ref],
        candidate_pos=130,
        variant="s",
        stage="refine_candidate_semantic_s",
        capture_path=capture,
    )

    assert result.decision == "NO_TEXT"
    assert "SCREEN DISPROOF AUDIT" in captured["messages"][0]["content"]
    assert len(captured["messages"][0]["images"]) == 1
    transported = base64.b64decode(captured["messages"][0]["images"][0])
    assert transported == capture.read_bytes()
    with Image.open(capture) as image:
        assert image.size == (960, 540)
    mosaic = result.call_record["mosaic"]
    assert mosaic["raw_candidate_frame"] is True
    assert mosaic["header_height"] == 0
    assert mosaic["original_size"] == [1280, 720]
    assert result.call_record["prompt_variant"] == "candidate_screen_disproof"


def test_live_schema_sends_indexed_mosaic_and_accepts_boundary_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _make_frames(tmp_path / "frames", count=3)
    refs = [
        FrameRef(pos=position, frame_no=position + 1, path=path, timestamp_seconds=float(position))
        for position, path in enumerate(paths)
    ]
    captured: dict[str, Any] = {}

    def fake_urlopen(request: object, timeout: float):
        assert timeout == 1.0
        captured.update(json.loads(request.data.decode("utf-8")))
        compact = {
            "state": "TRANSITION",
            "first": 1,
            "last_support": 2,
            "kind": "CREDIT_SEQUENCE",
            "continuity": "CONFIRMED",
            "reject": "NONE",
        }
        return _HttpResponse({
            "message": {"content": "", "thinking": json.dumps(compact)},
            "done_reason": "stop",
        })

    monkeypatch.setattr(ollama_module.urllib.request, "urlopen", fake_urlopen)
    result = _client().classify(refs, stage="coarse")

    assert len(captured["messages"][0]["images"]) == 1
    assert captured["format"]["required"] == [
        "state", "first", "last_support", "kind", "continuity", "reject"
    ]
    assert captured["format"]["properties"]["first"]["minimum"] == -1
    assert captured["format"]["properties"]["first"]["maximum"] == 2
    assert [item.label for item in result.observations] == [
        Label.FOOTAGE,
        Label.CREDIT,
        Label.CREDIT,
    ]
    assert [item.confidence for item in result.observations] == [0.9, 0.9, 0.9]
    assert all(
        item.metadata["response_format"] == "window_boundary_v1_legacy_adapter"
        for item in result.observations
    )
    assert result.call_record["transport_image_count"] == 1
    assert result.call_record["mosaic"]["columns"] == 3
    assert result.call_record["mosaic"]["header_height"] == 22


def test_invalid_positive_support_gets_audited_repair_prompt_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _make_frames(tmp_path / "frames", count=3)
    refs = [
        FrameRef(
            pos=position,
            frame_no=position + 1,
            path=path,
            timestamp_seconds=float(position),
        )
        for position, path in enumerate(paths)
    ]
    payloads: list[dict[str, Any]] = []

    def fake_urlopen(request: object, timeout: float):
        assert timeout == 1.0
        payloads.append(json.loads(request.data.decode("utf-8")))
        decision = (
            {
                "state": "TRANSITION",
                "first": 1,
                "last_support": -1,
                "kind": "CREDIT_SEQUENCE",
                "continuity": "CONFIRMED",
                "reject": "NONE",
            }
            if len(payloads) == 1 else {
                "state": "TRANSITION",
                "first": 1,
                "last_support": 2,
                "kind": "CREDIT_SEQUENCE",
                "continuity": "CONFIRMED",
                "reject": "NONE",
            }
        )
        return _HttpResponse({
            "message": {"content": "", "thinking": json.dumps(decision)},
            "done_reason": "stop",
        })

    monkeypatch.setattr(ollama_module.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(ollama_module.time, "sleep", lambda _seconds: None)
    client = _client()
    client.retry_count = 2
    result = client.locate_window(refs, stage="verify_a")

    assert result.evidence.first_pos == 1
    assert result.evidence.last_support_pos == 2
    assert result.call_record["attempts"] == 2
    assert len(result.call_record["validation_failures"]) == 1
    assert len(result.call_record["prompt_attempt_sha256"]) == 2
    assert result.call_record["prompt_attempt_sha256"][0] != (
        result.call_record["prompt_attempt_sha256"][1]
    )
    assert "STRICT JSON REPAIR" not in payloads[0]["messages"][0]["content"]
    assert "STRICT JSON REPAIR" in payloads[1]["messages"][0]["content"]
    assert "last_support>=first" in payloads[1]["messages"][0]["content"]


def test_locate_window_returns_strict_evidence_and_captures_exact_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _make_frames(tmp_path / "frames", count=3)
    refs = [
        FrameRef(
            pos=100 + index,
            frame_no=101 + index,
            path=path,
            timestamp_seconds=50.0 + index,
        )
        for index, path in enumerate(paths)
    ]
    captured: dict[str, Any] = {}

    def fake_urlopen(request: object, timeout: float):
        captured.update(json.loads(request.data.decode("utf-8")))
        return _HttpResponse({
            "message": {
                "content": "",
                "thinking": json.dumps({
                    "state": "TRANSITION",
                    "first": 1,
                    "last_support": 2,
                    "kind": "CREDIT_SEQUENCE",
                    "continuity": "CONFIRMED",
                    "reject": "NONE",
                }),
            },
            "done_reason": "stop",
        })

    monkeypatch.setattr(ollama_module.urllib.request, "urlopen", fake_urlopen)
    capture_path = tmp_path / "sent" / "fine_01.jpg"
    result = _client().locate_window(
        refs,
        stage="fine_gap",
        at_stream_eof=True,
        capture_path=capture_path,
        tile_width=192,
        jpeg_quality=95,
        mosaic_columns=3,
    )

    assert result.evidence.verdict == "TRANSITION"
    assert result.evidence.first_cell == 1
    assert result.evidence.first_pos == 101
    assert result.evidence.last_support_pos == 102
    assert result.evidence.at_stream_eof is True
    assert capture_path.is_file()
    assert result.call_record["input_sha256"] == hashlib.sha256(
        capture_path.read_bytes()
    ).hexdigest()
    assert result.call_record["input_mosaic_path"] == str(capture_path.resolve())
    assert result.call_record["prompt_protocol"] == "window_boundary_v1"
    assert len(result.call_record["prompt_sha256"]) == 64
    assert "images" not in result.call_record
    prompt = captured["messages"][0]["content"]
    assert "machine-added indexes" in prompt
    assert "real end of the extracted video tail" in prompt
    assert "Never select a later cell" in prompt
    assert "DIEGETIC" in captured["format"]["properties"]["reject"]["enum"]
    assert "source positions" not in prompt


@pytest.mark.parametrize(
    ("payload", "expected_labels", "expected_confidence"),
    [
        (
            {
                "state": "PRE_ONLY", "first": -1, "last_support": -1,
                "kind": "NONE", "continuity": "NONE",
                "reject": "NO_VISIBLE_ATTRIBUTION",
            },
            [Label.FOOTAGE, Label.FOOTAGE, Label.FOOTAGE],
            [0.9, 0.9, 0.9],
        ),
        (
            {
                "state": "TRANSITION", "first": 1, "last_support": 2,
                "kind": "END_CARD_THEN_CREDITS", "continuity": "CONFIRMED",
                "reject": "NONE",
            },
            [Label.FOOTAGE, Label.END_CARD, Label.CREDIT],
            [0.9, 0.9, 0.9],
        ),
        (
            {
                "state": "ACTIVE_FROM_LEFT", "first": 0, "last_support": 2,
                "kind": "CREDIT_SEQUENCE", "continuity": "CONFIRMED",
                "reject": "NONE",
            },
            [Label.CREDIT, Label.CREDIT, Label.CREDIT],
            [0.9, 0.9, 0.9],
        ),
        (
            {
                "state": "AMBIGUOUS", "first": -1, "last_support": -1,
                "kind": "NONE", "continuity": "UNVERIFIABLE",
                "reject": "MIXED",
            },
            [Label.UNCERTAIN, Label.UNCERTAIN, Label.UNCERTAIN],
            [0.0, 0.0, 0.0],
        ),
    ],
)
def test_window_decision_expands_to_temporal_observations(
    payload: dict[str, Any],
    expected_labels: list[Label],
    expected_confidence: list[float],
) -> None:
    refs = [
        FrameRef(pos=i, frame_no=i + 1, path=Path(f"c_{i + 1:04d}.png"), timestamp_seconds=float(i))
        for i in range(3)
    ]
    observations = OllamaFrameClassifier._validate_frames(
        payload, refs, "fine", "window"
    )

    assert [item.label for item in observations] == expected_labels
    assert [item.confidence for item in observations] == expected_confidence


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (
            {"state": "PRE_ONLY", "first": 0, "last_support": -1, "kind": "NONE",
             "continuity": "NONE", "reject": "NONE"},
            "PRE_ONLY requires",
        ),
        (
            {"state": "ACTIVE_FROM_LEFT", "first": -1, "last_support": 2,
             "kind": "CREDIT_SEQUENCE", "continuity": "CONFIRMED", "reject": "NONE"},
            "ACTIVE_FROM_LEFT requires",
        ),
        (
            {"state": "TRANSITION", "first": 3, "last_support": 3,
             "kind": "CREDIT_SEQUENCE", "continuity": "CONFIRMED", "reject": "NONE"},
            "TRANSITION requires",
        ),
        (
            {"state": "TRANSITION", "first": True, "last_support": 2,
             "kind": "CREDIT_SEQUENCE", "continuity": "CONFIRMED", "reject": "NONE"},
            "integer",
        ),
        (
            {"state": "BOGUS", "first": -1, "last_support": -1, "kind": "NONE",
             "continuity": "NONE", "reject": "NONE"},
            "invalid window state",
        ),
    ],
)
def test_window_decision_rejects_inconsistent_payloads(
    payload: dict[str, Any],
    error: str,
) -> None:
    refs = [
        FrameRef(pos=i, frame_no=i + 1, path=Path(f"c_{i + 1:04d}.png"), timestamp_seconds=float(i))
        for i in range(3)
    ]

    with pytest.raises(ValueError, match=error):
        OllamaFrameClassifier._validate_frames(payload, refs, "fine", "bad-window")


def test_compact_legacy_arrays_remain_readable_for_debug_replay() -> None:
    refs = [
        FrameRef(pos=0, frame_no=1, path=Path("c_0001.png"), timestamp_seconds=0.0),
        FrameRef(pos=1, frame_no=2, path=Path("c_0002.png"), timestamp_seconds=1.0),
    ]
    observations = OllamaFrameClassifier._validate_frames(
        {"labels": ["F", "C"], "confidence": [94, 97]},
        refs,
        "coarse",
        "legacy-debug",
    )

    assert [item.label for item in observations] == [Label.FOOTAGE, Label.CREDIT]
    assert [item.confidence for item in observations] == [0.94, 0.97]
    assert all(
        item.metadata["response_format"] == "compact_mosaic_v1_arrays"
        for item in observations
    )


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"labels": ["F"]}, "length mismatch"),
        ({"labels": ["F", "X"]}, "invalid compact label"),
        ({"labels": "FC"}, "labels array"),
    ],
)
def test_compact_label_protocol_rejects_malformed_payloads(
    payload: dict[str, Any],
    error: str,
) -> None:
    refs = [
        FrameRef(pos=0, frame_no=1, path=Path("c_0001.png"), timestamp_seconds=0.0),
        FrameRef(pos=1, frame_no=2, path=Path("c_0002.png"), timestamp_seconds=1.0),
    ]

    with pytest.raises(ValueError, match=error):
        OllamaFrameClassifier._validate_frames(payload, refs, "coarse", "bad")


def test_ollama_client_rejects_wrong_or_reordered_frame_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = _make_frames(tmp_path / "frames", count=1)[0]
    ref = FrameRef(pos=7, frame_no=8, path=image_path, timestamp_seconds=7.0)
    wrong_ids = {
        "frames": [{
            "id": 8,
            "label": "CREDIT",
            "text_plane": "SCREEN_OVERLAY",
            "cue": "ROLE_NAME_LAYOUT",
            "confidence": 0.99,
        }]
    }

    monkeypatch.setattr(
        ollama_module.urllib.request,
        "urlopen",
        lambda _request, timeout: _HttpResponse({
            "message": {"content": "", "thinking": json.dumps(wrong_ids)},
            "done_reason": "stop",
        }),
    )

    with pytest.raises(VlmCallError, match="strict validation") as caught:
        _client().classify([ref], stage="coarse")

    assert caught.value.record["ok"] is False
    assert "frame ids mismatch" in caught.value.record["error"]


def test_ollama_client_wraps_legacy_null_confidence_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = _make_frames(tmp_path / "frames", count=1)[0]
    ref = FrameRef(pos=7, frame_no=8, path=image_path, timestamp_seconds=7.0)
    malformed = {
        "frames": [{
            "id": 7,
            "label": "CREDIT",
            "text_plane": "SCREEN_OVERLAY",
            "cue": "ROLE_NAME_LAYOUT",
            "confidence": None,
        }]
    }
    monkeypatch.setattr(
        ollama_module.urllib.request,
        "urlopen",
        lambda _request, timeout: _HttpResponse({
            "message": {"content": "", "thinking": json.dumps(malformed)},
            "done_reason": "stop",
        }),
    )

    with pytest.raises(VlmCallError, match="strict validation") as caught:
        _client().classify([ref], stage="coarse")

    assert caught.value.record["ok"] is False
    assert "NoneType" in caught.value.record["error"]


def test_ollama_client_wraps_non_object_http_json_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = _make_frames(tmp_path / "frames", count=1)[0]
    ref = FrameRef(pos=7, frame_no=8, path=image_path, timestamp_seconds=7.0)
    monkeypatch.setattr(
        ollama_module.urllib.request,
        "urlopen",
        lambda _request, timeout: _HttpResponse([]),
    )

    with pytest.raises(VlmCallError, match="strict validation") as caught:
        _client().classify([ref], stage="coarse")

    assert caught.value.record["ok"] is False
    assert "root is not an object" in caught.value.record["error"]
