from __future__ import annotations

from dataclasses import dataclass
from .normalizasyon import similarity


@dataclass(frozen=True)
class RoleSpec:
    canonical: str
    label: str
    mode: str
    severity: str
    aliases: tuple[str, ...]


def load_roles(cfg: dict) -> dict[str, RoleSpec]:
    result: dict[str, RoleSpec] = {}
    for canonical, spec in (cfg.get("roles") or {}).items():
        aliases = tuple(dict.fromkeys([canonical, *(spec.get("aliases") or [])]))
        result[canonical] = RoleSpec(
            canonical=canonical,
            label=str(spec.get("label") or canonical),
            mode=str(spec.get("mode", "stable")),
            severity=str(spec.get("severity", "KIRMIZI")),
            aliases=aliases,
        )
    return result


def detect_role(text: str, roles: dict[str, RoleSpec], threshold: float) -> tuple[str | None, float]:
    best_role, best = None, 0.0
    for role, spec in roles.items():
        score = max((similarity(text, alias) for alias in spec.aliases), default=0.0)
        if score > best:
            best_role, best = role, score
    if best >= threshold:
        return best_role, best
    return None, best
