#!/usr/bin/env python3
"""29-film Sheriff kabul cohortunu gece boyunca güvenli izle ve kapat.

Bu araç üretim pipeline'ını ya da SQLite durumunu değiştirmez. Yalnız hedef
cohort henüz terminal değilken çalışan bir Sheriff yoksa ``./sheriff run``
başlatır. FAILED/BLOCKED görevleri asla yeniden açmaz; bunları kabul kapısı
hatası olarak kaydeder.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ALLSTAR = HERE.parents[1]
PROJECT = ALLSTAR.parent
SHERIFF = ALLSTAR / "sheriff"
DB = SHERIFF / "state" / "sheriff.sqlite3"
COHORT = "sheriff/0.2.0@467a05d3dbae9d50"
EXPECTED_FILMS = 29
EXPECTED_SECTIONS = 58
EXPECTED_TASKS = EXPECTED_FILMS * 13
RUN_TERMINAL = {"SUCCEEDED", "FAILED"}
TASK_TERMINAL = {"SUCCEEDED", "NO_CONTENT", "FAILED", "BLOCKED_CONTRACT", "CANCELLED"}

STATUS_LOG = HERE / "GECE_KABUL_20260818_DURUM.jsonl"
SUMMARY_PATH = HERE / "GECE_KABUL_20260818_TAMAMLAMA.json"
LOCK_PATH = HERE / "GECE_KABUL_20260818.lock"
RUN_LOG = HERE / "GECE_KABUL_20260818_SHERIFF_RUN.log"
REPORT_JSON = HERE / "LEBRON_NASH_JORDAN_SHERIFF_KABUL_20260818.json"
REPORT_MD = HERE / "LEBRON_NASH_JORDAN_SHERIFF_KABUL_20260818.md"
REPORTER = HERE / "sheriff_kabul_raporu.py"

EXTERNAL_GATES = {
    "lebron_parity": ALLSTAR / "lebron_james/out/lebron_kalici_kabul_20260818/ozet.json",
    "lebron_probe": Path("/tmp/lebron-private-ollama-kabul/")
    / "cag_output07_private_ollama_kabul/cikis/lebron.json",
    "nash_cyrillic": Path("/tmp/nash-multiscript-kabul-v2/")
    / "cag_output20_multiscript_kabul_v2/cikis/nash.json",
    "nash_arabic": Path("/tmp/nash-multiscript-kabul-v3/")
    / "cag_output23_multiscript_kabul_v3/cikis/nash.json",
}


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_json(value: str | None) -> dict[str, Any]:
    try:
        decoded = json.loads(value or "{}")
        return decoded if isinstance(decoded, dict) else {}
    except (TypeError, ValueError):
        return {}


def write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def event(kind: str, **data: Any) -> None:
    row = {"at": now(), "event": kind, **data}
    with STATUS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def readonly_connection() -> sqlite3.Connection:
    # uri=ro means this monitor cannot accidentally initialize/migrate the DB.
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def cohort_snapshot() -> dict[str, Any]:
    with readonly_connection() as conn:
        runs = conn.execute(
            "SELECT run_id, film_id, status, created_at, updated_at FROM runs "
            "WHERE pipeline_version=? ORDER BY film_id, run_id", (COHORT,)).fetchall()
        task_rows = conn.execute(
            "SELECT t.task_id,t.run_id,t.film_id,t.kind,t.logical_role,t.section,t.status,"
            "t.attempt_count,t.max_attempts,t.updated_at,t.result_json "
            "FROM tasks t JOIN runs r ON r.run_id=t.run_id "
            "WHERE r.pipeline_version=? AND t.pipeline_version=? "
            "ORDER BY t.updated_at,t.task_id", (COHORT, COHORT)).fetchall()
    run_statuses = Counter(str(row["status"]) for row in runs)
    task_statuses = Counter(str(row["status"]) for row in task_rows)
    reader_sections = {(str(row["run_id"]), str(row["section"])) for row in task_rows
                       if row["logical_role"] in {"reader_master", "reader_frame", "reader_video"}
                       and row["section"] in {"giris", "cikis"}}
    failed = []
    for row in task_rows:
        if row["status"] in {"FAILED", "BLOCKED_CONTRACT", "CANCELLED"}:
            result = safe_json(row["result_json"])
            failed.append({
                "film_id": row["film_id"], "run_id": row["run_id"],
                "task_id": row["task_id"], "kind": row["kind"],
                "logical_role": row["logical_role"], "section": row["section"],
                "status": row["status"], "attempt_count": row["attempt_count"],
                "max_attempts": row["max_attempts"],
                "retry_reason": result.get("retry_reason"),
                "reason": result.get("reason") or result.get("error"),
            })
    shape = {
        "run_count": len(runs),
        "distinct_film_count": len({str(row["film_id"]) for row in runs}),
        "task_count": len(task_rows),
        "reader_section_count": len(reader_sections),
        "expected_films": EXPECTED_FILMS,
        "expected_tasks": EXPECTED_TASKS,
        "expected_sections": EXPECTED_SECTIONS,
    }
    shape["ok"] = (shape["run_count"] == EXPECTED_FILMS
                   and shape["distinct_film_count"] == EXPECTED_FILMS
                   and shape["task_count"] == EXPECTED_TASKS
                   and shape["reader_section_count"] == EXPECTED_SECTIONS)
    all_runs_terminal = bool(runs) and all(row["status"] in RUN_TERMINAL for row in runs)
    all_tasks_terminal = bool(task_rows) and all(row["status"] in TASK_TERMINAL
                                                  for row in task_rows)
    return {
        "cohort": COHORT, "at": now(), "shape": shape,
        "run_status_counts": dict(sorted(run_statuses.items())),
        "task_status_counts": dict(sorted(task_statuses.items())),
        "all_runs_terminal": all_runs_terminal,
        "all_tasks_terminal": all_tasks_terminal,
        "terminal": all_runs_terminal and all_tasks_terminal,
        "failed_or_blocked_tasks": failed,
    }


def proc_rows() -> list[dict[str, Any]]:
    """Read /proc directly so the monitor has no ps/pgrep parsing ambiguity."""
    rows = []
    for candidate in Path("/proc").iterdir():
        if not candidate.name.isdecimal():
            continue
        try:
            tokens = [part.decode("utf-8", "replace") for part in
                      (candidate / "cmdline").read_bytes().split(b"\0") if part]
            stat = (candidate / "stat").read_text(encoding="utf-8")
            # comm can contain spaces/parentheses; field 4 starts after final ')'.
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
            if tokens:
                rows.append({"pid": int(candidate.name), "ppid": ppid, "argv": tokens})
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError, IndexError):
            continue
    return rows


def sheriff_runners(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_main = str((SHERIFF / "main.py").resolve())
    target_cli = str((SHERIFF / "sheriff").resolve())
    found = []
    for row in rows:
        argv = row["argv"]
        owns_program = target_main in argv or target_cli in argv
        if owns_program and any(arg in {"run", "_daemon"} for arg in argv):
            found.append({"pid": row["pid"], "ppid": row["ppid"], "argv": argv})
    return found


def start_runner_if_needed(runners: list[dict[str, Any]], *, no_start: bool) -> dict[str, Any] | None:
    if runners or no_start:
        return None
    command = [str(SHERIFF / "sheriff"), "run"]
    log_handle = RUN_LOG.open("ab", buffering=0)
    try:
        process = subprocess.Popen(command, cwd=SHERIFF, stdin=subprocess.DEVNULL,
                                   stdout=log_handle, stderr=subprocess.STDOUT,
                                   start_new_session=True, close_fds=True)
    finally:
        log_handle.close()
    started = {"pid": process.pid, "command": command, "log": str(RUN_LOG)}
    event("sheriff_started_by_monitor", **started)
    return started


def file_fingerprint(root: Path) -> dict[str, Any]:
    """Small, read-only ~/.ollama inventory; content hashes make the audit useful."""
    result: dict[str, Any] = {"path": str(root), "exists": root.exists(), "entries": []}
    if not root.is_dir():
        return result
    try:
        for item in sorted(root.rglob("*")):
            if item.is_dir():
                continue
            stat = item.stat()
            digest = hashlib.sha256()
            with item.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            result["entries"].append({"path": str(item.relative_to(root)),
                                      "bytes": stat.st_size,
                                      "sha256": digest.hexdigest()})
    except (OSError, PermissionError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def private_lebron_processes(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return only unequivocally tower-owned processes and the protected global ones."""
    runtime = str((ALLSTAR / "lebron_james/model/ollama-runtime").resolve())
    by_pid = {int(row["pid"]): row for row in rows}
    private_pids = {pid for pid, row in by_pid.items() if runtime in "\0".join(row["argv"])}
    # llama children do not always retain the runtime pathname in argv.
    changed = True
    while changed:
        changed = False
        for pid, row in by_pid.items():
            if row["ppid"] in private_pids and pid not in private_pids:
                private_pids.add(pid)
                changed = True
    private = [by_pid[pid] for pid in sorted(private_pids)]
    global_ollama = [row for row in rows if row["argv"][:2] == ["/usr/local/bin/ollama", "serve"]]
    return private, global_ollama


