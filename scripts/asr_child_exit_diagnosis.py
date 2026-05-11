from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(r"E:\MITAS")
OUTPUT_DIR = ROOT / "outputs" / "asr_child_exit_diagnosis"
REPORT_PATH = ROOT / "outputs" / "asr_child_exit_diagnosis_report.json"
INPUT_FILE = ROOT / "outputs" / "real_media_smoke" / "news_trt_haber_1_20s_16000hz_mono_asr_input.wav"
PROMO_INPUT_FILE = ROOT / "outputs" / "real_media_smoke" / "promo_1_20s_16000hz_mono_asr_input.wav"
WAV_INPUT_FILE = ROOT / "outputs" / "real_media_smoke" / "wav_erd_test_sound_20s_16000hz_mono_asr_input.wav"
FALLBACK_SOURCE = ROOT / "testklipler" / "trt_haber (1).mp4"
FFMPEG_BIN = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin"
FFMPEG = FFMPEG_BIN / "ffmpeg.exe"
ASR_PYTHON = ROOT / "venvs" / "asr" / "Scripts" / "python.exe"
LARGE_MODEL = ROOT / "models" / "asr" / "faster-whisper" / "large-v3"
USER_HF_CACHE = Path(os.environ.get("USERPROFILE", "")) / ".cache" / "huggingface" / "hub"
SMALL_MODEL_SNAPSHOT = (
    USER_HF_CACHE
    / "models--Systran--faster-whisper-small"
    / "snapshots"
    / "536b0662742c02347bc0e980a01041f333bce120"
)


def env_for_subprocess() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(FFMPEG_BIN) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    return env


