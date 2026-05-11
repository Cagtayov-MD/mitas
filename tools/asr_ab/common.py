from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Callable, Iterable, Sequence

from core.pipelines.asr.normalize import PROJECT_ROOT, TARGET_CODEC_NAME, TARGET_SAMPLE_RATE
from core.pipelines.asr.transcribe import DEFAULT_MODEL_PATH, WhisperModelConfig, load_whisper_model
from core.pipelines.asr.vad import VadSpeechSegment, read_wav_duration_seconds, run_silero_vad


DEFAULT_AUDIO_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "real_media_smoke"
    / "beyaz2_08_11"
    / "normalized"
    / "beyaz2_08_11_c1022f8a96_16000hz_mono_s16.wav"
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "asr_ab" / "beyaz2_08_11"
DEFAULT_FFMPEG_EXE = (
    PROJECT_ROOT
    / "tools"
    / "ffmpeg-shared"
    / "ffmpeg-8.1.1-full_build-shared"
    / "bin"
    / "ffmpeg.exe"
)
CODE_SWITCH_PROMPT = (
    "Türkçe yayın programı. Konuklar Türkçe sohbet ediyor, "
    "zaman zaman İngilizce şarkı, film veya marka adı geçiyor."
)


@dataclass(frozen=True)
class Chunk:
    index: int
    start: float
    end: float
    source_vad_index: int | None = None

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)


@dataclass(frozen=True)
class VariantConfig:
    name: str
    description: str
    output_name: str
    chunk_builder: Callable[[Sequence[VadSpeechSegment], float], list[Chunk]]
    transcribe_kwargs: dict[str, Any]
    model_path: Path = DEFAULT_MODEL_PATH
    compute_type: str = "float16"
    use_vad_for_transcribe: bool = True
    run_vad_metadata: bool = True
    exit_after_write: bool = False
    skip_initial_overlap_seconds: float | None = None
    single_pass: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, default=DEFAULT_AUDIO_PATH)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG_EXE)
    return parser.parse_args()


def standard_tr_kwargs(*, condition_on_previous_text: bool, vad_filter: bool = False) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "beam_size": 5,
        "language": "tr",
        "multilingual": False,
        "initial_prompt": CODE_SWITCH_PROMPT,
        "condition_on_previous_text": condition_on_previous_text,
        "vad_filter": vad_filter,
        "word_timestamps": False,
        "temperature": [0.0, 0.2, 0.4],
        "compression_ratio_threshold": 2.4,
        "log_prob_threshold": -1.0,
        "no_speech_threshold": 0.6,
    }
    if vad_filter:
        kwargs["vad_parameters"] = {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 200,
        }
    return kwargs


def multilingual_code_switch_kwargs(*, condition_on_previous_text: bool, vad_filter: bool = False) -> dict[str, Any]:
    kwargs = standard_tr_kwargs(condition_on_previous_text=condition_on_previous_text, vad_filter=vad_filter)
    kwargs["language"] = None
    kwargs["multilingual"] = True
    return kwargs


def no_prompt_tr_kwargs(*, condition_on_previous_text: bool, vad_filter: bool = False) -> dict[str, Any]:
    kwargs = standard_tr_kwargs(condition_on_previous_text=condition_on_previous_text, vad_filter=vad_filter)
    kwargs.pop("initial_prompt", None)
    return kwargs


def baseline_kwargs() -> dict[str, Any]:
    return {
        "beam_size": 5,
        "multilingual": True,
        "vad_filter": False,
        "word_timestamps": False,
        "condition_on_previous_text": False,
    }


def build_current_vad_chunks(vad_segments: Sequence[VadSpeechSegment], audio_duration: float) -> list[Chunk]:
    from core.pipelines.asr.transcribe import build_transcribe_chunks

    chunks = build_transcribe_chunks(vad_segments, audio_duration=audio_duration, padding_seconds=1.5)
    return [
        Chunk(
            index=index,
            start=chunk.chunk_segment.start,
            end=chunk.chunk_segment.end,
            source_vad_index=chunk.source_vad_index,
        )
        for index, chunk in enumerate(chunks)
    ]


def build_merged_chunks(vad_segments: Sequence[VadSpeechSegment], audio_duration: float) -> list[Chunk]:
    min_chunk = 12.0
    max_chunk = 30.0
    gap_merge = 1.2
    padding = 1.0

    if not vad_segments:
        return []

    groups: list[tuple[float, float]] = []
    current_start = vad_segments[0].start
    current_end = vad_segments[0].end

    for segment in vad_segments[1:]:
        gap = segment.start - current_end
        new_duration = segment.end - current_start
        if gap <= gap_merge and new_duration <= max_chunk:
            current_end = segment.end
        else:
            groups.append((current_start, current_end))
            current_start = segment.start
            current_end = segment.end
    groups.append((current_start, current_end))

    expanded: list[tuple[float, float]] = []
    for start, end in groups:
        if end - start >= min_chunk:
            expanded.append((start, end))
            continue
        needed = min_chunk - (end - start)
        left = needed / 2.0
        right = needed - left
        expanded.append((max(0.0, start - left), min(audio_duration, end + right)))

    padded: list[Chunk] = []
    for index, (start, end) in enumerate(expanded):
        previous_end = expanded[index - 1][1] if index > 0 else 0.0
        next_start = expanded[index + 1][0] if index + 1 < len(expanded) else audio_duration
        chunk_start = max(previous_end, start - padding)
        chunk_end = min(next_start, end + padding)
        padded.append(
            Chunk(
                index=index,
                start=round(chunk_start, 3),
                end=round(chunk_end, 3),
                source_vad_index=best_vad_index(chunk_start, chunk_end, vad_segments),
            )
        )
    return padded


