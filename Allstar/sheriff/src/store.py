from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .util import now_iso

STATUSES = {
    "WAITING", "READY", "RUNNING", "SUCCEEDED", "NO_CONTENT", "FAILED",
    "RETRY_WAIT", "BLOCKED_CONTRACT", "CANCELLED",
}
TERMINAL = {"SUCCEEDED", "NO_CONTENT", "FAILED", "BLOCKED_CONTRACT", "CANCELLED"}


class StoreError(RuntimeError):
    pass


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS films (
    film_id TEXT PRIMARY KEY,
    title TEXT,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    film_id TEXT NOT NULL REFERENCES films(film_id),
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL,
    forced INTEGER NOT NULL DEFAULT 0,
    stop_requested INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_idem_idx ON runs(idempotency_key, created_at);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    film_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    logical_role TEXT,
    section TEXT,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    result_json TEXT,
    input_hash TEXT,
    pipeline_version TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 2,
    available_at TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    heartbeat_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(run_id, kind, section)
);
CREATE INDEX IF NOT EXISTS tasks_status_idx ON tasks(status, available_at, created_at);
CREATE TABLE IF NOT EXISTS dependencies (
    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    depends_on TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    PRIMARY KEY(task_id, depends_on)
);
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    attempt_no INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    exit_code INTEGER,
    stdout_path TEXT,
    stderr_path TEXT,
    metrics_json TEXT,
    error_class TEXT,
    error_message TEXT,
    process_pid INTEGER,
    process_pgid INTEGER,
    process_host TEXT,
    process_create_time REAL,
    UNIQUE(task_id, attempt_no)
);
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    kind TEXT NOT NULL,
    bytes INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE(task_id, path)
);
CREATE TABLE IF NOT EXISTS resource_reservations (
    reservation_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    profile TEXT NOT NULL,
    vram_mb INTEGER NOT NULL,
    ram_mb INTEGER NOT NULL,
    cpu_threads INTEGER NOT NULL,
    exclusive_gpu INTEGER NOT NULL,
    family TEXT,
    acquired_at TEXT NOT NULL,
    released_at TEXT
);
CREATE INDEX IF NOT EXISTS reservations_live_idx
    ON resource_reservations(released_at, acquired_at);
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    task_id TEXT,
    level TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_run_idx ON events(run_id, event_id);
