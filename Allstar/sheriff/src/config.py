from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import string
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml


SHERIFF_ROOT = Path(__file__).resolve().parents[1]
ALLSTAR_ROOT = SHERIFF_ROOT.parent


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SheriffConfig:
    root: Path
    raw: dict[str, Any]

    @cached_property
    def pipeline_version(self) -> str:
        return self.calculate_pipeline_version()

    def calculate_pipeline_version(self) -> str:
        relevant = {key: self.raw[key] for key in ("media", "resources", "towers", "dag")}
        hasher = hashlib.sha256(json.dumps(
            relevant, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8"))
        sheriff_files = [SHERIFF_ROOT / "main.py", SHERIFF_ROOT / "sheriff",
                         SHERIFF_ROOT / "gereksinimler.txt",
                         SHERIFF_ROOT / "venv_kur.sh"]
        sheriff_files.extend(sorted((SHERIFF_ROOT / "src").rglob("*.py")))
        sheriff_files.extend(sorted((SHERIFF_ROOT / "schemas").glob("*.schema.json")))
        for file_path in sheriff_files:
            hasher.update(file_path.relative_to(SHERIFF_ROOT).as_posix().encode("utf-8"))
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
        for role in sorted(self.raw["towers"]):
            tower = self.raw["towers"][role]
            for raw_path in [tower["executable"], *(tower.get("version_paths") or [])]:
                path = self.resolve(raw_path)
                files = ([path] if path.is_file() else
                         sorted(item for item in path.rglob("*") if item.is_file()
                                and "__pycache__" not in item.parts
                                and item.suffix not in {".pyc", ".pyo"})) if path.is_dir() else []
                if not files:
                    hasher.update(f"{role}:MISSING:{raw_path}".encode("utf-8"))
                for file_path in files:
                    hasher.update(role.encode("utf-8"))
                    hasher.update(str(file_path.relative_to(path if path.is_dir()
                                                            else path.parent)).encode("utf-8"))
                    with file_path.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            hasher.update(chunk)
        digest = hasher.hexdigest()[:16]
        return f"{self.raw['pipeline']['version']}@{digest}"

    @property
    def state_dir(self) -> Path:
        override = os.environ.get("SHERIFF_STATE_DIR")
        return Path(override).resolve() if override else self.resolve(
            self.raw["paths"]["state"])

    @property
    def db_path(self) -> Path:
        return self.state_dir / "sheriff.sqlite3"

    @property
    def run_root(self) -> Path:
        override = os.environ.get("SHERIFF_RUN_DIR")
        return Path(override).resolve() if override else self.resolve(
            self.raw["paths"]["runs"])

    @property
    def log_root(self) -> Path:
        override = os.environ.get("SHERIFF_LOG_DIR")
        return Path(override).resolve() if override else self.resolve(
            self.raw["paths"]["logs"])

    @property
    def shaq_inbox(self) -> Path:
        override = os.environ.get("SHERIFF_SHAQ_INBOX")
        return Path(override).resolve() if override else self.resolve(
            self.raw["paths"]["shaq_inbox"])

    def resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path.resolve() if path.is_absolute() else (self.root / path).resolve()

    def tower(self, logical_role: str) -> dict[str, Any]:
        try:
            tower = copy.deepcopy(self.raw["towers"][logical_role])
        except KeyError as exc:
            raise ConfigError(f"kule rolu kayitli degil: {logical_role}") from exc
        tower["executable"] = str(self.resolve(tower["executable"]))
        for key in ("result", "marker", "legacy_result"):
            if tower.get(key):
                tower[key] = str(self.resolve(tower[key]))
        return tower

    def resource_profile(self, name: str) -> dict[str, Any]:
        try:
            return copy.deepcopy(self.raw["resources"]["profiles"][name])
        except KeyError as exc:
            raise ConfigError(f"kaynak profili kayitli degil: {name}") from exc


def load_config(path: Path | None = None) -> SheriffConfig:
    path = Path(os.environ.get("SHERIFF_CONFIG", path or SHERIFF_ROOT / "config.yaml"))
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"config bulunamadi: {path}") from exc
    for key in ("pipeline", "paths", "media", "resources", "towers", "dag"):
        if key not in raw:
            raise ConfigError(f"config alani eksik: {key}")
    config = SheriffConfig(path.parent.resolve(), raw)
    _validate(config)
    return config


def _validate(config: SheriffConfig) -> None:
    pipeline = config.raw["pipeline"]
    if (float(pipeline.get("lease_seconds", 0)) <= 10
            or float(pipeline.get("poll_seconds", 0)) <= 0
            or int(pipeline.get("max_attempts", 0)) < 1
            or float(pipeline.get("retry_backoff_seconds", -1)) < 0):
        raise ConfigError("pipeline sure/deneme ayarlari gecersiz")
    media = config.raw["media"]
    if (float(media.get("fps", 0)) <= 0
            or float(media.get("opening_seconds", 0)) <= 0
            or float(media.get("closing_seconds", 0)) <= 0
            or int(media.get("ffmpeg_timeout_seconds", 0)) <= 0):
        raise ConfigError("media sure/fps ayarlari gecersiz")
    resources = config.raw["resources"]
    if (int(resources.get("total_vram_mb", 0)) <= int(resources.get("safety_vram_mb", 0))
            or not 0 < float(resources.get("max_cpu_percent", 0)) <= 100):
        raise ConfigError("resources toplam/emniyet ayarlari gecersiz")
    dag = config.raw["dag"]
    dag_keys = ("boundary_role", "independent_reader_role",
                "boundary_frame_reader_role", "boundary_video_reader_role")
    try:
        roles = [str(dag[key]) for key in dag_keys]
    except KeyError as exc:
        raise ConfigError(f"DAG alani eksik: {exc.args[0]}") from exc
    if len(set(roles)) != len(roles):
        raise ConfigError(f"DAG kule rolleri benzersiz olmali: {roles!r}")
    if any(not re.fullmatch(r"[\w.-]+", role, re.UNICODE)
           or role in {".", ".."} for role in roles):
        raise ConfigError(f"DAG kule rolu dosya-bileseni olabilmeli: {roles!r}")
    missing = [role for role in roles if role not in config.raw["towers"]]
    if missing:
        raise ConfigError(f"DAG kayitsiz kule rolu kullaniyor: {missing!r}")
    sections = dag.get("sections")
    if (not isinstance(sections, list) or len(sections) != 2
            or set(sections) != {"giris", "cikis"}):
        raise ConfigError(f"DAG sections gecersiz: {sections!r}")
    producer_ids: list[str] = []
    for role in roles:
        tower = config.raw["towers"][role]
        for field in ("producer_id", "executable", "command", "resource_profile",
                      "timeout_seconds", "version_paths"):
            if field not in tower:
                raise ConfigError(f"kule {role}: {field} eksik")
        isolated_output = bool(tower.get("isolated_output"))
        if isolated_output:
            for field in ("result_relative", "marker_relative"):
                if not tower.get(field):
                    raise ConfigError(f"kule {role}: {field} eksik")
                relative = Path(str(tower[field]))
                if relative.is_absolute() or ".." in relative.parts:
                    raise ConfigError(f"kule {role}: {field} guvensiz")
        else:
            for field in ("result", "marker"):
                if not tower.get(field):
                    raise ConfigError(f"kule {role}: kule-owned {field} eksik")
        command = tower["command"]
        if not isinstance(command, list) or any(not isinstance(item, str) for item in command):
            raise ConfigError(f"kule {role}: command string listesi olmali")
        try:
            fields = {name for item in command for _, name, _, _ in
                      string.Formatter().parse(item) if name}
        except ValueError as exc:
            raise ConfigError(f"kule {role}: command format bozuk: {exc}") from exc
        allowed_fields = {"film_id", "section", "input", "run_id", "task_id",
                          "attempt_id", "output", "role"}
        required_fields = {"film_id", "section", "input"}
        if isolated_output:
            required_fields.add("output")
        if not required_fields <= fields or not fields <= allowed_fields:
            raise ConfigError(
                f"kule {role}: command placeholderlari gecersiz: {sorted(fields)}")
        if tower["resource_profile"] not in config.raw["resources"]["profiles"]:
            raise ConfigError(f"kule {role}: kaynak profili kayitsiz")
        if float(tower["timeout_seconds"]) <= 0:
            raise ConfigError(f"kule {role}: timeout_seconds pozitif olmali")
        executable = config.resolve(tower["executable"])
        try:
            executable.relative_to(ALLSTAR_ROOT)
        except ValueError as exc:
            raise ConfigError(f"kule {role}: executable Allstar disinda: {executable}") from exc
        if not isolated_output:
            expected_root = (executable.parent / "out").resolve()
            sample = {"film_id": "film", "section": "giris", "input": "input",
                      "run_id": "run", "task_id": "task", "attempt_id": "attempt",
                      "output": "output", "role": role}
            rendered_paths = []
            for field in ("result", "marker", "legacy_result"):
                if not tower.get(field):
                    continue
                try:
                    rendered = Path(str(config.resolve(tower[field])).format(**sample)).resolve()
                except (KeyError, ValueError) as exc:
                    raise ConfigError(f"kule {role}: {field} sablonu bozuk: {exc}") from exc
                if expected_root not in rendered.parents:
                    raise ConfigError(
                        f"kule {role}: {field} kulenin out/ dizini disinda: {rendered}")
                rendered_paths.append(rendered)
            if any(path.parent != rendered_paths[0].parent for path in rendered_paths[1:]):
                raise ConfigError(f"kule {role}: result/marker ayni bolum dizininde olmali")
        for raw_path in tower["version_paths"]:
            version_path = config.resolve(raw_path)
            try:
                version_path.relative_to(ALLSTAR_ROOT)
            except ValueError as exc:
                raise ConfigError(
                    f"kule {role}: version_path Allstar disinda: {version_path}") from exc
            if not version_path.exists():
                raise ConfigError(f"kule {role}: version_path yok: {version_path}")
        producer_ids.append(str(tower["producer_id"]))
        if (not re.fullmatch(r"[\w.-]+", str(tower["producer_id"]), re.UNICODE)
                or str(tower["producer_id"]) in {".", ".."}):
            raise ConfigError(f"kule {role}: producer_id guvensiz")
    if len(set(producer_ids)) != len(producer_ids):
        raise ConfigError(f"producer_id benzersiz olmali: {producer_ids!r}")
