from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .hafiza import SeriesMemory, load_profile, write_profile_atomic


def build_patch(memory: SeriesMemory, episode_id: str, decisions: list[dict]) -> dict:
    additions = []
    for d in decisions:
        additions.append({
            "role": d["role"],
            "canonical_name": d["new_name"],
            "source_decision": d["type"],
            "support_count": d["support_count"],
            "support_sources": d["support_sources"],
            "expected_count": d.get("expected_count"),
            "observed_count": d.get("observed_count"),
        })
    return {
        "schema_version": "kyle.memory-patch/v1",
        "series_id": memory.series_id,
        "episode_id": episode_id,
        "additions": additions,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def apply_patch(profile_path: str | Path, patch: dict) -> None:
    memory = load_profile(profile_path, patch.get("series_id"))
    data = deepcopy(memory.raw)
    for add in patch.get("additions") or []:
        role = add["role"]
        role_spec = data.setdefault("roles", {}).setdefault(role, {"expected_count": None, "mode": "stable", "members": []})
        members = role_spec.setdefault("members", [])
        existing = {str(x.get("canonical_name", "")).casefold() for x in members}
        if add["canonical_name"].casefold() in existing:
            continue
        decision = add.get("source_decision")
        if decision == "ROLE_HOLDER_CHANGED":
            for member in members:
                if member.get("active", True):
                    member["active"] = False
                    member.setdefault("last_seen_before", patch.get("episode_id"))
        pid = f"{role}:{len(members)+1:04d}"
        members.append({
            "person_id": pid,
            "canonical_name": add["canonical_name"],
            "active": True,
            "first_seen": patch.get("episode_id"),
        })
        if decision == "COUNT_INCREASE" and add.get("observed_count") is not None:
            role_spec["expected_count"] = int(add["observed_count"])
    data.setdefault("history", []).append({
        "episode_id": patch.get("episode_id"),
        "applied_additions": len(patch.get("additions") or []),
        "applied_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    })
    write_profile_atomic(profile_path, data)
