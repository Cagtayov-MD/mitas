from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable, Sequence

from core.pipelines.asr.normalize import PROJECT_ROOT, TARGET_CODEC_NAME, TARGET_SAMPLE_RATE, probe_audio_stream
from core.pipelines.asr.quality import QualityConfig, ResultSafetyDecision, evaluate_result_safety, evaluate_segment
from core.pipelines.asr.vad import VadSpeechSegment, read_wav_duration_seconds


DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "asr" / "faster-whisper" / "large-v3"
DEFAULT_DEVICE = "cuda"
DEFAULT_COMPUTE_TYPE = "float16"
DEFAULT_BEAM_SIZE = 5
TRANSCRIBE_MULTILINGUAL = True
TRANSCRIBE_WORD_TIMESTAMPS = False
TRANSCRIBE_VAD_FILTER = False
DEFAULT_CHUNK_PADDING_SECONDS = 1.5


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
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class TranscribeChunk:
    source_vad_index: int
    vad_segment: VadSpeechSegment
    chunk_segment: VadSpeechSegment


@dataclass(frozen=True)
class TranscribeResult:
    audio_path: Path
    model_path: Path
    device: str
    compute_type: str
    multilingual: bool
    chunk_padding_seconds: float
    vad_segments_count: int
    segments: list[TranscriptSegment]
    transcript: str
    language_distribution: dict[str, int]
    safety: ResultSafetyDecision | None = None
    quality_drops: list[dict[str, Any]] = field(default_factory=list)


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
    chunk_padding_seconds: float = DEFAULT_CHUNK_PADDING_SECONDS,
    ffmpeg_executable: str = "ffmpeg",
    quality_config: QualityConfig | None = None,
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
        return _empty_result(path, model_config, chunk_padding_seconds=chunk_padding_seconds)

    whisper_model = model if model is not None else load_whisper_model(model_config)
    audio_duration = read_wav_duration_seconds(path)
    chunks = build_transcribe_chunks(vad_segments, audio_duration=audio_duration, padding_seconds=chunk_padding_seconds)

    if chunk_output_dir is None:
        with tempfile.TemporaryDirectory() as temp_dir:
            return _transcribe_with_chunk_dir(
                path,
                chunks,
                whisper_model,
                model_config,
                chunk_padding_seconds=chunk_padding_seconds,
                chunk_dir=Path(temp_dir),
                ffmpeg_executable=ffmpeg_executable,
                quality_config=quality_config,
            )

    chunk_dir = Path(chunk_output_dir)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    return _transcribe_with_chunk_dir(
        path,
        chunks,
        whisper_model,
        model_config,
        chunk_padding_seconds=chunk_padding_seconds,
        chunk_dir=chunk_dir,
        ffmpeg_executable=ffmpeg_executable,
        quality_config=quality_config,
    )


def _transcribe_with_chunk_dir(
    audio_path: Path,
    chunks: Sequence[TranscribeChunk],
    model: Any,
    config: WhisperModelConfig,
    *,
    chunk_padding_seconds: float,
    chunk_dir: Path,
    ffmpeg_executable: str,
    quality_config: QualityConfig | None,
) -> TranscribeResult:
    transcript_segments: list[TranscriptSegment] = []

    for chunk in chunks:
        chunk_path = (
            chunk_dir
            / f"chunk_{chunk.source_vad_index:04d}_{int(chunk.chunk_segment.start * 1000):08d}_{int(chunk.chunk_segment.end * 1000):08d}.wav"
        )
        extract_wav_chunk(audio_path, chunk.chunk_segment, chunk_path, ffmpeg_executable=ffmpeg_executable)
        raw_segments, info = model.transcribe(
            str(chunk_path),
            beam_size=config.beam_size,
            multilingual=TRANSCRIBE_MULTILINGUAL,
            vad_filter=TRANSCRIBE_VAD_FILTER,
            word_timestamps=TRANSCRIBE_WORD_TIMESTAMPS,
            condition_on_previous_text=False,
        )
        transcript_segments.extend(_map_segments(raw_segments, info, chunk=chunk))

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
            flags=segment.flags,
        )
        for index, segment in enumerate(sorted(transcript_segments, key=lambda item: (item.start, item.end)))
    ]
    clean_segments, quality_drops = _apply_quality_gate(indexed_segments, quality_config=quality_config)
    transcript = " ".join(segment.text for segment in clean_segments).strip()
    language_distribution = Counter(segment.language or "unknown" for segment in clean_segments)
    speech_seconds = sum(chunk.vad_segment.duration for chunk in chunks)
    safety = evaluate_result_safety(
        transcript_text=transcript,
        word_count=len(transcript.split()),
        speech_seconds=speech_seconds,
    )

    return TranscribeResult(
        audio_path=audio_path,
        model_path=config.model_path,
        device=config.device,
        compute_type=config.compute_type,
        multilingual=TRANSCRIBE_MULTILINGUAL,
        chunk_padding_seconds=chunk_padding_seconds,
        vad_segments_count=len(chunks),
        segments=clean_segments,
        transcript=transcript,
        language_distribution=dict(language_distribution),
        safety=safety,
        quality_drops=quality_drops,
    )


