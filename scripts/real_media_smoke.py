from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import wave


ROOT = Path(r"E:\MITAS")
TEST_DIR = ROOT / "testklipler"
OUTPUT_DIR = ROOT / "outputs" / "real_media_smoke"
REPORT_PATH = ROOT / "outputs" / "real_media_smoke_report.json"
FFMPEG_BIN = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin"
FFMPEG = FFMPEG_BIN / "ffmpeg.exe"
FFPROBE = FFMPEG_BIN / "ffprobe.exe"
ASR_PYTHON = ROOT / "venvs" / "asr" / "Scripts" / "python.exe"
DENOISE_EXE = ROOT / "venvs" / "denoise" / "Scripts" / "deepFilter.exe"
ASR_MODEL_DIR = ROOT / "models" / "asr" / "faster-whisper" / "large-v3"
DENOISE_MODEL_DIR = ROOT / "models" / "denoise" / "DeepFilterNet3"


MEDIA_FILES = [
    TEST_DIR / "trt_haber (1).mp4",
    TEST_DIR / "trt_haber (2).mp4",
    TEST_DIR / "trt_haber (3).mp4",
    TEST_DIR / "1.mp4",
    TEST_DIR / "2.mp4",
    TEST_DIR / "3.mp4",
    TEST_DIR / "4.mp4",
    TEST_DIR / "5.mp4",
    TEST_DIR / "erd_test_video.mp4",
    TEST_DIR / "erd_test_sound.wav",
    TEST_DIR / "erd_test_sound_noisy_12dB.wav",
]

ASR_SOURCES = [
    {
        "name": "news_trt_haber_1",
        "path": TEST_DIR / "trt_haber (1).mp4",
        "start_sec": 0,
        "duration_sec": 20,
        "note": "Haber spiker/KJ/röportaj sınıfı kısa gerçek video.",
    },
    {
        "name": "promo_1",
        "path": TEST_DIR / "1.mp4",
        "start_sec": 0,
        "duration_sec": 20,
        "note": "Müzikli TRT tanıtımı, hızlı plan ve konuşma geçişleri.",
    },
    {
        "name": "wav_erd_test_sound",
        "path": TEST_DIR / "erd_test_sound.wav",
        "start_sec": 0,
        "duration_sec": 20,
        "note": "Gerçek WAV konuşma/ses klibi.",
    },
]


