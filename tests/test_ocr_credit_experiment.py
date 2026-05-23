from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.pipelines.ocr import credit_experiment as ce


class FakeOcrEngine:
    name = "fake"

    def recognize(self, image_path: Path, *, strategy: str, timestamp_seconds: float | None = None):
        text = "NISA SEREZLI" if strategy == "frame_ocr" else "NISA SEREZLI CANVAS"
        return [
            {
                "engine": self.name,
                "strategy": strategy,
                "frame": str(image_path),
                "timestamp_seconds": timestamp_seconds,
                "bbox": [8.0, 10.0, 80.0, 14.0],
                "text": text,
                "confidence": 0.91,
                "normalized_text": ce.normalize_text(text),
                "line_group_id": None,
                "warnings": [],
            }
        ]


def test_load_manifest_parses_items(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "film_001_end",
                        "path": "D:/films/example.mp4",
                        "kind": "end_credits",
                        "layout_type": "vertical_scroll",
                        "motion_type": "rolling_text",
                        "expected_language": "tr",
                        "start_seconds": 10,
                        "end_seconds": 15,
                        "fps": 6,
                        "roi": [0, 20, 640, 200],
                        "column_count": 2,
                        "ground_truth": ["Çağatay Ulusoy", "Nisa Serezli"],
                        "notes": "test",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = ce.load_manifest(manifest)

    assert loaded.items[0].id == "film_001_end"
    assert loaded.items[0].roi == (0, 20, 640, 200)
    assert loaded.items[0].layout_type == "vertical_scroll"
    assert loaded.items[0].motion_type == "rolling_text"
    assert loaded.items[0].expected_language == "tr"
    assert loaded.items[0].fps == 6
    assert loaded.items[0].column_count == 2
    assert loaded.items[0].ground_truth == ("CAGATAY ULUSOY", "NISA SEREZLI")


def test_load_manifest_rejects_bad_time_range(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"items": [{"id": "bad", "path": "x.mp4", "start_seconds": 5, "end_seconds": 5}]}),
        encoding="utf-8",
    )

    try:
        ce.load_manifest(manifest)
    except ValueError as exc:
        assert "end_seconds" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError")


def test_temporal_voting_groups_similar_names() -> None:
    records = [
        _record("NISA SEREZLI", timestamp=0.0),
        _record("NİSA SEREZLİ", timestamp=0.5),
        _record("NISA SEREZLl", timestamp=1.0),
    ]

    result = ce.group_temporal_records(records)

    assert result["stable_groups"] == 1
    assert result["unique_lines"] == 1
    assert result["groups"][0]["record_count"] == 3
    assert all(item["line_group_id"] == "lg_0001" for item in result["records"])


def test_ground_truth_scoring_penalizes_stable_wrong_text() -> None:
    result = ce._score_candidates(["NISA SEREZLI", "YANLIS ISIM"], ["NİSA SEREZLİ", "ÇAĞATAY ULUSOY"])

    assert result["metric_status"] == "scored"
    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5


def test_adaptive_fps_for_scroll_manifest() -> None:
    item = ce.CreditExperimentItem(
        id="scroll",
        path=Path("x.mp4"),
        kind="end_credits",
        layout_type="vertical_scroll",
        motion_type="rolling_text",
        expected_language="tr",
        start_seconds=0,
        end_seconds=10,
        fps=None,
        roi=None,
        column_count=1,
        ground_truth=(),
        notes="",
    )

    fps, policy = ce._effective_fps(item, None)

    assert fps == ce.DEFAULT_SCROLL_FPS
    assert policy == "adaptive_scroll"


