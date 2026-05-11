from __future__ import annotations

import difflib
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
CHILD_SCRIPT = ROOT / "scripts" / "multilingual_hipotez_child.py"
OUTPUT_DIR = ROOT / "outputs"
CHILD_OUTPUT_DIR = OUTPUT_DIR / "asr_multilingual_hipotez_child_outputs"
REPORT_PATH = OUTPUT_DIR / "asr_multilingual_hipotez_report.json"
SUMMARY_PATH = OUTPUT_DIR / "asr_multilingual_hipotez_summary.md"
REFERENCE_REPORT_PATH = OUTPUT_DIR / "asr_tek_klip_tekrar_report.json"
FFMPEG_BIN = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin"


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


def environment_info() -> dict[str, Any]:
    code = r"""
import inspect
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
try:
    from faster_whisper import WhisperModel
    out["transcribe_signature"] = str(inspect.signature(WhisperModel.transcribe))
    out["has_multilingual_param"] = "multilingual" in out["transcribe_signature"]
except Exception as exc:
    out["transcribe_signature_error"] = type(exc).__name__ + ": " + str(exc)
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


def run_child(test_id: str, timeout: int = 420) -> dict[str, Any]:
    print(f"{test_id} basladi", flush=True)
    started = time.perf_counter()
    result_json = CHILD_OUTPUT_DIR / f"{test_id}_{time.time_ns()}.json"
    try:
        completed = subprocess.run(
            [str(ASR_PYTHON), str(CHILD_SCRIPT), "--test-id", test_id, "--result-json", str(result_json)],
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
        return {
            "test_id": test_id,
            "exit_code_dec": completed.returncode,
            "exit_code_hex": returncode_hex(completed.returncode),
            "clean_exit": completed.returncode == 0,
            "wall_seconds": round(time.perf_counter() - started, 3),
            "child_result_path": str(result_json),
            "result_source": result_source,
            "child_stdout_parse_error": parse_error,
            "stderr_tail": completed.stderr[-3000:],
            "stdout_tail": completed.stdout[-3000:],
            "child_stdout_json": child_json,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        child_json, parse_error = parse_stdout_json(stdout)
        result_source = "stdout"
        if child_json is None:
            child_json, file_error = read_child_result(result_json)
            result_source = "child_result_json" if child_json is not None else "missing"
            parse_error = f"stdout: {parse_error}; file: {file_error}"
        return {
            "test_id": test_id,
            "exit_code_dec": None,
            "exit_code_hex": None,
            "clean_exit": False,
            "timeout": True,
            "wall_seconds": round(time.perf_counter() - started, 3),
            "child_result_path": str(result_json),
            "result_source": result_source,
            "child_stdout_parse_error": parse_error,
            "stderr_tail": stderr[-3000:],
            "stdout_tail": stdout[-3000:],
            "child_stdout_json": child_json,
        }


def load_references() -> dict[str, dict[str, Any]]:
    if not REFERENCE_REPORT_PATH.exists():
        return {}
    report = json.loads(REFERENCE_REPORT_PATH.read_text(encoding="utf-8"))
    refs: dict[str, dict[str, Any]] = {}
    for test in report.get("tests", []):
        iterations = test.get("per_iteration", [])
        first = iterations[0] if iterations else {}
        refs[test.get("clip", "")] = {
            "transcript": first.get("transcript", ""),
            "transcribe_seconds": first.get("transcribe_seconds"),
            "source_report": str(REFERENCE_REPORT_PATH),
        }
    return refs


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def compare_text(reference: str, candidate: str) -> dict[str, Any]:
    ref_norm = normalize(reference)
    cand_norm = normalize(candidate)
    return {
        "exact_match": reference == candidate,
        "normalized_exact_match": ref_norm == cand_norm,
        "similarity_ratio": round(difflib.SequenceMatcher(None, ref_norm, cand_norm).ratio(), 4)
        if ref_norm or cand_norm
        else None,
    }


def seconds(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "max": None, "avg": None}
    return {"min": round(min(values), 3), "max": round(max(values), 3), "avg": round(statistics.fmean(values), 3)}


def tm1_iterations(tm1: dict[str, Any]) -> list[dict[str, Any]]:
    child = tm1.get("child_stdout_json") or {}
    return list(child.get("iterations", []))


def tm2_result(tm2: dict[str, Any]) -> dict[str, Any]:
    child = tm2.get("child_stdout_json") or {}
    return dict(child.get("result", {}))


def tm3_clips(tm3: dict[str, Any]) -> list[dict[str, Any]]:
    child = tm3.get("child_stdout_json") or {}
    return list(child.get("clips", []))


def quality_flags(transcript: str) -> dict[str, Any]:
    text = normalize(transcript)
    english_markers = ["excuse", "one minute", "prime minister", "president", "mr."]
    forced_turkish_markers = ["esküviz", "prime minizer", "bir dakika"]
    return {
        "contains_english_markers": [marker for marker in english_markers if marker in text],
        "contains_forced_turkish_markers": [marker for marker in forced_turkish_markers if marker in text],
        "looks_multilingual_reasonable": any(marker in text for marker in english_markers)
        and not any(marker in text for marker in ["esküviz", "prime minizer"]),
    }


def add_analysis(tests: list[dict[str, Any]], references: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_id = {test["test_id"]: test for test in tests}
    tm1 = by_id["TM1"]
    tm2 = by_id["TM2"]
    tm3 = by_id["TM3"]

    tm1_texts = [item.get("transcript", "") for item in tm1_iterations(tm1)]
    tm1_quality = [quality_flags(text) for text in tm1_texts]
    tm2_text = tm2_result(tm2).get("transcript", "")
    tm2_quality = quality_flags(tm2_text)

    tm3_comparisons = []
    for clip in tm3_clips(tm3):
        clip_name = "news_trt_haber_1" if "news_trt_haber" in clip.get("clip_name", "") else "promo_1"
        ref = references.get(clip_name, {})
        ref_seconds = ref.get("transcribe_seconds")
        current_seconds = clip.get("transcribe_seconds")
        tm3_comparisons.append(
            {
                "clip": clip_name,
                "reference_transcript": ref.get("transcript", ""),
                "multilingual_transcript": clip.get("transcript", ""),
                "text_compare": compare_text(ref.get("transcript", ""), clip.get("transcript", "")),
                "reference_seconds": ref_seconds,
                "multilingual_seconds": current_seconds,
                "slowdown_ratio": round(float(current_seconds) / float(ref_seconds), 3)
                if ref_seconds and current_seconds
                else None,
            }
        )

    tm1_exit = "Temiz" if tm1.get("clean_exit") else "Kirli"
    tm1_transcript_ok = any(item["looks_multilingual_reasonable"] for item in tm1_quality) or tm2_quality[
        "looks_multilingual_reasonable"
    ]
    tm3_regression_ok = all(
        item["text_compare"]["similarity_ratio"] and item["text_compare"]["similarity_ratio"] >= 0.85
        for item in tm3_comparisons
    )
    tm3_slow = any(item["slowdown_ratio"] and item["slowdown_ratio"] >= 3.0 for item in tm3_comparisons)

    if tm1.get("clean_exit") and tm1_transcript_ok and tm3_regression_ok and not tm3_slow:
        decision = "multilingual=True default kullan, sorun tamamen çözüldü"
    elif tm1.get("clean_exit") and tm1_transcript_ok and tm3_slow:
        decision = "multilingual opt-in, sadece şüpheli kliplerde aç"
    elif not tm1.get("clean_exit") and tm1_transcript_ok:
        decision = "Multilingual çıktıyı düzeltiyor ama crash başka sebepli, iki ayrı sorun"
    elif tm1.get("clean_exit") and not tm1_transcript_ok:
        decision = 'multilingual yeterli değil, language="en" forced denenmeli'
    else:
        decision = "Hipotez yanlış, tolerant containment kararına geri dön"

    return {
        "tm1_final_exit": tm1_exit,
        "tm1_quality_flags": tm1_quality,
        "tm1_transcribe_seconds": seconds([float(item["transcribe_seconds"]) for item in tm1_iterations(tm1) if item.get("transcribe_seconds")]),
        "tm2_quality_flags": tm2_quality,
        "tm3_comparisons": tm3_comparisons,
        "tm3_regression_ok": tm3_regression_ok,
        "tm3_slow": tm3_slow,
        "matrix_decision": decision,
    }


def build_report() -> dict[str, Any]:
    started = time.perf_counter()
    references = load_references()
    tests = [run_child("TM1", timeout=720), run_child("TM2", timeout=420), run_child("TM3", timeout=420)]
    analysis = add_analysis(tests, references)
    report = {
        "tarih": "2026-05-11",
        "ortam": environment_info(),
        "tests": tests,
        "references": references,
        "analysis": analysis,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "notes": [
            "No package/model changes were made.",
            "No tqdm patch or explicit cleanup was used.",
            "Transcribe calls used multilingual=True with otherwise default faster-whisper parameters.",
        ],
    }
    write_json(REPORT_PATH, report)
    write_summary(SUMMARY_PATH, report)
    return report


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary(path: Path, report: dict[str, Any]) -> None:
    analysis = report["analysis"]
    tests = {test["test_id"]: test for test in report["tests"]}
    tm1_seconds = analysis["tm1_transcribe_seconds"]
    tm2 = tm2_result(tests["TM2"])
    tm3_rows = analysis["tm3_comparisons"]
    lines = [
        f"Sonuç: {analysis['matrix_decision']}",
        "",
        "| Test | Final exit | Transcript kalite | Süre | Not |",
        "|---|---:|---|---|---|",
        (
            f"| TM1 | {tests['TM1']['exit_code_hex']} | "
            f"reasonable={any(item['looks_multilingual_reasonable'] for item in analysis['tm1_quality_flags'])} | "
            f"min={tm1_seconds['min']}, max={tm1_seconds['max']}, avg={tm1_seconds['avg']} | "
            "wav_erd 3x aynı instance |"
        ),
        (
            f"| TM2 | {tests['TM2']['exit_code_hex']} | "
            f"reasonable={analysis['tm2_quality_flags']['looks_multilingual_reasonable']} | "
            f"{tm2.get('transcribe_seconds')} | wav_erd tek transcribe |"
        ),
    ]
    tm3_note = "; ".join(
        f"{row['clip']}: sim={row['text_compare']['similarity_ratio']}, slowdown={row['slowdown_ratio']}"
        for row in tm3_rows
    )
    lines.append(f"| TM3 | {tests['TM3']['exit_code_hex']} | regression_ok={analysis['tm3_regression_ok']} | - | {tm3_note} |")
    lines.extend(
        [
            "",
            "## TM2 Transcript",
            "",
            tm2.get("transcript", ""),
            "",
            "## TM3 Regression",
            "",
            "| Clip | Exact | Similarity | Ref sec | Multilingual sec | Slowdown |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in tm3_rows:
        compare = row["text_compare"]
        lines.append(
            f"| {row['clip']} | {str(compare['exact_match']).lower()} | {compare['similarity_ratio']} | "
            f"{row['reference_seconds']} | {row['multilingual_seconds']} | {row['slowdown_ratio']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    report = build_report()
    print(json.dumps(report["analysis"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
