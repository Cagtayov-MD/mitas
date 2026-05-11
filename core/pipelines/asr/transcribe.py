from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable, Sequence

from core.pipelines.asr.normalize import PROJECT_ROOT, TARGET_CODEC_NAME, TARGET_SAMPLE_RATE, probe_audio_stream
from core.pipelines.asr.vad import VadSpeechSegment


DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "asr" / "faster-whisper" / "large-v3"
DEFAULT_DEVICE = "cuda"
DEFAULT_COMPUTE_TYPE = "float16"
DEFAULT_BEAM_SIZE = 5
TRANSCRIBE_MULTILINGUAL = True
TRANSCRIBE_WORD_TIMESTAMPS = False
TRANSCRIBE_VAD_FILTER = False


class AudioTranscribeError(RuntimeError):
    """Raised when ASR transcription cannot run."""

    def __init__(self, message: str, *, command: tuple[str, ...] | None = None, stderr: str | None = None) -> None:
        super().__init__(message)
        self.command = command
        self.stderr = stderr


@dataclass(frozen=True)
class WhisperModelConfig:
    model_path: Path = DEFAULT_MODEL_PATH
    device: str = DEFAULT_DEVICE
    compute_type: str = DEFAULT_COMPUTE_TYPE
    beam_size: int = DEFAULT_BEAM_SIZE


@dataclass(frozen=True)
class TranscriptSegment:
    index: int
    start: float
    end: float
    text: str
    language: str | None
    avg_logprob: float
    no_speech_prob: float
    source_vad_index: int


@dataclass(frozen=True)
class TranscribeResult:
    audio_path: Path
    model_path: Path
    device: str
    compute_type: str
    multilingual: bool
    vad_segments_count: int
    segments: list[TranscriptSegment]
    transcript: str
    language_distribution: dict[str, int]


def load_whisper_model(config: WhisperModelConfig | None = None) -> Any:
    model_config = config or WhisperModelConfig()
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AudioTranscribeError("faster-whisper is not installed in this Python environment") from exc

    return WhisperModel(
        str(model_config.model_path),
        device=model_config.device,
        compute_type=model_config.compute_type,
        local_files_only=True,
    )


def transcribe_vad_segments(
    audio_path: str | Path,
    vad_segments: Sequence[VadSpeechSegment],
    *,
    model: Any | None = None,
    config: WhisperModelConfig | None = None,
    chunk_output_dir: str | Path | None = None,
    ffmpeg_executable: str = "ffmpeg",
) -> TranscribeResult:
    model_config = config or WhisperModelConfig()
    path = Path(audio_path)
    stream = probe_audio_stream(path)
    if not stream.is_target_wav:
        raise AudioTranscribeError(
            "faster-whisper transcribe expects normalized 16 kHz mono PCM WAV input; "
            f"got codec={stream.codec_name}, sample_rate={stream.sample_rate}, "
            f"channels={stream.channels}, sample_fmt={stream.sample_fmt}"
        )

    if not vad_segments:
        return _empty_result(path, model_config)

    whisper_model = model if model is not None else load_whisper_model(model_config)

    if chunk_output_dir is None:
        with tempfile.TemporaryDirectory() as temp_dir:
            return _transcribe_with_chunk_dir(
                path,
                vad_segments,
                whisper_model,
                model_config,
                chunk_dir=Path(temp_dir),
                ffmpeg_executable=ffmpeg_executable,
            )

    chunk_dir = Path(chunk_output_dir)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    return _transcribe_with_chunk_dir(
        path,
        vad_segments,
        whisper_model,
        model_config,
        chunk_dir=chunk_dir,
        ffmpeg_executable=ffmpeg_executable,
    )


