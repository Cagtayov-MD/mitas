"""Stereo channel analysis for ASR channel-mode auto selection."""

from __future__ import annotations

import array
from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
import tempfile
import wave

from core.pipelines.asr.normalize import AudioNormalizeError, AudioStreamInfo, TARGET_CODEC_NAME, TARGET_SAMPLE_RATE


LR_CORRELATION_MONO_THRESHOLD = 0.92


@dataclass(frozen=True)
class ChannelDecision:
    requested_mode: str
    effective_mode: str
    auto_decided: bool
    lr_correlation: float | None


def decide_channel_mode(
    input_path: str | Path,
    *,
    requested_mode: str,
    input_stream: AudioStreamInfo,
    ffmpeg_executable: str,
    window_seconds: float = 5.0,
    correlation_threshold: float = LR_CORRELATION_MONO_THRESHOLD,
) -> ChannelDecision:
    """Resolve requested channel mode to the effective ASR normalization mode."""
    if requested_mode in {"mono", "split"}:
        return ChannelDecision(
            requested_mode=requested_mode,
            effective_mode=requested_mode,
            auto_decided=False,
            lr_correlation=None,
        )
    if requested_mode != "auto":
        raise AudioNormalizeError(f"Unsupported ASR channel_mode: {requested_mode}")
    if input_stream.channels < 2:
        return ChannelDecision(
            requested_mode=requested_mode,
            effective_mode="mono",
            auto_decided=True,
            lr_correlation=None,
        )

    correlation = measure_lr_correlation(input_path, ffmpeg_executable=ffmpeg_executable, window_seconds=window_seconds)
    return ChannelDecision(
        requested_mode=requested_mode,
        effective_mode="mono" if correlation > correlation_threshold else "split",
        auto_decided=True,
        lr_correlation=round(correlation, 6),
    )


def measure_lr_correlation(
    stereo_path: str | Path,
    *,
    ffmpeg_executable: str,
    window_seconds: float = 5.0,
) -> float:
    """Return absolute Pearson correlation for L/R channels over a short decoded window."""
    source = Path(stereo_path)
    with tempfile.TemporaryDirectory() as temp_dir:
        analysis_wav = Path(temp_dir) / "lr_analysis.wav"
        command = (
            ffmpeg_executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-t",
            f"{window_seconds:.3f}",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "2",
            "-ar",
            str(TARGET_SAMPLE_RATE),
            "-acodec",
            TARGET_CODEC_NAME,
            str(analysis_wav),
        )
        _run_command(command)
        return _wav_lr_correlation(analysis_wav)


def _wav_lr_correlation(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.readframes(wav_file.getnframes())

    if channels < 2:
        return 1.0
    if sample_width != 2:
        raise AudioNormalizeError(f"Channel analysis expects 16-bit PCM WAV; got sample_width={sample_width}")

    samples = array.array("h")
    samples.frombytes(frames)
    if not samples:
        return 1.0

    left = samples[0::channels]
    right = samples[1::channels]
    if not left or not right:
        return 1.0
    length = min(len(left), len(right))
    return abs(_pearson(left[:length], right[:length]))


def _pearson(left: array.array[int], right: array.array[int]) -> float:
    count = len(left)
    if count == 0:
        return 1.0
    mean_l = sum(left) / count
    mean_r = sum(right) / count
    centered_l = [sample - mean_l for sample in left]
    centered_r = [sample - mean_r for sample in right]
    sum_l = sum(value * value for value in centered_l)
    sum_r = sum(value * value for value in centered_r)
    if sum_l == 0.0 and sum_r == 0.0:
        return 1.0 if list(left) == list(right) else 0.0
    if sum_l == 0.0 or sum_r == 0.0:
        return 0.0
    return sum(l_value * r_value for l_value, r_value in zip(centered_l, centered_r)) / math.sqrt(sum_l * sum_r)


def _run_command(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise AudioNormalizeError(f"Failed to run command: {command[0]}", command=command, stderr=str(exc)) from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        raise AudioNormalizeError(f"Audio command failed: {stderr}", command=command, stderr=stderr)
    return completed
