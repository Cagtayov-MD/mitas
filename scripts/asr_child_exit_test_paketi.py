from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(r"E:\MITAS")
ASR_PYTHON = ROOT / "venvs" / "asr" / "Scripts" / "python.exe"
CHILD_DIR = ROOT / "scripts" / "asr_exit_test_children"
OUTPUT_DIR = ROOT / "outputs"
REPORT_PATH = OUTPUT_DIR / "asr_child_exit_test_paketi_report.json"
SUMMARY_PATH = OUTPUT_DIR / "asr_child_exit_test_paketi_summary.md"
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
    stripped = stdout.strip()
    if not stripped:
        return None, "empty stdout"
    candidates = [line.strip() for line in stripped.splitlines() if line.strip()]
    for line in reversed(candidates):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed, None
    return None, "no parseable JSON object in stdout"


def run_child(
    test_id: str,
    child_name: str,
    extra_args: list[str] | None = None,
    python_flags: list[str] | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    extra_args = extra_args or []
    python_flags = python_flags or []
    command = [str(ASR_PYTHON), *python_flags, str(CHILD_DIR / child_name), *extra_args]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
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
        duration = round(time.perf_counter() - started, 3)
        stdout_json, parse_error = parse_stdout_json(completed.stdout)
        transcript_present = bool(stdout_json and stdout_json.get("transcript_present"))
        if stdout_json and stdout_json.get("status") == "skipped":
            transcript_present = False
        return {
            "test_id": test_id,
            "command": command,
            "exit_code": completed.returncode,
            "exit_code_hex": returncode_hex(completed.returncode),
            "clean_exit": completed.returncode == 0,
            "child_stdout_json": stdout_json,
            "child_stdout_parse_error": parse_error,
            "transcript_present": transcript_present,
            "duration_seconds": duration,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-4000:],
            "notes": notes_for_result(completed.returncode, stdout_json, parse_error),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stdout_json, parse_error = parse_stdout_json(stdout)
        return {
            "test_id": test_id,
            "command": command,
            "exit_code": None,
            "exit_code_hex": None,
            "clean_exit": False,
            "child_stdout_json": stdout_json,
            "child_stdout_parse_error": parse_error,
            "transcript_present": bool(stdout_json and stdout_json.get("transcript_present")),
            "duration_seconds": round(time.perf_counter() - started, 3),
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-4000:],
            "timeout": True,
            "notes": ["timeout"],
        }


def notes_for_result(returncode: int | None, stdout_json: dict[str, Any] | None, parse_error: str | None) -> list[str]:
    notes = []
    if stdout_json:
        notes.append("child stdout JSON parsed")
    else:
        notes.append(f"child stdout JSON missing: {parse_error}")
    if returncode == 0:
        notes.append("clean exit")
    elif stdout_json:
        notes.append("abnormal exit after parseable child output")
    else:
        notes.append("abnormal exit without parseable child output")
    return notes


