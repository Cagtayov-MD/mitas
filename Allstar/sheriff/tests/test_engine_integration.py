from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

from src.config import SheriffConfig, load_config
from src.engine import Engine
from src.store import Store
from src.util import sha256_file


FAKE_TOWER = r'''#!/usr/bin/env python3
import hashlib, json, os, shutil, sys
from pathlib import Path

role, source, film, section, output_root = sys.argv[1:]
out = Path(output_root) / film / section
out.mkdir(parents=True, exist_ok=True)

if role == "boundary":
    selected = out / "kareler"
    selected.mkdir(exist_ok=True)
    for p in sorted(Path(source).glob("*.png"))[:2]:
        shutil.copy2(p, selected / p.name)
    value = {"schema_version": "mitas.boundary/v1",
             "identity": {"run_id": os.environ["MITAS_SHERIFF_RUN_ID"],
                          "task_id": os.environ["MITAS_SHERIFF_TASK_ID"],
                          "attempt_id": os.environ["MITAS_SHERIFF_ATTEMPT_ID"]},
             "film_id": film, "bolum": section, "durum": "BULUNDU",
             "baslangic_kare": 1, "bitis_kare": 2,
             "baslangic_sn": 0.0, "bitis_sn": 0.5,
             "uretilen": [{"tip": "kare", "yol": "kareler"}], "kanit": {}}
    name = "boundary.json"
elif role in {"reader_master", "reader_frame"}:
    value = {"schema_version": "mitas.okuma/v2", "packet_id": "pkt-" + role,
             "created_at": "2026-01-01T00:00:00Z", "film": {"film_id": film},
             "section": section,
             "identity": {"run_id": os.environ["MITAS_SHERIFF_RUN_ID"],
                          "task_id": os.environ["MITAS_SHERIFF_TASK_ID"],
                          "attempt_id": os.environ["MITAS_SHERIFF_ATTEMPT_ID"]},
             "producer": {"id": {"reader_master": "lebron",
                                    "reader_frame": "nash"}[role]},
             "lineage": {"parent_tasks": [], "inputs": []},
             "status": {"execution": "SUCCEEDED", "content": "NO_TEXT", "proof": "NONE"},
             "assets": [], "lines": [], "rejected_lines": [], "unread_regions": [],
             "diagnostics": {}, "resource_usage": {}}
    name = role + ".okuma.json"
else:
    value = {"schema_version": "mitas.jordan/v1",
             "identity": {"run_id": os.environ["MITAS_SHERIFF_RUN_ID"],
                          "task_id": os.environ["MITAS_SHERIFF_TASK_ID"],
                          "attempt_id": os.environ["MITAS_SHERIFF_ATTEMPT_ID"]},
             "film_id": film, "bolum": section, "durum": "METIN_YOK",
             "bloklar": [], "ciftler": [], "kanit": {}, "motor_surumu": "fake",
             "uretim_zamani": "2026-01-01T00:00:00Z", "sure_sn": 0.1}
    name = "reader_video.json"
(out / name).write_text(json.dumps(value), encoding="utf-8")
(out / "_TAMAM").write_text("", encoding="utf-8")
'''


def test_fake_kulelerle_tam_dag_iki_bolumu_handoffa_tasir(tmp_path):
    script = tmp_path / "fake_tower.py"
    script.write_text(FAKE_TOWER, encoding="utf-8")
    script.chmod(0o755)
    source = tmp_path / "film.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=160x90:r=25:d=2", "-an", str(source)],
                   check=True, shell=False)

    raw = copy.deepcopy(load_config().raw)
    raw["paths"] = {"state": str(tmp_path / "state"), "runs": str(tmp_path / "runs"),
                    "logs": str(tmp_path / "logs"),
                    "shaq_inbox": str(tmp_path / "shaq-in")}
    raw["resources"]["safety_disk_gb"] = 0
    raw["resources"]["safety_ram_mb"] = 0
    raw["resources"]["safety_cpu_threads"] = 0
    outputs = {role: tmp_path / "tower-out" / role for role in raw["towers"]}
    names = {"boundary": "boundary.json", "reader_master": "reader_master.okuma.json",
             "reader_frame": "reader_frame.okuma.json", "reader_video": "reader_video.json"}
    for role, tower in raw["towers"].items():
        tower["isolated_output"] = False
        tower["executable"] = str(script)
        tower["command"] = [role, "{input}", "{film_id}", "{section}", str(outputs[role])]
        tower["result"] = str(outputs[role] / "{film_id}/{section}" / names[role])
        tower["marker"] = str(outputs[role] / "{film_id}/{section}/_TAMAM")
        tower.pop("legacy_result", None)
        tower["resource_profile"] = "cpu_media"
        tower["timeout_seconds"] = 30
    cfg = SheriffConfig(tmp_path, raw)
    store = Store(cfg.db_path)
    run_id, _ = store.enqueue(film_id="film", title="Film", source_path=str(source),
                              source_sha256=sha256_file(source),
                              pipeline_version=cfg.pipeline_version, max_attempts=2,
                              dag=cfg.raw["dag"])
    Engine(cfg, store).run()
    assert store.get_run(run_id)["status"] == "SUCCEEDED"
    for section in ("giris", "cikis"):
        root = tmp_path / f"shaq-in/film/{run_id}/{section}"
        assert (root / "_TAMAM").is_file()
        manifest = json.loads((root / "bundle.manifest.json").read_text(encoding="utf-8"))
        assert len(manifest["channels"]) == 3
        assert manifest["auto_started_shaq"] is False


