from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(r"E:\MITAS")
MODEL_PATH = ROOT / "models" / "asr" / "faster-whisper" / "large-v3"
CLIP_NEWS = ROOT / "outputs" / "real_media_smoke" / "news_trt_haber_1_20s_16000hz_mono_asr_input.wav"
CLIP_PROMO = ROOT / "outputs" / "real_media_smoke" / "promo_1_20s_16000hz_mono_asr_input.wav"
CLIP_WAV = ROOT / "outputs" / "real_media_smoke" / "wav_erd_test_sound_20s_16000hz_mono_asr_input.wav"
CLIPS_3 = [CLIP_NEWS, CLIP_PROMO, CLIP_WAV]
CLIPS_4 = [CLIP_NEWS, CLIP_PROMO, CLIP_WAV, CLIP_NEWS]
CLIPS_5 = [CLIP_NEWS, CLIP_PROMO, CLIP_WAV, CLIP_NEWS, CLIP_PROMO]


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def segment_payload(segment: Any) -> dict[str, Any]:
    return {
        "start": round(float(segment.start), 6),
        "end": round(float(segment.end), 6),
        "text": segment.text.strip(),
        "avg_logprob": float(getattr(segment, "avg_logprob", 0.0) or 0.0),
        "no_speech_prob": float(getattr(segment, "no_speech_prob", 0.0) or 0.0),
    }


def new_model() -> tuple[Any, float]:
    started = time.perf_counter()
    from faster_whisper import WhisperModel

    model = WhisperModel(
        str(MODEL_PATH),
        device="cuda",
        compute_type="float16",
        local_files_only=True,
    )
    return model, round(time.perf_counter() - started, 3)


def transcribe(model: Any, clip: Path, explicit_log_progress_false: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    kwargs: dict[str, Any] = {
        "language": "tr",
        "beam_size": 1,
        "vad_filter": False,
        "condition_on_previous_text": False,
    }
    if explicit_log_progress_false:
        kwargs["log_progress"] = False
    segments_iter, info = model.transcribe(str(clip), **kwargs)
    segments = [segment_payload(segment) for segment in segments_iter]
    transcript = " ".join(segment["text"] for segment in segments).strip()
    return {
        "clip_path": str(clip),
        "segments_count": len(segments),
        "transcript": transcript,
        "transcript_present": bool(transcript),
        "detected_language": getattr(info, "language", None),
        "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
        "segments": segments,
        "transcribe_seconds": round(time.perf_counter() - started, 3),
    }


def same_instance(
    test_id: str,
    clips: list[Path],
    *,
    explicit_log_progress_false: bool = False,
    monkeypatch_tqdm: bool = False,
) -> int:
    started = time.perf_counter()
    model, load_seconds = new_model()
    results = []
    for clip in clips:
        results.append(transcribe(model, clip, explicit_log_progress_false=explicit_log_progress_false))
    transcripts_valid = all(item["transcript_present"] for item in results)
    emit(
        {
            "test_id": test_id,
            "model_id": "large-v3",
            "device": "cuda",
            "compute_type": "float16",
            "clips_count": len(clips),
            "clips": results,
            "transcripts_count": len(results),
            "transcripts_valid": transcripts_valid,
            "transcript_present": transcripts_valid,
            "load_seconds": load_seconds,
            "explicit_log_progress_false": explicit_log_progress_false,
            "monkeypatch_tqdm": monkeypatch_tqdm,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "notes": ["JSON emitted before normal child exit"],
        }
    )
    return 0


def single_clip_process(test_id: str, clip: Path) -> int:
    started = time.perf_counter()
    model, load_seconds = new_model()
    result = transcribe(model, clip)
    emit(
        {
            "test_id": test_id,
            "model_id": "large-v3",
            "device": "cuda",
            "compute_type": "float16",
            "clips_count": 1,
            "clips": [result],
            "transcripts_count": 1,
            "transcripts_valid": bool(result["transcript_present"]),
            "transcript_present": bool(result["transcript_present"]),
            "load_seconds": load_seconds,
            "per_child_load_seconds": [load_seconds],
            "per_child_transcribe_seconds": [result["transcribe_seconds"]],
            "duration_seconds": round(time.perf_counter() - started, 3),
            "notes": ["one model load and one transcribe in this child"],
        }
    )
    return 0


def parse_clip_arg(default: Path = CLIP_NEWS) -> Path:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", default=str(default))
    args = parser.parse_args()
    return Path(args.clip)


def disable_tqdm_monkeypatch() -> None:
    import os

    os.environ["TQDM_DISABLE"] = "1"
    import tqdm
    import tqdm.auto

    class _NoOpTqdm:
        def __init__(self, iterable: Any = None, *args: Any, **kwargs: Any) -> None:
            self.iterable = iterable

        def __iter__(self) -> Any:
            return iter(self.iterable) if self.iterable is not None else iter([])

        def __enter__(self) -> "_NoOpTqdm":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def update(self, *args: Any, **kwargs: Any) -> None:
            return None

        def close(self) -> None:
            return None

        def set_description(self, *args: Any, **kwargs: Any) -> None:
            return None

        def set_postfix(self, *args: Any, **kwargs: Any) -> None:
            return None

        def write(self, *args: Any, **kwargs: Any) -> None:
            return None

    tqdm.tqdm = _NoOpTqdm
    tqdm.auto.tqdm = _NoOpTqdm
