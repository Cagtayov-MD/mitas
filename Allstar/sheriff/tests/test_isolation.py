from __future__ import annotations

import ast
from pathlib import Path

from src.config import ALLSTAR_ROOT, load_config


def test_sheriff_ve_aktif_kule_kodu_eski_pipeline_import_etmez():
    sheriff = Path(__file__).resolve().parents[1]
    config = load_config()
    roots = {sheriff}
    for role in config.raw["towers"]:
        roots.add(config.resolve(config.raw["towers"][role]["executable"]).parent)
    offenders = []
    for root in sorted(roots):
        paths = [root / "main.py", root / "sozlesme.py"]
        paths.extend(sorted((root / "src").rglob("*.py")))
        for path in paths:
            if not path.is_file():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = ([alias.name for alias in node.names]
                         if isinstance(node, ast.Import) else
                         [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                for name in names:
                    if name.split(".", 1)[0] in {"core", "scripts", "mitas_pipeline"}:
                        offenders.append(f"{path.relative_to(ALLSTAR_ROOT)}: {name}")
    assert not offenders, offenders


def test_configteki_tum_kule_executable_ve_surum_yollari_allstar_icinde():
    config = load_config()
    for tower in config.raw["towers"].values():
        paths = [config.resolve(tower["executable"])]
        paths.extend(config.resolve(item) for item in tower["version_paths"])
        for path in paths:
            path.relative_to(ALLSTAR_ROOT)


def test_jordan_model_recetesini_kuleye_birakir():
    config = load_config()
    tower = config.raw["towers"][config.raw["dag"]["boundary_video_reader_role"]]
    command = tower["command"]
    profile = config.resource_profile(tower["resource_profile"])

    assert tower["producer_id"] == "jordan"
    assert command == [
        "tek", "--video", "{input}", "--film-id", "{film_id}",
        "--bolum", "{section}",
    ]
    assert not ({"--backend", "--model", "--dtype", "--grup-kare",
                 "--bindirme-kare", "--ciftlemesiz", "--ciftle"} & set(command))
    assert profile["exclusive_gpu"] is True
    assert profile["vram_mb"] == 18432
    assert profile["ram_mb"] == 16384
    assert profile["family"] == "jordan25vl"
