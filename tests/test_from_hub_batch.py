# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import from_hub_batch as fhb  # noqa: E402


def _hub(root: Path, name: str, run_id: str = "parent-1") -> Path:
    p = root / name
    p.mkdir(parents=True)
    (p / "clip.json").write_text("{}", encoding="utf-8")
    (p / "_DURUM.json").write_text("{}", encoding="utf-8")
    (p / "run_manifest.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
    return p


def test_batch_child_env_zorunlu_ve_parent_bagli(tmp_path):
    hub = _hub(tmp_path, "FILM 1990-0001-1-0000-00-1")
    run_root = tmp_path / "candidate"
    env = fhb.build_env(hub, run_root)
    assert env["MITAS_BATCH_MODE"] == "1"
    assert env["MITAS_RUN_ROOT"] == str(run_root)
    assert env["MITAS_FROM_HUB_PATH"] == str(hub.resolve())
    assert env["MITAS_PARENT_RUN_ID"] == "parent-1"


def test_resume_yalniz_tam_teslimi_atlar(tmp_path):
    root = tmp_path / "run"
    hub = root / "Database" / "FILM"
    hub.mkdir(parents=True)
    (hub / "_DURUM.json").write_text("{}", encoding="utf-8")
    (hub / "clip.json").write_text("{}", encoding="utf-8")
    assert not fhb.candidate_complete(root, "FILM")
    (hub / "x.pdf").write_bytes(b"pdf")
    assert fhb.candidate_complete(root, "FILM")