def run_command(args: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            env=env_for_subprocess(),
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
            "returncode_hex": returncode_hex(completed.returncode),
            "output": completed.stdout.strip(),
            "runtime_sec": round(time.perf_counter() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout if isinstance(exc.stdout, str) else ""
        return {
            "command": args,
            "returncode": None,
            "returncode_hex": None,
            "output": output.strip(),
            "runtime_sec": round(time.perf_counter() - started, 3),
            "timeout": True,
        }


def returncode_hex(returncode: int | None) -> str | None:
    if returncode is None:
        return None
    return f"0x{returncode & 0xFFFFFFFF:08X}"


def ensure_input_clip() -> dict[str, Any]:
    if INPUT_FILE.exists():
        return {"status": "exists", "input_file": str(INPUT_FILE), "size_bytes": INPUT_FILE.stat().st_size}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(FFMPEG),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        "0",
        "-t",
        "20",
        "-i",
        str(FALLBACK_SOURCE),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(INPUT_FILE),
    ]
    result = run_command(command, timeout=120)
    result["input_file"] = str(INPUT_FILE)
    result["input_exists"] = INPUT_FILE.exists()
    if INPUT_FILE.exists():
        result["size_bytes"] = INPUT_FILE.stat().st_size
    return result


def input_files_for_case(case: dict[str, Any]) -> list[Path]:
    return [Path(path) for path in case.get("input_files", [INPUT_FILE])]


def parse_child_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"output_json_valid": False, "output_json_path": str(path), "error": "missing"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "output_json_valid": False,
            "output_json_path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    preview = str(data.get("transcript", ""))[:240]
    return {
        "output_json_valid": True,
        "output_json_path": str(path),
        "transcript_preview": preview,
        "child_json": data,
    }


def result_from_process(case: dict[str, Any], process: dict[str, Any], output_json: Path) -> dict[str, Any]:
    parsed = parse_child_json(output_json)
    child_json = parsed.get("child_json", {})
    segments_count = int(child_json.get("segments_count") or 0)
    transcribe_called = bool(case["transcribe_called"])
    output_valid = bool(parsed["output_json_valid"])
    functional = output_valid and (not transcribe_called or segments_count > 0)
    returncode = process.get("returncode")
    clean_exit = returncode == 0
    crash_after_output = output_valid and not clean_exit
    return {
        "case_id": case["case_id"],
        "input_file": str(INPUT_FILE),
        "input_files": [str(path) for path in input_files_for_case(case)],
        "model_id": case["model_id"],
        "model_path": str(case["model_path"]),
        "device": case["device"],
        "compute_type": case["compute_type"],
        "transcribe_called": transcribe_called,
        "cleanup_enabled": bool(case["cleanup"]),
        "output_json_valid": output_valid,
        "transcript_preview": parsed.get("transcript_preview", ""),
        "returncode": returncode,
        "returncode_hex": process.get("returncode_hex"),
        "crash_after_output": crash_after_output,
        "functional": functional,
        "segments_count": segments_count,
        "detected_language": child_json.get("detected_language"),
        "language_probability": child_json.get("language_probability"),
        "runtime_sec": process["runtime_sec"],
        "worker_runtime_sec": child_json.get("runtime_sec"),
        "stdout_tail": process.get("output", "")[-2000:],
        "timeout": bool(process.get("timeout", False)),
        "status": "passed" if functional and clean_exit else ("needs_review" if functional else "failed"),
        "output_json_path": str(output_json),
    }


def run_case(case: dict[str, Any], timeout: int) -> dict[str, Any]:
    if not Path(case["model_path"]).exists():
        return {
            "case_id": case["case_id"],
            "input_file": str(INPUT_FILE),
            "input_files": [str(path) for path in input_files_for_case(case)],
            "model_id": case["model_id"],
            "model_path": str(case["model_path"]),
            "device": case["device"],
            "compute_type": case["compute_type"],
            "transcribe_called": bool(case["transcribe_called"]),
            "output_json_valid": False,
            "transcript_preview": "",
            "returncode": None,
            "returncode_hex": None,
            "crash_after_output": False,
            "functional": False,
            "status": "skipped",
            "skip_reason": "local model path missing",
        }

    output_json = OUTPUT_DIR / f"{case['case_id']}.json"
    manifest_path = OUTPUT_DIR / f"{case['case_id']}_inputs.json"
    manifest_path.write_text(
        json.dumps([str(path) for path in input_files_for_case(case)], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    command = [
        str(ASR_PYTHON),
        str(Path(__file__)),
        "--worker",
        "--output-json",
        str(output_json),
        "--input-file",
        str(INPUT_FILE),
        "--input-files-manifest",
        str(manifest_path),
        "--model-path",
        str(case["model_path"]),
        "--model-id",
        str(case["model_id"]),
        "--device",
        str(case["device"]),
        "--compute-type",
        str(case["compute_type"]),
    ]
    if case["transcribe_called"]:
        command.append("--transcribe")
    if case["cleanup"]:
        command.append("--cleanup")
    process = run_command(command, timeout=timeout)
    return result_from_process(case, process, output_json)


def write_json_fsync(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def worker(args: argparse.Namespace) -> int:
    from faster_whisper import WhisperModel

    started = time.perf_counter()
    model = WhisperModel(
        args.model_path,
        device=args.device,
        compute_type=args.compute_type,
        local_files_only=True,
    )
    segments_payload: list[dict[str, Any]] = []
    clips_payload: list[dict[str, Any]] = []
    detected_language = None
    language_probability = None
    transcript = ""
    if args.transcribe:
        input_files = [args.input_file]
        if args.input_files_manifest:
            input_files = json.loads(Path(args.input_files_manifest).read_text(encoding="utf-8"))
        for input_file in input_files:
            segments_iter, info = model.transcribe(
                input_file,
                language="tr",
                beam_size=1,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            clip_segments = [
                {
                    "start": round(float(segment.start), 3),
                    "end": round(float(segment.end), 3),
                    "text": segment.text.strip(),
                }
                for segment in segments_iter
            ]
            detected_language = getattr(info, "language", None)
            language_probability = round(float(getattr(info, "language_probability", 0.0)), 4)
            clip_transcript = " ".join(segment["text"] for segment in clip_segments).strip()
            clips_payload.append(
                {
                    "input_file": input_file,
                    "detected_language": detected_language,
                    "language_probability": language_probability,
                    "segments_count": len(clip_segments),
                    "transcript": clip_transcript,
                    "segments": clip_segments,
                }
            )
            segments_payload.extend(clip_segments)
        transcript = " ".join(clip["transcript"] for clip in clips_payload).strip()

    payload = {
        "status": "passed",
        "input_file": args.input_file,
        "model_id": args.model_id,
        "model_path": args.model_path,
        "device": args.device,
        "compute_type": args.compute_type,
        "transcribe_called": bool(args.transcribe),
        "cleanup_enabled": bool(args.cleanup),
        "detected_language": detected_language,
        "language_probability": language_probability,
        "segments_count": len(segments_payload),
        "transcript": transcript,
        "clips_count": len(clips_payload),
        "clips": clips_payload,
        "segments": segments_payload,
        "runtime_sec": round(time.perf_counter() - started, 3),
    }
    write_json_fsync(Path(args.output_json), payload)

    if args.cleanup:
        del segments_payload
        try:
            del segments_iter  # type: ignore[name-defined]
        except NameError:
            pass
        try:
            del info  # type: ignore[name-defined]
        except NameError:
            pass
        del model
        gc.collect()
        time.sleep(0.5)

    return 0


def diagnosis_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "cpu_large_v3_int8_transcribe",
            "model_id": "large-v3",
            "model_path": LARGE_MODEL,
            "device": "cpu",
            "compute_type": "int8",
            "transcribe_called": True,
            "cleanup": False,
            "group": "cpu_result",
        },
        {
            "case_id": "cuda_small_float16_transcribe",
            "model_id": "small",
            "model_path": SMALL_MODEL_SNAPSHOT,
            "device": "cuda",
            "compute_type": "float16",
            "transcribe_called": True,
            "cleanup": False,
            "group": "cuda_tiny_result",
        },
        {
            "case_id": "cuda_large_v3_float16_load_only",
            "model_id": "large-v3",
            "model_path": LARGE_MODEL,
            "device": "cuda",
            "compute_type": "float16",
            "transcribe_called": False,
            "cleanup": False,
            "group": "cuda_large_load_only_result",
        },
        {
            "case_id": "cuda_large_v3_float16_transcribe",
            "model_id": "large-v3",
            "model_path": LARGE_MODEL,
            "device": "cuda",
            "compute_type": "float16",
            "transcribe_called": True,
            "cleanup": False,
            "group": "cuda_large_transcribe_result",
        },
        {
            "case_id": "cuda_large_v3_int8_float16_transcribe",
            "model_id": "large-v3",
            "model_path": LARGE_MODEL,
            "device": "cuda",
            "compute_type": "int8_float16",
            "transcribe_called": True,
            "cleanup": False,
            "group": "compute_type_results",
        },
        {
            "case_id": "cuda_large_v3_int8_transcribe",
            "model_id": "large-v3",
            "model_path": LARGE_MODEL,
            "device": "cuda",
            "compute_type": "int8",
            "transcribe_called": True,
            "cleanup": False,
            "group": "compute_type_results",
        },
        {
            "case_id": "cuda_large_v3_float16_cleanup_transcribe",
            "model_id": "large-v3",
            "model_path": LARGE_MODEL,
            "device": "cuda",
            "compute_type": "float16",
            "transcribe_called": True,
            "cleanup": True,
            "group": "cleanup_test_result",
        },
        {
            "case_id": "cuda_large_v3_float16_multiclip_transcribe",
            "model_id": "large-v3",
            "model_path": LARGE_MODEL,
            "device": "cuda",
            "compute_type": "float16",
            "transcribe_called": True,
            "cleanup": False,
            "input_files": [INPUT_FILE, PROMO_INPUT_FILE, WAV_INPUT_FILE],
            "group": "multiclip_result",
        },
        {
            "case_id": "cuda_large_v3_float16_multiclip_cleanup_transcribe",
            "model_id": "large-v3",
            "model_path": LARGE_MODEL,
            "device": "cuda",
            "compute_type": "float16",
            "transcribe_called": True,
            "cleanup": True,
            "input_files": [INPUT_FILE, PROMO_INPUT_FILE, WAV_INPUT_FILE],
            "group": "multiclip_cleanup_result",
        },
    ]


def infer_likely_cause(results: dict[str, Any]) -> str:
    cpu = results["cpu_result"]
    small = results["cuda_tiny_result"]
    load_only = results["cuda_large_load_only_result"]
    transcribe = results["cuda_large_transcribe_result"]
    cleanup = results["cleanup_test_result"]
    multiclip = results["multiclip_result"]
    multiclip_cleanup = results["multiclip_cleanup_result"]
    compute_results = results["compute_type_results"]

    cuda_abnormal = any(
        item.get("functional") and item.get("returncode") not in {0, None}
        for item in [small, load_only, transcribe, cleanup, multiclip, multiclip_cleanup, *compute_results]
    )
    cpu_clean = cpu.get("functional") and cpu.get("returncode") == 0
    load_only_abnormal = load_only.get("functional") and load_only.get("returncode") != 0
    cleanup_clean = cleanup.get("functional") and cleanup.get("returncode") == 0

    if cleanup_clean and transcribe.get("returncode") != 0:
        return "Explicit cleanup likely mitigates CUDA/CTranslate2 teardown abnormal exit."
    if transcribe.get("returncode") == 0 and multiclip.get("functional") and multiclip.get("returncode") != 0:
        if multiclip_cleanup.get("functional") and multiclip_cleanup.get("returncode") == 0:
            return "Single-clip CUDA exits cleanly; multi-clip same-process run reproduces teardown abnormal exit and explicit cleanup mitigates it."
        return "Single-clip CUDA exits cleanly; multi-clip same-process run suggests teardown/state accumulation issue."
    if cpu_clean and load_only_abnormal:
        return "Most likely CUDA/CTranslate2 model teardown on Windows; transcribe is not required to trigger it."
    if cpu_clean and cuda_abnormal:
        return "Most likely CUDA/CTranslate2 Windows teardown after valid output."
    if all(item.get("functional") and item.get("returncode") != 0 for item in compute_results):
        return "Compute type variation does not remove abnormal CUDA process exit."
    if not cuda_abnormal:
        return "No abnormal CUDA exit reproduced in this diagnostic run."
    return "Abnormal exit reproduced, but evidence is mixed; keep as needs_review."


def build_report(timeout: int) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    input_setup = ensure_input_clip()
    cases = diagnosis_cases()
    started = time.perf_counter()
    case_results = [run_case(case, timeout=timeout) for case in cases]
    by_case = {item["case_id"]: item for item in case_results}

    compute_type_results = [
        by_case["cuda_large_v3_float16_transcribe"],
        by_case["cuda_large_v3_int8_float16_transcribe"],
        by_case["cuda_large_v3_int8_transcribe"],
    ]
    grouped = {
        "cpu_result": by_case["cpu_large_v3_int8_transcribe"],
        "cuda_tiny_result": by_case["cuda_small_float16_transcribe"],
        "cuda_large_load_only_result": by_case["cuda_large_v3_float16_load_only"],
        "cuda_large_transcribe_result": by_case["cuda_large_v3_float16_transcribe"],
        "compute_type_results": compute_type_results,
        "cleanup_test_result": by_case["cuda_large_v3_float16_cleanup_transcribe"],
        "multiclip_result": by_case["cuda_large_v3_float16_multiclip_transcribe"],
        "multiclip_cleanup_result": by_case["cuda_large_v3_float16_multiclip_cleanup_transcribe"],
    }

    any_functional = any(item.get("functional") for item in case_results)
    any_failed = any(item.get("status") == "failed" for item in case_results)
    any_abnormal = any(item.get("functional") and item.get("returncode") != 0 for item in case_results)
    status = "failed" if any_failed or not any_functional else ("needs_review" if any_abnormal else "passed")

    report = {
        "status": status,
        "input_file": str(INPUT_FILE),
        "input_setup": input_setup,
        "model_id": "large-v3",
        "device": "cuda",
        "compute_type": "float16",
        "transcribe_called": True,
        "output_json_valid": grouped["cuda_large_transcribe_result"].get("output_json_valid", False),
        "transcript_preview": grouped["cuda_large_transcribe_result"].get("transcript_preview", ""),
        "returncode": grouped["cuda_large_transcribe_result"].get("returncode"),
        "returncode_hex": grouped["cuda_large_transcribe_result"].get("returncode_hex"),
        "crash_after_output": grouped["cuda_large_transcribe_result"].get("crash_after_output", False),
        "functional": grouped["cuda_large_transcribe_result"].get("functional", False),
        **grouped,
        "all_results": case_results,
        "likely_cause": infer_likely_cause(grouped),
        "runtime_sec": round(time.perf_counter() - started, 3),
        "notes": [
            "Paket, torch, ctranslate2, faster-whisper ve model dosyaları değiştirilmedi.",
            "cuda_tiny_result alanı yerel cache'te tiny bulunmadığı için faster-whisper-small ile dolduruldu.",
            "functional=true, child process geçerli JSON üretti ve beklenen temel çıktıyı yazdı anlamına gelir.",
            "returncode 0 değilse ancak output_json_valid=true ise crash_after_output=true olarak raporlanır.",
        ],
    }
    write_json_fsync(REPORT_PATH, report)
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="MITAS ASR child process abnormal exit diagnosis")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--output-json")
    parser.add_argument("--input-file")
    parser.add_argument("--input-files-manifest")
    parser.add_argument("--model-path")
    parser.add_argument("--model-id")
    parser.add_argument("--device")
    parser.add_argument("--compute-type")
    parser.add_argument("--transcribe", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    if args.worker:
        return worker(args)

    report = build_report(timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"passed", "needs_review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
