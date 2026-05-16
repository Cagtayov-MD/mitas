"""Production ASR transcription pipeline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
import logging
from pathlib import Path
import subprocess
import tempfile
from time import perf_counter
from typing import Any, Iterable, Sequence

from core.pipelines.asr.chunking import MergedChunk, build_merged_chunks
from core.pipelines.asr.models import (
    DEFAULT_TRANSCRIBE_PARAMS,
    FAST_MODEL,
    QUALITY_MODEL,
    ModelConfig,
    ProfileName,
    TranscribeParams,
    load_model,
)
from core.pipelines.asr.normalize import PROJECT_ROOT, TARGET_CODEC_NAME, TARGET_SAMPLE_RATE, probe_audio_stream
from core.pipelines.asr.quality import QualityConfig, ResultSafetyDecision, evaluate_result_safety, evaluate_segment
from core.pipelines.asr.result import DropRecord, ProductionTranscribeResult, TranscriptSegment, TranscribeTiming
from core.pipelines.asr.vad import VadSpeechSegment, read_wav_duration_seconds, run_silero_vad


logger = logging.getLogger("mitas.asr")

DEFAULT_MODEL_PATH = QUALITY_MODEL.model_path
DEFAULT_DEVICE = QUALITY_MODEL.device
DEFAULT_COMPUTE_TYPE = QUALITY_MODEL.compute_type
DEFAULT_BEAM_SIZE = QUALITY_MODEL.beam_size
TRANSCRIBE_MULTILINGUAL = True
TRANSCRIBE_WORD_TIMESTAMPS = False
TRANSCRIBE_VAD_FILTER = False
DEFAULT_CHUNK_PADDING_SECONDS = 1.5
_BUNDLED_FFMPEG = PROJECT_ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"
DEFAULT_FFMPEG_EXECUTABLE = str(_BUNDLED_FFMPEG) if _BUNDLED_FFMPEG.exists() else "ffmpeg"
CRITICAL_FALLBACK_DROP_PREFIXES = (
    "repetition_collapse",
    "long_token_artifact",
    "very_low_logprob_short_text",
    "multi_signal_low_quality",
)


class AsrPipelineError(RuntimeError):
    """Production pipeline failure."""

    def __init__(self, message: str, *, command: tuple[str, ...] | None = None, stderr: str | None = None) -> None:
        super().__init__(message)
        self.command = command
        self.stderr = stderr


class AudioTranscribeError(AsrPipelineError):
    """Backward-compatible error for legacy transcribe_vad_segments()."""


@dataclass(frozen=True)
class WhisperModelConfig:
    model_path: Path = DEFAULT_MODEL_PATH
    device: str = DEFAULT_DEVICE
    compute_type: str = DEFAULT_COMPUTE_TYPE
    beam_size: int = DEFAULT_BEAM_SIZE


@dataclass(frozen=True)
class TranscribeChunk:
    source_vad_index: int
    vad_segment: VadSpeechSegment
    chunk_segment: VadSpeechSegment


@dataclass(frozen=True)
class TranscribeResult:
    """Legacy result used by A/B regression tools."""

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


def transcribe(
    audio_path: str | Path,
    *,
    profile: ProfileName = "fast_with_fallback",
    vad_segments: Sequence[VadSpeechSegment] | None = None,
    quality_config: QualityConfig | None = None,
    safety_config: dict[str, Any] | None = None,
    ffmpeg_executable: str = DEFAULT_FFMPEG_EXECUTABLE,
    ffprobe_executable: str = "ffprobe",
) -> ProductionTranscribeResult:
    """Production ASR entry point for normalized 16 kHz mono PCM WAV input."""
    path = Path(audio_path)
    stream = probe_audio_stream(path, ffprobe_executable=ffprobe_executable)
    if not stream.is_target_wav:
        raise AsrPipelineError(
            "transcribe() expects normalized 16 kHz mono PCM WAV input; "
            f"got codec={stream.codec_name}, sample_rate={stream.sample_rate}, "
            f"channels={stream.channels}, sample_fmt={stream.sample_fmt}. Run normalize_audio() first."
        )

    started = perf_counter()
    audio_duration = read_wav_duration_seconds(path)

    if vad_segments is None:
        vad_result = run_silero_vad(path)
        vad_segments = vad_result.speech_segments
        vad_speech_seconds = vad_result.speech_seconds
        vad_speech_ratio = vad_result.speech_ratio
    else:
        vad_speech_seconds = round(sum(segment.duration for segment in vad_segments), 3)
        vad_speech_ratio = (
            round(min(1.0, vad_speech_seconds / audio_duration), 6) if audio_duration > 0.0 else 0.0
        )
    vad_segment_count = len(vad_segments)

    if not vad_segments:
        return _empty_result(
            path,
            audio_duration,
            profile,
            elapsed_seconds=perf_counter() - started,
            vad_speech_seconds=vad_speech_seconds,
            vad_speech_ratio=vad_speech_ratio,
            vad_segment_count=vad_segment_count,
        )

    chunks = build_merged_chunks(vad_segments, audio_duration=audio_duration)
    if not chunks:
        return _empty_result(
            path,
            audio_duration,
            profile,
            elapsed_seconds=perf_counter() - started,
            vad_speech_seconds=vad_speech_seconds,
            vad_speech_ratio=vad_speech_ratio,
            vad_segment_count=vad_segment_count,
        )

    expected_speech_end = _expected_speech_end(vad_segments)
    quality_cfg = quality_config or QualityConfig()
    safety_kwargs = safety_config or {}
    fallback_triggered = False
    fallback_reason = None
    fallback_time = 0.0
    fallback_chunk_count = 0
    fallback_total_chunk_count = 0
    fallback_mode = None
    selection_reason = None

    if profile == "quality":
        run_result = _run_single_pass(
            path,
            chunks,
            QUALITY_MODEL,
            quality_cfg,
            expected_speech_end=expected_speech_end,
            safety_kwargs=safety_kwargs,
            ffmpeg_executable=ffmpeg_executable,
        )
        profile_used = "quality"
        model_name = QUALITY_MODEL.name
        selection_reason = "profile_quality_requested"
    elif profile == "fast":
        run_result = _run_single_pass(
            path,
            chunks,
            FAST_MODEL,
            quality_cfg,
            expected_speech_end=expected_speech_end,
            safety_kwargs=safety_kwargs,
            ffmpeg_executable=ffmpeg_executable,
        )
        profile_used = "fast"
        model_name = FAST_MODEL.name
        selection_reason = "profile_fast_requested"
    elif profile == "fast_with_fallback":
        fast_result = _run_single_pass(
            path,
            chunks,
            FAST_MODEL,
            quality_cfg,
            expected_speech_end=expected_speech_end,
            safety_kwargs=safety_kwargs,
            ffmpeg_executable=ffmpeg_executable,
        )
        fast_failure = _fallback_failure_reason(fast_result)
        if fast_failure is None:
            run_result = fast_result
            profile_used = "fast"
            model_name = FAST_MODEL.name
            selection_reason = "fast_passed_fallback_checks"
        else:
            fallback_chunk_indexes = _select_fallback_chunk_indexes(
                fast_result,
                chunks,
                fast_failure=fast_failure,
            )
            fallback_chunks = [chunk for chunk in chunks if chunk.index in fallback_chunk_indexes]
            if not fallback_chunks:
                fallback_chunks = chunks
                fallback_chunk_indexes = tuple(chunk.index for chunk in chunks)

            fallback_chunk_count = len(fallback_chunks)
            fallback_total_chunk_count = len(chunks)
            fallback_mode = "full" if fallback_chunk_count == len(chunks) else "selective"
            logger.info(
                "ASR fallback triggered: reason=%s mode=%s chunks=%d/%d",
                fast_failure,
                fallback_mode,
                fallback_chunk_count,
                fallback_total_chunk_count,
            )
            fallback_started = perf_counter()
            quality_result = _run_single_pass(
                path,
                fallback_chunks,
                QUALITY_MODEL,
                quality_cfg,
                expected_speech_end=_expected_chunk_end(fallback_chunks),
                safety_kwargs=safety_kwargs,
                ffmpeg_executable=ffmpeg_executable,
            )
            fallback_time = perf_counter() - fallback_started
            fallback_triggered = True
            fallback_reason = fast_failure
            fallback_candidate = (
                quality_result
                if fallback_mode == "full"
                else _merge_selective_fallback_result(
                    fast_result,
                    quality_result,
                    selected_chunk_indexes=fallback_chunk_indexes,
                    quality_config=quality_cfg,
                    expected_speech_end=expected_speech_end,
                    safety_kwargs=safety_kwargs,
                )
            )
            run_result, profile_used, model_name, selection_reason = _select_fallback_result(
                fast_result,
                fallback_candidate,
                fast_failure=fast_failure,
                expected_speech_end=expected_speech_end,
            )
            if run_result is fallback_candidate and fallback_mode == "selective":
                profile_used = "fast_selective_quality"
                model_name = f"{FAST_MODEL.name}+{QUALITY_MODEL.name}"
            kept_fast_chunks = fallback_candidate.get("selective_kept_fast_chunks", ())
            selection_reason = (
                f"{selection_reason}:fallback_mode={fallback_mode}:"
                f"fallback_chunks={fallback_chunk_count}/{fallback_total_chunk_count}"
            )
            if kept_fast_chunks:
                selection_reason = (
                    f"{selection_reason}:kept_fast_chunks={len(kept_fast_chunks)}"
                    f"({','.join(str(index) for index in kept_fast_chunks)})"
                )
            logger.info(
                "ASR fallback selected: %s profile=%s model=%s",
                selection_reason,
                profile_used,
                model_name,
            )
    else:
        raise AsrPipelineError(f"Unknown ASR profile: {profile}")

    total_time = perf_counter() - started
    clean_segments = run_result["clean_segments"]
    return ProductionTranscribeResult(
        audio_path=path,
        audio_duration=audio_duration,
        profile_requested=profile,
        profile_used=profile_used,
        model_name=model_name,
        fallback_triggered=fallback_triggered,
        fallback_reason=fallback_reason,
        raw_segments=run_result["raw_segments"],
        clean_segments=clean_segments,
        verbatim_transcript=_build_verbatim(clean_segments),
        clean_transcript=_build_clean_paragraphs(clean_segments),
        normalized_transcript=None,
        quality_drops=run_result["drops"],
        safety=run_result["safety"],
        selection_reason=selection_reason,
        timing=TranscribeTiming(
            total_seconds=round(total_time, 3),
            chunk_count=len(chunks),
            decode_seconds=round(run_result["decode_time"], 3),
            fallback_seconds=round(fallback_time, 3),
            fallback_chunk_count=fallback_chunk_count,
            fallback_total_chunk_count=fallback_total_chunk_count,
            fallback_mode=fallback_mode,
        ),
        speaker_segments=[],
        normalized_entities=[],
        vad_speech_seconds=vad_speech_seconds,
        vad_speech_ratio=vad_speech_ratio,
        vad_segment_count=vad_segment_count,
    )


def _run_single_pass(
    audio_path: Path,
    chunks: list[MergedChunk],
    model_config: ModelConfig,
    quality_config: QualityConfig,
    *,
    expected_speech_end: float | None,
    safety_kwargs: dict[str, Any],
    ffmpeg_executable: str,
    transcribe_params: TranscribeParams = DEFAULT_TRANSCRIBE_PARAMS,
) -> dict[str, Any]:
    model = load_model(model_config)
    raw_segments: list[TranscriptSegment] = []

    decode_started = perf_counter()
    for chunk in chunks:
        raw_segments.extend(
            _transcribe_chunk(
                audio_path,
                chunk,
                model,
                model_config,
                transcribe_params,
                ffmpeg_executable=ffmpeg_executable,
            )
        )
    decode_time = perf_counter() - decode_started

    raw_segments = [
        replace(segment, index=index)
        for index, segment in enumerate(sorted(raw_segments, key=lambda item: (item.start, item.end)))
    ]

    return _evaluate_run_segments(
        raw_segments,
        quality_config,
        expected_speech_end=expected_speech_end,
        safety_kwargs=safety_kwargs,
        decode_time=decode_time,
    )


def _evaluate_run_segments(
    raw_segments: list[TranscriptSegment],
    quality_config: QualityConfig,
    *,
    expected_speech_end: float | None,
    safety_kwargs: dict[str, Any],
    decode_time: float,
) -> dict[str, Any]:
    raw_segments = [
        replace(segment, index=index)
        for index, segment in enumerate(sorted(raw_segments, key=lambda item: (item.start, item.end)))
    ]

    clean_segments: list[TranscriptSegment] = []
    drops: list[DropRecord] = []
    for segment in raw_segments:
        decision = evaluate_segment(
            text=segment.text,
            no_speech_prob=segment.no_speech_prob,
            avg_logprob=segment.avg_logprob,
            language=segment.language,
            config=quality_config,
        )
        if decision.keep:
            clean_segments.append(replace(segment, flags=tuple(decision.flags)))
        else:
            drops.append(
                DropRecord(
                    original_index=segment.index,
                    text=segment.text,
                    start=segment.start,
                    end=segment.end,
                    reason=decision.drop_reason or "unknown",
                    flags=tuple(decision.flags),
                )
            )

    transcript_text = " ".join(segment.text for segment in clean_segments).strip()
    speech_seconds = sum(segment.end - segment.start for segment in clean_segments)
    transcript_last_end = max((segment.end for segment in clean_segments), default=None)
    safety_inputs = {
        "transcript_text": transcript_text,
        "word_count": len(transcript_text.split()),
        "speech_seconds": speech_seconds,
        "expected_speech_end": expected_speech_end,
        "transcript_last_end": transcript_last_end,
        **safety_kwargs,
    }
    safety = evaluate_result_safety(**safety_inputs)

    return {
        "raw_segments": raw_segments,
        "clean_segments": clean_segments,
        "drops": drops,
        "safety": safety,
        "decode_time": decode_time,
    }


def _transcribe_chunk(
    audio_path: Path,
    chunk: MergedChunk,
    model: Any,
    model_config: ModelConfig,
    params: TranscribeParams,
    *,
    ffmpeg_executable: str,
) -> list[TranscriptSegment]:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
        chunk_path = Path(temporary_file.name)

    try:
        extract_wav_chunk(
            audio_path,
            VadSpeechSegment(start=chunk.start, end=chunk.end, duration=chunk.duration),
            chunk_path,
            ffmpeg_executable=ffmpeg_executable,
        )
        raw_segments, info = model.transcribe(
            str(chunk_path),
            beam_size=model_config.beam_size,
            language=params.language,
            multilingual=params.multilingual,
            initial_prompt=params.initial_prompt,
            condition_on_previous_text=params.condition_on_previous_text,
            vad_filter=params.vad_filter,
            word_timestamps=params.word_timestamps,
            temperature=list(params.temperature),
            compression_ratio_threshold=params.compression_ratio_threshold,
            log_prob_threshold=params.log_prob_threshold,
            no_speech_threshold=params.no_speech_threshold,
        )
        return _map_production_segments(raw_segments, info, chunk=chunk)
    finally:
        chunk_path.unlink(missing_ok=True)


def _map_production_segments(raw_segments: Iterable[Any], info: Any, *, chunk: MergedChunk) -> list[TranscriptSegment]:
    mapped: list[TranscriptSegment] = []
    fallback_language = getattr(info, "language", None)
    for raw_segment in raw_segments:
        text = str(getattr(raw_segment, "text", "")).strip()
        if not text:
            continue
        start = round(chunk.start + float(getattr(raw_segment, "start", 0.0)), 3)
        end = round(min(chunk.end, chunk.start + float(getattr(raw_segment, "end", 0.0))), 3)
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
                source_chunk_index=chunk.index,
                flags=(),
            )
        )
    return mapped


def _fallback_failure_reason(run_result: dict[str, Any]) -> str | None:
    # Drop reasons surfaced first: a critical drop (repetition, long-token,
    # very-low-logprob, multi-signal) often causes the downstream tail gap,
    # so the drop is the more informative root cause for telemetry.
    for drop in run_result["drops"]:
        if drop.reason.startswith(CRITICAL_FALLBACK_DROP_PREFIXES):
            return f"quality_drop:{drop.reason}"
    safety = run_result["safety"]
    if not safety.safe:
        return safety.failure_reason or "safety_failed"
    return None


def _select_fallback_chunk_indexes(
    fast_result: dict[str, Any],
    chunks: list[MergedChunk],
    *,
    fast_failure: str,
) -> tuple[int, ...]:
    selected: set[int] = set()
    valid_indexes = {chunk.index for chunk in chunks}
    safety = fast_result["safety"]
    safety_reason = None if safety.safe else safety.failure_reason

    if fast_failure.startswith("quality_drop:"):
        for drop in fast_result["drops"]:
            if drop.reason.startswith(CRITICAL_FALLBACK_DROP_PREFIXES):
                chunk_index = _drop_source_chunk_index(fast_result, drop)
                if chunk_index is not None:
                    selected.add(chunk_index)

    if fast_failure.startswith("tail_gap_uncovered") or (
        safety_reason is not None and safety_reason.startswith("tail_gap_uncovered")
    ):
        last_end = _last_clean_segment_end(fast_result)
        for chunk in chunks:
            if chunk.end > last_end:
                selected.add(chunk.index)
            elif chunk.start <= last_end <= chunk.end:
                selected.add(chunk.index)

    if not selected:
        for segment in fast_result["clean_segments"]:
            if "low_confidence" in segment.flags or "very_low_logprob" in segment.flags:
                selected.add(segment.source_chunk_index)

    if not selected:
        selected = valid_indexes

    return tuple(sorted(index for index in selected if index in valid_indexes))


def _drop_source_chunk_index(run_result: dict[str, Any], drop: DropRecord) -> int | None:
    raw_segments = run_result["raw_segments"]
    if 0 <= drop.original_index < len(raw_segments):
        return raw_segments[drop.original_index].source_chunk_index
    for segment in raw_segments:
        if segment.start == drop.start and segment.end == drop.end and segment.text == drop.text:
            return segment.source_chunk_index
    return None


def _expected_chunk_end(chunks: list[MergedChunk]) -> float | None:
    return max((chunk.end for chunk in chunks), default=None)


def _merge_selective_fallback_result(
    fast_result: dict[str, Any],
    quality_result: dict[str, Any],
    *,
    selected_chunk_indexes: Sequence[int],
    quality_config: QualityConfig,
    expected_speech_end: float | None,
    safety_kwargs: dict[str, Any],
    coverage_tolerance_seconds: float = 1.0,
    coverage_tolerance_ratio: float = 0.05,
) -> dict[str, Any]:
    selected = set(selected_chunk_indexes)
    # Per-chunk safety net. The whole-result coverage guard in
    # _select_fallback_result only inspects the LAST clean segment end, so a
    # chunk the quality re-pass fails to transcribe becomes an invisible
    # mid-timeline hole (fast segments dropped, nothing replaces them). Keep
    # the fast segments for any chunk whose quality speech coverage regressed
    # materially against fast.
    kept_fast_chunks: list[int] = []
    for chunk_index in sorted(selected):
        fast_seconds = _chunk_clean_speech_seconds(fast_result, chunk_index)
        quality_seconds = _chunk_clean_speech_seconds(quality_result, chunk_index)
        quality_regressed = (
            fast_seconds > 0.0
            and quality_seconds + coverage_tolerance_seconds < fast_seconds
            and quality_seconds < fast_seconds * (1.0 - coverage_tolerance_ratio)
        )
        if quality_regressed:
            kept_fast_chunks.append(chunk_index)
            logger.warning(
                "selective fallback kept fast for chunk %d: quality regressed "
                "(fast=%.2fs quality=%.2fs)",
                chunk_index,
                fast_seconds,
                quality_seconds,
            )

    quality_chunks = selected.difference(kept_fast_chunks)
    merged_raw = [
        segment
        for segment in fast_result["raw_segments"]
        if segment.source_chunk_index not in quality_chunks
    ]
    merged_raw.extend(
        segment
        for segment in quality_result["raw_segments"]
        if segment.source_chunk_index in quality_chunks
    )
    evaluated = _evaluate_run_segments(
        merged_raw,
        quality_config,
        expected_speech_end=expected_speech_end,
        safety_kwargs=safety_kwargs,
        decode_time=fast_result["decode_time"] + quality_result["decode_time"],
    )
    evaluated["selective_kept_fast_chunks"] = tuple(kept_fast_chunks)
    return evaluated


def _chunk_clean_speech_seconds(run_result: dict[str, Any], chunk_index: int) -> float:
    return sum(
        segment.end - segment.start
        for segment in run_result["clean_segments"]
        if segment.source_chunk_index == chunk_index
    )


def _select_fallback_result(
    fast_result: dict[str, Any],
    quality_result: dict[str, Any],
    *,
    fast_failure: str,
    expected_speech_end: float | None,
    coverage_tolerance_seconds: float = 1.0,
    coverage_tolerance_ratio: float = 0.05,
) -> tuple[dict[str, Any], str, str, str]:
    """Pick between fast and fallback (quality) results with honest reasoning.

    Order matters: when both passes are unsafe we MUST report that explicitly
    rather than silently returning fast under a "quality_unsafe" reason
    (audit HIGH-1). When only one side is unsafe we prefer the safe side.
    Otherwise we prefer the quality result unless its coverage is materially
    worse than fast's (kept_fast:quality_coverage_worse).
    """
    fast_safety = fast_result["safety"]
    quality_safety = quality_result["safety"]
    fast_last_end = _last_clean_segment_end(fast_result)
    quality_last_end = _last_clean_segment_end(quality_result)
    fast_coverage = _coverage_ratio(fast_last_end, expected_speech_end)
    quality_coverage = _coverage_ratio(quality_last_end, expected_speech_end)

    if not fast_safety.safe and not quality_safety.safe:
        fast_reason = fast_safety.failure_reason or "safety_failed"
        quality_reason = quality_safety.failure_reason or "safety_failed"
        if quality_last_end >= fast_last_end:
            return (
                quality_result,
                "quality",
                QUALITY_MODEL.name,
                "degraded_both_unsafe:fast="
                f"{fast_reason}:quality={quality_reason}:kept=quality:"
                f"fast_end={fast_last_end:.2f}:quality_end={quality_last_end:.2f}",
            )
        return (
            fast_result,
            "fast",
            FAST_MODEL.name,
            "degraded_both_unsafe:fast="
            f"{fast_reason}:quality={quality_reason}:kept=fast:"
            f"fast_end={fast_last_end:.2f}:quality_end={quality_last_end:.2f}",
        )

    if not quality_safety.safe:
        return (
            fast_result,
            "fast",
            FAST_MODEL.name,
            f"kept_fast:quality_unsafe:{quality_safety.failure_reason or 'safety_failed'}",
        )

    if not fast_safety.safe:
        return (
            quality_result,
            "quality",
            QUALITY_MODEL.name,
            f"selected_quality:fast_unsafe:{fast_failure}",
        )

    quality_is_much_shorter = (
        quality_last_end + coverage_tolerance_seconds < fast_last_end
        and quality_coverage + coverage_tolerance_ratio < fast_coverage
    )
    if quality_is_much_shorter:
        return (
            fast_result,
            "fast",
            FAST_MODEL.name,
            "kept_fast:quality_coverage_worse:"
            f"fast_end={fast_last_end:.2f}:quality_end={quality_last_end:.2f}",
        )

    return (
        quality_result,
        "quality",
        QUALITY_MODEL.name,
        f"selected_quality:fallback_reason={fast_failure}",
    )


def _last_clean_segment_end(run_result: dict[str, Any]) -> float:
    return max((segment.end for segment in run_result["clean_segments"]), default=0.0)


def _coverage_ratio(last_end: float, expected_speech_end: float | None) -> float:
    if expected_speech_end is None or expected_speech_end <= 0.0:
        return 0.0
    return max(0.0, min(1.0, last_end / expected_speech_end))


def _expected_speech_end(vad_segments: Sequence[VadSpeechSegment]) -> float | None:
    return max((segment.end for segment in vad_segments), default=None)


def _build_verbatim(segments: list[TranscriptSegment]) -> str:
    return " ".join(segment.text.strip() for segment in segments).strip()


def _build_clean_paragraphs(segments: list[TranscriptSegment]) -> str:
    if not segments:
        return ""

    paragraphs: list[list[str]] = [[segments[0].text.strip()]]
    last_end = segments[0].end
    for segment in segments[1:]:
        if segment.start - last_end >= 2.0:
            paragraphs.append([segment.text.strip()])
        else:
            paragraphs[-1].append(segment.text.strip())
        last_end = segment.end
    return "\n\n".join(" ".join(paragraph) for paragraph in paragraphs).strip()


def _empty_result(
    path: Path,
    duration: float,
    profile: str,
    *,
    elapsed_seconds: float = 0.0,
    vad_speech_seconds: float | None = None,
    vad_speech_ratio: float | None = None,
    vad_segment_count: int | None = None,
) -> ProductionTranscribeResult:
    return ProductionTranscribeResult(
        audio_path=path,
        audio_duration=duration,
        profile_requested=profile,
        profile_used=profile,
        model_name="",
        fallback_triggered=False,
        fallback_reason=None,
        raw_segments=[],
        clean_segments=[],
        verbatim_transcript="",
        clean_transcript="",
        normalized_transcript=None,
        quality_drops=[],
        safety=evaluate_result_safety(transcript_text="", word_count=0, speech_seconds=0.0),
        timing=TranscribeTiming(total_seconds=round(elapsed_seconds, 3), chunk_count=0, decode_seconds=0.0),
        speaker_segments=[],
        normalized_entities=[],
        vad_speech_seconds=vad_speech_seconds,
        vad_speech_ratio=vad_speech_ratio,
        vad_segment_count=vad_segment_count,
    )


def load_whisper_model(config: WhisperModelConfig | None = None) -> Any:
    """Backward-compatible model loader used by A/B tooling."""
    model_config = config or WhisperModelConfig()
    try:
        return load_model(
            ModelConfig(
                model_path=model_config.model_path,
                device=model_config.device,
                compute_type=model_config.compute_type,
                beam_size=model_config.beam_size,
                name=model_config.model_path.name,
            )
        )
    except RuntimeError as exc:
        raise AudioTranscribeError(str(exc)) from exc


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
    """Legacy VAD-segment transcriber retained for regression tests."""
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
        return _empty_legacy_result(path, model_config, chunk_padding_seconds=chunk_padding_seconds)

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
        transcript_segments.extend(_map_legacy_segments(raw_segments, info, chunk=chunk))

    indexed_segments = [
        replace(segment, index=index)
        for index, segment in enumerate(sorted(transcript_segments, key=lambda item: (item.start, item.end)))
    ]
    clean_segments, quality_drops = _apply_quality_gate(indexed_segments, quality_config=quality_config)
    transcript = " ".join(segment.text for segment in clean_segments).strip()
    language_distribution = Counter(segment.language or "unknown" for segment in clean_segments)
    speech_seconds = sum(chunk.vad_segment.duration for chunk in chunks)
    expected_speech_end = max((chunk.vad_segment.end for chunk in chunks), default=None)
    transcript_last_end = max((segment.end for segment in clean_segments), default=None)
    safety = evaluate_result_safety(
        transcript_text=transcript,
        word_count=len(transcript.split()),
        speech_seconds=speech_seconds,
        expected_speech_end=expected_speech_end,
        transcript_last_end=transcript_last_end,
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


def _map_legacy_segments(
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
                source_chunk_index=chunk.source_vad_index,
                flags=(),
                source_vad_index=chunk.source_vad_index,
            )
        )

    return mapped


def _empty_legacy_result(audio_path: Path, config: WhisperModelConfig, *, chunk_padding_seconds: float) -> TranscribeResult:
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
