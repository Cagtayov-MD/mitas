from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest


class _InlineExecutor:
    def __init__(self) -> None:
        self.submitted: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def submit(self, func: Any, *args: Any, **kwargs: Any) -> object:
        self.submitted.append((func, args, kwargs))
        return object()


@pytest.fixture
def asr_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from core.api import asr_server

    clips_root = tmp_path / "clips"
    legacy_root = tmp_path / "legacy_jobs"
    executor = _InlineExecutor()
    events: list[dict[str, Any]] = []

    monkeypatch.setattr(asr_server, "CLIPS_ROOT", clips_root)
    monkeypatch.setattr(asr_server, "INCOMING_ROOT", clips_root / "_incoming")
    monkeypatch.setattr(asr_server, "LEGACY_JOB_ROOT", legacy_root)
    monkeypatch.setattr(asr_server, "_executor", executor)
    monkeypatch.setattr(
        asr_server.system_events,
        "log_event",
        lambda kind, **payload: events.append({"kind": kind, **payload}),
    )
    with asr_server._jobs_lock:
        asr_server._jobs.clear()

    return TestClient(asr_server.app), asr_server, executor, events


def test_transcribe_upload_reuses_existing_clip_without_new_job(asr_api) -> None:
    client, asr_server, executor, events = asr_api
    payload = b"same media bytes"
    expected_hash = hashlib.sha256(payload).hexdigest()

    first = client.post("/api/asr/transcribe?filename=sample.wav", content=payload)
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["reused"] is False
    assert first_body["content_hash"] == expected_hash
    assert first_body["clip_id"] == "sample"
    assert first_body["status"] == "queued"
    assert len(executor.submitted) == 1

    duplicate = client.post("/api/asr/transcribe?filename=sample.wav", content=payload)
    assert duplicate.status_code == 200
    duplicate_body = duplicate.json()
    assert duplicate_body["reused"] is True
    assert duplicate_body["content_hash"] == expected_hash
    assert duplicate_body["clip_id"] == "sample"
    assert duplicate_body["job_id"] == first_body["job_id"]
    assert duplicate_body["status"] == "queued"
    assert duplicate_body["latest_asr_job_id"] == first_body["job_id"]
    assert duplicate_body["asr_status"] == "queued"
    assert duplicate_body["module_summary"]["asr"]["job_count"] == 1
    assert len(executor.submitted) == 1
    assert [event["kind"] for event in events].count("media_reused") == 1

    assert not asr_server.INCOMING_ROOT.exists() or not list(asr_server.INCOMING_ROOT.glob("*.bin"))
    assert len(list(asr_server.CLIPS_ROOT.glob("*/clip.json"))) == 1


def test_transcribe_upload_force_full_creates_new_job_under_same_clip(asr_api) -> None:
    client, asr_server, executor, _events = asr_api
    payload = b"same media bytes"

    first = client.post("/api/asr/transcribe?filename=sample.wav", content=payload)
    assert first.status_code == 200
    first_body = first.json()

    forced = client.post("/api/asr/transcribe?filename=sample.wav&force=full", content=payload)
    assert forced.status_code == 200
    forced_body = forced.json()
    assert forced_body["reused"] is False
    assert forced_body["reprocessed"] is True
    assert forced_body["clip_id"] == first_body["clip_id"]
    assert forced_body["previous_job_id"] == first_body["job_id"]
    assert forced_body["input_path"] == first_body["input_path"]
    assert forced_body["job_id"] != first_body["job_id"]
    assert len(executor.submitted) == 2

    clip = asr_server._load_clip_record(first_body["clip_id"])
    assert clip is not None
    asr_state = clip["modules"]["asr"]
    assert asr_state["latest_job_id"] == forced_body["job_id"]
    assert asr_state["jobs"] == [first_body["job_id"], forced_body["job_id"]]