def test_eski_pipeline_surumu_aktif_kodla_calistirilmaz(tmp_path):
    raw = copy.deepcopy(load_config().raw)
    raw["paths"] = {"state": str(tmp_path / "state"), "runs": str(tmp_path / "runs"),
                    "logs": str(tmp_path / "logs"), "shaq_inbox": str(tmp_path / "shaq-in")}
    raw["resources"]["safety_disk_gb"] = 0
    cfg = SheriffConfig(tmp_path, raw)
    store = Store(cfg.db_path)
    run_id, _ = store.enqueue(
        film_id="film", title=None, source_path=str(tmp_path / "yok.mp4"),
        source_sha256="f" * 64, pipeline_version="sheriff/eski@0000",
        max_attempts=2, dag=cfg.raw["dag"])
    Engine(cfg, store).run()
    media = next(task for task in store.tasks(run_id) if task["kind"] == "media_prep")
    assert media["status"] == "BLOCKED_CONTRACT"
    assert media["attempt_count"] == 0


def test_dag_rol_adlari_degistiginde_adapter_akisi_devam_eder(tmp_path):
    script = tmp_path / "fake_tower.py"
    script.write_text(FAKE_TOWER, encoding="utf-8")
    script.chmod(0o755)
    source = tmp_path / "film.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=80x60:r=2:d=1", "-an", str(source)],
                   check=True, shell=False)
    raw = copy.deepcopy(load_config().raw)
    raw["paths"] = {"state": str(tmp_path / "state"), "runs": str(tmp_path / "runs"),
                    "logs": str(tmp_path / "logs"), "shaq_inbox": str(tmp_path / "shaq-in")}
    raw["resources"].update({"safety_disk_gb": 0, "safety_ram_mb": 0,
                             "safety_cpu_threads": 0})
    aliases = {"boundary": "sinir_b", "reader_master": "master_b",
               "reader_frame": "ham_b", "reader_video": "video_b"}
    names = {"boundary": "boundary.json", "reader_master": "reader_master.okuma.json",
             "reader_frame": "reader_frame.okuma.json", "reader_video": "reader_video.json"}
    towers = {}
    for behavior, alias in aliases.items():
        tower = copy.deepcopy(raw["towers"][behavior])
        output = tmp_path / "tower-out" / alias
        tower.update({"isolated_output": False, "executable": str(script),
                      "command": [behavior, "{input}", "{film_id}", "{section}", str(output)],
                      "result": str(output / "{film_id}/{section}" / names[behavior]),
                      "marker": str(output / "{film_id}/{section}/_TAMAM"),
                      "resource_profile": "cpu_media", "timeout_seconds": 30})
        tower.pop("legacy_result", None)
        towers[alias] = tower
    raw["towers"] = towers
    raw["dag"] = {"boundary_role": aliases["boundary"],
                  "independent_reader_role": aliases["reader_frame"],
                  "boundary_frame_reader_role": aliases["reader_master"],
                  "boundary_video_reader_role": aliases["reader_video"],
                  "sections": ["giris", "cikis"]}
    cfg = SheriffConfig(tmp_path, raw)
    store = Store(cfg.db_path)
    run_id, _ = store.enqueue(film_id="film", title=None, source_path=str(source),
                              source_sha256=sha256_file(source),
                              pipeline_version=cfg.pipeline_version, max_attempts=2,
                              dag=cfg.raw["dag"])
    Engine(cfg, store).run()
    assert store.get_run(run_id)["status"] == "SUCCEEDED"


def test_enqueue_sonrasi_degisen_video_eski_hashle_islenmez(tmp_path):
    raw = copy.deepcopy(load_config().raw)
    raw["paths"] = {"state": str(tmp_path / "state"), "runs": str(tmp_path / "runs"),
                    "logs": str(tmp_path / "logs"), "shaq_inbox": str(tmp_path / "shaq-in")}
    raw["resources"].update({"safety_disk_gb": 0, "safety_ram_mb": 0,
                             "safety_cpu_threads": 0, "max_cpu_percent": 100})
    cfg = SheriffConfig(tmp_path, raw)
    source = tmp_path / "film.mp4"
    source.write_bytes(b"ilk")
    store = Store(cfg.db_path)
    run_id, _ = store.enqueue(film_id="film", title=None, source_path=str(source),
                              source_sha256=sha256_file(source),
                              pipeline_version=cfg.pipeline_version, max_attempts=2,
                              dag=cfg.raw["dag"])
    source.write_bytes(b"degisti")
    Engine(cfg, store).run()
    media = next(task for task in store.tasks(run_id) if task["kind"] == "media_prep")
    assert media["status"] == "BLOCKED_CONTRACT"
    assert media["attempt_count"] == 1
