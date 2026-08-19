from __future__ import annotations

import fcntl
import json
import os
import socket
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .adapters import TowerAdapter, TowerContractError, TowerError
from .config import SheriffConfig
from .handoff import HandoffError, HandoffPublisher
from .logging import SheriffLogger
from .materialize import Materializer
from .media import MediaError, MediaPreparer, verify_frame_pool
from .resources import ResourceManager
from .runner import terminate_recorded_process
from .store import Store, TERMINAL
from .util import sha256_file, sha256_json


class AlreadyRunning(RuntimeError):
    pass


class Engine:
    def __init__(self, config: SheriffConfig, store: Store) -> None:
        self.config = config
        self.store = store
        self.resources = ResourceManager(config, store)
        self.media = MediaPreparer(config)
        self.adapter = TowerAdapter(config)
        self.materializer = Materializer(config)
        self.handoff = HandoffPublisher(config)
        self.log = SheriffLogger(config.log_root)
        self.owner = f"{socket.gethostname()}:{os.getpid()}"
        self._lock_handle = None
        self._admission_notices: dict[str, tuple[str, float]] = {}
        self._last_gpu_launch_exclusive = False

    def run(self, *, forever: bool = False) -> None:
        self._acquire_instance_lock()
        try:
            self._recover_expired()
            workers = max(4, min(16, (os.cpu_count() or 2) // 2))
            futures: dict[Future, tuple[str, str]] = {}
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sheriff") as pool:
                idle_cycles = 0
                while True:
                    self.store.release_orphan_reservations()
                    self._recover_expired()
                    self.store.promote_due_retries()
                    self.reconcile()
                    self._cancel_stopped_runs()
                    for future, (task_id, reservation_id) in list(futures.items()):
                        if not future.done():
                            continue
                        try:
                            future.result()
                        except Exception as exc:  # worker already records; protect scheduler
                            self.log.write("ERROR", "WORKER_ESCAPE", str(exc), task_id=task_id)
                        finally:
                            self.store.release(reservation_id)
                            futures.pop(future)

                    shutdown = self._shutdown_mode()
                    if shutdown and not futures:
                        break

                    launched = 0
                    active_ids = {task_id for task_id, _ in futures.values()}
                    active_tower_keys = {
                        self._tower_output_key(active)
                        for active_id in active_ids
                        if (active := self.store.task(active_id)) and active["kind"] == "tower"
                    }
                    ready_tasks = self.store.tasks(status="READY")
                    runtime_pipeline_version = (self.config.calculate_pipeline_version()
                                                if ready_tasks else self.config.pipeline_version)
                    # Only drain Sheriff's own shared GPU jobs. An exclusive
                    # task that cannot fit because of an external GPU process
                    # must not prevent a smaller admitted task from progressing.
                    aged_exclusive_ids = self._aged_exclusive_ids(ready_tasks)
                    shared_gpu_ids = {
                        task["task_id"] for task in ready_tasks
                        if self.config.resource_profile(self._profile(task)).get("gpu")
                        and not self._is_exclusive_gpu(task)
                    }
                    yield_to_shared = bool(
                        self._last_gpu_launch_exclusive and shared_gpu_ids)
                    if yield_to_shared:
                        aged_exclusive_ids = set()
                    drain_for_exclusive = self._must_drain_for_exclusive(
                        aged_exclusive_ids, self.store.active_reservations())
                    ready_tasks.sort(key=lambda item: (
                        self._ready_rank(item, yield_to_shared=yield_to_shared,
                                         shared_gpu_ids=shared_gpu_ids,
                                         aged_exclusive_ids=aged_exclusive_ids),
                        item["updated_at"]))
                    for task in ready_tasks:
                        if task["task_id"] in active_ids:
                            continue
                        tower_key = (self._tower_output_key(task)
                                     if task["kind"] == "tower" else None)
                        if tower_key and tower_key in active_tower_keys:
                            continue
                        run = self.store.get_run(task["run_id"])
                        if shutdown or not run or int(run.get("stop_requested") or 0):
                            continue
                        if (task["pipeline_version"] != self.config.pipeline_version
                                or runtime_pipeline_version != self.config.pipeline_version):
                            reason = (f"gorev pipeline surumu {task['pipeline_version']} "
                                      f"aktif surum {self.config.pipeline_version}, "
                                      f"diskteki surum {runtime_pipeline_version} ile uyusmuyor")
                            self.store.set_status(
                                task["task_id"], "BLOCKED_CONTRACT",
                                result={"reason": "PIPELINE_VERSION_MISMATCH",
                                        "detail": reason})
                            self.log.write("ERROR", "PIPELINE_VERSION_MISMATCH", reason,
                                           run_id=task["run_id"], task_id=task["task_id"])
                            continue
                        profile = self._profile(task)
                        profile_value = self.config.resource_profile(profile)
                        if (drain_for_exclusive and profile_value.get("gpu")
                                and not self._is_exclusive_gpu(task)):
                            # Drain current shared jobs; do not continuously refill
                            # the GPU while an older/larger exclusive job is ready.
                            continue
                        retry_reason = (task.get("result") or {}).get("retry_reason")
                        exclusive_retry = retry_reason == "OOM"
                        admission = self.resources.admit(profile,
                                                         exclusive_override=exclusive_retry)
                        if not admission.allowed:
                            self._record_admission_denial(task, admission.reason,
                                                          admission.snapshot)
                            continue
                        self._admission_notices.pop(task["task_id"], None)
                        lease = _future_iso(float(self.config.raw["pipeline"]["lease_seconds"]))
                        attempt_id = self.store.claim(task["task_id"], self.owner, lease)
                        if not attempt_id:
                            continue
                        try:
                            reservation = self.resources.acquire(
                                task["task_id"], profile,
                                exclusive_override=exclusive_retry)
                        except Exception as exc:
                            # A claim without a reservation must never be left
                            # RUNNING with no worker attached.
                            self.store.abandon(task["task_id"], attempt_id,
                                               f"resource reservation failed: {exc}")
                            self.log.write("ERROR", "RESERVATION_FAILED", str(exc),
                                           run_id=task["run_id"], task_id=task["task_id"])
                            continue
                        if profile_value.get("gpu"):
                            self._last_gpu_launch_exclusive = self._is_exclusive_gpu(task)
                        future = pool.submit(self._execute, task["task_id"], attempt_id)
                        futures[future] = (task["task_id"], reservation)
                        if tower_key:
                            active_tower_keys.add(tower_key)
                        launched += 1

                    pending = self._has_pending_work()
                    if launched or futures or pending:
                        idle_cycles = 0
                    else:
                        idle_cycles += 1
                    if not forever and not futures and not pending:
                        break
                    if forever and idle_cycles % 30 == 0:
                        self.log.write("INFO", "IDLE", "kuyruk bekleniyor")
                    time.sleep(float(self.config.raw["pipeline"]["poll_seconds"]))
        finally:
            pid_path = self.config.state_dir / "sheriff.pid"
            if pid_path.is_file():
                try:
                    if int(pid_path.read_text(encoding="utf-8").strip()) == os.getpid():
                        pid_path.unlink(missing_ok=True)
                except ValueError:
                    pass
            self._release_instance_lock()

    def reconcile(self) -> None:
        for run in self.store.list_runs():
            tasks = self.store.tasks(run["run_id"])
            by_kind = {(t["kind"], t["section"], t.get("logical_role")): t for t in tasks}
            media = next((t for t in tasks if t["kind"] == "media_prep"), None)
            if not media:
                continue
            for section in self.config.raw["dag"].get("sections", ["giris", "cikis"]):
                boundary = by_kind.get(("tower", section,
                                        self.config.raw["dag"]["boundary_role"]))
                independent = by_kind.get(("tower", section,
                    self.config.raw["dag"]["independent_reader_role"]))
                material = by_kind.get(("materialize", section, None))
                master = by_kind.get(("tower", section,
                    self.config.raw["dag"]["boundary_frame_reader_role"]))
                video = by_kind.get(("tower", section,
                    self.config.raw["dag"]["boundary_video_reader_role"]))
                handoff = by_kind.get(("handoff", section, None))
                if media["status"] == "SUCCEEDED":
                    self._ready(boundary)
                    self._ready(independent)
                elif media["status"] in TERMINAL and media["status"] != "SUCCEEDED":
                    self._upstream_terminal(boundary, media)
                    self._upstream_terminal(independent, media)
                if boundary:
                    if boundary["status"] == "SUCCEEDED":
                        self._ready(material)
                    elif boundary["status"] == "NO_CONTENT":
                        self._no_content(material, "boundary_no_content")
                        self._no_content(master, "boundary_no_content")
                        self._no_content(video, "boundary_no_content")
                    elif boundary["status"] in TERMINAL:
                        self._upstream_terminal(material, boundary)
                        self._upstream_terminal(master, boundary)
                        self._upstream_terminal(video, boundary)
                if material:
                    if material["status"] == "SUCCEEDED":
                        self._ready(master)
                        self._ready(video)
                    elif material["status"] == "NO_CONTENT":
                        self._no_content(master, "material_no_content")
                        self._no_content(video, "material_no_content")
                    elif material["status"] in TERMINAL:
                        self._upstream_terminal(master, material)
                        self._upstream_terminal(video, material)
                readers = [value for value in (master, independent, video) if value]
                if handoff and len(readers) == 3 and all(r["status"] in TERMINAL for r in readers):
                    self._ready(handoff)

    def _execute(self, task_id: str, attempt_id: str) -> None:
        task = self.store.task(task_id)
        if not task:
            return
        run = self.store.get_run(task["run_id"])
        if not run:
            return
        run_dir = self.config.run_root / task["film_id"] / task["run_id"]
        run_dir.mkdir(parents=True, exist_ok=True)

        def heartbeat() -> None:
            self.store.heartbeat(task_id, _future_iso(
                float(self.config.raw["pipeline"]["lease_seconds"])))

        def force_stop() -> bool:
            current = self.store.get_run(task["run_id"])
            return bool((current and int(current.get("stop_requested") or 0) >= 2)
                        or self._shutdown_mode() == "force")

        def process_started(pid: int, pgid: int, create_time: float | None) -> None:
            self.store.bind_process(attempt_id, pid=pid, pgid=pgid,
                                    host=socket.gethostname(), create_time=create_time)

        self.log.write("INFO", "TASK_STARTED", task["kind"], run_id=task["run_id"],
                       task_id=task_id, data={"attempt_id": attempt_id})
        try:
            if task["kind"] == "media_prep":
                source_path = Path(run["source_path"])
                try:
                    actual_hash = sha256_file(source_path) if source_path.is_file() else None
                except OSError:
                    actual_hash = None
                if actual_hash != run["source_sha256"]:
                    self.store.finish_attempt(
                        task_id, attempt_id, "BLOCKED_CONTRACT",
                        result={"reason": "SOURCE_CHANGED",
                                "expected_sha256": run["source_sha256"],
                                "actual_sha256": actual_hash,
                                "source_path": str(source_path)},
                        error_class="SOURCE_CHANGED",
                        error_message="enqueue sonrasi video yok veya icerigi degisti")
                    return
                result = self.media.prepare(source_path, run_dir,
                                            heartbeat=heartbeat, should_cancel=force_stop,
                                            on_process_start=process_started)
                try:
                    post_hash = sha256_file(source_path)
                except OSError:
                    post_hash = None
                if (post_hash != run["source_sha256"]
                        or result.get("source", {}).get("sha256") != run["source_sha256"]):
                    self.store.finish_attempt(
                        task_id, attempt_id, "BLOCKED_CONTRACT", result={
                            "reason": "SOURCE_CHANGED_DURING_MEDIA_PREP",
                            "expected_sha256": run["source_sha256"],
                            "actual_sha256": post_hash,
                            "media_manifest": result},
                        error_class="SOURCE_CHANGED",
                        error_message="video media-prep sirasinda degisti")
                    return
                self.store.finish_attempt(task_id, attempt_id, "SUCCEEDED", result=result,
                                          metrics={"kind": "media_prep",
                                                   **(result.get("resource_usage") or {})})
                self._register_paths(task_id, [
                    run_dir / "media/media.manifest.json",
                    run_dir / "media/frames/giris/frames.jsonl",
                    run_dir / "media/frames/cikis/frames.jsonl",
                    run_dir / "media/audio.wav"])
            elif task["kind"] == "materialize":
                source_path = Path(run["source_path"])
                try:
                    actual_hash = sha256_file(source_path)
                except OSError:
                    actual_hash = None
                if actual_hash != run["source_sha256"]:
                    self.store.finish_attempt(
                        task_id, attempt_id, "BLOCKED_CONTRACT", result={
                            "reason": "SOURCE_CHANGED_BEFORE_MATERIALIZE",
                            "expected_sha256": run["source_sha256"],
                            "actual_sha256": actual_hash},
                        error_class="SOURCE_CHANGED",
                        error_message="video materialize oncesi degisti")
                    return
                boundary = next(t for t in self.store.dependency_tasks(task_id)
                                if t.get("logical_role") == self.config.raw["dag"]["boundary_role"])
                material_input_hash = sha256_json({
                    "source": run["source_sha256"], "boundary": boundary.get("result")})
                self.store.set_input_hash(task_id, material_input_hash)
                result = self.materializer.build(task, boundary, run_dir,
                                                 source_path, heartbeat=heartbeat,
                                                 should_cancel=force_stop,
                                                 input_fingerprint=material_input_hash,
                                                 on_process_start=process_started)
                try:
                    post_hash = sha256_file(source_path)
                except OSError:
                    post_hash = None
                if post_hash != run["source_sha256"]:
                    self.store.finish_attempt(
                        task_id, attempt_id, "BLOCKED_CONTRACT", result={
                            "reason": "SOURCE_CHANGED_DURING_MATERIALIZE",
                            "expected_sha256": run["source_sha256"],
                            "actual_sha256": post_hash,
                            "material_manifest": result},
                        error_class="SOURCE_CHANGED",
                        error_message="video materialize sirasinda degisti")
                    return
                self.store.finish_attempt(task_id, attempt_id, "SUCCEEDED", result=result,
                                          metrics={"kind": "materialize",
                                                   **(result.get("resource_usage") or {})})
                self._register_paths(task_id, [
                    run_dir / "materialized" / task["section"] / "material.manifest.json",
                    run_dir / "materialized" / task["section"] / "frames/frames.jsonl",
                    run_dir / "materialized" / task["section"] / "credits.mp4"])
            elif task["kind"] == "handoff":
                readers = self.store.dependency_tasks(task_id)
                self.store.set_input_hash(task_id, sha256_json([
                    {"task_id": item["task_id"], "status": item["status"],
                     "result": item.get("result")} for item in readers]))
                result = self.handoff.publish(task, readers)
                self.store.finish_attempt(task_id, attempt_id, "SUCCEEDED", result=result,
                                          metrics={"kind": "handoff"})
                bundle = self.config.shaq_inbox / task["film_id"] / task["run_id"] / task["section"]
                self._register_paths(task_id, [bundle / "bundle.manifest.json"])
            elif task["kind"] == "tower":
                input_path = self._tower_input(task, run_dir)
                try:
                    parent_tasks = self.store.dependency_tasks(task_id)
                    tower_input_hash = self._verified_tower_input_hash(
                        task, input_path, parent_tasks)
                except (OSError, json.JSONDecodeError, AttributeError, TypeError,
                        ValueError, MediaError) as exc:
                    self.store.finish_attempt(
                        task_id, attempt_id, "BLOCKED_CONTRACT",
                        result={"reason": "TOWER_INPUT_INTEGRITY", "detail": str(exc)},
                        error_class="INPUT_INTEGRITY", error_message=str(exc))
                    return
                self.store.set_input_hash(task_id, tower_input_hash)
                status, result, process = self.adapter.execute(
                    task, attempt_id, input_path, run_dir,
                    heartbeat=heartbeat, should_cancel=force_stop,
                    on_process_start=process_started,
                    parent_tasks=[item["task_id"] for item in parent_tasks])
                try:
                    post_input_hash = self._verified_tower_input_hash(
                        task, input_path, parent_tasks)
                    if post_input_hash != tower_input_hash:
                        raise MediaError("kule girdisi calisma sirasinda degisti")
                except (OSError, json.JSONDecodeError, AttributeError, TypeError,
                        ValueError, MediaError) as exc:
                    self.store.finish_attempt(
                        task_id, attempt_id, "BLOCKED_CONTRACT",
                        result={"reason": "TOWER_INPUT_CHANGED_DURING_EXECUTION",
                                "detail": str(exc), "tower_result": result},
                        exit_code=process.exit_code,
                        stdout_path=process.stdout_path,
                        stderr_path=process.stderr_path,
                        metrics=process.metrics(), error_class="INPUT_INTEGRITY",
                        error_message=str(exc))
                    return
                if status == "FAILED":
                    error_class = self._tower_error_class(result, process)
                    self.store.retry_or_fail(
                        task_id, attempt_id, error_class=error_class,
                        error_message=f"kule terminal sonucu: {result.get('tower_status')}",
                        exit_code=process.exit_code, stdout_path=process.stdout_path,
                        stderr_path=process.stderr_path, metrics=process.metrics(),
                        result=result,
                        retry_delay_seconds=float(
                            self.config.raw["pipeline"].get("retry_backoff_seconds", 10)))
                else:
                    self.store.finish_attempt(
                        task_id, attempt_id, status, result=result,
                        exit_code=process.exit_code, stdout_path=process.stdout_path,
                        stderr_path=process.stderr_path, metrics=process.metrics())
                    self._register_paths(task_id, [Path(value) for key, value in result.items()
                                                   if key.endswith("_path") and
                                                   isinstance(value, str)])
            else:
                raise RuntimeError(f"bilinmeyen gorev: {task['kind']}")
        except TowerContractError as exc:
            process = exc.result
            self.store.finish_attempt(
                task_id, attempt_id, "BLOCKED_CONTRACT",
                exit_code=process.exit_code if process else None,
                stdout_path=process.stdout_path if process else None,
                stderr_path=process.stderr_path if process else None,
                metrics=process.metrics() if process else {},
                error_class=exc.error_class, error_message=str(exc))
        except TowerError as exc:
            process = exc.result
            if exc.error_class == "CANCELLED":
                self.store.finish_attempt(task_id, attempt_id, "CANCELLED",
                                          exit_code=process.exit_code if process else None,
                                          stdout_path=process.stdout_path if process else None,
                                          stderr_path=process.stderr_path if process else None,
                                          metrics=process.metrics() if process else {},
                                          error_class="CANCELLED", error_message=str(exc))
            else:
                error_class = "OOM" if self._looks_like_oom(str(exc), process) else exc.error_class
                self.store.retry_or_fail(
                    task_id, attempt_id, error_class=error_class, error_message=str(exc),
                    exit_code=process.exit_code if process else None,
                    stdout_path=process.stdout_path if process else None,
                    stderr_path=process.stderr_path if process else None,
                    metrics=process.metrics() if process else {},
                    retry_delay_seconds=float(
                        self.config.raw["pipeline"].get("retry_backoff_seconds", 10)))
        except HandoffError as exc:
            self.store.finish_attempt(task_id, attempt_id, "BLOCKED_CONTRACT",
                                      error_class="HANDOFF_CONTRACT", error_message=str(exc))
        except Exception as exc:  # media/materialize/runner failures are retryable
            self.store.retry_or_fail(task_id, attempt_id,
                                     error_class=type(exc).__name__, error_message=str(exc),
                                     retry_delay_seconds=float(
                                         self.config.raw["pipeline"].get(
                                             "retry_backoff_seconds", 10)))
        finally:
            final = self.store.task(task_id)
            self.log.write("INFO" if final and final["status"] not in {"FAILED", "BLOCKED_CONTRACT"}
                           else "ERROR", "TASK_FINISHED",
                           final["status"] if final else "missing", run_id=task["run_id"],
                           task_id=task_id)

    def _tower_input(self, task: dict[str, Any], run_dir: Path) -> Path:
        role = task["logical_role"]
        section = task["section"]
        dag = self.config.raw["dag"]
        if role in {dag["boundary_role"], dag["independent_reader_role"]}:
            return run_dir / "media" / "frames" / section
        if role == dag["boundary_frame_reader_role"]:
            return run_dir / "materialized" / section / "frames"
        if role == dag["boundary_video_reader_role"]:
            return run_dir / "materialized" / section / "credits.mp4"
        raise RuntimeError(f"rol icin girdi rotasi yok: {role}")

    def _verified_tower_input_hash(self, task: dict[str, Any], input_path: Path,
                                   parent_tasks: list[dict[str, Any]]) -> str:
        if len(parent_tasks) != 1:
            raise MediaError(f"kule tek upstream gorev bekliyor: {len(parent_tasks)}")
        parent = parent_tasks[0]
        parent_result = parent.get("result") or {}
        video_role = self.config.raw["dag"]["boundary_video_reader_role"]
        if task["logical_role"] == video_role:
            if not input_path.is_file():
                raise MediaError(f"Jordan klibi yok: {input_path}")
            input_hash = sha256_file(input_path)
            material_manifest = json.loads((
                input_path.parent / "material.manifest.json").read_text(
                    encoding="utf-8"))
            if (not isinstance(material_manifest, dict)
                    or input_hash != material_manifest.get("clip_sha256")
                    or input_hash != parent_result.get("clip_sha256")):
                raise MediaError(
                    "Jordan klibi upstream/material manifest hash'iyle uyusmuyor")
            return input_hash
        input_hash = verify_frame_pool(
            input_path, expected_section=task["section"],
            require_contiguous_sequence=(parent["kind"] == "media_prep"))
        if parent["kind"] == "media_prep":
            expected_hash = ((parent_result.get("sections") or {}).get(
                task["section"]) or {}).get("pool_sha256")
        else:
            expected_hash = parent_result.get("frames_pool_sha256")
        if input_hash != expected_hash:
            raise MediaError("frame havuzu upstream gorev hash'iyle uyusmuyor")
        return input_hash

    def _record_admission_denial(self, task: dict[str, Any], reason: str,
                                 snapshot: dict[str, Any]) -> None:
        now = time.monotonic()
        previous = self._admission_notices.get(task["task_id"])
        interval = float(self.config.raw["pipeline"].get("admission_log_seconds", 60))
        if previous and previous[0] == reason and now - previous[1] < interval:
            return
        self._admission_notices[task["task_id"]] = (reason, now)
        data = {"reason": reason, "snapshot": snapshot, "profile": self._profile(task)}
        self.log.write("WARNING", "RESOURCE_WAIT", reason, run_id=task["run_id"],
                       task_id=task["task_id"], data=data)
        self.store.event(task["run_id"], task["task_id"], "WARNING",
                         "RESOURCE_WAIT", reason, data)

    def _profile(self, task: dict[str, Any]) -> str:
        if task["kind"] == "tower":
            return str(self.config.tower(task["logical_role"])["resource_profile"])
        if task["kind"] == "handoff":
            return "cpu_light"
        return "cpu_media"

    def _is_exclusive_gpu(self, task: dict[str, Any]) -> bool:
        profile = self.config.resource_profile(self._profile(task))
        oom_retry = (task.get("result") or {}).get("retry_reason") == "OOM"
        return bool(profile.get("gpu") and (profile.get("exclusive_gpu") or oom_retry))

    def _aged_exclusive_ids(self, ready_tasks: list[dict[str, Any]]) -> set[str]:
        threshold = float(self.config.raw["pipeline"].get(
            "exclusive_starvation_seconds", 60))
        now = datetime.now(timezone.utc).astimezone()
        output = set()
        for task in ready_tasks:
            if not self._is_exclusive_gpu(task):
                continue
            try:
                waited = (now - datetime.fromisoformat(task["updated_at"])).total_seconds()
            except (KeyError, TypeError, ValueError):
                waited = threshold
            if waited >= threshold:
                output.add(task["task_id"])
        return output

    def _ready_rank(self, task: dict[str, Any], *, yield_to_shared: bool,
                    shared_gpu_ids: set[str],
                    aged_exclusive_ids: set[str]) -> int:
        task_id = task["task_id"]
        if yield_to_shared and task_id in shared_gpu_ids:
            return 0
        if task_id in aged_exclusive_ids:
            return 0
        profile = self.config.resource_profile(self._profile(task))
        if profile.get("gpu"):
            return 1
        if task["kind"] == "handoff":
            return 2
        return 3

    @staticmethod
    def _must_drain_for_exclusive(aged_exclusive_ids: set[str],
                                  reservations: list[dict[str, Any]]) -> bool:
        return (bool(aged_exclusive_ids)
                and any(int(item["vram_mb"]) > 0 for item in reservations))

    @staticmethod
    def _tower_output_key(task: dict[str, Any]) -> tuple[str, str, str]:
        return (str(task.get("logical_role")), str(task.get("film_id")),
                str(task.get("section")))

    def _register_paths(self, task_id: str, paths: list[Path]) -> None:
        for path in paths:
            if not path.is_file():
                continue
            kind = ("manifest" if path.name.endswith((".json", ".jsonl"))
                    else "media")
            self.store.artifact(task_id, str(path.resolve()), sha256_file(path), kind,
                                path.stat().st_size)

    def _ready(self, task: dict[str, Any] | None) -> None:
        if task and task["status"] == "WAITING":
            self.store.set_status(task["task_id"], "READY")

    def _no_content(self, task: dict[str, Any] | None, reason: str) -> None:
        if task and task["status"] == "WAITING":
            self.store.set_status(task["task_id"], "NO_CONTENT", result={"reason": reason})

    def _upstream_terminal(self, task: dict[str, Any] | None,
                           upstream: dict[str, Any]) -> None:
        if task and task["status"] == "WAITING":
            self.store.set_status(task["task_id"], "FAILED",
                                  result={"reason": "upstream_failed",
                                          "upstream_task_id": upstream["task_id"],
                                          "upstream_status": upstream["status"]})

    def _cancel_stopped_runs(self) -> None:
        for run in self.store.list_runs():
            requested = int(run.get("stop_requested") or 0)
            if not requested:
                continue
            for task in self.store.tasks(run["run_id"]):
                if task["status"] in {"WAITING", "READY", "RETRY_WAIT"}:
                    self.store.set_status(task["task_id"], "CANCELLED",
                                          result={"reason": "stop_requested"})

    def _has_pending_work(self) -> bool:
        return any(run["status"] in {"READY", "RUNNING"} and
                   not int(run.get("stop_requested") or 0) for run in self.store.list_runs())

    def _shutdown_mode(self) -> str | None:
        path = self.config.state_dir / "shutdown.requested"
        if not path.is_file():
            return None
        value = path.read_text(encoding="utf-8", errors="replace").strip().lower()
        return "force" if value == "force" else "graceful"

    def _recover_expired(self) -> None:
        for task in self.store.expired_running(_future_iso(0)):
            attempt = self.store.running_attempt(task["task_id"])
            if not attempt:
                self.store.set_status(task["task_id"], "READY",
                                      result={"retry_reason": "LEASE_EXPIRED"})
                continue
            if attempt.get("process_host") == socket.gethostname():
                terminated = terminate_recorded_process(
                    attempt.get("process_pid"), attempt.get("process_pgid"),
                    attempt.get("process_create_time"))
                if terminated:
                    self.store.event(task["run_id"], task["task_id"], "WARNING",
                                     "ORPHAN_TERMINATED",
                                     "bayat denemenin proses grubu sonlandirildi")
            recovered = None
            if task["kind"] == "tower":
                run_dir = self.config.run_root / task["film_id"] / task["run_id"]
                try:
                    parents = self.store.dependency_tasks(task["task_id"])
                    verified_input_hash = self._verified_tower_input_hash(
                        task, self._tower_input(task, run_dir), parents)
                    if verified_input_hash != task.get("input_hash"):
                        raise MediaError(
                            "recovery girdisi kayitli task input hash'iyle uyusmuyor")
                    recovered = self.adapter.inspect_existing(
                        task, attempt["attempt_id"], self._tower_input(task, run_dir), run_dir,
                        [item["task_id"] for item in parents])
                except Exception:
                    recovered = None
            if recovered and recovered[0] in {"SUCCEEDED", "NO_CONTENT"}:
                self.store.finish_attempt(task["task_id"], attempt["attempt_id"],
                                          recovered[0], result=recovered[1],
                                          metrics={"recovered_after_crash": True})
                self.store.release_task_reservations(task["task_id"])
                self.store.event(task["run_id"], task["task_id"], "INFO",
                                 "OUTPUT_RECOVERED", "tamamlanmis kule cikisi dogrulandi")
            else:
                self.store.abandon(task["task_id"], attempt["attempt_id"],
                                   "lease expired; mevcut cikti sozlesmeyi gecmedi")
                self.store.event(task["run_id"], task["task_id"], "WARNING",
                                 "LEASE_RECOVERED", "bayat gorev temiz retry icin acildi")

    def _acquire_instance_lock(self) -> None:
        path = self.config.state_dir / "sheriff.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_handle = path.open("a+")
        try:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AlreadyRunning("baska Sheriff instance calisiyor") from exc
        self._lock_handle.seek(0)
        self._lock_handle.truncate()
        self._lock_handle.write(f"{os.getpid()}\n")
        self._lock_handle.flush()

    def _release_instance_lock(self) -> None:
        if self._lock_handle:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            self._lock_handle.close()
            self._lock_handle = None

    @staticmethod
    def _tower_error_class(result: dict[str, Any], process) -> str:
        document = result.get("document") or {}
        legacy = (document.get("diagnostics") or {}).get("legacy_result") or {}
        classes = {str(document.get("sinif", "")).upper(),
                   str(legacy.get("sinif", "")).upper()}
        if classes & {"BELLEK", "OOM"} or Engine._looks_like_oom("", process):
            return "OOM"
        return "TOWER_REPORTED_FAILURE"

    @staticmethod
    def _looks_like_oom(message: str, process) -> bool:
        text = message.lower()
        try:
            if process and Path(process.stderr_path).is_file():
                text += Path(process.stderr_path).read_text(
                    encoding="utf-8", errors="replace")[-4000:].lower()
        except OSError:
            pass
        return "out of memory" in text or "cuda oom" in text or "bellek" in text


def _future_iso(seconds: float) -> str:
    return (datetime.now(timezone.utc).astimezone() + timedelta(seconds=seconds)).isoformat(
        timespec="milliseconds")
