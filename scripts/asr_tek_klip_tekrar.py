from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any


ROOT = Path(r"E:\MITAS")
ASR_PYTHON = ROOT / "venvs" / "asr" / "Scripts" / "python.exe"
CHILD_SCRIPT = ROOT / "scripts" / "tek_klip_child.py"
OUTPUT_DIR = ROOT / "outputs"
REPORT_PATH = OUTPUT_DIR / "asr_tek_klip_tekrar_report.json"
SUMMARY_PATH = OUTPUT_DIR / "asr_tek_klip_tekrar_summary.md"
CHILD_OUTPUT_DIR = OUTPUT_DIR / "asr_tek_klip_tekrar_child_outputs"
FFMPEG_BIN = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin"

CLIPS = [
    {
        "test_id": "TF1",
        "clip_name": "wav_erd_test_sound",
        "clip_path": ROOT / "outputs" / "real_media_smoke" / "wav_erd_test_sound_20s_16000hz_mono_asr_input.wav",
    },
    {
        "test_id": "TF2",
        "clip_name": "news_trt_haber_1",
        "clip_path": ROOT / "outputs" / "real_media_smoke" / "news_trt_haber_1_20s_16000hz_mono_asr_input.wav",
    },
    {
        "test_id": "TF3",
        "clip_name": "promo_1",
        "clip_path": ROOT / "outputs" / "real_media_smoke" / "promo_1_20s_16000hz_mono_asr_input.wav",
    },
]


def env_for_child() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(FFMPEG_BIN) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    return env


def returncode_hex(returncode: int | None) -> str | None:
    if returncode is None:
        return None
    return f"0x{returncode & 0xFFFFFFFF:08X}"


def parse_stdout_json(stdout: str) -> tuple[dict[str, Any] | None, str | None]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed, None
    return None, "no parseable JSON object in stdout"


