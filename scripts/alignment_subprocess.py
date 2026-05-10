from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
import wave

import numpy as np


ROOT = Path(r"E:\MITAS")
DEFAULT_FFMPEG_BIN = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin"
DEFAULT_MODEL_DIR = ROOT / "models" / "alignment" / "whisperx"


if os.name == "nt":
    ffmpeg_bin = Path(os.environ.get("MITAS_FFMPEG_DLL_DIR", str(DEFAULT_FFMPEG_BIN)))
    if ffmpeg_bin.exists():
        os.add_dll_directory(str(ffmpeg_bin))


def read_wav_as_16k_mono(path: Path) -> tuple[np.ndarray, dict[str, object]]:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)

    if sample_width != 2:
        raise ValueError(f"Only PCM16 WAV is supported by this prototype, got {sample_width} bytes")

    audio = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    original_sample_rate = sample_rate
    original_duration = float(len(audio) / original_sample_rate)
    target_rate = 16000
    if sample_rate != target_rate:
        old_x = np.linspace(0.0, original_duration, num=len(audio), endpoint=False, dtype="float64")
        new_len = int(round(original_duration * target_rate))
        new_x = np.linspace(0.0, original_duration, num=new_len, endpoint=False, dtype="float64")
        audio = np.interp(new_x, old_x, audio).astype("float32")
        sample_rate = target_rate

    metadata = {
        "source_channels": channels,
        "source_sample_width": sample_width,
        "source_sample_rate": original_sample_rate,
        "duration_seconds": original_duration,
        "loaded_sample_rate": target_rate,
        "loaded_shape": list(audio.shape),
    }
    return audio, metadata


def load_segments(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    raw_segments = data.get("segments", data if isinstance(data, list) else [])
    segments: list[dict[str, object]] = []
    for item in raw_segments:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        segments.append(
            {
                "start": float(item["start"]),
                "end": float(item["end"]),
                "text": text,
            }
        )
    return segments


def main() -> int:
    parser = argparse.ArgumentParser(description="MITAS WhisperX alignment subprocess prototype")
    parser.add_argument("--wav", required=True, type=Path)
    parser.add_argument("--segments", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--language", default="tr")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()

    import whisperx

    args.model_dir.mkdir(parents=True, exist_ok=True)
    segments = load_segments(args.segments)
    audio, audio_metadata = read_wav_as_16k_mono(args.wav)
    model, metadata = whisperx.load_align_model(
        language_code=args.language,
        device=args.device,
        model_dir=str(args.model_dir),
        model_cache_only=args.local_files_only,
    )
    aligned = whisperx.align(
        segments,
        model,
        metadata,
        audio,
        device=args.device,
        return_char_alignments=False,
        print_progress=False,
    )
    output = {
        "status": "success",
        "wav_path": str(args.wav),
        "segments_path": str(args.segments),
        "language": args.language,
        "device": args.device,
        "model_dir": str(args.model_dir),
        "input_segments_count": len(segments),
        "aligned_segments_count": len(aligned.get("segments", [])),
        "word_segments_count": len(aligned.get("word_segments", [])),
        "audio": audio_metadata,
        "runtime_sec": round(time.perf_counter() - started, 3),
        "result": aligned,
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
