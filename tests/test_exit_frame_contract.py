from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import mitas_pipeline as pipeline  # noqa: E402


def test_exit_contract_is_exact_for_production_defaults():
    start, length, count = pipeline.exit_frame_contract(5835.989, 480.0, 1.5)

    assert start == pytest.approx(5355.989)
    assert length == 480.0
    assert count == 720


def test_exit_contract_uses_full_short_video():
    start, length, count = pipeline.exit_frame_contract(100.0, 480.0, 1.5)

    assert start == 0.0
    assert length == 100.0
    assert count == 150


def test_invalid_contract_fails_closed():
    with pytest.raises(pipeline.FrameContractError):
        pipeline.exit_frame_contract(0.0, 480.0, 1.5)

    with pytest.raises(pipeline.FrameContractError):
        pipeline.expected_frame_count(480.0, 0.0)


def test_extract_window_does_not_publish_incomplete_frames(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"placeholder")
    output = tmp_path / "cikis"
    output.mkdir()
    (output / "c_0001.png").write_bytes(b"old")

    def fake_run(cmd, timeout):
        pattern = Path(cmd[-1])
        pattern.parent.mkdir(parents=True, exist_ok=True)
        for index in range(1, 3):
            (pattern.parent / f"c_{index:04d}.png").write_bytes(b"new")
        return 0, "", ""

    monkeypatch.setattr(pipeline, "run", fake_run)

    with pytest.raises(pipeline.FrameContractError, match="beklenen=3, uretilen=2"):
        pipeline.extract_window(
            video,
            output,
            prefix="c",
            fps=1.5,
            start=0.0,
            length=2.0,
            expected_count=3,
        )

    assert (output / "c_0001.png").read_bytes() == b"old"
    assert sorted(output.glob("c_*.png")) == [output / "c_0001.png"]


def test_extract_window_replaces_stale_verified_output(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"placeholder")
    output = tmp_path / "cikis"
    output.mkdir()
    for index in range(1, 5):
        (output / f"c_{index:04d}.png").write_bytes(b"old")

    def fake_run(cmd, timeout):
        pattern = Path(cmd[-1])
        pattern.parent.mkdir(parents=True, exist_ok=True)
        for index in range(1, 4):
            (pattern.parent / f"c_{index:04d}.png").write_bytes(b"new")
        return 0, "", ""

    monkeypatch.setattr(pipeline, "run", fake_run)

    count = pipeline.extract_window(
        video,
        output,
        prefix="c",
        fps=1.5,
        start=0.0,
        length=2.0,
        expected_count=3,
    )

    assert count == 3
    assert [p.name for p in sorted(output.glob("c_*.png"))] == [
        "c_0001.png",
        "c_0002.png",
        "c_0003.png",
    ]
    assert all(p.read_bytes() == b"new" for p in output.glob("c_*.png"))