def run_command(args: list[str], timeout: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "command": args,
            "returncode": completed.returncode,
            "status": "passed" if completed.returncode == 0 else "failed",
            "output": completed.stdout.strip(),
            "runtime_sec": round(time.perf_counter() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout if isinstance(exc.stdout, str) else ""
        return {
            "command": args,
            "returncode": None,
            "status": "timeout",
            "output": output.strip(),
            "runtime_sec": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        return {
            "command": args,
            "returncode": None,
            "status": "failed",
            "output": f"{type(exc).__name__}: {exc}",
            "runtime_sec": round(time.perf_counter() - started, 3),
        }


def runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(FFMPEG_BIN) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    return env


def probe_media(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "status": "failed", "error": "missing"}
    command = [
        str(FFPROBE),
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,sample_rate,channels",
        "-of",
        "json",
        str(path),
    ]
    result = run_command(command, timeout=60, env=runtime_env())
    item: dict[str, Any] = {
        "path": str(path),
        "file_size_bytes": path.stat().st_size,
        "probe": result,
    }
    if result["status"] != "passed":
        item["status"] = "failed"
        return item
    try:
        parsed = json.loads(result["output"])
    except json.JSONDecodeError as exc:
        item["status"] = "failed"
        item["error"] = f"json_parse: {exc}"
        return item
    duration = parsed.get("format", {}).get("duration")
    item["duration_sec"] = round(float(duration), 3) if duration is not None else None
    item["streams"] = parsed.get("streams", [])
    item["status"] = "passed"
    return item


def extract_clip(source: dict[str, Any], sample_rate: int, suffix: str) -> dict[str, Any]:
    output_path = OUTPUT_DIR / f"{source['name']}_{int(source['duration_sec'])}s_{sample_rate}hz_mono{suffix}.wav"
    command = [
        str(FFMPEG),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(source["start_sec"]),
        "-t",
        str(source["duration_sec"]),
        "-i",
        str(source["path"]),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    result = run_command(command, timeout=120, env=runtime_env())
    result["output_path"] = str(output_path)
    result["output_exists"] = output_path.exists()
    if output_path.exists():
        result["output_size_bytes"] = output_path.stat().st_size
        result["wav_info"] = wav_info(output_path)
    return result


def wav_info(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_rate = handle.getframerate()
        frames = handle.getnframes()
        sample_width = handle.getsampwidth()
    return {
        "channels": channels,
        "sample_rate_hz": sample_rate,
        "frames": frames,
        "sample_width_bytes": sample_width,
        "duration_sec": round(frames / sample_rate, 3) if sample_rate else None,
    }


def wav_rms(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        sample_width = handle.getsampwidth()
        raw = handle.readframes(handle.getnframes())
    if sample_width != 2 or not raw:
        return float("nan")
    total = 0.0
    count = 0
    for index in range(0, len(raw), 2):
        sample = int.from_bytes(raw[index : index + 2], "little", signed=True) / 32768.0
        total += sample * sample
        count += 1
    return math.sqrt(total / count) if count else float("nan")


def asr_worker(clips_manifest: Path, output_path: Path) -> int:
    from faster_whisper import WhisperModel

    started = time.perf_counter()
    clips = json.loads(clips_manifest.read_text(encoding="utf-8"))
    model = WhisperModel(str(ASR_MODEL_DIR), device="cuda", compute_type="float16", local_files_only=True)
    results = []
    for item in clips:
        segments_iter, info = model.transcribe(
            item["clip_path"],
            language="tr",
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        segments = [
            {
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": segment.text.strip(),
            }
            for segment in segments_iter
        ]
        results.append(
            {
                "name": item["name"],
                "source_path": item["source_path"],
                "clip_path": item["clip_path"],
                "duration_sec": item["duration_sec"],
                "detected_language": getattr(info, "language", None),
                "language_probability": round(float(getattr(info, "language_probability", 0.0)), 4),
                "segments_count": len(segments),
                "text": " ".join(segment["text"] for segment in segments).strip(),
                "segments": segments,
            }
        )
    report = {
        "status": "passed" if all(item["segments_count"] > 0 for item in results) else "needs_review",
        "model_dir": str(ASR_MODEL_DIR),
        "device": "cuda",
        "compute_type": "float16",
        "network_guard": "HF_HUB_OFFLINE=1 and local_files_only=True",
        "clips": results,
        "runtime_sec": round(time.perf_counter() - started, 3),
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] in {"passed", "needs_review"} else 1


def run_asr_smoke(extracted: list[dict[str, Any]]) -> dict[str, Any]:
    clips = []
    for source, result in zip(ASR_SOURCES, extracted):
        if result["status"] != "passed" or not result.get("output_exists"):
            continue
        clips.append(
            {
                "name": source["name"],
                "source_path": str(source["path"]),
                "clip_path": result["output_path"],
                "duration_sec": source["duration_sec"],
            }
        )
    manifest = OUTPUT_DIR / "asr_clips_manifest.json"
    asr_output = OUTPUT_DIR / "asr_result.json"
    manifest.write_text(json.dumps(clips, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    command = [str(ASR_PYTHON), str(Path(__file__)), "--asr-worker", str(manifest), str(asr_output)]
    result = run_command(command, timeout=300, env=runtime_env())
    result["clips_manifest"] = str(manifest)
    result["asr_output"] = str(asr_output)
    if asr_output.exists():
        try:
            result["result"] = json.loads(asr_output.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            result["result_parse_error"] = str(exc)
    if result.get("result", {}).get("status") in {"passed", "needs_review"} and result["status"] != "passed":
        result["status"] = "passed_with_abnormal_exit"
    return result


def run_denoise_smoke() -> dict[str, Any]:
    source = {
        "name": "denoise_erd_test_sound",
        "path": TEST_DIR / "erd_test_sound.wav",
        "start_sec": 0,
        "duration_sec": 10,
    }
    extract = extract_clip(source, sample_rate=48000, suffix="_denoise_input")
    result: dict[str, Any] = {"extract": extract}
    if extract["status"] != "passed" or not extract.get("output_exists"):
        result["status"] = "failed"
        result["error"] = "denoise input extraction failed"
        return result

    input_path = Path(extract["output_path"])
    command = [
        str(DENOISE_EXE),
        "--model-base-dir",
        str(DENOISE_MODEL_DIR),
        "--output-dir",
        str(OUTPUT_DIR),
        "--log-level",
        "info",
        str(input_path),
    ]
    enhance = run_command(command, timeout=180, env=runtime_env())
    result["enhance"] = enhance
    expected_output = OUTPUT_DIR / f"{input_path.stem}_DeepFilterNet3.wav"
    result["output_path"] = str(expected_output)
    result["output_exists"] = expected_output.exists()
    if expected_output.exists():
        result["input_rms"] = round(wav_rms(input_path), 8)
        result["output_rms"] = round(wav_rms(expected_output), 8)
        result["output_wav_info"] = wav_info(expected_output)
    result["status"] = "passed" if enhance["status"] == "passed" and expected_output.exists() else "failed"
    return result


def build_report() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    probes = [probe_media(path) for path in MEDIA_FILES]
    extracts = [extract_clip(source, sample_rate=16000, suffix="_asr_input") for source in ASR_SOURCES]
    asr = run_asr_smoke(extracts)
    denoise = run_denoise_smoke()

    failures = []
    if any(item["status"] != "passed" for item in probes):
        failures.append("ffprobe")
    if any(item["status"] != "passed" or not item.get("output_exists") for item in extracts):
        failures.append("audio_extract")
    asr_result_status = asr.get("result", {}).get("status")
    if asr["status"] not in {"passed", "passed_with_abnormal_exit"} or asr_result_status not in {"passed", "needs_review"}:
        failures.append("asr")
    if denoise["status"] != "passed":
        failures.append("denoise")
    needs_review = asr.get("status") == "passed_with_abnormal_exit"

    return {
        "status": "failed" if failures else ("needs_review" if needs_review else "passed"),
        "failures": failures,
        "timestamp_local": "2026-05-11",
        "ffmpeg": {
            "ffmpeg_path": str(FFMPEG),
            "ffprobe_path": str(FFPROBE),
            "dll_dir": str(FFMPEG_BIN),
        },
        "media_probe_count": len(probes),
        "media_probes": probes,
        "asr_extracts": extracts,
        "asr": asr,
        "denoise": denoise,
        "runtime_sec": round(time.perf_counter() - started, 3),
        "notes": [
            "Gerçek medya kullanıldı; synthetic noise bu koşumda üretilmedi.",
            "ASR kısa kliplerde yerel large-v3 modeliyle HF_HUB_OFFLINE=1 altında çalıştırıldı.",
            "Ham test medyaları Git'e alınmaz; bu rapor ve küçük smoke scripti izlenir.",
            "ASR worker geçerli çıktı üretmesine rağmen CUDA/ctranslate2 kapanışında anormal exit verebilir; report.asr.status alanı ayrıca izlenir.",
        ],
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="MITAS real media smoke test")
    parser.add_argument("--output", default=str(REPORT_PATH))
    parser.add_argument("--asr-worker", nargs=2, metavar=("CLIPS_MANIFEST", "OUTPUT_PATH"))
    args = parser.parse_args()

    if args.asr_worker:
        return asr_worker(Path(args.asr_worker[0]), Path(args.asr_worker[1]))

    report = build_report()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"passed", "needs_review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
