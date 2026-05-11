from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any
import argparse


ROOT = Path(r"E:\MITAS")
MODEL_PATH = ROOT / "models" / "asr" / "faster-whisper" / "large-v3"
DEFAULT_CLIP_PATH = ROOT / "outputs" / "real_media_smoke" / "wav_erd_test_sound_120s_16000hz_mono_asr_input.wav"
DEFAULT_REPORT_PATH = ROOT / "outputs" / "asr_multilingual_120s_report.json"
DEFAULT_SUMMARY_PATH = ROOT / "outputs" / "asr_multilingual_120s_summary.md"


def segment_payload(segment: Any) -> dict[str, Any]:
    return {
        "start": round(float(segment.start), 3),
        "end": round(float(segment.end), 3),
        "text": segment.text.strip(),
        "avg_logprob": float(getattr(segment, "avg_logprob", 0.0) or 0.0),
        "no_speech_prob": float(getattr(segment, "no_speech_prob", 0.0) or 0.0),
        "language": getattr(segment, "language", None),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# ASR Multilingual 120s Check",
        "",
        f"Clip: `{payload['clip_path']}`",
        f"Exit: child script completed normally before process teardown",
        f"Transcribe seconds: `{payload['transcribe_seconds']}`",
        f"Detected language: `{payload['detected_language']}` (`{payload['language_probability']}`)",
        "",
        "## Full Transcript",
        "",
        payload["transcript"],
        "",
        "## Segments",
        "",
        "| Start | End | Text |",
        "|---:|---:|---|",
    ]
    for segment in payload["segments"]:
        text = segment["text"].replace("|", "\\|")
        lines.append(f"| {segment['start']} | {segment['end']} | {text} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", default=str(DEFAULT_CLIP_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY_PATH))
    args = parser.parse_args()
    clip_path = Path(args.clip)
    report_path = Path(args.report)
    summary_path = Path(args.summary)

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
    segments_iter, info = model.transcribe(str(clip_path), multilingual=True)
    segments = [segment_payload(segment) for segment in segments_iter]
    transcript = " ".join(segment["text"] for segment in segments).strip()

    payload = {
        "clip_path": str(clip_path),
        "model_id": "large-v3",
        "device": "cuda",
        "compute_type": "float16",
        "transcribe_kwargs": {"multilingual": True},
        "load_seconds": load_seconds,
        "transcribe_seconds": round(time.perf_counter() - transcribe_started, 3),
        "segments_count": len(segments),
        "detected_language": getattr(info, "language", None),
        "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
        "transcript": transcript,
        "segments": segments,
        "duration_seconds": round(time.perf_counter() - started, 3),
    }
    write_json(report_path, payload)
    write_summary(summary_path, payload)
    print(json.dumps({"transcribe_seconds": payload["transcribe_seconds"], "segments_count": len(segments)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
