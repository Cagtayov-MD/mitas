# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sanitize_manifests as sm  # noqa: E402


def test_manifest_secretleri_atomik_maskelenir(tmp_path):
    p = tmp_path / "run_manifest.json"
    p.write_text(json.dumps({"config_snapshot": {
        "MITAS_GEMINI": "secret-value", "MITAS_NORMAL_FLAG": "1"}}), encoding="utf-8")
    assert sm.sanitize_file(p, apply=False) == 1
    assert "secret-value" in p.read_text(encoding="utf-8")
    assert sm.sanitize_file(p, apply=True) == 1
    obj = json.loads(p.read_text(encoding="utf-8"))
    assert obj["config_snapshot"]["MITAS_GEMINI"].startswith("<redacted:")
    assert obj["config_snapshot"]["MITAS_NORMAL_FLAG"] == "1"
    assert sm.sanitize_file(p, apply=True) == 0