def environment_info() -> dict[str, Any]:
    code = r"""
import json
import sys
import importlib.metadata as md
out = {"python": sys.version.split()[0]}
for name, dist in [("ctranslate2", "ctranslate2"), ("faster_whisper", "faster-whisper"), ("torch", "torch")]:
    try:
        out[name] = md.version(dist)
    except Exception as exc:
        out[name] = type(exc).__name__ + ": " + str(exc)
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
    return parsed or {"error": error, "stderr": completed.stderr[-2000:]}


def compare_segments(reference: dict[str, Any], suspect: dict[str, Any], tolerance: float = 1e-4) -> dict[str, Any]:
    ref_segments = first_clip_segments(reference)
    suspect_segments = first_clip_segments(suspect)
    text_mismatches = []
    numeric_mismatches = []
    segments_count_match = len(ref_segments) == len(suspect_segments)
    for index, (left, right) in enumerate(zip(ref_segments, suspect_segments)):
        if left.get("text") != right.get("text"):
            text_mismatches.append({"index": index, "reference": left.get("text"), "suspect": right.get("text")})
        for key in ["start", "end", "avg_logprob", "no_speech_prob"]:
            left_value = left.get(key)
            right_value = right.get(key)
            if left_value is None and right_value is None:
                continue
            if left_value is None or right_value is None:
                numeric_mismatches.append({"index": index, "field": key, "reference": left_value, "suspect": right_value})
                continue
            if abs(float(left_value) - float(right_value)) >= tolerance:
                numeric_mismatches.append({"index": index, "field": key, "reference": left_value, "suspect": right_value})
    return {
        "segments_count_match": segments_count_match,
        "reference_segments_count": len(ref_segments),
        "suspect_segments_count": len(suspect_segments),
        "segments_match": segments_count_match and not text_mismatches and not numeric_mismatches,
        "text_mismatches": text_mismatches,
        "numeric_mismatches": numeric_mismatches,
        "tolerance": tolerance,
    }


def first_clip_segments(child_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not child_json:
        return []
    clips = child_json.get("clips")
    if isinstance(clips, list) and clips:
        return list(clips[0].get("segments", []))
    return list(child_json.get("segments", []))


def test_status(test: dict[str, Any]) -> str:
    child = test.get("child_stdout_json") or {}
    if child.get("status") == "skipped":
        return "skipped"
    if test.get("transcript_present") and test.get("clean_exit"):
        return "passed"
    if test.get("transcript_present") and not test.get("clean_exit"):
        return "needs_review"
    if child.get("scenario") == "new_instance_per_clip_same_process" and test.get("clean_exit"):
        return "passed"
    return "failed"


def build_t5_result(reference: dict[str, Any], dirty: dict[str, Any] | None) -> dict[str, Any]:
    if dirty is None:
        return {
            "test_id": "T5",
            "exit_code": None,
            "exit_code_hex": None,
            "clean_exit": True,
            "child_stdout_json": None,
            "transcript_present": False,
            "duration_seconds": 0.0,
            "notes": ["skipped: no dirty baseline to compare"],
            "status": "skipped",
            "diff_summary": {"skipped": "no dirty baseline to compare"},
        }
    diff_summary = compare_segments(reference.get("child_stdout_json"), dirty.get("child_stdout_json"))
    return {
        "test_id": "T5",
        "exit_code": reference.get("exit_code"),
        "exit_code_hex": reference.get("exit_code_hex"),
        "clean_exit": bool(reference.get("clean_exit")),
        "child_stdout_json": reference.get("child_stdout_json"),
        "transcript_present": bool(reference.get("transcript_present")),
        "duration_seconds": reference.get("duration_seconds"),
        "notes": [
            "reference clean single-transcribe compared with first clip from dirty multi-clip baseline",
            "dirty_baseline=" + str(dirty.get("test_id")),
        ],
        "status": "passed" if diff_summary["segments_match"] else "needs_review",
        "diff_summary": diff_summary,
    }


def t4_decision(t4: dict[str, Any]) -> dict[str, str]:
    if t4.get("clean_exit"):
        return {
            "result": "clean",
            "containment": "instance-per-clip may be enough inside the same process",
            "interpretation": "same model instance state accumulation is the stronger suspect",
        }
    return {
        "result": "dirty",
        "containment": "process-per-clip is the safer containment",
        "interpretation": "problem is not only same-instance state; process-level CUDA lifecycle remains suspect",
    }


def build_report() -> dict[str, Any]:
    started = time.perf_counter()
    tests: list[dict[str, Any]] = []

    t1 = run_child("T1", "t1_child.py", timeout=180)
    tests.append(t1)
    t2 = run_child("T2", "t2_child.py", timeout=240)
    tests.append(t2)
    t3 = run_child("T3", "t3_child.py", timeout=360)
    tests.append(t3)
    t4 = run_child("T4", "t4_child.py", timeout=420)
    tests.append(t4)

    dirty_baseline = None
    for candidate in [t2, t3]:
        if candidate.get("transcript_present") and not candidate.get("clean_exit"):
            dirty_baseline = candidate
            break
    t5_reference = run_child("T5_REF", "t5_child.py", timeout=180) if dirty_baseline else None
    t5 = build_t5_result(t5_reference or {}, dirty_baseline)
    tests.append(t5)

    t6a = run_child("T6a", "t6_child.py", ["--variant", "empty_cache"], timeout=300)
    tests.append(t6a)
    t6b = run_child("T6b", "t6_child.py", ["--variant", "gc"], timeout=300)
    tests.append(t6b)
    t6c = run_child("T6c", "t6_child.py", ["--variant", "both"], timeout=300)
    tests.append(t6c)
    t6d = run_child("T6d", "t6_child.py", ["--variant", "ct2_api"], timeout=120)
    tests.append(t6d)

    t7 = run_child("T7", "t7_child.py", python_flags=["-X", "faulthandler", "-X", "dev"], timeout=360)
    t7["faulthandler_stderr"] = t7.get("stderr_tail", "")
    t7["minidump_path"] = None
    t7["top_frame_module"] = None
    t7["notes"].append("minidump not configured in this no-registry-change run")
    tests.append(t7)

    t8 = run_child("T8", "t8_child.py", timeout=60)
    tests.append(t8)

    for test in tests:
        test["status"] = test.get("status") or test_status(test)

    dirty_tests = [test for test in tests if test.get("transcript_present") and not test.get("clean_exit")]
    failed_tests = [test for test in tests if test["status"] == "failed"]
    status = "failed" if failed_tests else ("needs_review" if dirty_tests else "passed")

    report = {
        "paket_versiyonu": "1",
        "tarih": "2026-05-11",
        "ortam": environment_info(),
        "status": status,
        "testler": tests,
        "ozet": {
            "dirty_tests": [test["test_id"] for test in dirty_tests],
            "failed_tests": [test["test_id"] for test in failed_tests],
            "t4_karari": t4_decision(t4),
            "t5_diff_summary": t5.get("diff_summary"),
            "likely_cause": likely_cause(tests, t4, t5),
        },
        "duration_seconds": round(time.perf_counter() - started, 3),
    }
    write_json(REPORT_PATH, report)
    write_summary(SUMMARY_PATH, report)
    return report


def likely_cause(tests: list[dict[str, Any]], t4: dict[str, Any], t5: dict[str, Any]) -> str:
    test_by_id = {test["test_id"]: test for test in tests}
    t1 = test_by_id.get("T1", {})
    t2 = test_by_id.get("T2", {})
    t3 = test_by_id.get("T3", {})
    if not t1.get("clean_exit"):
        return "Threshold starts at two transcribe calls on one CUDA large-v3 instance."
    if t2.get("clean_exit") and not t3.get("clean_exit") and t4.get("clean_exit"):
        return "Different-clip multi-transcribe on one instance triggers dirty teardown; fresh instance per clip exits cleanly."
    if not t2.get("clean_exit") and not t3.get("clean_exit"):
        return "Repeated transcribe on one instance is enough to trigger dirty teardown."
    if not t4.get("clean_exit"):
        return "Fresh instances in one process still exit dirty; process-per-clip containment is favored."
    if t5.get("diff_summary", {}).get("segments_match") is False:
        return "Dirty exit may affect output consistency; containment priority increases."
    return "No dirty teardown reproduced in package tests."


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# ASR Child Exit Test Paketi Summary",
        "",
        f"Status: `{report['status']}`",
        "",
        "| Test | Clean Exit | Transcript Valid | Note |",
        "|---|---:|---:|---|",
    ]
    for test in report["testler"]:
        child = test.get("child_stdout_json") or {}
        note = "; ".join(test.get("notes", [])[:2])
        if child.get("status") == "skipped":
            note = "skipped: " + str(child.get("skip_reason"))
        lines.append(
            f"| {test['test_id']} | {str(test.get('clean_exit')).lower()} | "
            f"{str(test.get('transcript_present')).lower()} | {note} |"
        )
    lines.extend(
        [
            "",
            "## T4 Karari",
            "",
            json.dumps(report["ozet"]["t4_karari"], ensure_ascii=False, indent=2),
            "",
            "## T5 Diff Ozeti",
            "",
            json.dumps(report["ozet"]["t5_diff_summary"], ensure_ascii=False, indent=2),
            "",
            "## Likely Cause",
            "",
            report["ozet"]["likely_cause"],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["ozet"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"passed", "needs_review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
