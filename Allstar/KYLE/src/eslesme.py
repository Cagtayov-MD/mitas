from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .hafiza import Person, SeriesMemory
from .modeller import AnnotatedObservation, UnknownCluster
from .normalizasyon import diacritic_score, looks_like_name, normal, similarity


@dataclass(frozen=True)
class KnownMatch:
    person: Person | None
    score: float
    margin: float


def match_known(text: str, memory: SeriesMemory, role: str | None,
                threshold: float, margin_required: float) -> KnownMatch:
    candidates = []
    if role and role in memory.roles:
        candidates = [p for p in memory.roles[role].members if p.active]
    if not candidates:
        candidates = [p for p in memory.all_people() if p.active]
    scored = sorted(((similarity(text, p.canonical_name), p) for p in candidates),
                    key=lambda x: x[0], reverse=True)
    if not scored:
        return KnownMatch(None, 0.0, 0.0)
    best_score, best_person = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    margin = best_score - second
    if best_score >= threshold and (margin >= margin_required or best_score >= 0.96):
        return KnownMatch(best_person, best_score, margin)
    return KnownMatch(None, best_score, margin)


def cluster_unknown(items: list[AnnotatedObservation], threshold: float,
                    min_chars: int) -> list[UnknownCluster]:
    clusters: list[UnknownCluster] = []
    for item in items:
        if not item.role or item.is_role_heading:
            continue
        if not looks_like_name(item.observation.raw_text, min_chars=min_chars):
            item.review_reason = item.review_reason or "NAME_LIKE_DEGIL"
            continue
        best_idx, best_score = None, 0.0
        for idx, cluster in enumerate(clusters):
            if cluster.role != item.role:
                continue
            score = max((similarity(item.observation.raw_text, x.observation.raw_text)
                         for x in cluster.observations), default=0.0)
            if score > best_score:
                best_idx, best_score = idx, score
        if best_idx is not None and best_score >= threshold:
            clusters[best_idx].observations.append(item)
        else:
            clusters.append(UnknownCluster(role=item.role, observations=[item]))
    return clusters


def representative(cluster: UnknownCluster) -> tuple[str, str, dict]:
    """Yalniz mevcut bir raw observation sec. Yeni metin sentezleme."""
    by_norm: dict[str, list[AnnotatedObservation]] = defaultdict(list)
    for item in cluster.observations:
        by_norm[normal(item.observation.raw_text)].append(item)

    ranked = []
    for key, obs in by_norm.items():
        sources = {x.observation.source for x in obs}
        raw_choices = [x.observation.raw_text for x in obs]
        best_raw = max(raw_choices, key=lambda t: (diacritic_score(t), len(t)))
        ranked.append((len(sources), diacritic_score(best_raw), len(best_raw), best_raw, obs))
    ranked.sort(reverse=True)
    exact_support, _, _, raw, obs = ranked[0]

    if exact_support < 2:
        all_obs = cluster.observations
        def medoid_score(item: AnnotatedObservation) -> tuple[float, int, int]:
            scores = [similarity(item.observation.raw_text, other.observation.raw_text)
                      for other in all_obs if other is not item]
            avg = sum(scores) / len(scores) if scores else 0.0
            return avg, diacritic_score(item.observation.raw_text), len(item.observation.raw_text)
        chosen = max(all_obs, key=medoid_score)
        raw = chosen.observation.raw_text
        chosen_id = chosen.observation.observation_id
    else:
        candidates = [x for x in obs if x.observation.raw_text == raw]
        chosen_id = candidates[0].observation.observation_id if candidates else obs[0].observation.observation_id

    meta = {
        "support_sources": sorted(cluster.sources),
        "support_count": cluster.support_count,
        "exact_variant_support": exact_support,
        "observation_ids": [x.observation.observation_id for x in cluster.observations],
    }
    return raw, chosen_id, meta