def terminate_private_lebron() -> dict[str, Any]:
    before_rows = proc_rows()
    private, global_ollama = private_lebron_processes(before_rows)
    outcome: dict[str, Any] = {
        "private_before": private,
        "global_ollama_protected": global_ollama,
        "signals": [],
    }
    # Never use a name-based kill. The only signal targets are the unique, tower-owned
    # runtime process and its direct descendants identified above.
    for row in reversed(private):
        try:
            os.kill(int(row["pid"]), signal.SIGTERM)
            outcome["signals"].append({"pid": row["pid"], "signal": "SIGTERM"})
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            outcome.setdefault("errors", []).append(f"SIGTERM {row['pid']}: {exc}")
    if private:
        time.sleep(5)
    remaining, _ = private_lebron_processes(proc_rows())
    for row in reversed(remaining):
        try:
            os.kill(int(row["pid"]), signal.SIGKILL)
            outcome["signals"].append({"pid": row["pid"], "signal": "SIGKILL"})
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            outcome.setdefault("errors", []).append(f"SIGKILL {row['pid']}: {exc}")
    time.sleep(1 if remaining else 0)
    outcome["private_after"] = private_lebron_processes(proc_rows())[0]
    outcome["ok"] = not outcome["private_after"]
    return outcome


def command_result(command: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        process = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                                 timeout=timeout, check=False)
        return {"command": command, "cwd": str(cwd), "returncode": process.returncode,
                "duration_s": round(time.monotonic() - started, 3),
                "stdout_tail": process.stdout[-12000:], "stderr_tail": process.stderr[-12000:]}
    except subprocess.TimeoutExpired as exc:
        return {"command": command, "cwd": str(cwd), "returncode": None,
                "duration_s": round(time.monotonic() - started, 3), "timed_out": True,
                "stdout_tail": (exc.stdout or "")[-12000:],
                "stderr_tail": (exc.stderr or "")[-12000:]}
    except OSError as exc:
        return {"command": command, "cwd": str(cwd), "returncode": None,
                "duration_s": round(time.monotonic() - started, 3),
                "error": f"{type(exc).__name__}: {exc}"}


