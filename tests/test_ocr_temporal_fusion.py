"""Tests for temporal fusion strategies (K-3 temporal_median_fusion, K-4 temporal_variance_masking)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# K-3 — temporal median fusion
# ---------------------------------------------------------------------------


def test_temporal_median_reduces_noise_and_writes_outputs(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    from core.pipelines.ocr.temporal_fusion import run_temporal_median_fusion

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()

    rng = np.random.default_rng(42)
    base = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.putText(base, "ANKARA", (60, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    frame_paths = []
    for i in range(10):
        noisy = (base.astype(np.int32) + rng.integers(-40, 41, size=base.shape)).clip(0, 255).astype(np.uint8)
        path = frames_dir / f"frame_{i:02d}.png"
        cv2.imwrite(str(path), noisy)
        frame_paths.append(path)

    output_dir = tmp_path / "fusion_out"
    result = run_temporal_median_fusion(frame_paths, output_dir, max_frames=None)

    assert result.output_path.exists(), "fused.png must exist"
    assert result.summary_path.exists(), "summary.json must exist"
    assert result.report_path.exists(), "report.md must exist"
    assert result.strategy == "temporal_median_fusion"

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["frame_count"] == 10
    assert "quality" in summary

    report_text = result.report_path.read_text(encoding="utf-8")
    assert "temporal_median_fusion" in report_text
    assert "Sharpness" in report_text

    fused = cv2.imread(str(result.output_path), cv2.IMREAD_GRAYSCALE).astype(np.float32)

    # Measure noise in a background patch (top-left corner, away from text)
    # Base image is all-black there, so every value in a noisy frame is pure random noise.
    patch = np.s_[0:40, 0:40]   # 40x40 pixels, clearly in black background
    fused_patch_std = float(fused[patch].std())

    all_noisy_stds = [
        cv2.imread(str(p), cv2.IMREAD_GRAYSCALE).astype(np.float32)[patch].std()
        for p in frame_paths
    ]
    mean_noisy_patch_std = float(np.mean(all_noisy_stds))

    # Median of 10 i.i.d. uniform[-40,40] random vars should have ~2x lower std than each individual
    assert fused_patch_std < mean_noisy_patch_std, (
        f"Background patch std after fusion {fused_patch_std:.2f} should be < mean single-frame noise {mean_noisy_patch_std:.2f}"
    )


# ---------------------------------------------------------------------------
# K-4 — temporal variance masking
# ---------------------------------------------------------------------------


def test_temporal_variance_keeps_static_text_and_zeros_moving_bg(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    from core.pipelines.ocr.temporal_fusion import run_temporal_variance_masking

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()

    H, W = 240, 320
    # Text is always at (x=60, y=130)
    TEXT_X, TEXT_Y = 60, 130
    TEXT_W, TEXT_H = 180, 40  # approximate bounding box of rendered text

    # Rectangle that slides across the frame (simulates moving background element)
    RECT_H, RECT_W = 30, 60

    frame_paths = []
    for i in range(12):
        img = np.zeros((H, W, 3), dtype=np.uint8)
        # Moving rectangle — different x position per frame (far from text region)
        rect_x = 10 + i * 10   # moves from x=10 to x=120
        rect_y = 10
        cv2.rectangle(img, (rect_x, rect_y), (rect_x + RECT_W, rect_y + RECT_H), (180, 80, 80), -1)
        # Static text — always at same position
        cv2.putText(img, "ANKARA 14:30", (TEXT_X, TEXT_Y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (240, 240, 240), 2, cv2.LINE_AA)
        path = frames_dir / f"frame_{i:02d}.png"
        cv2.imwrite(str(path), img)
        frame_paths.append(path)

    output_dir = tmp_path / "variance_out"
    result = run_temporal_variance_masking(frame_paths, output_dir, max_frames=None, low_var_quantile=0.30)

    assert result.output_path.exists(), "fused.png must exist"
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert "static_pixel_ratio" in summary
    assert result.strategy == "temporal_variance_masking"

    mask_path = output_dir / "mask.png"
    assert mask_path.exists(), "mask.png must exist"

    report_text = result.report_path.read_text(encoding="utf-8")
    assert "temporal_variance_masking" in report_text
    assert "Static-pixel ratio" in report_text

    fused = cv2.imread(str(result.output_path), cv2.IMREAD_GRAYSCALE).astype(np.float32)

    # Text region (always static) should retain brightness
    text_region = fused[TEXT_Y - TEXT_H : TEXT_Y + 5, TEXT_X : TEXT_X + TEXT_W]
    text_brightness = float(text_region.mean())

    # Rectangle region (always moving, spans x=10..130, y=10..40): should be suppressed
    rect_region = fused[rect_y : rect_y + RECT_H, 10:20]  # any position the rect occupied
    rect_brightness = float(rect_region.mean())

    assert text_brightness > rect_brightness, (
        f"Text region brightness {text_brightness:.1f} should exceed moving-BG region {rect_brightness:.1f}"
    )


# ---------------------------------------------------------------------------
# Pipeline selector routing tests
# ---------------------------------------------------------------------------


def test_pipeline_selector_routes_static_card_static_bg_to_median() -> None:
    from core.pipelines.ocr.credit_pipeline_selector import select_credit_pipeline

    profile = {
        "text_motion": {"type": "static_card", "confidence": 0.78},
        "background": {"type": "static", "confidence": 0.85},
        "layout": {"type": "center_single_column"},
        "difficulty": {"labels": [], "score": 0.1},
    }
    rec = select_credit_pipeline(profile)
    assert rec.temporal == "temporal_median_fusion", f"Expected temporal_median_fusion, got {rec.temporal}"
    assert "temporal_median_stack" in rec.steps


def test_pipeline_selector_routes_static_card_moving_bg_to_variance() -> None:
    from core.pipelines.ocr.credit_pipeline_selector import select_credit_pipeline

    profile = {
        "text_motion": {"type": "static_card", "confidence": 0.78},
        "background": {"type": "moving_scene", "confidence": 0.82},
        "layout": {"type": "lower_third"},
        "difficulty": {"labels": [], "score": 0.2},
    }
    rec = select_credit_pipeline(profile)
    assert rec.temporal == "temporal_variance_masking", f"Expected temporal_variance_masking, got {rec.temporal}"
    assert "temporal_variance_mask" in rec.steps


def test_pipeline_selector_accepts_router_native_static_bg_names() -> None:
    """Router emits flat_static / image_static — selector must route them to median."""
    from core.pipelines.ocr.credit_pipeline_selector import select_credit_pipeline

    for bg_type in ("flat_static", "image_static"):
        profile = {
            "text_motion": {"type": "static_card", "confidence": 0.78},
            "background": {"type": bg_type, "confidence": 0.85},
            "layout": {"type": "lower_third"},
            "difficulty": {"labels": [], "score": 0.1},
        }
        rec = select_credit_pipeline(profile)
        assert rec.temporal == "temporal_median_fusion", (
            f"Router-native bg={bg_type} must route to median, got {rec.temporal}"
        )


def test_pipeline_selector_unknown_bg_falls_back_to_variance() -> None:
    """Unknown BG → variance masking (conservative default; works for both BG kinds)."""
    from core.pipelines.ocr.credit_pipeline_selector import select_credit_pipeline

    profile = {
        "text_motion": {"type": "static_card", "confidence": 0.78},
        "background": {"type": "unknown", "confidence": 0.35},
        "layout": {"type": "center_single_column"},
        "difficulty": {"labels": [], "score": 0.3},
    }
    rec = select_credit_pipeline(profile)
    assert rec.temporal == "temporal_variance_masking"
    assert "temporal_median_fusion" in rec.fallback_pipelines


# ---------------------------------------------------------------------------
# Edge case: too few frames
# ---------------------------------------------------------------------------


def test_temporal_fusion_handles_too_few_frames(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    from core.pipelines.ocr.temporal_fusion import run_temporal_median_fusion

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    # Create exactly 1 valid frame
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    path = frames_dir / "single.png"
    cv2.imwrite(str(path), img)

    with pytest.raises(RuntimeError, match="at least 2"):
        run_temporal_median_fusion([path], tmp_path / "out")


# ---------------------------------------------------------------------------
# Hook skip test (no cv2 needed)
# ---------------------------------------------------------------------------


def test_temporal_fusion_hook_skips_when_recommendation_mismatches() -> None:
    from core.pipelines.ocr.credit_experiment import _run_temporal_fusion_hook

    fake_profile: dict = {
        "recommended_pipeline": {
            "temporal": "row_reconstruct",
        }
    }
    result = _run_temporal_fusion_hook(Path("."), [], fake_profile)
    assert result["status"] == "skipped"
    assert "row_reconstruct" in result["reason"]


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


def test_cli_runs_auto_strategy_and_writes_both_outputs(tmp_path: Path, capsys) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    from scripts import ocr_temporal_fusion as cli

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    rng = np.random.default_rng(7)
    base = np.zeros((120, 180, 3), dtype=np.uint8)
    cv2.putText(base, "TEST", (40, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    for i in range(6):
        noisy = (base.astype(np.int32) + rng.integers(-20, 21, size=base.shape)).clip(0, 255).astype(np.uint8)
        cv2.imwrite(str(frames_dir / f"f_{i:02d}.png"), noisy)

    out_dir = tmp_path / "out"
    code = cli.main(["--strategy", "auto", "--frames-dir", str(frames_dir), "--output-dir", str(out_dir)])
    assert code == 0

    assert (out_dir / "median" / "fused.png").exists()
    assert (out_dir / "median" / "summary.json").exists()
    assert (out_dir / "variance" / "fused.png").exists()
    assert (out_dir / "variance" / "mask.png").exists()

    captured = json.loads(capsys.readouterr().out)
    assert "median" in captured and "variance" in captured
