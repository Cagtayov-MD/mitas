from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(r"E:\MITAS")
MODEL_PATH = ROOT / "models" / "asr" / "faster-whisper" / "large-v3"


def segment_payload(segment: Any) -> dict[str, Any]:
    return {
        "start": round(float(segment.start), 6),
        "end": round(float(segment.end), 6),
        "text": segment.text.strip(),
        "avg_logprob": float(getattr(segment, "avg_logprob", 0.0) or 0.0),
        "no_speech_prob": float(getattr(segment, "no_speech_prob", 0.0) or 0.0),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(clip: Path, result_json: Path | None = None) -> dict[str, Any]:
    started = time.perf_counter()

    from faster_whisper import WhisperModel

    model = WhisperModel(
        str(MODEL_PATH),
        device="cuda",
        compute_type="float16",
        local_files_only=True,
    )
    load_seconds = round(time.perf_counter() - started, 3)

    transcribe_started = time.perf_counter()
    segments_iter, info = model.transcribe(
        str(clip),
        language="tr",
        beam_size=1,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    segments = [segment_payload(segment) for segment in segments_iter]
    transcript = " ".join(segment["text"] for segment in segments).strip()

    payload = {
        "clip_path": str(clip),
        "model_id": "large-v3",
        "device": "cuda",
        "compute_type": "float16",
        "load_seconds": load_seconds,
        "transcribe_seconds": round(time.perf_counter() - transcribe_started, 3),
        "segments_count": len(segments),
        "transcript": transcript,
        "transcript_first_100_chars": transcript[:100],
        "avg_logprob_first_segment": segments[0]["avg_logprob"] if segments else None,
        "no_speech_prob_first_segment": segments[0]["no_speech_prob"] if segments else None,
        "detected_language": getattr(info, "language", None),
        "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
        "segments": segments,
        "duration_seconds": round(time.perf_counter() - started, 3),
    }
    if result_json is not None:
        write_json(result_json, payload)
    return payload


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("clip_path")
    parser.add_argument("--result-json")
    args = parser.parse_args()
    payload = run(Path(args.clip_path), Path(args.result_json) if args.result_json else None)
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
