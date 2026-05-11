from __future__ import annotations

import json
from pathlib import Path
import time
import wave

import numpy as np

from tools.asr_ab.common import (
    DEFAULT_AUDIO_PATH,
    DEFAULT_MODEL_PATH,
    DEFAULT_OUTPUT_ROOT,
    apply_filter,
    build_filter_report,
    write_clean_transcript,
    write_json,
)


ROOT = Path(__file__).resolve().parents[2]
VAD_REPORT = ROOT / "outputs" / "real_media_smoke" / "beyaz2_08_11" / "beyaz2_08_11_asr_models_report.json"
OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / "out_v9"


def read_wav_as_16k_mono(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        raw = wav_file.readframes(wav_file.getnframes())

    if channels != 1 or sample_width != 2 or sample_rate != 16_000:
        raise ValueError(f"Expected normalized 16 kHz mono PCM16 WAV: {path}")

    return np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0


def load_precomputed_vad_segments() -> list[dict[str, float]]:
    report = json.loads(VAD_REPORT.read_text(encoding="utf-8"))
    return [
        {"start": float(segment["start"]), "end": float(segment["end"])}
        for segment in report["vad"]["segments"]
    ]


def make_precomputed_vad(vad_segments: list[dict[str, float]]):
    from whisperx.diarize import Segment as SegmentX
    from whisperx.vads.vad import Vad

    class PrecomputedVad(Vad):
        def __init__(self) -> None:
            super().__init__(0.5)

        @staticmethod
        def preprocess_audio(audio):
            return audio

        def __call__(self, audio, **kwargs):
            return [SegmentX(segment["start"], segment["end"], "UNKNOWN") for segment in vad_segments]

    return PrecomputedVad()


def main() -> None:
    import whisperx

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total_started = time.perf_counter()
    vad_segments = load_precomputed_vad_segments()
    audio = read_wav_as_16k_mono(DEFAULT_AUDIO_PATH)

    asr_options = {
        "beam_size": 5,
        "temperatures": [0.0, 0.2, 0.4],
        "compression_ratio_threshold": 2.4,
        "log_prob_threshold": -1.0,
        "no_speech_threshold": 0.6,
        "condition_on_previous_text": True,
        "initial_prompt": None,
        "word_timestamps": False,
    }

    started = time.perf_counter()
    model = whisperx.load_model(
        str(DEFAULT_MODEL_PATH),
        device="cuda",
        compute_type="float16",
        language="tr",
        vad_model=make_precomputed_vad(vad_segments),
        asr_options=asr_options,
        local_files_only=True,
    )
    load_model_seconds = round(time.perf_counter() - started, 3)

    started = time.perf_counter()
    result = model.transcribe(audio, batch_size=8, language="tr", chunk_size=30)
    transcribe_seconds = round(time.perf_counter() - started, 3)

    raw_segments: list[dict[str, object]] = []
    for index, segment in enumerate(result.get("segments", [])):
        start = round(float(segment["start"]), 3)
        end = round(float(segment["end"]), 3)
        item = {
            "start": start,
            "end": end,
            "duration": round(end - start, 3),
            "text": str(segment.get("text", "")).strip(),
            "language": result.get("language") or "tr",
            "avg_logprob": float(segment.get("avg_logprob", 0.0) or 0.0),
            "no_speech_prob": 0.0,
            "compression_ratio": None,
            "chunk_index": index,
            "chunk_start": start,
            "chunk_end": end,
            "source_vad_index": None,
            "kept": True,
            "drop_reason": None,
            "flags": [],
        }
        apply_filter(item)
        raw_segments.append(item)

    clean_segments = [segment for segment in raw_segments if segment["kept"]]
    filter_report = build_filter_report(raw_segments, clean_segments)
    timing = {
        "variant": "v9_whisperx_precomputed_vad",
        "description": "WhisperX ASR in alignment venv, using MITAS precomputed VAD segments and no prompt.",
        "model_call_count": 1,
        "load_model_seconds": load_model_seconds,
        "transcribe_seconds": transcribe_seconds,
        "total_seconds": round(time.perf_counter() - total_started, 3),
        "raw_segment_count": len(raw_segments),
        "clean_segment_count": len(clean_segments),
        "model_path": str(DEFAULT_MODEL_PATH),
        "audio_path": str(DEFAULT_AUDIO_PATH),
    }
    payload = {
        "variant": timing["variant"],
        "description": timing["description"],
        "audio_path": str(DEFAULT_AUDIO_PATH),
        "vad": {
            "source": str(VAD_REPORT),
            "speech_segments_count": len(vad_segments),
            "segments": vad_segments,
        },
        "chunks": [],
        "segments": raw_segments,
    }
    clean_payload = dict(payload)
    clean_payload["segments"] = clean_segments

    write_json(OUTPUT_DIR / "raw_segments.json", payload)
    write_json(OUTPUT_DIR / "clean_segments.json", clean_payload)
    write_json(OUTPUT_DIR / "filter_report.json", filter_report)
    write_json(OUTPUT_DIR / "timing.json", timing)
    write_clean_transcript(OUTPUT_DIR / "clean_transcript.txt", clean_segments)
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()
