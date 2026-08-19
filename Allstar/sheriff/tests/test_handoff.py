from __future__ import annotations

from pathlib import Path
import json

import pytest

from src.config import load_config
from src.contracts import asset_record, line_record, packet, write_packet
from src.handoff import HandoffError, HandoffPublisher


def make_reader(tmp_path: Path, role: str, producer: str, proof: str = "COMPLETE"):
    asset_path = tmp_path / f"{producer} proof image.png"
    asset_path.write_bytes(b"proof-" + producer.encode())
    asset = asset_record(asset_path, asset_id=f"{producer}-asset", width=100,
                         height=100, frame_sequence=1, source_time_s=0.0)
    line = line_record("AHMET", 0, [{"asset_id": asset["asset_id"],
                                     "bbox": [1, 2, 20, 30],
                                     "coordinate_space": "pixel_xyxy"}])
    doc = packet(film_id="film", section="giris", run_id="run-1", task_id=f"task-{producer}",
                 attempt_id=f"attempt-{producer}", producer={"id": producer}, inputs=[],
                 execution_status="SUCCEEDED", content_status="READ", proof_status=proof,
                 assets=[asset], lines=[line])
    packet_path = tmp_path / f"{producer}.json"
    write_packet(packet_path, doc)
    return {"task_id": f"task-{producer}", "run_id": "run-1", "film_id": "film",
            "section": "giris", "kind": "tower", "logical_role": role,
            "status": "SUCCEEDED", "result": {"producer": producer,
                                                "packet_path": str(packet_path)}}


def test_handoff_self_contained_atomik_ve_shaq_baslatmaz(tmp_path, monkeypatch):
    monkeypatch.setenv("SHERIFF_SHAQ_INBOX", str(tmp_path / "shaq-in"))
    cfg = load_config()
    readers = [make_reader(tmp_path, "reader_master", "lebron"),
               make_reader(tmp_path, "reader_frame", "nash")]
    readers.append({"task_id": "task-jordan", "run_id": "run-1", "film_id": "film",
                    "section": "giris", "kind": "tower", "logical_role": "reader_video",
                    "status": "NO_CONTENT", "result": {}})
    task = {"task_id": "task-handoff", "run_id": "run-1", "film_id": "film",
            "section": "giris"}
    manifest = HandoffPublisher(cfg).publish(task, readers)
    root = tmp_path / "shaq-in/film/run-1/giris"
    assert (root / "_TAMAM").is_file()
    assert len(manifest["channels"]) == 3
    assert manifest["auto_started_shaq"] is False
    assert manifest["decision_policy"] == "UNASSIGNED"
    assert (root / "lebron-film-giris.okuma.json").is_file()
    assert (root / "nash-film-giris.okuma.json").is_file()
    assert (root / "jordan-film-giris.okuma.json").is_file()
    assert any((root / "assets/lebron").iterdir())
    assert HandoffPublisher(cfg).publish(task, readers) == manifest


def test_handoff_okuyucu_degistiyse_eski_bundle_reuse_etmez(tmp_path, monkeypatch):
    monkeypatch.setenv("SHERIFF_SHAQ_INBOX", str(tmp_path / "shaq-in"))
    cfg = load_config()
    readers = [make_reader(tmp_path, "reader_master", "lebron"),
               make_reader(tmp_path, "reader_frame", "nash")]
    readers.append({"task_id": "task-jordan", "run_id": "run-1", "film_id": "film",
                    "section": "giris", "kind": "tower", "logical_role": "reader_video",
                    "status": "NO_CONTENT", "result": {}})
    task = {"task_id": "task-handoff", "run_id": "run-1", "film_id": "film",
            "section": "giris"}
    first = HandoffPublisher(cfg).publish(task, readers)
    readers[2]["status"] = "FAILED"
    readers[2]["result"] = {"reason": "new-result"}
    second = HandoffPublisher(cfg).publish(task, readers)
    jordan = next(item for item in second["channels"] if item["logical_role"] == "reader_video")
    assert second["input_fingerprint"] != first["input_fingerprint"]
    assert jordan["task_status"] == "FAILED"


def test_handoff_manifest_kimligi_bozulduysa_bundle_yeniden_kurulur(tmp_path,
                                                                    monkeypatch):
    monkeypatch.setenv("SHERIFF_SHAQ_INBOX", str(tmp_path / "shaq-in"))
    cfg = load_config()
    readers = [make_reader(tmp_path, "reader_master", "lebron"),
               make_reader(tmp_path, "reader_frame", "nash"),
               {"task_id": "task-jordan", "run_id": "run-1", "film_id": "film",
                "section": "giris", "kind": "tower", "logical_role": "reader_video",
                "status": "NO_CONTENT", "result": {}}]
    task = {"task_id": "task-handoff", "run_id": "run-1", "film_id": "film",
            "section": "giris"}
    HandoffPublisher(cfg).publish(task, readers)
    path = tmp_path / "shaq-in/film/run-1/giris/bundle.manifest.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["film_id"] = "yanlis-film"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    rebuilt = HandoffPublisher(cfg).publish(task, readers)
    assert rebuilt["film_id"] == "film"


def test_handoff_manifest_alani_silinirse_bundle_yeniden_kurulur(tmp_path,
                                                                 monkeypatch):
    monkeypatch.setenv("SHERIFF_SHAQ_INBOX", str(tmp_path / "shaq-in"))
    cfg = load_config()
    readers = [make_reader(tmp_path, "reader_master", "lebron"),
               make_reader(tmp_path, "reader_frame", "nash"),
               {"task_id": "task-jordan", "run_id": "run-1", "film_id": "film",
                "section": "giris", "kind": "tower", "logical_role": "reader_video",
                "status": "NO_CONTENT", "result": {}}]
    task = {"task_id": "task-handoff", "run_id": "run-1", "film_id": "film",
            "section": "giris"}
    HandoffPublisher(cfg).publish(task, readers)
    path = tmp_path / "shaq-in/film/run-1/giris/bundle.manifest.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    del tampered["channels"][0]["packet_sha256"]
    path.write_text(json.dumps(tampered), encoding="utf-8")
    rebuilt = HandoffPublisher(cfg).publish(task, readers)
    assert all(channel.get("packet_sha256") for channel in rebuilt["channels"])


def test_handoff_yanlis_run_readerini_ilk_yayinda_reddeder(tmp_path, monkeypatch):
    monkeypatch.setenv("SHERIFF_SHAQ_INBOX", str(tmp_path / "shaq-in"))
    cfg = load_config()
    readers = [make_reader(tmp_path, "reader_master", "lebron"),
               make_reader(tmp_path, "reader_frame", "nash"),
               {"task_id": "task-jordan", "run_id": "run-1", "film_id": "film",
                "section": "giris", "kind": "tower", "logical_role": "reader_video",
                "status": "NO_CONTENT", "result": {}}]
    readers[0]["run_id"] = "baska-run"
    task = {"task_id": "task-handoff", "run_id": "run-1", "film_id": "film",
            "section": "giris"}
    with pytest.raises(HandoffError, match="run_id"):
        HandoffPublisher(cfg).publish(task, readers)
