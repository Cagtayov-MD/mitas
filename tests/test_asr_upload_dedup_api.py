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

    monkeypatch.setenv("MITAS_ACCESS_SECRET", "test-secret")
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

    client = TestClient(asr_server.app)
    login = client.post("/api/auth/login", json={"username": "mitas", "pwId": "test_61"})
    assert login.status_code == 200
    return client, asr_server, executor, events


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
    assert first_body["content_profile"] == "bulten_haber"
    assert first_body["diarize"] == "auto"
    assert first_body["word_alignment_mode"] == "whisperx"
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


def test_delete_asr_data_removes_module_and_next_upload_reprocesses(asr_api) -> None:
    client, asr_server, executor, events = asr_api
    payload = b"same media bytes"

    first = client.post("/api/asr/transcribe?filename=sample.wav", content=payload)
    assert first.status_code == 200
    first_body = first.json()
    asr_server._update_job(first_body["job_id"], status="done", completed_at=asr_server._now_iso())
    asr_server._update_clip_module_status(first_body["clip_id"], module="asr", status="done", job_id=first_body["job_id"])

    deleted = client.delete(f"/api/clips/{first_body['clip_id']}/modules/asr")
    assert deleted.status_code == 200
    deleted_body = deleted.json()
    assert deleted_body["module"] == "asr"
    assert deleted_body["deleted"] is True
    assert deleted_body["deleted_job_ids"] == [first_body["job_id"]]
    assert not (asr_server.CLIPS_ROOT / first_body["clip_id"] / "asr").exists()

    clip = asr_server._load_clip_record(first_body["clip_id"])
    assert clip is not None
    assert "asr" not in clip["modules"]

    duplicate = client.post("/api/asr/transcribe?filename=sample.wav", content=payload)
    assert duplicate.status_code == 200
    duplicate_body = duplicate.json()
    assert duplicate_body["reused"] is False
    assert duplicate_body["job_id"] != first_body["job_id"]
    assert duplicate_body["clip_id"] == first_body["clip_id"]
    assert len(executor.submitted) == 2
    assert [event["kind"] for event in events].count("generated_data_deleted") == 1


def test_reprocess_clip_asr_starts_job_from_preserved_source(asr_api) -> None:
    client, _asr_server, executor, _events = asr_api
    payload = b"source media"

    first = client.post("/api/asr/transcribe?filename=sample.wav", content=payload)
    assert first.status_code == 200
    first_body = first.json()

    response = client.post(f"/api/clips/{first_body['clip_id']}/modules/asr/reprocess")
    assert response.status_code == 200
    body = response.json()
    assert body["reused"] is False
    assert body["reprocessed"] is True
    assert body["clip_id"] == first_body["clip_id"]
    assert body["previous_job_id"] == first_body["job_id"]
    assert body["input_path"] == first_body["input_path"]
    assert len(executor.submitted) == 2


def test_process_clip_asr_range_starts_job_from_trimmed_source(asr_api, monkeypatch: pytest.MonkeyPatch) -> None:
    client, asr_server, executor, _events = asr_api
    payload = b"source media"

    first = client.post("/api/asr/transcribe?filename=sample.mp4", content=payload)
    assert first.status_code == 200
    first_body = first.json()

    def fake_trim(source_path: Path, output_path: Path, *, start_seconds: float, end_seconds: float) -> None:
        assert source_path == Path(first_body["input_path"])
        assert start_seconds == pytest.approx(12.5)
        assert end_seconds == pytest.approx(18.25)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"trimmed media")

    monkeypatch.setattr(asr_server, "_trim_media_range", fake_trim)

    response = client.post(
        f"/api/clips/{first_body['clip_id']}/modules/asr/range?start_seconds=12.5&end_seconds=18.25"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reused"] is False
    assert body["reprocessed"] is True
    assert body["clip_id"] == first_body["clip_id"]
    assert body["previous_job_id"] == first_body["job_id"]
    assert body["range_start_seconds"] == 12.5
    assert body["range_end_seconds"] == 18.25
    assert body["input_path"] != first_body["input_path"]
    assert body["input_path"].endswith(".mp4")
    assert Path(body["input_path"]).read_bytes() == b"trimmed media"
    assert len(executor.submitted) == 2


def test_process_clip_asr_range_accepts_zero_start(asr_api, monkeypatch: pytest.MonkeyPatch) -> None:
    client, asr_server, executor, _events = asr_api
    payload = b"source media"

    first = client.post("/api/asr/transcribe?filename=sample.mp4", content=payload)
    assert first.status_code == 200
    first_body = first.json()

    def fake_trim(source_path: Path, output_path: Path, *, start_seconds: float, end_seconds: float) -> None:
        assert source_path == Path(first_body["input_path"])
        assert start_seconds == pytest.approx(0.0)
        assert end_seconds == pytest.approx(8.0)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"trimmed media")

    monkeypatch.setattr(asr_server, "_trim_media_range", fake_trim)

    response = client.post(
        f"/api/clips/{first_body['clip_id']}/modules/asr/range?start_seconds=0&end_seconds=8"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["range_start_seconds"] == 0.0
    assert body["range_end_seconds"] == 8.0
    assert len(executor.submitted) == 2