def sheriff_hash() -> dict[str, Any]:
    code = ("import sys; sys.path.insert(0, '.'); from src.config import load_config; "
            "print(load_config().pipeline_version)")
    result = command_result([str(SHERIFF / "venv/bin/python"), "-c", code],
                            cwd=SHERIFF, timeout=900)
    result["pipeline_version"] = result.get("stdout_tail", "").strip().splitlines()[-1:] or None
    if isinstance(result["pipeline_version"], list):
        result["pipeline_version"] = result["pipeline_version"][0] if result["pipeline_version"] else None
    return result


def validate_external_gates() -> dict[str, Any]:
    result: dict[str, Any] = {"paths": {key: str(path) for key, path in EXTERNAL_GATES.items()}}
    docs: dict[str, dict[str, Any]] = {}
    for key, path in EXTERNAL_GATES.items():
        try:
            docs[key] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            result[key] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if len(docs) != len(EXTERNAL_GATES):
        result["ok"] = False
        return result
    parity = docs["lebron_parity"]
    film_count = parity.get("film_count")
    parity_ok = (film_count == EXPECTED_FILMS
                 and parity.get("pixel_identical_count") == film_count
                 and parity.get("lebron_mode_count") == film_count
                 and parity.get("summary_equal_count") == film_count
                 and not parity.get("failed_films"))
    probe = docs["lebron_probe"]
    metrics = (probe.get("kanit") or {}).get("model_olcum") or {}
    probe_ok = (probe.get("durum") == "OKUNDU"
                and metrics.get("backend") == "private-ollama"
                and isinstance((probe.get("kanit") or {}).get("paddle_release_vram_mb"), (int, float)))
    def has_script(document: dict[str, Any], marker: str) -> bool:
        return any(marker in str(row.get("text") or "") for row in document.get("satirlar") or [])
    cyrillic_ok = docs["nash_cyrillic"].get("durum") == "OKUNDU" and has_script(docs["nash_cyrillic"], "К")
    arabic_ok = docs["nash_arabic"].get("durum") == "OKUNDU" and any(
        any("ARABIC" in __import__("unicodedata").name(char, "") for char in str(row.get("text") or ""))
        for row in docs["nash_arabic"].get("satirlar") or [])
    result.update({
        "lebron_parity": {"ok": parity_ok, "film_count": film_count,
                           "pixel_identical_count": parity.get("pixel_identical_count"),
                           "failed_films": parity.get("failed_films")},
        "lebron_probe": {"ok": probe_ok, "durum": probe.get("durum"),
                          "backend": metrics.get("backend")},
        "nash_cyrillic": {"ok": cyrillic_ok, "durum": docs["nash_cyrillic"].get("durum")},
        "nash_arabic": {"ok": arabic_ok, "durum": docs["nash_arabic"].get("durum")},
    })
    result["ok"] = all(result[key]["ok"] for key in EXTERNAL_GATES)
    return result