def environment_info() -> dict[str, Any]:
    code = r"""
import json
import sys
import importlib.metadata as md
out = {"python": sys.version.split()[0]}
for key, dist in [("faster_whisper", "faster-whisper"), ("ctranslate2", "ctranslate2"), ("torch", "torch")]:
    try:
        out[key] = md.version(dist)
    except Exception as exc:
        out[key] = type(exc).__name__ + ": " + str(exc)
try:
    import torch
    out["cuda"] = bool(torch.cuda.is_available())
    out["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
except Exception as exc:
    out["cuda_error"] = type(exc).__name__ + ": " + str(exc)
print(json.dumps(out, ensure_ascii=False))
"""
    completed = subprocess.run(
        [str(ASR_PYTHON), "-c", code],
        cwd=str(ROOT),
        env=env_for_child(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    parsed, error = parse_stdout_json(completed.stdout)
    return parsed or {"error": error, "stderr_tail": completed.stderr[-2000:]}


def read_child_result(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "child result file missing"
    except json.JSONDecodeError as exc:
        return None, f"child result file JSON parse error: {exc}"
    if not isinstance(parsed, dict):
        return None, "child result file is not a JSON object"
    return parsed, None


def run_iteration(test_id: str, iter_index: int, clip_path: Path, timeout: int = 300) -> dict[str, Any]:
    started = time.perf_counter()
    result_json = CHILD_OUTPUT_DIR / f"{test_id}_{iter_index}_{clip_path.stem}_{time.time_ns()}.json"
    try:
        completed = subprocess.run(
            [str(ASR_PYTHON), str(CHILD_SCRIPT), str(clip_path), "--result-json", str(result_json)],
            cwd=str(ROOT),
            env=env_for_child(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        child_json, parse_error = parse_stdout_json(completed.stdout)
        result_source = "stdout"
        if child_json is None:
            child_json, file_error = read_child_result(result_json)
            result_source = "child_result_json" if child_json is not None else "missing"
            parse_error = f"stdout: {parse_error}; file: {file_error}"
        return iteration_payload(
            iter_index=iter_index,
            exit_code=completed.returncode,
            duration_seconds=round(time.perf_counter() - started, 3),
            child_json=child_json,
            parse_error=parse_error,
            stderr_tail=completed.stderr[-2000:],
            timeout=False,
            child_result_path=result_json,
            result_source=result_source,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        child_json, parse_error = parse_stdout_json(stdout)
        result_source = "stdout"
        if child_json is None:
            child_json, file_error = read_child_result(result_json)
            result_source = "child_result_json" if child_json is not None else "missing"
            parse_error = f"stdout: {parse_error}; file: {file_error}"
        return iteration_payload(
            iter_index=iter_index,
            exit_code=None,
            duration_seconds=round(time.perf_counter() - started, 3),
            child_json=child_json,
            parse_error=parse_error,
            stderr_tail=stderr[-2000:],
            timeout=True,
            child_result_path=result_json,
            result_source=result_source,
        )


def iteration_payload(
    *,
    iter_index: int,
    exit_code: int | None,
    duration_seconds: float,
    child_json: dict[str, Any] | None,
    parse_error: str | None,
    stderr_tail: str,
    timeout: bool,
    child_result_path: Path,
    result_source: str,
) -> dict[str, Any]:
    return {
        "iter_index": iter_index,
        "exit_code_dec": exit_code,
        "exit_code_hex": returncode_hex(exit_code),
        "clean_exit": exit_code == 0,
        "transcribe_seconds": child_json.get("transcribe_seconds") if child_json else None,
        "segments_count": child_json.get("segments_count") if child_json else None,
        "transcript_first_100_chars": child_json.get("transcript_first_100_chars") if child_json else "",
        "avg_logprob_first_segment": child_json.get("avg_logprob_first_segment") if child_json else None,
        "transcript": child_json.get("transcript") if child_json else "",
        "child_duration_seconds": child_json.get("duration_seconds") if child_json else None,
        "wall_seconds": duration_seconds,
        "child_stdout_parse_error": parse_error,
        "stderr_tail": stderr_tail,
        "timeout": timeout,
        "child_result_path": str(child_result_path),
        "result_source": result_source,
    }


def test_result(test_id: str, clip_name: str, clip_path: Path, iterations: int = 10) -> dict[str, Any]:
    per_iteration = []
    for index in range(iterations):
        print(f"{test_id} {clip_name} iter {index + 1}/{iterations}", flush=True)
        per_iteration.append(run_iteration(test_id, index, clip_path))

    transcripts = [item["transcript"] for item in per_iteration if item["transcript"]]
    unique_transcripts = sorted(set(transcripts))
    transcribe_seconds = [float(item["transcribe_seconds"]) for item in per_iteration if item["transcribe_seconds"] is not None]
    dirty_exit_count = sum(1 for item in per_iteration if not item["clean_exit"])
    clean_exit_count = sum(1 for item in per_iteration if item["clean_exit"])

    return {
        "test_id": test_id,
        "clip": clip_name,
        "clip_path": str(clip_path),
        "iterations": iterations,
        "dirty_exit_count": dirty_exit_count,
        "clean_exit_count": clean_exit_count,
        "transcript_variance": {
            "all_identical": len(unique_transcripts) <= 1 and len(transcripts) == iterations,
            "unique_transcripts_count": len(unique_transcripts),
            "unique_transcripts_first_100_chars": [text[:100] for text in unique_transcripts],
        },
        "transcribe_seconds": stats(transcribe_seconds),
        "per_iteration": per_iteration,
    }


def stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "max": None, "avg": None}
    return {
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "avg": round(statistics.fmean(values), 3),
    }


def classify_wav_erd(test: dict[str, Any]) -> str:
    dirty = test["dirty_exit_count"]
    clean = test["clean_exit_count"]
    if dirty == 10:
        return "deterministic_dirty"
    if clean == 10:
        return "clean"
    if 0 < dirty < 10:
        return "stochastic_dirty"
    return "mixed"


def classify_controls(news: dict[str, Any], promo: dict[str, Any]) -> str:
    if news["clean_exit_count"] == 10 and promo["clean_exit_count"] == 10:
        return "all_clean"
    return "mixed"


def recommended_safety_net(wav_pattern: str, control_pattern: str, wav_test: dict[str, Any]) -> str:
    transcript_note = "transcript deterministic" if wav_test["transcript_variance"]["all_identical"] else "transcript varied"
    if wav_pattern == "deterministic_dirty" and control_pattern == "all_clean":
        return (
            "Tolerant containment + low_quality flag wav_erd benzeri için yeterli. "
            f"Multi-clip aynı process güvenli; wav_erd exit 10/10 kirli, {transcript_note}."
        )
    if wav_pattern == "stochastic_dirty" and control_pattern == "all_clean":
        return (
            "Tolerant containment + retry mantığı. wav_erd benzerini farklı sırayla dene veya CPU fallback. "
            f"{transcript_note}."
        )
    if wav_pattern == "clean" and control_pattern == "all_clean":
        return "En rahat durum: tolerant containment yeterli, ek güvenlik ağı düşük öncelik."
    if wav_pattern == "deterministic_dirty" and control_pattern == "mixed":
        return "Tolerant containment + per-clip sanity check + batch size limiti."
    return "Eskalasyon: NVIDIA driver güncellemesi veya CUDA toolkit versiyonu denenmeli. Tolerant containment + memory monitor zorunlu."


def build_report() -> dict[str, Any]:
    started = time.perf_counter()
    tests = [
        test_result(item["test_id"], item["clip_name"], item["clip_path"])
        for item in CLIPS
    ]
    wav_pattern = classify_wav_erd(tests[0])
    control_pattern = classify_controls(tests[1], tests[2])
    report = {
        "tarih": "2026-05-11",
        "ortam": environment_info(),
        "tests": tests,
        "decision_input": {
            "wav_erd_pattern": wav_pattern,
            "control_clips_pattern": control_pattern,
            "recommended_safety_net": recommended_safety_net(wav_pattern, control_pattern, tests[0]),
        },
        "duration_seconds": round(time.perf_counter() - started, 3),
        "notes": [
            "No package/model changes were made.",
            "Each child process executed one WhisperModel load and one transcribe, then returned 0.",
            "No tqdm patch or explicit cleanup was used.",
        ],
    }
    write_json(REPORT_PATH, report)
    write_summary(SUMMARY_PATH, report)
    return report


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary(path: Path, report: dict[str, Any]) -> None:
    tests = report["tests"]
    first_line = decision_line(report)
    lines = [
        first_line,
        "",
        "| Test | Clip | Dirty/Clean | Transcript variance | Transcribe seconds |",
        "|---|---|---:|---|---|",
    ]
    for test in tests:
        variance = test["transcript_variance"]
        seconds = test["transcribe_seconds"]
        lines.append(
            f"| {test['test_id']} | {test['clip']} | "
            f"{test['dirty_exit_count']}/{test['clean_exit_count']} | "
            f"all_identical={str(variance['all_identical']).lower()}, unique={variance['unique_transcripts_count']} | "
            f"min={seconds['min']}, max={seconds['max']}, avg={seconds['avg']} |"
        )
    lines.extend(
        [
            "",
            "## Pipeline Karari",
            "",
            report["decision_input"]["recommended_safety_net"],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def decision_line(report: dict[str, Any]) -> str:
    wav_test = report["tests"][0]
    pattern = report["decision_input"]["wav_erd_pattern"]
    if pattern == "deterministic_dirty":
        label = "deterministik patolojik klip"
    elif pattern == "stochastic_dirty":
        label = "stokastik kirli exit"
    elif pattern == "clean":
        label = "temiz"
    else:
        label = "karisik"
    return f"wav_erd_test_sound: {wav_test['dirty_exit_count']}/10 kirli ({label})"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    report = build_report()
    print(json.dumps(report["decision_input"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
