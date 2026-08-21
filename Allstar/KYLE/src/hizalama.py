from __future__ import annotations

from collections import defaultdict

from .eslesme import match_known
from .hafiza import SeriesMemory
from .modeller import AnnotatedObservation, Observation
from .roller import RoleSpec, detect_role


def annotate_sources(source_observations: dict[str, list[Observation]], memory: SeriesMemory,
                     roles: dict[str, RoleSpec], cfg: dict) -> list[AnnotatedObservation]:
    mcfg = cfg["matching"]
    role_threshold = float(mcfg["role_threshold"])
    known_threshold = float(mcfg["known_threshold"])
    known_margin = float(mcfg["known_margin"])
    result: list[AnnotatedObservation] = []

    default_role = "OYUNCULAR" if "OYUNCULAR" in memory.roles else None
    for source, observations in source_observations.items():
        current_role = default_role
        local: list[AnnotatedObservation] = []
        for obs in observations:
            role, _ = detect_role(obs.raw_text, roles, role_threshold)
            if role:
                current_role = role
                local.append(AnnotatedObservation(obs, role=role, is_role_heading=True))
                continue
            item = AnnotatedObservation(obs, role=current_role)
            km = match_known(obs.raw_text, memory, current_role, known_threshold, known_margin)
            if not km.person and current_role is not None:
                km = match_known(obs.raw_text, memory, None, known_threshold, known_margin)
            if km.person:
                item.known_person_id = km.person.person_id
                item.known_name = km.person.canonical_name
                item.known_role = km.person.role
                item.known_score = km.score
                if item.role is None or item.role not in memory.roles:
                    item.role = km.person.role
            local.append(item)

        for i, item in enumerate(local):
            if item.is_role_heading or item.known_person_id or item.role in memory.roles:
                continue
            prev_role = next((local[j].known_role or local[j].role for j in range(i - 1, -1, -1)
                              if (local[j].known_role or local[j].role) in memory.roles), None)
            next_role = next((local[j].known_role or local[j].role for j in range(i + 1, len(local))
                              if (local[j].known_role or local[j].role) in memory.roles), None)
            if prev_role and prev_role == next_role:
                item.role = prev_role
            else:
                item.review_reason = "ROL_BELIRSIZ"
        result.extend(local)
    return result


def summarize_known(items: list[AnnotatedObservation]) -> dict[str, dict[str, list[AnnotatedObservation]]]:
    by_role: dict[str, dict[str, list[AnnotatedObservation]]] = defaultdict(lambda: defaultdict(list))
    for item in items:
        if item.known_person_id and item.known_role:
            by_role[item.known_role][item.known_person_id].append(item)
    return by_role
