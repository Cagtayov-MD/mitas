from __future__ import annotations

from dataclasses import dataclass
import array
from pathlib import Path
import sys
from typing import Any
import wave

from core.pipelines.asr.normalize import TARGET_SAMPLE_RATE, probe_audio_stream


DEFAULT_THRESHOLD = 0.5
DEFAULT_MIN_SPEECH_DURATION_MS = 250
DEFAULT_MIN_SILENCE_DURATION_MS = 100
DEFAULT_SPEECH_PAD_MS = 30


class AudioVadError(RuntimeError):
    """Raised when VAD cannot run on the provided audio."""


@dataclass(frozen=True)
class VadSpeechSegment:
    start: float
    end: float
    duration: float


@dataclass(frozen=True)
class VadResult:
    audio_path: Path
    audio_duration: float
    speech_segments: list[VadSpeechSegment]
    speech_seconds: float
    speech_ratio: float
    threshold: float


def run_silero_vad(
    audio_path: str | Path,
    *,
    model: Any | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    min_speech_duration_ms: int = DEFAULT_MIN_SPEECH_DURATION_MS,
    min_silence_duration_ms: int = DEFAULT_MIN_SILENCE_DURATION_MS,
    speech_pad_ms: int = DEFAULT_SPEECH_PAD_MS,
) -> VadResult:
    path = Path(audio_path)
    stream = probe_audio_stream(path)
    if not stream.is_target_wav:
        raise AudioVadError(
            "Silero VAD expects normalized 16 kHz mono PCM WAV input; "
            f"got codec={stream.codec_name}, sample_rate={stream.sample_rate}, "
            f"channels={stream.channels}, sample_fmt={stream.sample_fmt}"
        )

    try:
        from silero_vad import get_speech_timestamps, load_silero_vad
    except ImportError as exc:
        raise AudioVadError("silero-vad is not installed in this Python environment") from exc

    vad_model = model if model is not None else load_silero_vad()
    waveform = read_normalized_wav_tensor(path)
    timestamps = get_speech_timestamps(
        waveform,
        vad_model,
        threshold=threshold,
        sampling_rate=TARGET_SAMPLE_RATE,
        min_speech_duration_ms=min_speech_duration_ms,
        min_silence_duration_ms=min_silence_duration_ms,
        speech_pad_ms=speech_pad_ms,
        return_seconds=True,
    )
    audio_duration = read_wav_duration_seconds(path)
    speech_segments = segments_from_timestamps(timestamps, audio_duration=audio_duration)
    speech_seconds = round(sum(segment.duration for segment in speech_segments), 3)
    speech_ratio = round(min(1.0, speech_seconds / audio_duration), 6) if audio_duration > 0.0 else 0.0

    return VadResult(
        audio_path=path,
        audio_duration=audio_duration,
        speech_segments=speech_segments,
        speech_seconds=speech_seconds,
        speech_ratio=speech_ratio,
        threshold=threshold,
    )


def read_wav_duration_seconds(audio_path: str | Path) -> float:
    path = Path(audio_path)
    with wave.open(str(path), "rb") as wav_file:
        frame_count = wav_file.getnframes()
        frame_rate = wav_file.getframerate()
    if frame_rate <= 0:
        raise AudioVadError(f"Invalid WAV frame rate: {frame_rate}")
    return round(frame_count / frame_rate, 3)


def read_normalized_wav_tensor(audio_path: str | Path) -> Any:
    path = Path(audio_path)
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frame_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())

    if channels != 1 or sample_width != 2 or frame_rate != TARGET_SAMPLE_RATE:
        raise AudioVadError(
            "Manual VAD WAV loader expects normalized 16 kHz mono 16-bit PCM WAV; "
            f"got channels={channels}, sample_width={sample_width}, frame_rate={frame_rate}"
        )

    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()

    try:
        import torch
    except ImportError as exc:
        raise AudioVadError("torch is required to build the Silero VAD waveform tensor") from exc

    return torch.tensor(samples, dtype=torch.float32) / 32768.0


def segments_from_timestamps(timestamps: list[dict[str, Any]], *, audio_duration: float) -> list[VadSpeechSegment]:
    normalized: list[VadSpeechSegment] = []
    for item in timestamps:
        start = max(0.0, float(item["start"]))
        end = min(audio_duration, float(item["end"]))
        if end <= start:
            continue
        normalized.append(VadSpeechSegment(start=round(start, 3), end=round(end, 3), duration=round(end - start, 3)))
    return normalized
