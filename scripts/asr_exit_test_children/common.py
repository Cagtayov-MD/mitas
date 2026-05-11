from __future__ import annotations

import argparse
import gc
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
CLIPS_DIFFERENT = [CLIP_NEWS, CLIP_PROMO, CLIP_WAV]


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def segment_payload(segment: Any) -> dict[str, Any]:
    return {
        "start": round(float(segment.start), 6),
        "end": round(float(segment.end), 6),
        "text": segment.text.strip(),
        "avg_logprob": _float_or_none(getattr(segment, "avg_logprob", None)),
        "no_speech_prob": _float_or_none(getattr(segment, "no_speech_prob", None)),
    }


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def new_model() -> Any:
    from faster_whisper import WhisperModel

    return WhisperModel(
        str(MODEL_PATH),
        device="cuda",
        compute_type="float16",
        local_files_only=True,
    )


def transcribe(model: Any, clip: Path) -> dict[str, Any]:
    started = time.perf_counter()
    segments_iter, info = model.transcribe(
        str(clip),
        language="tr",
        beam_size=1,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    segments = [segment_payload(segment) for segment in segments_iter]
    transcript = " ".join(segment["text"] for segment in segments).strip()
    return {
        "clip_path": str(clip),
        "segments_count": len(segments),
        "transcript": transcript,
        "transcript_present": bool(transcript),
        "detected_language": getattr(info, "language", None),
        "language_probability": _float_or_none(getattr(info, "language_probability", None)),
        "segments": segments,
        "duration_seconds": round(time.perf_counter() - started, 3),
    }


def cleanup_variant(variant: str) -> dict[str, Any]:
    details: dict[str, Any] = {"variant": variant, "actions": []}
    if variant in {"gc", "both"}:
        gc.collect()
        details["actions"].append("gc.collect")
    if variant in {"empty_cache", "both"}:
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                details["actions"].append("torch.cuda.empty_cache")
        except Exception as exc:
            details["torch_error"] = f"{type(exc).__name__}: {exc}"
    return details


def same_instance(test_id: str, clips: list[Path], cleanup_after_each: str = "none") -> int:
    started = time.perf_counter()
    model = new_model()
    clip_results = []
    cleanup_results = []
    for clip in clips:
        clip_results.append(transcribe(model, clip))
        if cleanup_after_each != "none":
            cleanup_results.append(cleanup_variant(cleanup_after_each))
    transcripts_valid = all(item["transcript_present"] for item in clip_results)
    emit(
        {
            "test_id": test_id,
            "scenario": "same_instance",
            "model_id": "large-v3",
            "device": "cuda",
            "compute_type": "float16",
            "clips_count": len(clips),
            "clips": clip_results,
            "transcripts_count": len(clip_results),
            "transcripts_valid": transcripts_valid,
            "transcript_present": transcripts_valid,
            "cleanup_after_each": cleanup_after_each,
            "cleanup_results": cleanup_results,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "notes": ["child emitted JSON before normal sys.exit(0)"],
        }
    )
    return 0


def new_instance_per_clip(test_id: str, clips: list[Path]) -> int:
    started = time.perf_counter()
    clip_results = []
    cleanup_results = []
    for index, clip in enumerate(clips):
        model = new_model()
        clip_results.append(transcribe(model, clip))
        # T4 is explicitly about lifecycle crashes, so emit progress before
        # destructor/cache cleanup can terminate the native process.
        emit(
            {
                "test_id": test_id,
                "scenario": "new_instance_per_clip_same_process",
                "partial": True,
                "completed_clips": index + 1,
                "expected_clips": len(clips),
                "model_id": "large-v3",
                "device": "cuda",
                "compute_type": "float16",
                "clips_count": len(clip_results),
                "clips": clip_results,
                "transcripts_count": len(clip_results),
                "transcripts_valid": all(item["transcript_present"] for item in clip_results),
                "transcript_present": all(item["transcript_present"] for item in clip_results),
                "duration_seconds": round(time.perf_counter() - started, 3),
                "notes": ["partial progress JSON emitted before model cleanup"],
            }
        )
        del model
        gc.collect()
        cleanup_results.append(cleanup_variant("empty_cache"))
    transcripts_valid = all(item["transcript_present"] for item in clip_results)
    emit(
        {
            "test_id": test_id,
            "scenario": "new_instance_per_clip_same_process",
            "model_id": "large-v3",
            "device": "cuda",
            "compute_type": "float16",
            "clips_count": len(clips),
            "clips": clip_results,
            "transcripts_count": len(clip_results),
            "transcripts_valid": transcripts_valid,
            "transcript_present": transcripts_valid,
            "cleanup_results": cleanup_results,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "notes": ["each clip used a fresh WhisperModel instance in the same child process"],
        }
    )
    return 0


def ctranslate2_cleanup_api_probe(test_id: str) -> int:
    started = time.perf_counter()
    import ctranslate2

    cache_like = [
        name
        for name in dir(ctranslate2)
        if any(token in name.lower() for token in ["cache", "flush", "clear", "release"])
    ]
    emit(
        {
            "test_id": test_id,
            "scenario": "ctranslate2_cleanup_api_probe",
            "status": "skipped",
            "skip_reason": "no_api_found" if not cache_like else "api_candidates_not_called_in_diagnostic",
            "api_candidates": cache_like,
            "transcript_present": False,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "notes": ["no safe public CTranslate2 cache flush API was called"],
        }
    )
    return 0


def parse_variant_arg() -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="none")
    args = parser.parse_args()
    return str(args.variant)