"""


class Store:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(attempts)")}
        wanted = {
            "process_pid": "INTEGER", "process_pgid": "INTEGER",
            "process_host": "TEXT", "process_create_time": "REAL",
        }
        for name, kind in wanted.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE attempts ADD COLUMN {name} {kind}")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()

    def enqueue(self, *, film_id: str, title: str | None, source_path: str,
                source_sha256: str, pipeline_version: str, max_attempts: int,
                dag: dict[str, Any],
                force: bool = False) -> tuple[str, bool]:
        idem = f"{film_id}:{source_sha256}:{pipeline_version}"
        stamp = now_iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not force:
                existing = conn.execute(
                    "SELECT run_id FROM runs WHERE idempotency_key=? "
                    "ORDER BY created_at DESC, rowid DESC LIMIT 1", (idem,)).fetchone()
                if existing:
                    conn.commit()
                    return str(existing["run_id"]), False
            conn.execute(
                "INSERT INTO films(film_id,title,source_path,source_sha256,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(film_id) DO UPDATE SET "
                "title=excluded.title, source_path=excluded.source_path, "
                "source_sha256=excluded.source_sha256, updated_at=excluded.updated_at",
                (film_id, title, source_path, source_sha256, stamp, stamp))
            run_id = f"run-{uuid.uuid4().hex}"
            conn.execute(
                "INSERT INTO runs(run_id,film_id,source_path,source_sha256,pipeline_version,"
                "idempotency_key,status,forced,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id, film_id, source_path, source_sha256, pipeline_version, idem,
                 "READY", int(force), stamp, stamp))
            tasks: dict[str, str] = {}

            def add(kind: str, section: str | None = None, role: str | None = None,
                    status: str = "WAITING", payload: dict[str, Any] | None = None) -> str:
                task_id = f"task-{uuid.uuid4().hex}"
                key = f"{kind}:{role or '-'}:{section or '-'}"
                tasks[key] = task_id
                # SQLite uniqueness also protects against a partially repeated DAG
                # creation. Multiple tower roles share a section, so their persisted
                # kind includes the role; `_task_dict` exposes the public kind `tower`.
                stored_kind = f"tower.{role}" if kind == "tower" else kind
                conn.execute(
                    "INSERT INTO tasks(task_id,run_id,film_id,kind,logical_role,section,status,"
                    "payload_json,input_hash,pipeline_version,max_attempts,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (task_id, run_id, film_id, stored_kind, role, section, status,
                     json.dumps(payload or {}, ensure_ascii=False), source_sha256,
                     pipeline_version, max_attempts, stamp, stamp))
                return task_id

            roles = {
                "boundary": str(dag["boundary_role"]),
                "independent": str(dag["independent_reader_role"]),
                "frame": str(dag["boundary_frame_reader_role"]),
                "video": str(dag["boundary_video_reader_role"]),
            }
            if len(set(roles.values())) != len(roles):
                raise StoreError(f"DAG kule rolleri benzersiz olmali: {roles}")
            sections = [str(section) for section in dag["sections"]]
            if not sections or len(set(sections)) != len(sections):
                raise StoreError(f"DAG sections eksik/tekrarli: {sections!r}")

            media = add("media_prep", status="READY", payload={"source_path": source_path})
            for section in sections:
                boundary = add("tower", section, roles["boundary"])
                independent = add("tower", section, roles["independent"])
                materialize = add("materialize", section)
                master = add("tower", section, roles["frame"])
                video = add("tower", section, roles["video"])
                handoff = add("handoff", section)
                for child in (boundary, independent):
                    conn.execute("INSERT INTO dependencies VALUES(?,?)", (child, media))
                conn.execute("INSERT INTO dependencies VALUES(?,?)", (materialize, boundary))
                conn.execute("INSERT INTO dependencies VALUES(?,?)", (master, materialize))
                conn.execute("INSERT INTO dependencies VALUES(?,?)", (video, materialize))
                for parent in (master, independent, video):
                    conn.execute("INSERT INTO dependencies VALUES(?,?)", (handoff, parent))
            self._event_conn(conn, run_id, None, "INFO", "RUN_ENQUEUED",
                             "film kuyruga alindi", {"force": force, "source": source_path})
            conn.commit()
        return run_id, True

    def event(self, run_id: str | None, task_id: str | None, level: str,
              event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        with self.connect() as conn:
            self._event_conn(conn, run_id, task_id, level, event_type, message, data or {})

    @staticmethod
    def _event_conn(conn: sqlite3.Connection, run_id: str | None, task_id: str | None,
                    level: str, event_type: str, message: str,
                    data: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO events(run_id,task_id,level,event_type,message,data_json,created_at) "
            "VALUES(?,?,?,?,?,?,?)", (run_id, task_id, level, event_type, message,
                                      json.dumps(data, ensure_ascii=False), now_iso()))

    def list_runs(self, film_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            sql = "SELECT * FROM runs"
            args: tuple[Any, ...] = ()
            if film_id:
                sql += " WHERE film_id=?"
                args = (film_id,)
            sql += " ORDER BY created_at DESC, rowid DESC"
            return [dict(row) for row in conn.execute(sql, args)]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            return dict(row) if row else None

    def tasks(self, run_id: str | None = None, *, status: str | None = None,
              kind: str | None = None) -> list[dict[str, Any]]:
        where, args = [], []
        if run_id:
            where.append("run_id=?")
            args.append(run_id)
        if status:
            where.append("status=?")
            args.append(status)
        if kind:
            if kind == "tower":
                where.append("kind LIKE 'tower.%'")
            else:
                where.append("kind=?")
                args.append(kind)
        sql = "SELECT * FROM tasks" + (" WHERE " + " AND ".join(where) if where else "")
        sql += " ORDER BY created_at, section, kind"
        with self.connect() as conn:
            return [self._task_dict(row) for row in conn.execute(sql, args)]

    def task(self, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            return self._task_dict(row) if row else None

    @staticmethod
    def _task_dict(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["stored_kind"] = value["kind"]
        if value["kind"].startswith("tower."):
            value["kind"] = "tower"
        value["payload"] = json.loads(value.pop("payload_json") or "{}")
        value["result"] = json.loads(value.pop("result_json") or "null")
        return value

    def dependency_tasks(self, task_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT p.* FROM tasks p JOIN dependencies d ON p.task_id=d.depends_on "
                "WHERE d.task_id=? ORDER BY p.kind,p.logical_role", (task_id,))
            return [self._task_dict(row) for row in rows]

    def set_status(self, task_id: str, status: str, *, result: Any = None,
                   available_at: str | None = None) -> None:
        if status not in STATUSES:
            raise StoreError(f"gecersiz durum: {status}")
        with self.connect() as conn:
            row = conn.execute("SELECT run_id,status FROM tasks WHERE task_id=?",
                               (task_id,)).fetchone()
            if not row:
                raise StoreError(f"gorev yok: {task_id}")
            conn.execute(
                "UPDATE tasks SET status=?,result_json=?,available_at=?,lease_owner=NULL,"
                "lease_expires_at=NULL,heartbeat_at=NULL,updated_at=? WHERE task_id=?",
                (status, json.dumps(result, ensure_ascii=False) if result is not None else None,
                 available_at, now_iso(), task_id))
            self._event_conn(conn, row["run_id"], task_id, "INFO", "TASK_STATUS",
                             f"{row['status']} -> {status}", {"status": status})
            self._refresh_run_conn(conn, row["run_id"])

    def set_input_hash(self, task_id: str, input_hash: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE tasks SET input_hash=?,updated_at=? WHERE task_id=?",
                         (input_hash, now_iso(), task_id))

    def claim(self, task_id: str, owner: str, lease_expires_at: str) -> str | None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if not row or row["status"] != "READY":
                conn.rollback()
                return None
            previous = conn.execute(
                "SELECT COALESCE(MAX(attempt_no),0) AS n FROM attempts WHERE task_id=?",
                (task_id,)).fetchone()
            attempt_no = int(previous["n"]) + 1
            budget_count = int(row["attempt_count"]) + 1
            attempt_id = f"attempt-{uuid.uuid4().hex}"
            stamp = now_iso()
            conn.execute(
                "UPDATE tasks SET status='RUNNING',attempt_count=?,lease_owner=?,"
                "lease_expires_at=?,heartbeat_at=?,updated_at=? WHERE task_id=?",
                (budget_count, owner, lease_expires_at, stamp, stamp, task_id))
            conn.execute(
                "INSERT INTO attempts(attempt_id,task_id,attempt_no,status,started_at) "
                "VALUES(?,?,?,?,?)", (attempt_id, task_id, attempt_no, "RUNNING", stamp))
            self._event_conn(conn, row["run_id"], task_id, "INFO", "TASK_STARTED",
                             f"deneme {attempt_no} basladi", {"attempt_id": attempt_id})
            self._refresh_run_conn(conn, row["run_id"])
            conn.commit()
            return attempt_id

    def heartbeat(self, task_id: str, lease_expires_at: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE tasks SET heartbeat_at=?,lease_expires_at=?,updated_at=? "
                         "WHERE task_id=? AND status='RUNNING'",
                         (now_iso(), lease_expires_at, now_iso(), task_id))

    def bind_process(self, attempt_id: str, *, pid: int, pgid: int,
                     host: str, create_time: float | None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE attempts SET process_pid=?,process_pgid=?,process_host=?,"
                "process_create_time=? WHERE attempt_id=? AND status='RUNNING'",
                (pid, pgid, host, create_time, attempt_id))

    def finish_attempt(self, task_id: str, attempt_id: str, status: str, *,
                       result: Any = None, exit_code: int | None = None,
                       stdout_path: str | None = None, stderr_path: str | None = None,
                       metrics: dict[str, Any] | None = None,
                       error_class: str | None = None,
                       error_message: str | None = None) -> None:
        if status not in STATUSES:
            raise StoreError(f"gecersiz durum: {status}")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            task = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if not task:
                raise StoreError(f"gorev yok: {task_id}")
            attempt = conn.execute(
                "SELECT task_id,status FROM attempts WHERE attempt_id=?",
                (attempt_id,)).fetchone()
            if (not attempt or attempt["task_id"] != task_id
                    or attempt["status"] != "RUNNING"):
                raise StoreError(
                    f"aktif deneme gorevle uyusmuyor: {attempt_id} / {task_id}")
            stamp = now_iso()
            conn.execute(
                "UPDATE attempts SET status=?,ended_at=?,exit_code=?,stdout_path=?,stderr_path=?,"
                "metrics_json=?,error_class=?,error_message=? WHERE attempt_id=?",
                (status, stamp, exit_code, stdout_path, stderr_path,
                 json.dumps(metrics or {}, ensure_ascii=False), error_class, error_message,
                 attempt_id))
            conn.execute(
                "UPDATE tasks SET status=?,result_json=?,lease_owner=NULL,lease_expires_at=NULL,"
                "heartbeat_at=NULL,updated_at=? WHERE task_id=?",
                (status, json.dumps(result, ensure_ascii=False) if result is not None else None,
                 stamp, task_id))
            level = "ERROR" if status in {"FAILED", "BLOCKED_CONTRACT"} else "INFO"
            self._event_conn(conn, task["run_id"], task_id, level, "TASK_FINISHED",
                             f"gorev {status}", {"attempt_id": attempt_id,
                                                 "error_class": error_class})
            self._refresh_run_conn(conn, task["run_id"])
            conn.commit()

    def retry_or_fail(self, task_id: str, attempt_id: str, *, error_class: str,
                      error_message: str, exit_code: int | None = None,
                      stdout_path: str | None = None, stderr_path: str | None = None,
                      metrics: dict[str, Any] | None = None,
                      result: Any = None,
                      retry_delay_seconds: float = 10.0) -> str:
        task = self.task(task_id)
        if not task:
            raise StoreError(f"gorev yok: {task_id}")
        retry = int(task["attempt_count"]) < int(task["max_attempts"])
        status = "RETRY_WAIT" if retry else "FAILED"
        self.finish_attempt(task_id, attempt_id, status, exit_code=exit_code,
                            stdout_path=stdout_path, stderr_path=stderr_path,
                            metrics=metrics, result=result, error_class=error_class,
                            error_message=error_message)
        if retry:
            available = (datetime.now(timezone.utc).astimezone()
                         + timedelta(seconds=max(0.0, retry_delay_seconds))).isoformat(
                             timespec="milliseconds")
            self.set_status(task_id, "RETRY_WAIT",
                            result={"retry_reason": error_class,
                                    "last_result": result}, available_at=available)
        return status

    def promote_due_retries(self, at_iso: str | None = None) -> int:
        at_iso = at_iso or now_iso()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT task_id,run_id FROM tasks WHERE status='RETRY_WAIT' "
                "AND available_at IS NOT NULL AND available_at<=?", (at_iso,)).fetchall()
            for row in rows:
                conn.execute("UPDATE tasks SET status='READY',available_at=NULL,updated_at=? "
                             "WHERE task_id=?", (now_iso(), row["task_id"]))
                self._event_conn(conn, row["run_id"], row["task_id"], "INFO",
                                 "RETRY_READY", "retry bekleme suresi doldu", {})
            return len(rows)

    def expired_running(self, before_iso: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks WHERE status='RUNNING' "
                                "AND lease_expires_at IS NOT NULL AND lease_expires_at<?",
                                (before_iso,))
            return [self._task_dict(row) for row in rows]

    def running_attempt(self, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM attempts WHERE task_id=? AND status='RUNNING' "
                "ORDER BY attempt_no DESC LIMIT 1", (task_id,)).fetchone()
            return dict(row) if row else None

    def abandon(self, task_id: str, attempt_id: str, reason: str) -> None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            stamp = now_iso()
            task = conn.execute(
                "SELECT run_id FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if not task:
                raise StoreError(f"gorev yok: {task_id}")
            conn.execute("UPDATE attempts SET status='ABANDONED',ended_at=?,"
                         "error_class='LEASE_EXPIRED',error_message=? WHERE attempt_id=?",
                         (stamp, reason, attempt_id))
            conn.execute("UPDATE tasks SET status='READY',result_json=?,lease_owner=NULL,"
                         "lease_expires_at=NULL,heartbeat_at=NULL,updated_at=? WHERE task_id=?",
                         (json.dumps({"retry_reason": "LEASE_EXPIRED",
                                      "recovery": "previous_output_rejected"}), stamp, task_id))
            conn.execute("UPDATE resource_reservations SET released_at=? "
                         "WHERE task_id=? AND released_at IS NULL", (stamp, task_id))
            self._refresh_run_conn(conn, task["run_id"])
            conn.commit()

    def request_stop(self, *, force: bool = False) -> int:
        with self.connect() as conn:
            rows = conn.execute("SELECT run_id FROM runs WHERE status IN ('READY','RUNNING')").fetchall()
            for row in rows:
                conn.execute("UPDATE runs SET stop_requested=?,updated_at=? WHERE run_id=?",
                             (2 if force else 1, now_iso(), row["run_id"]))
            return len(rows)

    def retry(self, film_id: str, task_name: str | None = None,
              run_id: str | None = None) -> int:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if run_id:
                run = conn.execute("SELECT run_id FROM runs WHERE run_id=? AND film_id=?",
                                   (run_id, film_id)).fetchone()
            else:
                run = conn.execute("SELECT run_id FROM runs WHERE film_id=? "
                                   "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                                   (film_id,)).fetchone()
            if not run:
                conn.rollback()
                return 0
            target_run = str(run["run_id"])
            selectable = ("('SUCCEEDED','NO_CONTENT','FAILED','BLOCKED_CONTRACT','CANCELLED')"
                          if task_name else "('FAILED','BLOCKED_CONTRACT','CANCELLED')")
            sql = f"SELECT t.* FROM tasks t WHERE t.run_id=? AND t.status IN {selectable}"
            args: list[Any] = [target_run]
            if task_name:
                sql += " AND (t.kind=? OR t.logical_role=? OR t.task_id=?)"
                args.extend([task_name, task_name, task_name])
            rows = conn.execute(sql, args).fetchall()
            root_ids = {row["task_id"] for row in rows}
            descendant_ids: set[str] = set()
            frontier = set(root_ids)
            while frontier:
                marks = ",".join("?" for _ in frontier)
                children = conn.execute(
                    f"SELECT task_id FROM dependencies WHERE depends_on IN ({marks})",
                    tuple(frontier)).fetchall()
                found = {row["task_id"] for row in children} - root_ids - descendant_ids
                descendant_ids.update(found)
                frontier = found
            for row in rows:
                conn.execute("UPDATE tasks SET status='READY',attempt_count=0,result_json=NULL,"
                             "available_at=NULL,lease_owner=NULL,lease_expires_at=NULL,"
                             "heartbeat_at=NULL,updated_at=? WHERE task_id=?",
                             (now_iso(), row["task_id"]))
                conn.execute("UPDATE runs SET status='READY',stop_requested=0,updated_at=? "
                             "WHERE run_id=?", (now_iso(), row["run_id"]))
            for task_id in descendant_ids:
                conn.execute("UPDATE tasks SET status='WAITING',attempt_count=0,result_json=NULL,"
                             "available_at=NULL,updated_at=? WHERE task_id=?",
                             (now_iso(), task_id))
            conn.commit()
            return len(root_ids)

    def reserve(self, task_id: str, profile_name: str, profile: dict[str, Any]) -> str:
        reservation_id = f"reservation-{uuid.uuid4().hex}"
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO resource_reservations(reservation_id,task_id,profile,vram_mb,"
                "ram_mb,cpu_threads,exclusive_gpu,family,acquired_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (reservation_id, task_id, profile_name, int(profile.get("vram_mb", 0)),
                 int(profile.get("ram_mb", 0)), int(profile.get("cpu_threads", 0)),
                 int(bool(profile.get("exclusive_gpu"))), profile.get("family"), now_iso()))
        return reservation_id

    def release(self, reservation_id: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE resource_reservations SET released_at=? "
                         "WHERE reservation_id=? AND released_at IS NULL",
                         (now_iso(), reservation_id))

    def release_task_reservations(self, task_id: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE resource_reservations SET released_at=? "
                             "WHERE task_id=? AND released_at IS NULL", (now_iso(), task_id))

    def release_orphan_reservations(self) -> int:
        """Release reservations whose task no longer owns a running worker."""
        with self.connect() as conn:
            cursor = conn.execute(
                "UPDATE resource_reservations SET released_at=? "
                "WHERE released_at IS NULL AND task_id IN "
                "(SELECT task_id FROM tasks WHERE status!='RUNNING')",
                (now_iso(),))
            return int(cursor.rowcount)

    def active_reservations(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM resource_reservations WHERE released_at IS NULL")]

    def artifact(self, task_id: str, path: str, sha256: str, kind: str,
                 size: int | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO artifacts(artifact_id,task_id,path,sha256,kind,bytes,"
                "created_at) VALUES(?,?,?,?,?,?,?)",
                (f"artifact-{uuid.uuid4().hex}", task_id, path, sha256, kind, size, now_iso()))

    @staticmethod
    def _refresh_run_conn(conn: sqlite3.Connection, run_id: str) -> None:
        rows = conn.execute("SELECT status FROM tasks WHERE run_id=?", (run_id,)).fetchall()
        statuses = [row["status"] for row in rows]
        if statuses and all(value in TERMINAL for value in statuses):
            failed = any(value in {"FAILED", "BLOCKED_CONTRACT"} for value in statuses)
            cancelled = any(value == "CANCELLED" for value in statuses)
            run_status = "FAILED" if failed else "CANCELLED" if cancelled else "SUCCEEDED"
        elif any(value == "RUNNING" for value in statuses):
            run_status = "RUNNING"
        else:
            run_status = "READY"
        conn.execute("UPDATE runs SET status=?,updated_at=? WHERE run_id=?",
                     (run_status, now_iso(), run_id))
