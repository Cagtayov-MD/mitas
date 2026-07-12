# -*- coding: utf-8 -*-
"""Mevcut production hub'larından güvenli, yeniden-başlatılabilir full-gate candidate batch'i.

Her film `mitas_pipeline --from-hub --run-root` ile koşar. Batch modu zorunludur: temiz tracked
ağaç, global tek-writer kilidi ve manifest provenance kapıları bypass edilemez. Canonical hub'a
ve production export'a yazmaz; promotion ayrı ve insan-onaylıdır.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DB_ROOT = PROJECT_ROOT / "Database"
PIPELINE = HERE / "mitas_pipeline.py"

sys.path.insert(0, str(HERE))
import retry_planner  # noqa: E402
import run_manifest  # noqa: E402


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _last_json(text: str) -> dict | None:
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def candidate_complete(run_root: Path, hub_name: str) -> bool:
    hub = run_root / "Database" / hub_name
    return ((hub / "_DURUM.json").is_file() and (hub / "clip.json").is_file()
            and any(p.stat().st_size > 0 for p in hub.rglob("*.pdf")))


def select_hubs(db_root: Path, *, hub_names: list[str], trts: list[str]) -> list[Path]:
    if hub_names:
        hubs = [db_root / n for n in hub_names]
    elif trts:
        hubs = []
        for trt in trts:
            found = retry_planner.resolve_hub(trt, db_root)
            if found is None:
                raise retry_planner.RetryError(f"NOT_FOUND: {trt}")
            hubs.append(found)
    else:
        hubs = [p for p in sorted(db_root.iterdir())
                if p.is_dir() and not p.name.startswith("_") and (p / "_DURUM.json").is_file()]
    invalid = [str(p) for p in hubs if not ((p / "clip.json").is_file()
                                             and (p / "_DURUM.json").is_file())]
    if invalid:
        raise RuntimeError(f"geçersiz canonical hub: {invalid}")
    return hubs


def build_env(hub: Path, run_root: Path) -> dict:
    env = retry_planner.retry_env(dict(os.environ), str(run_root))
    env["MITAS_BATCH_MODE"] = "1"
    env["MITAS_FROM_HUB_PATH"] = str(hub.resolve())
    parent = _load_json(hub / "run_manifest.json").get("run_id")
    if parent:
        env["MITAS_PARENT_RUN_ID"] = str(parent)
    else:
        env.pop("MITAS_PARENT_RUN_ID", None)
    return env


def build_cmd(hub: Path, run_root: Path) -> list[str]:
    return [sys.executable, str(PIPELINE), "--from-hub", str(hub),
            "--run-root", str(run_root), "--no-asr", "--no-copy-source"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-root", required=True, help="candidate run kökü")
    ap.add_argument("--hub", action="append", default=[], help="tam hub adı; tekrarlanabilir")
    ap.add_argument("--trt", action="append", default=[], help="TRT-ID; tekrarlanabilir")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true", help="tam candidate hub'larını atla")
    a = ap.parse_args(argv)

    gs = run_manifest.git_state()
    if gs["git_dirty"]:
        print(f"RED: batch kirli tracked-ağaçla başlayamaz ({gs['dirty_patch_bytes']} byte)")
        return 3
    run_root = Path(a.run_root).resolve()
    if run_root == PROJECT_ROOT.resolve() or PROJECT_ROOT.resolve() not in run_root.parents:
        print(f"RED: run-root proje içindeki ayrı candidate dizini olmalı: {run_root}")
        return 3
    run_root.mkdir(parents=True, exist_ok=True)
    report = run_root / "_from_hub_batch.jsonl"
    hubs = select_hubs(DB_ROOT, hub_names=a.hub, trts=a.trt)
    if a.limit:
        hubs = hubs[:a.limit]

    failed = 0
    for index, hub in enumerate(hubs, 1):
        if a.resume and candidate_complete(run_root, hub.name):
            row = {"ts": datetime.now().isoformat(timespec="seconds"), "hub": hub.name,
                   "status": "SKIPPED_COMPLETE", "index": index, "total": len(hubs)}
        else:
            proc = subprocess.run(build_cmd(hub, run_root), cwd=str(PROJECT_ROOT),
                                  env=build_env(hub, run_root), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            result = _last_json(proc.stdout)
            ok = proc.returncode == 0 and result is not None and candidate_complete(run_root, hub.name)
            row = {"ts": datetime.now().isoformat(timespec="seconds"), "hub": hub.name,
                   "status": "OK" if ok else "FAILED", "rc": proc.returncode,
                   "result": result, "stderr_tail": (proc.stderr or "")[-1000:],
                   "index": index, "total": len(hubs)}
            if not ok:
                failed += 1
        with report.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[{index}/{len(hubs)}] {row['status']} {hub.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
