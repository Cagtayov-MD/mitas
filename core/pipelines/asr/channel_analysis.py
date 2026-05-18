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

# Heuristic thresholds for redundant-stereo detection.
# pearson_median >= 0.90 AND midside_db_median <= -10 dB → likely two mics on same source.
REDUNDANT_STEREO_PEARSON_THRESHOLD = 0.90
REDUNDANT_STEREO_MIDSIDE_DB_THRESHOLD = -10.0


@dataclass(frozen=True)
class StereoRedundancyAnalysis:
    speech_windows_sampled: int
    speech_windows_used: int
    pearson_min: float | None
    pearson_p10: float | None
    pearson_median: float | None
    pearson_max: float | None
    midside_db_median: float | None
    is_redundant_stereo: bool
    redundancy_confidence: str  # "high" / "medium" / "low" / "insufficient_data"

    def to_dict(self) -> dict:
        return {
            "speech_windows_sampled": self.speech_windows_sampled,
            "speech_windows_used": self.speech_windows_used,
            "pearson_min": self.pearson_min,
            "pearson_p10": self.pearson_p10,
            "pearson_median": self.pearson_median,
            "pearson_max": self.pearson_max,
            "midside_db_median": self.midside_db_median,
            "is_redundant_stereo": self.is_redundant_stereo,
            "redundancy_confidence": self.redundancy_confidence,
        }


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
    ffprobe_executable: str | None = None,
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

    correlation = measure_lr_correlation(
        input_path,
        ffmpeg_executable=ffmpeg_executable,
        ffprobe_executable=ffprobe_executable,
        window_seconds=window_seconds,
    )
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
    ffprobe_executable: str | None = None,
    window_seconds: float = 5.0,
    max_windows: int = 5,
) -> float:
    """Return the lowest absolute Pearson correlation across sampled L/R windows."""
    source = Path(stereo_path)
    duration = _probe_duration_seconds(source, ffprobe_executable=ffprobe_executable)
    start_times = _analysis_start_times(duration, window_seconds=window_seconds, max_windows=max_windows)
    with tempfile.TemporaryDirectory() as temp_dir:
        correlations: list[float] = []
        for index, start_time in enumerate(start_times):
            analysis_wav = Path(temp_dir) / f"lr_analysis_{index}.wav"
            command = (
                ffmpeg_executable,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{start_time:.3f}",
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
            correlations.append(_wav_lr_correlation(analysis_wav))
        return min(correlations) if correlations else 1.0


def _analysis_start_times(duration_seconds: float | None, *, window_seconds: float, max_windows: int) -> tuple[float, ...]:
    if max_windows <= 1 or duration_seconds is None or duration_seconds <= window_seconds:
        return (0.0,)
    last_start = max(0.0, duration_seconds - window_seconds)
    return tuple(
        sorted(
            {
                round((last_start * index) / max(1, max_windows - 1), 3)
                for index in range(max_windows)
            }
        )
    )


def _probe_duration_seconds(path: Path, *, ffprobe_executable: str | None) -> float | None:
    if not ffprobe_executable:
        ffprobe_executable = "ffprobe"
    command = (
        ffprobe_executable,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    )
    try:
        completed = _run_command(command)
    except AudioNormalizeError:
        return None
    try:
        return max(0.0, float(completed.stdout.strip()))
    except ValueError:
        return None


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


# ---------------------------------------------------------------------------
# Stereo redundancy analysis (two separate mono WAVs)
# ---------------------------------------------------------------------------


def analyze_stereo_redundancy(
    left_wav: str | Path,
    right_wav: str | Path,
    *,
    window_seconds: float = 3.0,
    max_windows: int = 20,
    energy_floor_rms: float = 200.0,
    pearson_threshold: float = REDUNDANT_STEREO_PEARSON_THRESHOLD,
    midside_db_threshold: float = REDUNDANT_STEREO_MIDSIDE_DB_THRESHOLD,
) -> StereoRedundancyAnalysis:
    """Measure acoustic redundancy between two mono WAV files (split L/R channels).

    Samples up to max_windows windows across the clip, skips near-silent windows,
    and returns Pearson correlation and Mid/Side energy statistics.  These metrics
    are written to summary.json on every run so that later threshold decisions are
    data-driven.
    """
    left_path = Path(left_wav)
    right_path = Path(right_wav)

    duration = _mono_wav_duration(left_path)
    start_times = _analysis_start_times(duration, window_seconds=window_seconds, max_windows=max_windows)

    pearsons: list[float] = []
    midside_dbs: list[float] = []

    for start_time in start_times:
        l_samples = _read_mono_wav_window(left_path, start_time, window_seconds)
        r_samples = _read_mono_wav_window(right_path, start_time, window_seconds)
        if l_samples is None or r_samples is None:
            continue
        length = min(len(l_samples), len(r_samples))
        if length == 0:
            continue
        l = l_samples[:length]
        r = r_samples[:length]

        rms_l = math.sqrt(sum(x * x for x in l) / length)
        rms_r = math.sqrt(sum(x * x for x in r) / length)
        if rms_l < energy_floor_rms and rms_r < energy_floor_rms:
            continue

        pearsons.append(abs(_pearson(l, r)))

        mid_sq = sum(((a + b) / 2) ** 2 for a, b in zip(l, r)) / length
        side_sq = sum(((a - b) / 2) ** 2 for a, b in zip(l, r)) / length
        rms_mid = math.sqrt(mid_sq)
        rms_side = math.sqrt(side_sq)
        if rms_mid > 0:
            db = 20.0 * math.log10(max(rms_side, 1.0) / rms_mid)
            midside_dbs.append(db)

    sampled = len(start_times)
    used = len(pearsons)

    if used == 0:
        return StereoRedundancyAnalysis(
            speech_windows_sampled=sampled,
            speech_windows_used=0,
            pearson_min=None,
            pearson_p10=None,
            pearson_median=None,
            pearson_max=None,
            midside_db_median=None,
            is_redundant_stereo=False,
            redundancy_confidence="insufficient_data",
        )

    sorted_p = sorted(pearsons)
    p_median = _percentile(sorted_p, 50)
    p_p10 = _percentile(sorted_p, 10)
    ms_median = _percentile(sorted(midside_dbs), 50) if midside_dbs else None

    is_redundant = p_median >= pearson_threshold and (ms_median is None or ms_median <= midside_db_threshold)

    if is_redundant and p_median >= 0.95 and used >= 5:
        confidence = "high"
    elif is_redundant:
        confidence = "medium"
    elif p_median < 0.5:
        confidence = "low"
    else:
        confidence = "medium"

    return StereoRedundancyAnalysis(
        speech_windows_sampled=sampled,
        speech_windows_used=used,
        pearson_min=round(sorted_p[0], 6),
        pearson_p10=round(p_p10, 6),
        pearson_median=round(p_median, 6),
        pearson_max=round(sorted_p[-1], 6),
        midside_db_median=round(ms_median, 2) if ms_median is not None else None,
        is_redundant_stereo=is_redundant,
        redundancy_confidence=confidence,
    )


def _mono_wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return None


def _read_mono_wav_window(path: Path, start_seconds: float, duration_seconds: float) -> array.array | None:
    try:
        with wave.open(str(path), "rb") as wf:
            if wf.getsampwidth() != 2:
                return None
            rate = wf.getframerate()
            n_frames = wf.getnframes()
            start_frame = min(int(start_seconds * rate), n_frames)
            end_frame = min(start_frame + int(duration_seconds * rate), n_frames)
            if end_frame <= start_frame:
                return None
            wf.setpos(start_frame)
            raw = wf.readframes(end_frame - start_frame)
    except Exception:
        return None
    samples: array.array = array.array("h")
    samples.frombytes(raw)
    return samples


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (k - lo) * (sorted_values[hi] - sorted_values[lo])
