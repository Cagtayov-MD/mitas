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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def segment_payload(segment: Any) -> dict[str, Any]:
    return {
        "start": round(float(segment.start), 6),
        "end": round(float(segment.end), 6),
        "text": segment.text.strip(),
        "avg_logprob": float(getattr(segment, "avg_logprob", 0.0) or 0.0),
        "no_speech_prob": float(getattr(segment, "no_speech_prob", 0.0) or 0.0),
        "language": getattr(segment, "language", None),
    }


def load_model() -> tuple[Any, float]:
    started = time.perf_counter()
    from faster_whisper import WhisperModel

    model = WhisperModel(
        str(MODEL_PATH),
        device="cuda",
        compute_type="float16",
        local_files_only=True,
    )
    return model, round(time.perf_counter() - started, 3)


def transcribe_multilingual(model: Any, clip: Path) -> dict[str, Any]:
    started = time.perf_counter()
    fallback_used = False
    try:
        segments_iter, info = model.transcribe(str(clip), multilingual=True)
        transcribe_kwargs = {"multilingual": True}
    except TypeError as exc:
        if "multilingual" not in str(exc):
            raise
        fallback_used = True
        segments_iter, info = model.transcribe(str(clip), language_detection_segments=5)
        transcribe_kwargs = {"language_detection_segments": 5}

    segments = [segment_payload(segment) for segment in segments_iter]
    transcript = " ".join(segment["text"] for segment in segments).strip()
    return {
        "clip_path": str(clip),
        "clip_name": clip.stem,
        "transcribe_kwargs": transcribe_kwargs,
        "fallback_used": fallback_used,
        "transcribe_seconds": round(time.perf_counter() - started, 3),
        "segments_count": len(segments),
        "transcript": transcript,
        "transcript_first_200_chars": transcript[:200],
        "avg_logprob_first_segment": segments[0]["avg_logprob"] if segments else None,
        "no_speech_prob_first_segment": segments[0]["no_speech_prob"] if segments else None,
        "detected_language": getattr(info, "language", None),
        "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
        "all_language_probs": getattr(info, "all_language_probs", None),
        "segments": segments,
    }


def emit_partial(result_json: Path | None, payload: dict[str, Any]) -> None:
    if result_json is not None:
        write_json(result_json, payload)


def run_tm1(result_json: Path | None) -> dict[str, Any]:
    started = time.perf_counter()
    model, load_seconds = load_model()
    payload: dict[str, Any] = {
        "test_id": "TM1",
        "scenario": "wav_erd_three_transcribes_same_instance_multilingual_true",
        "model_id": "large-v3",
        "device": "cuda",
        "compute_type": "float16",
        "load_seconds": load_seconds,
        "iterations": [],
    }
    for index in range(3):
        result = transcribe_multilingual(model, CLIP_WAV)
        result["iter_index"] = index
        payload["iterations"].append(result)
        payload["duration_seconds_so_far"] = round(time.perf_counter() - started, 3)
        emit_partial(result_json, payload)
    payload["duration_seconds"] = round(time.perf_counter() - started, 3)
    emit_partial(result_json, payload)
    return payload


def run_tm2(result_json: Path | None) -> dict[str, Any]:
    started = time.perf_counter()
    model, load_seconds = load_model()
    result = transcribe_multilingual(model, CLIP_WAV)
    payload = {
        "test_id": "TM2",
        "scenario": "wav_erd_single_transcribe_multilingual_true",
        "model_id": "large-v3",
        "device": "cuda",
        "compute_type": "float16",
        "load_seconds": load_seconds,
        "result": result,
        "duration_seconds": round(time.perf_counter() - started, 3),
    }
    emit_partial(result_json, payload)
    return payload


def run_tm3(result_json: Path | None) -> dict[str, Any]:
    started = time.perf_counter()
    model, load_seconds = load_model()
    payload: dict[str, Any] = {
        "test_id": "TM3",
        "scenario": "control_clips_two_transcribes_same_instance_multilingual_true",
        "model_id": "large-v3",
        "device": "cuda",
        "compute_type": "float16",
        "load_seconds": load_seconds,
        "clips": [],
    }
    for clip in [CLIP_NEWS, CLIP_PROMO]:
        result = transcribe_multilingual(model, clip)
        payload["clips"].append(result)
        payload["duration_seconds_so_far"] = round(time.perf_counter() - started, 3)
        emit_partial(result_json, payload)
    payload["duration_seconds"] = round(time.perf_counter() - started, 3)
    emit_partial(result_json, payload)
    return payload


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-id", choices=["TM1", "TM2", "TM3"], required=True)
    parser.add_argument("--result-json")
    args = parser.parse_args()

    result_json = Path(args.result_json) if args.result_json else None
    if args.test_id == "TM1":
        payload = run_tm1(result_json)
    elif args.test_id == "TM2":
        payload = run_tm2(result_json)
    else:
        payload = run_tm3(result_json)
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
