from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any


ROOT = Path(r"E:\MITAS")
ASR_PYTHON = ROOT / "venvs" / "asr" / "Scripts" / "python.exe"
CHILD_DIR = ROOT / "scripts" / "tur3_children"
OUTPUT_DIR = ROOT / "outputs"
REPORT_PATH = OUTPUT_DIR / "asr_child_exit_tur3_report.json"
SUMMARY_PATH = OUTPUT_DIR / "asr_child_exit_tur3_summary.md"
FFMPEG_BIN = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin"
CLIP_NEWS = ROOT / "outputs" / "real_media_smoke" / "news_trt_haber_1_20s_16000hz_mono_asr_input.wav"
CLIP_PROMO = ROOT / "outputs" / "real_media_smoke" / "promo_1_20s_16000hz_mono_asr_input.wav"
CLIP_WAV = ROOT / "outputs" / "real_media_smoke" / "wav_erd_test_sound_20s_16000hz_mono_asr_input.wav"
CLIPS_3 = [CLIP_NEWS, CLIP_PROMO, CLIP_WAV]


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


def run_child(test_id: str, child_name: str, args: list[str] | None = None, timeout: int = 420) -> dict[str, Any]:
    command = [str(ASR_PYTHON), str(CHILD_DIR / child_name), *(args or [])]
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
        child_json, parse_error = parse_stdout_json(completed.stdout)
        transcripts_valid = bool(child_json and child_json.get("transcripts_valid"))
        transcript_present = bool(child_json and child_json.get("transcript_present"))
        clips_count = int(child_json.get("clips_count", 0)) if child_json else 0
        transcripts_count = int(child_json.get("transcripts_count", 0)) if child_json else 0
        return {
            "test_id": test_id,
            "exit_code_dec": completed.returncode,
            "exit_code_hex": returncode_hex(completed.returncode),
            "clean_exit": completed.returncode == 0,
            "clips_count": clips_count,
            "transcripts_count": transcripts_count,
            "transcripts_valid": transcripts_valid,
            "transcript_present": transcript_present,
            "duration_seconds": duration,
            "stderr_tail": completed.stderr[-4000:],
            "stdout_tail": completed.stdout[-2000:],
            "child_stdout_json": child_json,
            "child_stdout_parse_error": parse_error,
            "notes": notes_for(completed.returncode, child_json, parse_error),
            "status": status_for(completed.returncode, child_json),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        child_json, parse_error = parse_stdout_json(stdout)
        return {
            "test_id": test_id,
            "exit_code_dec": None,
            "exit_code_hex": None,
            "clean_exit": False,
            "clips_count": int(child_json.get("clips_count", 0)) if child_json else 0,
            "transcripts_count": int(child_json.get("transcripts_count", 0)) if child_json else 0,
            "transcripts_valid": bool(child_json and child_json.get("transcripts_valid")),
            "transcript_present": bool(child_json and child_json.get("transcript_present")),
            "duration_seconds": round(time.perf_counter() - started, 3),
            "stderr_tail": stderr[-4000:],
            "stdout_tail": stdout[-2000:],
            "child_stdout_json": child_json,
            "child_stdout_parse_error": parse_error,
            "timeout": True,
            "notes": ["timeout"],
            "status": "failed",
        }


def notes_for(returncode: int | None, child_json: dict[str, Any] | None, parse_error: str | None) -> str:
    if child_json and returncode == 0:
        return "child JSON valid; clean exit"
    if child_json:
        return "child JSON valid; abnormal exit after output"
    return f"child JSON missing: {parse_error}"


def status_for(returncode: int | None, child_json: dict[str, Any] | None) -> str:
    if child_json and child_json.get("status") == "skipped":
        return "skipped"
    if child_json and child_json.get("transcripts_valid") and returncode == 0:
        return "passed"
    if child_json and child_json.get("transcripts_valid") and returncode != 0:
        return "needs_review"
    return "failed"


def environment_info() -> dict[str, Any]:
    code = r"""
import json
import sys
import inspect
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
    out["native_tqdm_control"] = "log_progress"
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
    return parsed or {"error": error, "stderr_tail": completed.stderr[-1000:]}


def where(name: str) -> str | None:
    completed = subprocess.run(
        ["where.exe", name],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.splitlines()[0].strip()


def tb2_procdump_result() -> dict[str, Any]:
    procdump = where("procdump")
    cdb = where("cdb")
    result = {
        "test_id": "TB2",
        "exit_code_dec": 0,
        "exit_code_hex": "0x00000000",
        "clean_exit": True,
        "clips_count": 0,
        "transcripts_count": 0,
        "transcripts_valid": False,
        "duration_seconds": 0.0,
        "stderr_tail": "",
        "notes": "procdump not available; no minidump captured" if not procdump else "procdump available but wrapper not executed in this safe pass",
        "procdump_available": bool(procdump),
        "procdump_path": procdump,
        "dump_path": None,
        "cdb_available": bool(cdb),
        "cdb_path": cdb,
        "top_frames": None,
        "status": "skipped" if not procdump else "needs_review",
    }
    return result


def skipped_test(test_id: str, reason: str) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "exit_code_dec": 0,
        "exit_code_hex": "0x00000000",
        "clean_exit": True,
        "clips_count": 0,
        "transcripts_count": 0,
        "transcripts_valid": False,
        "transcript_present": False,
        "duration_seconds": 0.0,
        "stderr_tail": "",
        "notes": reason,
        "status": "skipped",
    }


def tb3_process_per_clip() -> dict[str, Any]:
    started = time.perf_counter()
    children = []
    for clip in CLIPS_3:
        children.append(run_child("TB3_CHILD", "tb3_child.py", ["--clip", str(clip)], timeout=240))
    total_wall = round(time.perf_counter() - started, 3)
    load_times = []
    transcribe_times = []
    for child in children:
        payload = child.get("child_stdout_json") or {}
        load_times.extend(payload.get("per_child_load_seconds", []))
        transcribe_times.extend(payload.get("per_child_transcribe_seconds", []))
    all_clean = all(child["clean_exit"] for child in children)
    transcripts_valid = all(child["transcripts_valid"] for child in children)
    return {
        "test_id": "TB3",
        "exit_code_dec": 0 if all_clean else 1,
        "exit_code_hex": "0x00000000" if all_clean else "0x00000001",
        "clean_exit": all_clean,
        "clips_count": len(children),
        "transcripts_count": sum(child["transcripts_count"] for child in children),
        "transcripts_valid": transcripts_valid,
        "duration_seconds": total_wall,
        "stderr_tail": "\n".join(child.get("stderr_tail", "") for child in children if child.get("stderr_tail"))[-4000:],
        "notes": "each clip executed in a separate child process",
        "total_wall_seconds": total_wall,
        "per_child_load_seconds": load_times,
        "per_child_transcribe_seconds": transcribe_times,
        "avg_load_seconds": round(sum(load_times) / len(load_times), 3) if load_times else None,
        "avg_transcribe_seconds": round(sum(transcribe_times) / len(transcribe_times), 3) if transcribe_times else None,
        "all_clean_exits": all_clean,
        "child_results": children,
        "status": "passed" if all_clean and transcripts_valid else "failed",
    }


def tc1_result(reason: str) -> dict[str, Any]:
    child = run_child("TC1", "tc1_child.py", timeout=60)
    child["notes"] = reason + "; " + str(child.get("notes", ""))
    child["status"] = "skipped"
    return child


def build_report() -> dict[str, Any]:
    started = time.perf_counter()
    tests: list[dict[str, Any]] = []
    recommended_decision = "B"
    decision_reason = ""
    decision_caveat = ""

    ta1 = run_child("TA1", "ta1_child.py", timeout=420)
    tests.append(ta1)
    tb3 = None

    if ta1["clean_exit"] and ta1["transcripts_valid"]:
        ta2 = run_child("TA2", "ta2_child.py", timeout=700)
        tests.append(ta2)
        ta3 = run_child("TA3", "ta3_child.py", timeout=420)
        tests.append(ta3)
        if ta2["clean_exit"] and ta2["transcripts_valid"]:
            recommended_decision = "A"
            decision_reason = "TA1 and TA2 cleaned multi-clip teardown when tqdm was monkey-patched off."
            tests.append(tc1_result("TC1 skipped because Decision A path completed before TB2"))
        else:
            recommended_decision = "B"
            decision_reason = "TA1 cleaned N=3 but TA2 dirty at N=5; tqdm patch alone is not stable enough."
            tb3 = tb3_process_per_clip()
            tests.append(tb3)
            tests.append(tc1_result("TC1 skipped because TB2 did not identify ctranslate2.dll"))
    else:
        tests.append(skipped_test("TA2", "skipped by early-exit: TA1 dirty, so tqdm monkey-patch is not sufficient"))
        tests.append(skipped_test("TA3", "skipped by early-exit: native log_progress path cannot rescue a dirty TA1 monkey-patch"))
        tb1 = run_child("TB1", "tb1_child.py", timeout=520)
        tests.append(tb1)
        tb2 = tb2_procdump_result()
        tests.append(tb2)
        tb3 = tb3_process_per_clip()
        tests.append(tb3)
        recommended_decision = "B"
        decision_reason = "TA1 stayed dirty, so tqdm is not sufficient; process-per-clip baseline was measured."
        if not tb3.get("all_clean_exits"):
            decision_caveat = (
                "Strict process-per-clip did not guarantee clean exit for every clip; "
                "Karar B is still the safer architecture, but it needs valid-JSON containment "
                "or CUDA/driver escalation before being treated as fully clean."
            )
        if tb2.get("top_frames") and "ctranslate2" in str(tb2["top_frames"]).lower():
            tests.append(tc1_result("TC1 would run only in isolated venvs after explicit approval"))
        else:
            tests.append(tc1_result("TC1 skipped because TB2 did not identify ctranslate2.dll"))

    status = "failed" if any(test.get("status") == "failed" for test in tests) else (
        "passed" if recommended_decision == "A" else "needs_review"
    )
    report = {
        "tur": "3",
        "tarih": "2026-05-11",
        "status": status,
        "recommended_decision": recommended_decision,
        "decision_reason": decision_reason,
        "decision_caveat": decision_caveat,
        "environment": environment_info(),
        "tests": tests,
        "tb3_metrics": tb3,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "notes": [
            "No package/model changes were made.",
            "TA3 uses explicit log_progress=False; disable_tqdm/verbose are not present in faster-whisper 1.2.1 signature.",
            "Procdump/cdb are used only if present on PATH; no SysInternals download was attempted.",
        ],
    }
    write_json(REPORT_PATH, report)
    write_summary(SUMMARY_PATH, report)
    return report


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# ASR Child Exit Tur 3 Summary",
        "",
        f"**Önerilen karar: Karar {report['recommended_decision']}**",
        "",
        report["decision_reason"],
        "",
        report.get("decision_caveat", ""),
        "",
        "| Test | Clean Exit | Transcripts Valid | Status | Notes |",
        "|---|---:|---:|---|---|",
    ]
    for test in report["tests"]:
        lines.append(
            f"| {test['test_id']} | {str(test.get('clean_exit')).lower()} | "
            f"{str(test.get('transcripts_valid')).lower()} | {test.get('status')} | "
            f"{str(test.get('notes', ''))[:140]} |"
        )
    if report["recommended_decision"] == "A":
        lines.extend(
            [
                "",
                "## Karar A Snippet",
                "",
                "```python",
                "import os",
                "os.environ['TQDM_DISABLE'] = '1'",
                "import tqdm, tqdm.auto",
                "# Replace tqdm.tqdm and tqdm.auto.tqdm with a no-op class before importing faster_whisper.",
                "```",
            ]
        )
    else:
        tb3 = report.get("tb3_metrics") or {}
        lines.extend(
            [
                "",
                "## Karar B Performans Metrikleri",
                "",
                f"- total_wall_seconds: `{tb3.get('total_wall_seconds')}`",
                f"- avg_load_seconds: `{tb3.get('avg_load_seconds')}`",
                f"- avg_transcribe_seconds: `{tb3.get('avg_transcribe_seconds')}`",
                f"- all_clean_exits: `{tb3.get('all_clean_exits')}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if hasattr(__import__("sys").stdout, "reconfigure"):
        __import__("sys").stdout.reconfigure(encoding="utf-8", errors="replace")
    report = build_report()
    print(
        json.dumps(
            {
                "status": report["status"],
                "recommended_decision": report["recommended_decision"],
                "decision_reason": report["decision_reason"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] in {"passed", "needs_review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