def _transcribe_with_chunk_dir(
    audio_path: Path,
    vad_segments: Sequence[VadSpeechSegment],
    model: Any,
    config: WhisperModelConfig,
    *,
    chunk_dir: Path,
    ffmpeg_executable: str,
) -> TranscribeResult:
    transcript_segments: list[TranscriptSegment] = []

    for vad_index, vad_segment in enumerate(vad_segments):
        chunk_path = chunk_dir / f"chunk_{vad_index:04d}_{int(vad_segment.start * 1000):08d}_{int(vad_segment.end * 1000):08d}.wav"
        extract_wav_chunk(audio_path, vad_segment, chunk_path, ffmpeg_executable=ffmpeg_executable)
        raw_segments, info = model.transcribe(
            str(chunk_path),
            beam_size=config.beam_size,
            multilingual=TRANSCRIBE_MULTILINGUAL,
            vad_filter=TRANSCRIBE_VAD_FILTER,
            word_timestamps=TRANSCRIBE_WORD_TIMESTAMPS,
            condition_on_previous_text=False,
        )
        transcript_segments.extend(_map_segments(raw_segments, info, vad_segment=vad_segment, vad_index=vad_index))

    indexed_segments = [
        TranscriptSegment(
            index=index,
            start=segment.start,
            end=segment.end,
            text=segment.text,
            language=segment.language,
            avg_logprob=segment.avg_logprob,
            no_speech_prob=segment.no_speech_prob,
            source_vad_index=segment.source_vad_index,
        )
        for index, segment in enumerate(sorted(transcript_segments, key=lambda item: (item.start, item.end)))
    ]
    transcript = " ".join(segment.text for segment in indexed_segments).strip()
    language_distribution = Counter(segment.language or "unknown" for segment in indexed_segments)

    return TranscribeResult(
        audio_path=audio_path,
        model_path=config.model_path,
        device=config.device,
        compute_type=config.compute_type,
        multilingual=TRANSCRIBE_MULTILINGUAL,
        vad_segments_count=len(vad_segments),
        segments=indexed_segments,
        transcript=transcript,
        language_distribution=dict(language_distribution),
    )


def extract_wav_chunk(
    audio_path: str | Path,
    vad_segment: VadSpeechSegment,
    output_path: str | Path,
    *,
    ffmpeg_executable: str = "ffmpeg",
) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = (
        ffmpeg_executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{vad_segment.start:.3f}",
        "-t",
        f"{vad_segment.duration:.3f}",
        "-i",
        str(audio_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-acodec",
        TARGET_CODEC_NAME,
        str(destination),
    )
    _run_command(command)
    return destination


def _map_segments(
    raw_segments: Iterable[Any],
    info: Any,
    *,
    vad_segment: VadSpeechSegment,
    vad_index: int,
) -> list[TranscriptSegment]:
    mapped: list[TranscriptSegment] = []
    fallback_language = getattr(info, "language", None)

    for raw_segment in raw_segments:
        text = str(getattr(raw_segment, "text", "")).strip()
        if not text:
            continue
        start = round(vad_segment.start + float(raw_segment.start), 3)
        end = round(min(vad_segment.end, vad_segment.start + float(raw_segment.end)), 3)
        if end <= start:
            continue
        mapped.append(
            TranscriptSegment(
                index=0,
                start=start,
                end=end,
                text=text,
                language=getattr(raw_segment, "language", None) or fallback_language,
                avg_logprob=float(getattr(raw_segment, "avg_logprob", 0.0) or 0.0),
                no_speech_prob=float(getattr(raw_segment, "no_speech_prob", 0.0) or 0.0),
                source_vad_index=vad_index,
            )
        )

    return mapped


def _empty_result(audio_path: Path, config: WhisperModelConfig) -> TranscribeResult:
    return TranscribeResult(
        audio_path=audio_path,
        model_path=config.model_path,
        device=config.device,
        compute_type=config.compute_type,
        multilingual=TRANSCRIBE_MULTILINGUAL,
        vad_segments_count=0,
        segments=[],
        transcript="",
        language_distribution={},
    )


def _run_command(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise AudioTranscribeError(f"Failed to run command: {command[0]}", command=command, stderr=str(exc)) from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        raise AudioTranscribeError(f"Audio chunk command failed: {stderr}", command=command, stderr=stderr)

    return completed