def _apply_quality_gate(
    raw_segments: list[TranscriptSegment],
    *,
    quality_config: QualityConfig | None = None,
) -> tuple[list[TranscriptSegment], list[dict[str, Any]]]:
    clean: list[TranscriptSegment] = []
    drops: list[dict[str, Any]] = []

    for segment in raw_segments:
        decision = evaluate_segment(
            text=segment.text,
            no_speech_prob=segment.no_speech_prob,
            avg_logprob=segment.avg_logprob,
            language=segment.language,
            config=quality_config,
        )
        if not decision.keep:
            drops.append(
                {
                    "index": segment.index,
                    "text": segment.text,
                    "start": segment.start,
                    "end": segment.end,
                    "reason": decision.drop_reason,
                    "flags": decision.flags,
                }
            )
            continue
        clean.append(replace(segment, flags=tuple(decision.flags)))

    return clean, drops


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


def build_transcribe_chunks(
    vad_segments: Sequence[VadSpeechSegment],
    *,
    audio_duration: float,
    padding_seconds: float = DEFAULT_CHUNK_PADDING_SECONDS,
) -> list[TranscribeChunk]:
    if padding_seconds < 0.0:
        raise AudioTranscribeError(f"chunk padding must be non-negative: {padding_seconds}")

    chunks: list[TranscribeChunk] = []
    for index, vad_segment in enumerate(vad_segments):
        previous_end = vad_segments[index - 1].end if index > 0 else 0.0
        next_start = vad_segments[index + 1].start if index + 1 < len(vad_segments) else audio_duration
        start = max(0.0, previous_end, vad_segment.start - padding_seconds)
        end = min(audio_duration, next_start, vad_segment.end + padding_seconds)
        if end <= start:
            continue
        chunk_segment = VadSpeechSegment(start=round(start, 3), end=round(end, 3), duration=round(end - start, 3))
        chunks.append(TranscribeChunk(source_vad_index=index, vad_segment=vad_segment, chunk_segment=chunk_segment))
    return chunks


def _map_segments(
    raw_segments: Iterable[Any],
    info: Any,
    *,
    chunk: TranscribeChunk,
) -> list[TranscriptSegment]:
    mapped: list[TranscriptSegment] = []
    fallback_language = getattr(info, "language", None)

    for raw_segment in raw_segments:
        text = str(getattr(raw_segment, "text", "")).strip()
        if not text:
            continue
        start = round(chunk.chunk_segment.start + float(raw_segment.start), 3)
        end = round(min(chunk.chunk_segment.end, chunk.chunk_segment.start + float(raw_segment.end)), 3)
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
                source_vad_index=chunk.source_vad_index,
                flags=(),
            )
        )

    return mapped


def _empty_result(audio_path: Path, config: WhisperModelConfig, *, chunk_padding_seconds: float) -> TranscribeResult:
    return TranscribeResult(
        audio_path=audio_path,
        model_path=config.model_path,
        device=config.device,
        compute_type=config.compute_type,
        multilingual=TRANSCRIBE_MULTILINGUAL,
        chunk_padding_seconds=chunk_padding_seconds,
        vad_segments_count=0,
        segments=[],
        transcript="",
        language_distribution={},
        safety=evaluate_result_safety(transcript_text="", word_count=0, speech_seconds=0.0),
        quality_drops=[],
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
