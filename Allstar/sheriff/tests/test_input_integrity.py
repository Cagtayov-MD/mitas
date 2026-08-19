from __future__ import annotations

import copy
import json
import subprocess

import pytest

from src.config import SheriffConfig, load_config
from src.engine import Engine
from src.media import MediaError, MediaPreparer
from src.store import Store
from src.util import sha256_file


def _config(tmp_path):
    raw = copy.deepcopy(load_config().raw)
    raw["paths"] = {"state": str(tmp_path / "state"),
                    "runs": str(tmp_path / "runs"),
                    "logs": str(tmp_path / "logs"),
                    "shaq_inbox": str(tmp_path / "shaq-in")}
    return SheriffConfig(tmp_path, raw)


def test_frame_ve_manifest_birlikte_degisse_bile_upstream_hashi_korur(tmp_path):
    cfg = _config(tmp_path)
    source = tmp_path / "x.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=80x60:rate=4:duration=1", "-an", str(source)],
                   check=True, shell=False)
    media = MediaPreparer(cfg).prepare(source, tmp_path / "run")
    pool = tmp_path / "run/media/frames/giris"
    parent = {"kind": "media_prep", "result": media}
    task = {"logical_role": cfg.raw["dag"]["boundary_role"], "section": "giris"}
    engine = Engine(cfg, Store(cfg.db_path))
    engine._verified_tower_input_hash(task, pool, [parent])

    first, second = pool / "frame_000001.png", pool / "frame_000002.png"
    first.write_bytes(second.read_bytes())
    manifest = pool / "frames.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    rows[0]["sha256"] = sha256_file(first)
    manifest.write_text("\n".join(json.dumps(row) for row in rows) + "\n",
                        encoding="utf-8")

    with pytest.raises(MediaError, match="upstream"):
        engine._verified_tower_input_hash(task, pool, [parent])


def test_jordan_klibi_ve_manifest_birlikte_degisse_upstream_hashi_korur(tmp_path):
    cfg = _config(tmp_path)
    material = tmp_path / "materialized/giris"
    material.mkdir(parents=True)
    clip = material / "credits.mp4"
    clip.write_bytes(b"ilk-klip")
    original_hash = sha256_file(clip)
    manifest = material / "material.manifest.json"
    manifest.write_text(json.dumps({"clip_sha256": original_hash}), encoding="utf-8")
    parent = {"kind": "materialize", "result": {"clip_sha256": original_hash}}
    task = {"logical_role": cfg.raw["dag"]["boundary_video_reader_role"],
            "section": "giris"}
    engine = Engine(cfg, Store(cfg.db_path))
    engine._verified_tower_input_hash(task, clip, [parent])

    clip.write_bytes(b"degisen-klip")
    manifest.write_text(json.dumps({"clip_sha256": sha256_file(clip)}), encoding="utf-8")
    with pytest.raises(MediaError, match="upstream"):
        engine._verified_tower_input_hash(task, clip, [parent])
