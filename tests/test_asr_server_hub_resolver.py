# -*- coding: utf-8 -*-
"""Flow worker'ın canonical hub seçimi ilk-eşleşme yapamaz."""
import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import retry_planner as rp  # noqa: E402


def _load_find_processed_hub(db_root: Path):
    src = (ROOT / "core" / "api" / "asr_server.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "_find_processed_hub")
    ns = {
        "Path": Path,
        "CLIPS_ROOT": db_root,
        "_TRT_RE": re.compile(r"\d{4}-\d{3,4}-\d-\d{3,4}-\d{2}-\d"),
        "_flow_clip_id": lambda p: Path(p).stem,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "asr_server.py", "exec"), ns)
    return ns["_find_processed_hub"]


def _hub(db: Path, name: str) -> Path:
    p = db / name
    p.mkdir()
    (p / "_DURUM.json").write_text("{}", encoding="utf-8")
    return p


def test_flow_resolver_ambiguous_hub_hard_fail(tmp_path):
    trt = "1990-0001-1-0000-00-1"
    f = _load_find_processed_hub(tmp_path)
    first = _hub(tmp_path, f"A {trt}")
    assert f(f"X_{trt}.mp4") == first
    _hub(tmp_path, f"B {trt}")
    with pytest.raises(rp.RetryError, match="AMBIGUOUS_HUB"):
        f(f"X_{trt}.mp4")