def build_fixed_windows(vad_segments: Sequence[VadSpeechSegment], audio_duration: float) -> list[Chunk]:
    window = 28.0
    overlap = 2.0
    chunks: list[Chunk] = []
    start = 0.0
    index = 0
    while start < audio_duration:
        end = min(start + window, audio_duration)
        chunks.append(
            Chunk(
                index=index,
                start=round(start, 3),
                end=round(end, 3),
                source_vad_index=best_vad_index(start, end, vad_segments),
            )
        )
        if end >= audio_duration:
            break
        start = end - overlap
        index += 1
    return chunks


def build_single_pass_chunk(vad_segments: Sequence[VadSpeechSegment], audio_duration: float) -> list[Chunk]:
    return [Chunk(index=0, start=0.0, end=audio_duration, source_vad_index=None)]


def keep_segment(segment: dict[str, Any]) -> tuple[bool, str | None]:
    text = str(segment.get("text") or "").strip()
    if len(text) < 2:
        return False, "too_short"
    if float(segment.get("no_speech_prob") or 0.0) > 0.6:
        return False, "no_speech"
    if float(segment.get("avg_logprob") or 0.0) < -1.0:
        return False, "low_logprob"
    if segment.get("language") not in {"tr", "en", None}:
        return False, "unexpected_lang"
    if not any(character.isalnum() for character in text):
        return False, "no_alnum"
    return True, "low_confidence" if float(segment.get("no_speech_prob") or 0.0) > 0.3 else None


def run_variant(config: VariantConfig, *, audio_path: Path, output_root: Path, ffmpeg_executable: Path) -> None:
    output_dir = output_root / config.output_name
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir = output_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    timing: dict[str, Any] = {
        "variant": config.name,
        "description": config.description,
        "model_path": str(config.model_path),
        "audio_path": str(audio_path),
    }
    total_started = time.perf_counter()

    started = time.perf_counter()
    audio_duration = read_wav_duration_seconds(audio_path)
    vad_result = run_silero_vad(audio_path) if config.run_vad_metadata else None
    vad_segments = vad_result.speech_segments if vad_result is not None else []
    timing["load_vad_seconds"] = round(time.perf_counter() - started, 3)

    started = time.perf_counter()
    model = load_whisper_model(WhisperModelConfig(model_path=config.model_path, compute_type=config.compute_type))
    timing["load_model_seconds"] = round(time.perf_counter() - started, 3)

    chunks = config.chunk_builder(vad_segments, audio_duration)
    raw_segments: list[dict[str, Any]] = []
    transcribe_seconds = 0.0

    for chunk in chunks:
        if config.single_pass:
            chunk_path = audio_path
        else:
            chunk_path = chunk_dir / f"chunk_{chunk.index:04d}_{int(chunk.start * 1000):08d}_{int(chunk.end * 1000):08d}.wav"
            extract_wav_chunk(audio_path, chunk, chunk_path, ffmpeg_executable=ffmpeg_executable)

        started = time.perf_counter()
        segments, info = model.transcribe(str(chunk_path), **config.transcribe_kwargs)
        materialized_segments = list(segments)
        transcribe_seconds += time.perf_counter() - started

        for raw in materialized_segments:
            local_start = round(float(raw.start), 3)
            local_end = round(float(raw.end), 3)
            absolute_start = round(chunk.start + local_start, 3)
            absolute_end = round(min(chunk.end, chunk.start + local_end), 3)
            if absolute_end <= absolute_start:
                continue

            segment = build_raw_segment(raw, info, chunk, absolute_start=absolute_start, absolute_end=absolute_end)
            if (
                config.skip_initial_overlap_seconds is not None
                and chunk.index > 0
                and local_start < config.skip_initial_overlap_seconds
            ):
                segment["kept"] = False
                segment["drop_reason"] = "overlap_duplicate"
                segment["flags"] = ["overlap_duplicate"]
            else:
                apply_filter(segment)
            raw_segments.append(segment)

    clean_segments = [segment for segment in raw_segments if segment["kept"]]
    timing["transcribe_seconds"] = round(transcribe_seconds, 3)
    timing["total_seconds"] = round(time.perf_counter() - total_started, 3)
    timing["model_call_count"] = len(chunks)
    timing["raw_segment_count"] = len(raw_segments)
    timing["clean_segment_count"] = len(clean_segments)

    filter_report = build_filter_report(raw_segments, clean_segments)
    write_json(output_dir / "raw_segments.json", build_output_payload(config, audio_path, vad_result, chunks, raw_segments))
    write_json(output_dir / "clean_segments.json", build_output_payload(config, audio_path, vad_result, chunks, clean_segments))
    write_json(output_dir / "filter_report.json", filter_report)
    write_json(output_dir / "timing.json", timing)
    write_clean_transcript(output_dir / "clean_transcript.txt", clean_segments)
    if config.exit_after_write:
        # The converted Selimc CT2 model sometimes aborts during native CUDA teardown after outputs are written.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)