def final_report() -> dict[str, Any]:
    command = [str(SHERIFF / "venv/bin/python"), str(REPORTER), "--db", str(DB),
               "--pipeline", COHORT, "--out-json", str(REPORT_JSON),
               "--out-md", str(REPORT_MD), "--lebron-parity",
               str(EXTERNAL_GATES["lebron_parity"]), "--lebron-probe",
               str(EXTERNAL_GATES["lebron_probe"]), "--nash-gate",
               str(EXTERNAL_GATES["nash_cyrillic"]), "--nash-gate",
               str(EXTERNAL_GATES["nash_arabic"])]
    result = command_result(command, cwd=PROJECT, timeout=1800)
    result["json_exists"] = REPORT_JSON.is_file()
    result["markdown_exists"] = REPORT_MD.is_file()
    return result


def full_tests() -> dict[str, dict[str, Any]]:
    suites = {"lebron": ALLSTAR / "lebron_james", "nash": ALLSTAR / "nash", "sheriff": SHERIFF}
    results = {}
    for name, root in suites.items():
        event("tests_started", suite=name)
        results[name] = command_result([str(root / "venv/bin/python"), "-m", "pytest"],
                                       cwd=root, timeout=7200)
        event("tests_finished", suite=name, returncode=results[name].get("returncode"),
              duration_s=results[name].get("duration_s"))
    return results


