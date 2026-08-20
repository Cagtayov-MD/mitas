from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def test_yayinlanan_semalar_gecerli_draft_2020_12():
    root = Path(__file__).resolve().parents[1] / "schemas"
    for path in sorted(root.glob("*.schema.json")):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_okuma_semasi_complete_kanitsiz_satiri_reddeder():
    root = Path(__file__).resolve().parents[1] / "schemas"
    schema = json.loads((root / "okuma-v2.schema.json").read_text(encoding="utf-8"))
    value = {
        "schema_version": "mitas.okuma/v2", "packet_id": "p", "created_at": "now",
        "film": {"film_id": "f"}, "section": "giris",
        "identity": {"run_id": "r", "task_id": "t", "attempt_id": "a"},
        "producer": {"id": "reader"}, "lineage": {"parent_tasks": [], "inputs": []},
        "status": {"execution": "SUCCEEDED", "content": "READ", "proof": "COMPLETE"},
        "assets": [], "lines": [{"line_id": "l", "order": 0, "raw_text": "AHMET",
                                    "normalized_text": "ahmet", "evidence": []}],
        "rejected_lines": [], "unread_regions": [], "diagnostics": {},
        "resource_usage": {},
    }
    assert list(Draft202012Validator(schema).iter_errors(value))
