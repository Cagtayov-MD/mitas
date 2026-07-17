from __future__ import annotations

from pathlib import Path

import pytest

from experiments.closing_credit_onset_vlm.batch_video_runner import (
    build_ffmpeg_command,
    extraction_contract,
    safe_source_slug,
    source_fingerprint,
    validate_frame_sequence,
    validate_roots,
)


def test_unicode_slug_is_ascii_bounded_and_path_identity_is_stable(tmp_path: Path) -> None:
    source = tmp_path / "ATTİLA MARCEL'in ŞEHRİ.mp4"
    source.write_bytes(b"video")

    first = safe_source_slug(source, 35)
    second = safe_source_slug(source, 35)

    assert first == second
    assert first.startswith("035_ATT_LA_MARCEL_in_EHR")
    assert len(first) <= 69
    assert all(character.isascii() for character in first)


def test_source_fingerprint_changes_when_edge_bytes_change(tmp_path: Path) -> None:
    source = tmp_path / "film.mp4"
    source.write_bytes(b"a" * 64)
    before = source_fingerprint(source, edge_bytes=8)
    source.write_bytes(b"b" + b"a" * 63)
    after = source_fingerprint(source, edge_bytes=8)

    assert before["path"] == after["path"]
    assert before["size_bytes"] == after["size_bytes"]
    assert before["edge_sha256"] != after["edge_sha256"]


def test_600_second_contract_is_exactly_900_frames_and_absolute_seek() -> None:
    contract = extraction_contract(
        {"duration_seconds": 5992.341},
        tail_seconds=600.0,
        fps=1.5,
    )

    assert contract["tail_start_seconds"] == pytest.approx(5392.341)
    assert contract["clip_seconds"] == 600.0
    assert contract["expected_frames"] == 900
    assert contract["last_file"] == "c_0900.png"


def test_ffmpeg_command_uses_argv_fixed_tail_fps_and_lossless_png(tmp_path: Path) -> None:
    source = tmp_path / "ATTİLA MARCEL.mp4"
    stage = tmp_path / "stage"
    contract = extraction_contract(
        {"duration_seconds": 1000.0}, tail_seconds=600.0, fps=1.5
    )

    command = build_ffmpeg_command(source, stage, contract, Path("ffmpeg.exe"))

    assert command[0] == "ffmpeg.exe"
    assert command[command.index("-ss") + 1] == "400.000000"
    assert command[command.index("-t") + 1] == "600.000000"
    assert command[command.index("-vf") + 1] == "fps=1.5"
    assert command[-1] == str(stage / "c_%04d.png")
    assert "-compression_level" in command


def test_frame_sequence_gate_requires_exact_contiguous_contract(tmp_path: Path) -> None:
    for index in (1, 2, 4):
        (tmp_path / f"c_{index:04d}.png").write_bytes(b"png")

    invalid = validate_frame_sequence(tmp_path, 4)
    (tmp_path / "c_0003.png").write_bytes(b"png")
    valid = validate_frame_sequence(tmp_path, 4)

    assert invalid["ok"] is False
    assert invalid["errors"]
    assert valid["ok"] is True
    assert valid["first_file"] == "c_0001.png"
    assert valid["last_file"] == "c_0004.png"


def test_roots_reject_input_mutation_and_output_outside_allowlist(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    with pytest.raises(ValueError, match="scratch root"):
        validate_roots(input_root, input_root / "scratch", allowed / "batch", allowed)
    with pytest.raises(ValueError, match="batch output"):
        validate_roots(input_root, tmp_path / "scratch", tmp_path / "outside", allowed)

    validate_roots(
        input_root,
        tmp_path / "scratch",
        allowed / "batch",
        allowed,
    )