def test_auto_roi_detects_lower_third_text_region(tmp_path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    item = ce.CreditExperimentItem(
        id="kj",
        path=Path("x.mp4"),
        kind="kj_overlay",
        layout_type="lower_third",
        motion_type="static",
        expected_language="tr",
        start_seconds=0,
        end_seconds=5,
        fps=None,
        roi=None,
        column_count=1,
        ground_truth=(),
        notes="alt bilgi KJ",
    )
    frames = []
    for index in range(5):
        image = np.full((360, 640, 3), (28, 32, 36), dtype=np.uint8)
        cv2.rectangle(image, (48, 242), (590, 328), (18, 18, 18), -1)
        cv2.putText(image, "CANLI YAYIN", (74, 286), cv2.FONT_HERSHEY_SIMPLEX, 0.86, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(image, "ANKARA", (400, 286), cv2.FONT_HERSHEY_SIMPLEX, 0.86, (20, 220, 255), 2, cv2.LINE_AA)
        path = tmp_path / f"kj_{index:03d}.png"
        cv2.imwrite(str(path), image)
        frames.append(path)

    info = ce._infer_text_roi_info(frames, item)

    assert info["status"] == "detected"
    assert info["strategy"] == "text_density_lower_third"
    x, y, w, h = info["roi"]
    assert y >= 130
    assert h < 220
    assert w < 640


def test_auto_roi_detects_center_credit_region(tmp_path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    item = ce.CreditExperimentItem(
        id="credit",
        path=Path("x.mp4"),
        kind="end_credits",
        layout_type="rolling_vertical",
        motion_type="text_scrolling",
        expected_language="en",
        start_seconds=0,
        end_seconds=5,
        fps=None,
        roi=None,
        column_count=1,
        ground_truth=(),
        notes="akan jenerik",
    )
    frames = []
    for index in range(6):
        image = np.zeros((360, 640, 3), dtype=np.uint8)
        y_base = 320 - index * 12
        for row_index, text in enumerate(["DIRECTOR", "MICHAEL DANTE", "EDITOR", "NISA SEREZLI"]):
            y = y_base + row_index * 36
            if 0 < y < 350:
                cv2.putText(image, text, (220, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (245, 245, 245), 2, cv2.LINE_AA)
        path = tmp_path / f"credit_{index:03d}.png"
        cv2.imwrite(str(path), image)
        frames.append(path)

    info = ce._infer_text_roi_info(frames, item)

    assert info["status"] == "detected"
    assert info["strategy"] == "text_density_credit"
    x, y, w, h = info["roi"]
    assert 120 <= x <= 260
    assert w < 420
    assert h < 300


def test_second_pass_roi_refines_from_ocr_boxes(tmp_path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    frame = tmp_path / "frame_000.png"
    Image.new("RGB", (640, 360), "black").save(frame)
    item = ce.CreditExperimentItem(
        id="credit",
        path=Path("x.mp4"),
        kind="end_credits",
        layout_type="vertical_scroll",
        motion_type="rolling_text",
        expected_language="en",
        start_seconds=0,
        end_seconds=5,
        fps=None,
        roi=None,
        column_count=1,
        ground_truth=(),
        notes="akan jenerik",
    )
    records = [
        {**_record("DIRECTOR", timestamp=0.0), "frame": str(frame), "bbox": [250.0, 110.0, 140.0, 22.0]},
        {**_record("MICHAEL DANTE", timestamp=0.0), "frame": str(frame), "bbox": [220.0, 150.0, 220.0, 24.0]},
        {**_record("EDITOR", timestamp=1.0), "frame": str(frame), "bbox": [258.0, 190.0, 124.0, 22.0]},
        {**_record("NISA SEREZLI", timestamp=1.0), "frame": str(frame), "bbox": [226.0, 230.0, 208.0, 24.0]},
    ]

    info = ce._infer_second_pass_roi_info([frame], records, item)

    assert info["status"] == "detected"
    assert info["strategy"] == "ocr_bbox_second_pass"
    x, y, w, h = info["roi"]
    assert 150 <= x <= 230
    assert 40 <= y <= 120
    assert w < 420
    assert h < 260


def test_second_pass_roi_falls_back_to_text_mask_when_ocr_boxes_missing(tmp_path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    item = ce.CreditExperimentItem(
        id="mask_credit",
        path=Path("x.mp4"),
        kind="end_credits",
        layout_type="vertical_scroll",
        motion_type="rolling_text",
        expected_language="en",
        start_seconds=0,
        end_seconds=5,
        fps=None,
        roi=None,
        column_count=1,
        ground_truth=(),
        notes="akan jenerik",
    )
    frames = []
    for index in range(5):
        image = np.zeros((360, 640, 3), dtype=np.uint8)
        y_base = 330 - index * 34
        for row_index, text in enumerate(["DIRECTOR", "MICHAEL DANTE", "EDITOR", "NISA SEREZLI"]):
            y = y_base + row_index * 34
            if 0 < y < 350:
                cv2.putText(image, text, (225, y), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (245, 245, 245), 2, cv2.LINE_AA)
        path = tmp_path / f"mask_credit_{index:03d}.png"
        cv2.imwrite(str(path), image)
        frames.append(path)

    info = ce._infer_second_pass_roi_info(frames, [], item)

    assert info["status"] == "detected"
    assert info["strategy"] == "text_mask_track_second_pass"
    assert info["evidence"]["prior_reason"] == "too_few_ocr_boxes"
    x, y, w, h = info["roi"]
    assert 100 <= x <= 250
    assert w < 430
    assert h == 360


def test_descroll_canvas_expands_for_synthetic_vertical_scroll(tmp_path) -> None:
    pytest.importorskip("cv2")
    pytest.importorskip("PIL")
    frames = _make_synthetic_scroll_frames(tmp_path)
    motion = ce.analyze_text_motion(frames, [])
    canvas = ce.build_descroll_canvas(frames, motion, output_path=tmp_path / "canvas.png")

    assert Path(canvas["canvas_path"]).exists()
    assert canvas["canvas_size"][1] > 80
    assert canvas["estimated_orientation"] in {"vertical", "mixed_or_static"}
    assert len(canvas["motion_shifts"]) == 2


def test_run_credit_experiment_writes_outputs_with_fake_engine(tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fake-video")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "sample",
                        "path": str(source),
                        "kind": "end_credits",
                        "start_seconds": 0,
                        "end_seconds": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_extract(input_path, frames_dir, **kwargs):
        frames_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        for index in range(3):
            path = frames_dir / f"frame_{index:03d}.png"
            path.write_bytes(b"fake-png")
            frames.append(path)
        return frames

    def fake_motion(frames, records, **kwargs):
        return {"strategy": "text_mask_motion", "frame_count": len(frames), "shifts": [{"dx": 0.0, "dy": 8.0}], "mean_text_shift": [0.0, 8.0], "mean_global_shift": [0.0, 0.0]}

    def fake_canvas(frames, motion, *, output_path):
        output_path.write_bytes(b"fake-canvas")
        return {
            "strategy": "descroll_canvas",
            "frame_count": len(frames),
            "canvas_path": str(output_path),
            "canvas_size": [100, 120],
            "estimated_orientation": "vertical",
            "motion_shifts": motion["shifts"],
            "warnings": [],
        }

    monkeypatch.setattr(ce, "_extract_segment_frames", fake_extract)
    monkeypatch.setattr(ce, "analyze_text_motion", fake_motion)
    monkeypatch.setattr(ce, "build_descroll_canvas", fake_canvas)

    result = ce.run_credit_experiment(
        manifest,
        output_dir=tmp_path / "out",
        engines=["fake"],
        preprocess_mode="always",
        allow_model_download=True,
        engine_factories={"fake": lambda: FakeOcrEngine()},
    )

    item_dir = result.output_dir / "items" / "sample"
    assert result.summary["allow_model_download"] is True
    assert result.summary["items"][0]["status"] == "done"
    assert (item_dir / "frame_ocr.json").exists()
    assert (item_dir / "temporal_voting.json").exists()
    assert (item_dir / "text_motion.json").exists()
    assert (item_dir / "descroll_canvas.json").exists()
    assert (item_dir / "comparison.md").exists()
    assert json.loads((item_dir / "temporal_voting.json").read_text(encoding="utf-8"))["stable_groups"] == 1


def test_temporal_fusion_hook_runs_when_scene_recommends_median(tmp_path, monkeypatch) -> None:
    """Integration: when scene_router recommends temporal_median_fusion,
    the experiment hook must actually execute it and write temporal_fusion.json."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    source = tmp_path / "input.mp4"
    source.write_bytes(b"fake-video")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"items": [{"id": "sample", "path": str(source), "kind": "end_credits", "start_seconds": 0, "end_seconds": 2}]}),
        encoding="utf-8",
    )

    def fake_extract(input_path, frames_dir, **kwargs):
        frames_dir.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(11)
        base = np.zeros((120, 200, 3), dtype=np.uint8)
        cv2.putText(base, "STATIC", (40, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        frames = []
        for index in range(5):
            noisy = (base.astype(np.int32) + rng.integers(-15, 16, size=base.shape)).clip(0, 255).astype(np.uint8)
            path = frames_dir / f"frame_{index:03d}.png"
            cv2.imwrite(str(path), noisy)
            frames.append(path)
        return frames

    def fake_scene(frames, item, **kwargs):
        return {
            "segment_id": "sample",
            "background": {"type": "flat_static", "confidence": 0.88, "evidence": {}},
            "text_motion": {"type": "static_card", "confidence": 0.78, "evidence": {}},
            "layout": {"type": "lower_third", "confidence": 0.85, "evidence": {}},
            "difficulty": {"labels": [], "score": 0.2, "confidence": 0.7, "evidence": {}},
            "recommended_pipeline": {"temporal": "temporal_median_fusion", "steps": [], "roi": "full_frame", "preprocess": [], "ocr": "paddle_ppocrv5", "parser": "plain_line_parser", "fallback_pipelines": [], "why": []},
            "raw_features": {"frame_count": 5},
        }

    def fake_motion(frames, records, **kwargs):
        return {"strategy": "text_mask_motion", "frame_count": len(frames), "shifts": [], "mean_text_shift": [0.0, 0.0], "mean_global_shift": [0.0, 0.0]}

    def fake_canvas(frames, motion, *, output_path):
        output_path.write_bytes(b"fake-canvas")
        return {"strategy": "descroll_canvas", "frame_count": len(frames), "canvas_path": str(output_path), "canvas_size": [100, 100], "estimated_orientation": "static", "motion_shifts": [], "warnings": []}

    monkeypatch.setattr(ce, "_extract_segment_frames", fake_extract)
    monkeypatch.setattr(ce, "_analyze_scene_profile", fake_scene)
    monkeypatch.setattr(ce, "analyze_text_motion", fake_motion)
    monkeypatch.setattr(ce, "build_descroll_canvas", fake_canvas)

    result = ce.run_credit_experiment(
        manifest,
        output_dir=tmp_path / "out",
        engines=["fake"],
        preprocess_mode="off",
        allow_model_download=False,
        engine_factories={"fake": lambda: FakeOcrEngine()},
    )

    item_dir = result.output_dir / "items" / "sample"
    fusion_json_path = item_dir / "temporal_fusion.json"
    assert fusion_json_path.exists(), "temporal_fusion.json must be written"

    fusion = json.loads(fusion_json_path.read_text(encoding="utf-8"))
    assert fusion["status"] == "done", f"hook must succeed, got: {fusion}"
    assert fusion["strategy"] == "temporal_median_fusion"
    assert Path(fusion["output_path"]).exists()
    assert (Path(fusion["output_path"]).parent / "report.md").exists()


def test_cli_delegates_to_runner(tmp_path, monkeypatch, capsys) -> None:
    from scripts import ocr_credit_experiment as cli

    class Result:
        summary_path = tmp_path / "summary.json"
        report_path = tmp_path / "report.md"

    captured = {}

    def fake_run(manifest, **kwargs):
        captured["manifest"] = manifest
        captured.update(kwargs)
        return Result()

    monkeypatch.setattr(cli, "run_credit_experiment", fake_run)

    code = cli.main(["--manifest", "m.json", "--output-dir", "out", "--engines", "fake", "--fps", "1.5", "--preprocess-mode", "off", "--allow-model-download"])

    assert code == 0
    assert captured["manifest"] == "m.json"
    assert captured["output_dir"] == "out"
    assert captured["engines"] == ["fake"]
    assert captured["fps"] == 1.5
    assert captured["preprocess_mode"] == "off"
    assert captured["allow_model_download"] is True
    assert "summary.json" in capsys.readouterr().out


def test_preprocess_auto_skips_when_frame_ocr_is_confident() -> None:
    item = ce.CreditExperimentItem(
        id="clean",
        path=Path("x.mp4"),
        kind="end_credits",
        layout_type="vertical_scroll",
        motion_type="rolling_text",
        expected_language="tr",
        start_seconds=0,
        end_seconds=10,
        fps=None,
        roi=None,
        column_count=1,
        ground_truth=(),
        notes="",
    )
    record = _record("NISA SEREZLI", timestamp=0.0)
    record["bbox"] = [10.0, 20.0, 100.0, 24.0]
    frame_ocr = {"records": [record]}

    run, reason = ce._should_run_preprocess(item, frame_ocr, "auto")

    assert run is False
    assert reason == "auto_not_needed"


def _record(text: str, *, timestamp: float):
    return {
        "engine": "fake",
        "strategy": "frame_ocr",
        "frame": f"frame_{timestamp}.png",
        "timestamp_seconds": timestamp,
        "bbox": [10.0, 20.0, 100.0, 16.0],
        "text": text,
        "confidence": 0.9,
        "normalized_text": ce.normalize_text(text),
        "line_group_id": None,
        "warnings": [],
    }


def _make_synthetic_scroll_frames(directory: Path) -> list[Path]:
    from PIL import Image, ImageDraw

    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, y in enumerate([8, 18, 28]):
        image = Image.new("RGB", (140, 80), "black")
        draw = ImageDraw.Draw(image)
        draw.rectangle((30, y, 105, y + 10), fill="white")
        draw.rectangle((35, y + 16, 100, y + 23), fill="white")
        path = directory / f"frame_{index:03d}.png"
        image.save(path)
        paths.append(path)
    return paths
