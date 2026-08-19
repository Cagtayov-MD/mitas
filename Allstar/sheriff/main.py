#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parent
sys.path.insert(0, str(KULE))

from src.config import ConfigError, load_config  # noqa: E402
from src.engine import AlreadyRunning, Engine  # noqa: E402
from src.resources import ResourceManager  # noqa: E402
from src.store import Store  # noqa: E402
from src.util import safe_component, sha256_file, slug_component  # noqa: E402

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".ts", ".m4v", ".webm"}


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sheriff", description="Allstar orkestra sefi")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="bagimliliklari ve kule kayitlarini denetle")
    enqueue = sub.add_parser("enqueue", help="video veya dizini kuyruga al")
    source = enqueue.add_mutually_exclusive_group(required=True)
    source.add_argument("--video")
    source.add_argument("--input")
    enqueue.add_argument("--film-id")
    enqueue.add_argument("--title")
    enqueue.add_argument("--force", action="store_true")
    sub.add_parser("run", help="mevcut kuyrugu bitirene kadar calis")
    internal = sub.add_parser("_daemon", help=argparse.SUPPRESS)
    internal.set_defaults(hidden=True)
    sub.add_parser("start", help="arka planda kuyruk bekleyicisini baslat")
    status = sub.add_parser("status", help="film ve gorev durumlarini goster")
    status.add_argument("--film-id")
    retry = sub.add_parser("retry", help="terminal hatali gorevi yeniden ac")
    retry.add_argument("--film-id", required=True)
    retry.add_argument("--task")
    retry.add_argument("--run-id", help="varsayilan: filmin en yeni run'i")
    stop = sub.add_parser("stop", help="Sheriff calismasini durdur")
    stop.add_argument("--force", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_config()
        store = Store(config.db_path)
        if args.command == "doctor":
            return doctor(config, store)
        if args.command == "enqueue":
            return enqueue(config, store, args)
        if args.command == "status":
            return status(store, args.film_id)
        if args.command == "retry":
            run_id = safe_component(args.run_id, "run_id") if args.run_id else None
            count = store.retry(safe_component(args.film_id, "film_id"), args.task, run_id)
            print(json.dumps({"retry_opened": count}, ensure_ascii=False))
            return 0 if count else 1
        if args.command == "stop":
            return stop(config, store, args.force)
        if args.command == "start":
            return start(config)
        if args.command in {"run", "_daemon"}:
            if args.command == "run":
                (config.state_dir / "shutdown.requested").unlink(missing_ok=True)
            engine = Engine(config, store)
            engine.run(forever=args.command == "_daemon")
            return 0
    except (ConfigError, ValueError, AlreadyRunning) as exc:
        print(f"[HATA] {exc}", file=sys.stderr)
        return 2
    return 2


def enqueue(config, store: Store, args) -> int:
    if args.video:
        if not args.film_id:
            raise ValueError("--video ile --film-id zorunlu")
        sources = [(Path(args.video), safe_component(args.film_id, "film_id"), args.title)]
    else:
        root = Path(args.input)
        if not root.is_dir():
            raise ValueError(f"input dizini yok: {root}")
        sources = [(path, slug_component(path.stem, "film_id"), path.stem)
                   for path in sorted(root.iterdir())
                   if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS]
        if not sources:
            raise ValueError(f"video bulunamadi: {root}")
        ids = [item[1] for item in sources]
        if len(ids) != len(set(ids)):
            raise ValueError("dosya adlari ayni film-id slug'ina donusuyor; tek tek enqueue edin")
    results = []
    for path, film_id, title in sources:
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"video yok: {path}")
        digest = sha256_file(path)
        run_id, created = store.enqueue(
            film_id=film_id, title=title, source_path=str(path), source_sha256=digest,
            pipeline_version=config.pipeline_version,
            max_attempts=int(config.raw["pipeline"]["max_attempts"]),
            dag=config.raw["dag"], force=args.force)
        results.append({"film_id": film_id, "run_id": run_id,
                        "created": created, "source_sha256": digest})
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def status(store: Store, film_id: str | None) -> int:
    runs = store.list_runs(safe_component(film_id, "film_id") if film_id else None)
    value = []
    for run in runs:
        value.append({**run, "tasks": [{key: task.get(key) for key in (
            "task_id", "kind", "logical_role", "section", "status", "attempt_count",
            "max_attempts", "updated_at")} for task in store.tasks(run["run_id"])]})
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def doctor(config, store: Store) -> int:
    checks = []
    for binary in (config.raw["media"]["ffmpeg"], config.raw["media"]["ffprobe"]):
        path = shutil.which(str(binary))
        checks.append({"check": str(binary), "ok": bool(path), "path": path})
    for role in config.raw["towers"]:
        tower = config.tower(role)
        path = Path(tower["executable"])
        executable_ok = path.is_file() and os.access(path, os.X_OK)
        help_rc = None
        help_error = None
        if executable_ok:
            try:
                probe = subprocess.run([str(path), "--help"], cwd=path.parent,
                                       capture_output=True, text=True, timeout=30,
                                       shell=False)
                help_rc = probe.returncode
                if help_rc:
                    help_error = probe.stderr[-500:]
            except (OSError, subprocess.SubprocessError) as exc:
                help_error = f"{type(exc).__name__}: {exc}"
        checks.append({"check": f"tower:{role}",
                       "ok": executable_ok and help_rc == 0,
                       "path": str(path), "producer_id": tower.get("producer_id"),
                       "cli_help_rc": help_rc, "error": help_error})
        checks.append(_venv_pin_check(path.parent, f"tower_venv:{role}"))
    checks.append(_venv_pin_check(KULE, "sheriff_venv"))
    snapshot = ResourceManager(config, store).snapshot()
    with store.connect() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
    checks.append({"check": "sqlite_wal", "ok": journal_mode.lower() == "wal"
                   and integrity == "ok", "path": str(store.path),
                   "journal_mode": journal_mode, "integrity": integrity})
    try:
        from jsonschema import Draft202012Validator
        schema_paths = sorted((KULE / "schemas").glob("*.schema.json"))
        for schema_path in schema_paths:
            Draft202012Validator.check_schema(json.loads(schema_path.read_text(encoding="utf-8")))
        checks.append({"check": "json_schemas", "ok": len(schema_paths) >= 5,
                       "count": len(schema_paths)})
    except Exception as exc:
        checks.append({"check": "json_schemas", "ok": False,
                       "error": f"{type(exc).__name__}: {exc}"})
    checks.append({"check": "gpu_telemetry", "ok": snapshot["vram_free_mb"] is not None,
                   "snapshot": snapshot})
    print(json.dumps({"ok": all(item["ok"] for item in checks), "checks": checks},
                     ensure_ascii=False, indent=2))
    return 0 if all(item["ok"] for item in checks) else 1