def complete(initial_ollama: dict[str, Any]) -> int:
    event("cohort_terminal")
    snapshot = cohort_snapshot()
    gates = validate_external_gates()
    report = final_report()
    hash_before = sheriff_hash()
    tests = full_tests()
    hash_after = sheriff_hash()
    cleanup = terminate_private_lebron()
    ollama_after = file_fingerprint(Path.home() / ".ollama")
    report_acceptance: dict[str, Any] = {}
    try:
        report_acceptance = json.loads(REPORT_JSON.read_text(encoding="utf-8")).get("acceptance") or {}
    except (OSError, ValueError) as exc:
        report_acceptance = {"read_error": f"{type(exc).__name__}: {exc}"}
    tests_ok = all(result.get("returncode") == 0 for result in tests.values())
    hash_ok = (hash_before.get("pipeline_version") == COHORT
               and hash_after.get("pipeline_version") == COHORT
               and hash_before.get("pipeline_version") == hash_after.get("pipeline_version"))
    passed = (snapshot["shape"]["ok"] and not snapshot["failed_or_blocked_tasks"]
              and gates.get("ok") and report.get("returncode") == 0
              and report.get("json_exists") and report.get("markdown_exists")
              and bool(report_acceptance.get("promotion_pass")) and tests_ok and hash_ok
              and cleanup.get("ok"))
    summary = {
        "schema": "mitas.gece-kabul-completion/v1", "completed_at": now(),
        "cohort": COHORT, "outcome": "PASSED" if passed else "GATE_FAILED",
        "automatic_retry_or_db_mutation": False, "cohort_snapshot": snapshot,
        "external_gates": gates, "report": report, "report_acceptance": report_acceptance,
        "production_hash_before_tests": hash_before,
        "production_hash_after_tests": hash_after,
        "production_hash_unchanged": hash_ok, "tests": tests,
        "private_lebron_cleanup": cleanup,
        "ollama_home_audit_before_monitor": initial_ollama,
        "ollama_home_audit_after": ollama_after,
        "ollama_home_changed_during_monitor": initial_ollama != ollama_after,
        "outputs": {"report_json": str(REPORT_JSON), "report_markdown": str(REPORT_MD),
                    "status_jsonl": str(STATUS_LOG), "completion_json": str(SUMMARY_PATH)},
    }
    write_json(SUMMARY_PATH, summary)
    event("completion_written", outcome=summary["outcome"], path=str(SUMMARY_PATH))
    return 0 if passed else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    parser.add_argument("--max-runtime-seconds", type=float, default=0.0,
                        help="0 = terminale kadar bekle")
    parser.add_argument("--no-start", action="store_true",
                        help="sadece izle; Sheriff başlatma")
    args = parser.parse_args()
    if args.poll_seconds < 5:
        parser.error("--poll-seconds en az 5 olmalı")
    if args.max_runtime_seconds < 0:
        parser.error("--max-runtime-seconds negatif olamaz")
    lock_handle = LOCK_PATH.open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"Başka bir gece kabul monitörü çalışıyor: {LOCK_PATH}", file=sys.stderr)
        return 2
    initial_ollama = file_fingerprint(Path.home() / ".ollama")
    started_at = time.monotonic()
    event("monitor_started", cohort=COHORT, db=str(DB), no_start=args.no_start,
          poll_seconds=args.poll_seconds, ollama_home_audit=initial_ollama)
    try:
        while True:
            try:
                snapshot = cohort_snapshot()
            except (sqlite3.Error, OSError) as exc:
                event("snapshot_error", error=f"{type(exc).__name__}: {exc}")
                time.sleep(args.poll_seconds)
                continue
            runners = sheriff_runners(proc_rows())
            event("status", snapshot=snapshot, sheriff_runners=runners)
            if snapshot["terminal"]:
                return complete(initial_ollama)
            started = start_runner_if_needed(runners, no_start=args.no_start)
            if started:
                event("runner_recovery_requested", runner=started)
            if args.max_runtime_seconds and time.monotonic() - started_at >= args.max_runtime_seconds:
                summary = {"schema": "mitas.gece-kabul-completion/v1", "completed_at": now(),
                           "cohort": COHORT, "outcome": "MONITOR_TIMEOUT",
                           "automatic_retry_or_db_mutation": False,
                           "cohort_snapshot": snapshot, "outputs": {"status_jsonl": str(STATUS_LOG)}}
                write_json(SUMMARY_PATH, summary)
                event("monitor_timeout", path=str(SUMMARY_PATH))
                return 4
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        event("monitor_interrupted")
        return 130
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