def build_raw_segment(raw: Any, info: Any, chunk: Chunk, *, absolute_start: float, absolute_end: float) -> dict[str, Any]:
    language = getattr(raw, "language", None) or getattr(info, "language", None)
    return {
        "start": absolute_start,
        "end": absolute_end,
        "duration": round(absolute_end - absolute_start, 3),
        "text": str(getattr(raw, "text", "")).strip(),
        "language": language,
        "avg_logprob": float(getattr(raw, "avg_logprob", 0.0) or 0.0),
        "no_speech_prob": float(getattr(raw, "no_speech_prob", 0.0) or 0.0),
        "compression_ratio": getattr(raw, "compression_ratio", None),
        "chunk_index": chunk.index,
        "chunk_start": chunk.start,
        "chunk_end": chunk.end,
        "source_vad_index": chunk.source_vad_index,
        "kept": True,
        "drop_reason": None,
        "flags": [],
    }


def apply_filter(segment: dict[str, Any]) -> None:
    kept, reason = keep_segment(segment)
    segment["kept"] = kept
    if kept:
        segment["drop_reason"] = None
        segment["flags"] = [reason] if reason else []
    else:
        segment["drop_reason"] = reason
        segment["flags"] = [reason] if reason else []


def build_filter_report(raw_segments: Sequence[dict[str, Any]], clean_segments: Sequence[dict[str, Any]]) -> dict[str, Any]:
    drop_reasons = Counter(segment["drop_reason"] for segment in raw_segments if not segment["kept"])
    flags = Counter(flag for segment in raw_segments for flag in segment["flags"])
    languages_raw = Counter(segment.get("language") or "unknown" for segment in raw_segments)
    languages_clean = Counter(segment.get("language") or "unknown" for segment in clean_segments)
    return {
        "raw_segment_count": len(raw_segments),
        "clean_segment_count": len(clean_segments),
        "dropped_segment_count": len(raw_segments) - len(clean_segments),
        "drop_reasons": dict(drop_reasons),
        "flags": dict(flags),
        "languages_raw": dict(languages_raw),
        "languages_clean": dict(languages_clean),
    }


def build_output_payload(
    config: VariantConfig,
    audio_path: Path,
    vad_result: Any | None,
    chunks: Sequence[Chunk],
    segments: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "variant": config.name,
        "description": config.description,
        "audio_path": str(audio_path),
        "vad": None
        if vad_result is None
        else {
            "audio_duration": vad_result.audio_duration,
            "speech_segments_count": len(vad_result.speech_segments),
            "speech_seconds": vad_result.speech_seconds,
            "speech_ratio": vad_result.speech_ratio,
            "threshold": vad_result.threshold,
            "segments": [asdict(segment) for segment in vad_result.speech_segments],
        },
        "chunks": [asdict(chunk) for chunk in chunks],
        "segments": list(segments),
    }


def write_clean_transcript(path: Path, clean_segments: Sequence[dict[str, Any]]) -> None:
    paragraphs: list[str] = []
    current: list[str] = []
    previous_end: float | None = None

    for segment in clean_segments:
        start = float(segment["start"])
        if previous_end is not None and start - previous_end >= 2.0 and current:
            paragraphs.append(clean_join(current))
            current = []
        current.append(str(segment["text"]).strip())
        previous_end = float(segment["end"])

    if current:
        paragraphs.append(clean_join(current))

    path.write_text("\n\n".join(paragraphs).strip() + "\n", encoding="utf-8")


def clean_join(parts: Sequence[str]) -> str:
    text = " ".join(part for part in parts if part)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_wav_chunk(audio_path: Path, chunk: Chunk, output_path: Path, *, ffmpeg_executable: Path) -> None:
    command = (
        str(ffmpeg_executable),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{chunk.start:.3f}",
        "-t",
        f"{chunk.duration:.3f}",
        "-i",
        str(audio_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-acodec",
        TARGET_CODEC_NAME,
        str(output_path),
    )
    subprocess.run(command, check=True)


def best_vad_index(start: float, end: float, vad_segments: Sequence[VadSpeechSegment]) -> int | None:
    best_index: int | None = None
    best_overlap = 0.0
    for index, segment in enumerate(vad_segments):
        overlap = max(0.0, min(end, segment.end) - max(start, segment.start))
        if overlap > best_overlap:
            best_overlap = overlap
            best_index = index
    return best_index


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main_for(config: VariantConfig) -> None:
    args = parse_args()
    run_variant(config, audio_path=args.audio, output_root=args.out_root, ffmpeg_executable=args.ffmpeg)