def _venv_pin_check(root: Path, label: str) -> dict:
    python = root / "venv/bin/python"
    requirements = root / "gereksinimler.txt"
    base = {"check": label, "python": str(python),
            "requirements": str(requirements)}
    if not python.is_file() or not requirements.is_file():
        return {**base, "ok": False, "error": "venv python veya pin dosyasi yok"}
    try:
        listed = subprocess.run(
            [str(python), "-m", "pip", "list", "--format=json"],
            cwd=root, capture_output=True, text=True, timeout=60, shell=False)
        dependency_check = subprocess.run(
            [str(python), "-m", "pip", "check"], cwd=root,
            capture_output=True, text=True, timeout=60, shell=False)
        if listed.returncode:
            return {**base, "ok": False,
                    "error": f"pip list rc={listed.returncode}: {listed.stderr[-500:]}"}
        installed = {
            re.sub(r"[-_.]+", "-", str(item["name"])).lower(): str(item["version"])
            for item in json.loads(listed.stdout)
        }
        mismatches = []
        for raw_line in requirements.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "==" not in line:
                mismatches.append({"requirement": line, "error": "exact pin degil"})
                continue
            name, expected = line.split("==", 1)
            key = re.sub(r"[-_.]+", "-", name.strip()).lower()
            actual = installed.get(key)
            if actual != expected.strip():
                mismatches.append({"package": name.strip(),
                                   "expected": expected.strip(), "installed": actual})
        ok = not mismatches and dependency_check.returncode == 0
        return {**base, "ok": ok, "pin_mismatches": mismatches,
                "pip_check_rc": dependency_check.returncode,
                "pip_check": (dependency_check.stdout or dependency_check.stderr).strip()[-500:]}
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        return {**base, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def start(config) -> int:
    pid_path = config.state_dir / "sheriff.pid"
    if pid_path.is_file():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            print(json.dumps({"started": False, "pid": pid, "reason": "already_running"}))
            return 0
        except (ValueError, ProcessLookupError, PermissionError):
            pid_path.unlink(missing_ok=True)
    config.log_root.mkdir(parents=True, exist_ok=True)
    (config.state_dir / "shutdown.requested").unlink(missing_ok=True)
    daemon_log = (config.log_root / "daemon.log").open("ab")
    process = subprocess.Popen([sys.executable, str(KULE / "main.py"), "_daemon"],
                               cwd=KULE, stdin=subprocess.DEVNULL,
                               stdout=daemon_log, stderr=subprocess.STDOUT,
                               start_new_session=True, close_fds=True)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
    print(json.dumps({"started": True, "pid": process.pid}, ensure_ascii=False))
    return 0


def stop(config, store: Store, force: bool) -> int:
    count = store.request_stop(force=force)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    (config.state_dir / "shutdown.requested").write_text(
        "force\n" if force else "graceful\n", encoding="utf-8")
    pid_path = config.state_dir / "sheriff.pid"
    daemon_seen = False
    if pid_path.is_file():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            daemon_seen = True  # daemon polls; it retains authority to kill child groups
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    print(json.dumps({"runs_marked": count, "force": force, "daemon_seen": daemon_seen},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
