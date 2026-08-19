from __future__ import annotations

import copy
import json
import struct
from pathlib import Path

import pytest

from src.config import SheriffConfig, load_config
from src.contracts import packet, write_packet
from src.engine import AlreadyRunning, Engine
from src.media import verify_frame_pool
from src.store import Store
from src.util import sha256_file


def config_for(tmp_path):
    raw = copy.deepcopy(load_config().raw)
    raw["paths"] = {"state": str(tmp_path / "state"), "runs": str(tmp_path / "runs"),
                    "logs": str(tmp_path / "logs"), "shaq_inbox": str(tmp_path / "shaq")}
    for role, tower in raw["towers"].items():
        tower["isolated_output"] = False
        root = tmp_path / "tower" / role
        tower["result"] = str(root / "{film_id}/{section}" /
                              ("reader.okuma.json" if role in {"reader_frame", "reader_master"}
                               else "legacy.json"))
        tower["marker"] = str(root / "{film_id}/{section}/_TAMAM")
    return SheriffConfig(tmp_path, raw)


def claimed_reader(cfg, store):
    run_id, _ = store.enqueue(film_id="film", title=None, source_path="/tmp/x.mp4",
                              source_sha256="c" * 64, pipeline_version=cfg.pipeline_version,
                              max_attempts=2, dag=cfg.raw["dag"])
    media = next(t for t in store.tasks(run_id) if t["kind"] == "media_prep")
    frame_dir = cfg.run_root / "film" / run_id / "media/frames/giris"
    frame_dir.mkdir(parents=True)
    frame = frame_dir / "frame_000001.png"
    frame.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
                      + struct.pack(">II", 1, 1))
    row = {"schema_version": "mitas.frame/v1", "section": "giris",
           "filename": frame.name, "sequence": 1, "source_time_s": 0.0,
           "section_time_s": 0.0, "width": 1, "height": 1,
           "sha256": sha256_file(frame)}
    (frame_dir / "frames.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    pool_sha256 = verify_frame_pool(frame_dir, expected_section="giris")
    store.set_status(media["task_id"], "SUCCEEDED", result={
        "sections": {"giris": {"pool_sha256": pool_sha256}}})
    Engine(cfg, store).reconcile()
    task = next(t for t in store.tasks(run_id) if t["section"] == "giris" and
                t.get("logical_role") == "reader_frame")
    store.set_input_hash(task["task_id"], pool_sha256)
    attempt_id = store.claim(task["task_id"], "dead-owner", "2000-01-01T00:00:00+00:00")
    return store.task(task["task_id"]), attempt_id


def test_crash_recovery_gecerli_v2_ciktisini_yeniden_calistirmadan_alir(tmp_path):
    cfg = config_for(tmp_path)
    store = Store(cfg.db_path)
    task, attempt_id = claimed_reader(cfg, store)
    tower = cfg.tower("reader_frame")
    values = {"film_id": "film", "section": "giris", "run_id": task["run_id"],
              "task_id": task["task_id"], "attempt_id": attempt_id, "input": ""}
    result = Path(tower["result"].format(**values))
    marker = Path(tower["marker"].format(**values))
    doc = packet(film_id="film", section="giris", run_id=task["run_id"],
                 task_id=task["task_id"], attempt_id=attempt_id,
                 producer={"id": "nash"}, inputs=[], execution_status="SUCCEEDED",
                 content_status="NO_TEXT", proof_status="NONE")
    write_packet(result, doc)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("", encoding="utf-8")
    Engine(cfg, store)._recover_expired()
    assert store.task(task["task_id"])["status"] == "NO_CONTENT"
    assert store.running_attempt(task["task_id"]) is None


def test_crash_recovery_yanlis_run_kimligini_abandoned_yapip_retry_acar(tmp_path):
    cfg = config_for(tmp_path)
    store = Store(cfg.db_path)
    task, attempt_id = claimed_reader(cfg, store)
    tower = cfg.tower("reader_frame")
    values = {"film_id": "film", "section": "giris", "run_id": task["run_id"],
              "task_id": task["task_id"], "attempt_id": attempt_id, "input": ""}
    result = Path(tower["result"].format(**values))
    marker = Path(tower["marker"].format(**values))
    doc = packet(film_id="film", section="giris", run_id="wrong-run",
                 task_id=task["task_id"], attempt_id=attempt_id,
                 producer={"id": "nash"}, inputs=[], execution_status="SUCCEEDED",
                 content_status="NO_TEXT", proof_status="NONE")
    write_packet(result, doc)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("", encoding="utf-8")
    Engine(cfg, store)._recover_expired()
    assert store.task(task["task_id"])["status"] == "READY"
    with store.connect() as conn:
        row = conn.execute("SELECT status FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
    assert row["status"] == "ABANDONED"


def test_crash_recovery_girdi_degistiyse_tamam_paketini_kabul_etmez(tmp_path):
    cfg = config_for(tmp_path)
    store = Store(cfg.db_path)
    task, attempt_id = claimed_reader(cfg, store)
    tower = cfg.tower("reader_frame")
    values = {"film_id": "film", "section": "giris", "run_id": task["run_id"],
              "task_id": task["task_id"], "attempt_id": attempt_id, "input": ""}
    result = Path(tower["result"].format(**values))
    marker = Path(tower["marker"].format(**values))
    doc = packet(film_id="film", section="giris", run_id=task["run_id"],
                 task_id=task["task_id"], attempt_id=attempt_id,
                 producer={"id": "nash"}, inputs=[], execution_status="SUCCEEDED",
                 content_status="NO_TEXT", proof_status="NONE")
    write_packet(result, doc)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("", encoding="utf-8")
    frame = cfg.run_root / "film" / task["run_id"] / "media/frames/giris/frame_000001.png"
    frame.write_bytes(frame.read_bytes() + b"degisti")
    Engine(cfg, store)._recover_expired()
    assert store.task(task["task_id"])["status"] == "READY"


def test_tek_instance_kilidi(tmp_path):
    cfg = config_for(tmp_path)
    store = Store(cfg.db_path)
    first, second = Engine(cfg, store), Engine(cfg, store)
    first._acquire_instance_lock()
    try:
        with pytest.raises(AlreadyRunning):
            second._acquire_instance_lock()
    finally:
        first._release_instance_lock()
