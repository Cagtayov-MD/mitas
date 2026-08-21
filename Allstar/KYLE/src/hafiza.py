from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class Person:
    person_id: str
    canonical_name: str
    role: str
    active: bool = True


@dataclass
class RoleMemory:
    canonical_role: str
    expected_count: int | None
    mode: str
    members: list[Person]


@dataclass
class SeriesMemory:
    series_id: str
    title: str
    roles: dict[str, RoleMemory]
    raw: dict
    path: Path

    def all_people(self) -> Iterable[Person]:
        for role in self.roles.values():
            yield from role.members


def load_profile(path: str | Path, expected_series_id: str | None = None) -> SeriesMemory:
    p = Path(path)
    if not p.exists():
        raise ProfileError(f"profile bulunamadi: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_version") != "kyle.series/v1":
        raise ProfileError("schema_version kyle.series/v1 olmali")
    series_id = str(data.get("series_id") or "").strip()
    if not series_id:
        raise ProfileError("series_id bos")
    if expected_series_id and series_id != expected_series_id:
        raise ProfileError(f"series_id uyusmuyor: {series_id} != {expected_series_id}")
    roles: dict[str, RoleMemory] = {}
    seen_ids: set[str] = set()
    for role_name, spec in (data.get("roles") or {}).items():
        members: list[Person] = []
        for idx, item in enumerate(spec.get("members") or []):
            name = str(item.get("canonical_name") or "").strip()
            if not name:
                raise ProfileError(f"{role_name}: canonical_name bos")
            pid = str(item.get("person_id") or f"{role_name}:{idx+1}")
            if pid in seen_ids:
                raise ProfileError(f"duplicate person_id: {pid}")
            seen_ids.add(pid)
            members.append(Person(pid, name, role_name, bool(item.get("active", True))))
        exp = spec.get("expected_count")
        if exp is not None:
            exp = int(exp)
            if exp < 0:
                raise ProfileError(f"{role_name}: expected_count negatif")
        roles[role_name] = RoleMemory(
            canonical_role=role_name,
            expected_count=exp,
            mode=str(spec.get("mode") or "stable"),
            members=members,
        )
    return SeriesMemory(series_id, str(data.get("title") or series_id), roles, data, p)


def write_profile_atomic(path: str | Path, data: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def create_profile(path: str | Path, series_id: str, title: str, seed: dict) -> Path:
    data = {
        "schema_version": "kyle.series/v1",
        "series_id": series_id,
        "title": title or series_id,
        "roles": seed.get("roles", seed),
        "history": [],
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp_validate = p.with_suffix(".validate.json")
    tmp_validate.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        load_profile(tmp_validate, series_id)
    finally:
        tmp_validate.unlink(missing_ok=True)
    write_profile_atomic(p, data)
    return p
