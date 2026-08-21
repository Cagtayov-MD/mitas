from __future__ import annotations

from dataclasses import dataclass

from .eslesme import representative
from .hafiza import SeriesMemory
from .modeller import AnnotatedObservation, UnknownCluster
from .roller import RoleSpec


@dataclass
class Decision:
    type: str
    severity: str
    role: str
    role_label: str
    new_name: str
    selected_observation_id: str
    support_count: int
    support_sources: list[str]
    previous_names: list[str]
    expected_count: int | None
    observed_count: int | None
    reason: str
    exact_variant_support: int

    def as_dict(self) -> dict:
        return {
            "type": self.type,
            "severity": self.severity,
            "role": self.role,
            "role_label": self.role_label,
            "new_name": self.new_name,
            "selected_observation_id": self.selected_observation_id,
            "support_count": self.support_count,
            "support_sources": self.support_sources,
            "previous_names": self.previous_names,
            "expected_count": self.expected_count,
            "observed_count": self.observed_count,
            "reason": self.reason,
            "exact_variant_support": self.exact_variant_support,
        }


def decide(memory: SeriesMemory, roles: dict[str, RoleSpec], annotated: list[AnnotatedObservation],
           clusters: list[UnknownCluster], min_sources: int) -> tuple[list[Decision], list[dict]]:
    known_observed: dict[str, set[str]] = {}
    known_sources: dict[str, set[str]] = {}
    for role_name, role_mem in memory.roles.items():
        known_observed[role_name] = {
            item.known_person_id for item in annotated
            if item.known_person_id and item.known_role == role_name
        }
        known_sources[role_name] = {
            item.observation.source for item in annotated
            if item.known_person_id and item.known_role == role_name
        }

    accepted_by_role: dict[str, list[tuple[UnknownCluster, str, str, dict]]] = {}
    review: list[dict] = []
    for cluster in clusters:
        raw, obs_id, meta = representative(cluster)
        if cluster.support_count < min_sources:
            review.append({
                "role": cluster.role,
                "candidate": raw,
                "reason": "TEK_KAYNAK_YETERSIZ",
                **meta,
            })
            continue
        accepted_by_role.setdefault(cluster.role, []).append((cluster, raw, obs_id, meta))

    decisions: list[Decision] = []
    for role_name, accepted in accepted_by_role.items():
        role_mem = memory.roles.get(role_name)
        role_spec = roles.get(role_name)
        if not role_mem or not role_spec:
            for _, raw, _, meta in accepted:
                review.append({"role": role_name, "candidate": raw,
                               "reason": "PROFILE_ROLU_YOK", **meta})
            continue

        prev_active = [p for p in role_mem.members if p.active]
        prev_names = [p.canonical_name for p in prev_active]
        observed_known_count = len(known_observed.get(role_name, set()))
        role_known_sources = known_sources.get(role_name, set())
        observed_count = observed_known_count + len(accepted)
        expected = role_mem.expected_count

        for cluster, raw, obs_id, meta in accepted:
            dtype = "NEW_MEMBER"
            reason = "Bu birimde profile eslesmeyen yeni kisi en az iki bagimsiz kaynakta desteklendi."

            # Oyuncu listesi doğal olarak büyüyüp küçülebilir. Her yeni oyuncuyu
            # COUNT_INCREASE diye ayrı alarm yapmak yerine NEW_MEMBER olarak tut;
            # PDF tek OYUNCULAR tablosunda MEVCUT/YENI gösterecek.
            if role_spec.mode == "roster":
                dtype = "NEW_MEMBER"
                reason = "Dogrulanmis oyuncu listesinde olmayan yeni kisi en az iki bagimsiz kaynakta desteklendi."
            elif role_spec.mode == "guest":
                dtype = "NEW_GUEST"
                reason = "Yeni konuk oyuncu en az iki bagimsiz kaynakta desteklendi."
            elif role_spec.mode == "episode":
                dtype = "NEW_EPISODE_MEMBER"
                reason = "Yeni bolum oyuncusu en az iki bagimsiz kaynakta desteklendi."
            elif expected == 1:
                # Tek kişilik sabit rolde iki ayrı durum vardır:
                # 1) Eski kişi hiç görülmüyor + yeni kişi 2+ kaynakta: gerçek değişim adayı.
                # 2) Eski kişi bazı kaynaklarda, yeni kişi başka kaynaklarda: bu çoğunluk
                #    oylamasıyla çözülemez; OCR/VLM halüsinasyonu veya rol hizalama hatası olabilir.
                if observed_known_count == 0 and len(accepted) == 1:
                    dtype = "ROLE_HOLDER_CHANGED"
                    reason = "Beklenen tek rol sahibi bu bolumde gorulmedi; yeni kisi en az iki bagimsiz kaynakta desteklendi."
                elif observed_known_count > 0:
                    cooccur_sources = sorted(role_known_sources.intersection(cluster.sources))
                    if len(cooccur_sources) < min_sources:
                        review.append({
                            "role": role_name,
                            "candidate": raw,
                            "reason": "KAYNAK_CELISKISI",
                            "known_names": prev_names,
                            "known_sources": sorted(role_known_sources),
                            "candidate_sources": sorted(cluster.sources),
                            "cooccur_sources": cooccur_sources,
                            **meta,
                        })
                        continue
                    dtype = "COUNT_INCREASE"
                    reason = (
                        f"Beklenen kisi sayisi 1; mevcut rol sahibi ve yeni kisi en az {min_sources} "
                        "aynı bagimsiz kaynakta birlikte goruldu."
                    )
                else:
                    dtype = "NEW_MEMBER"
            elif expected is not None and observed_count > expected:
                dtype = "COUNT_INCREASE"
                reason = f"Beklenen kisi sayisi {expected}, bu bolumde dogrulanan kisi sayisi {observed_count}. Yeni kisi desteklendi."

            decisions.append(Decision(
                type=dtype,
                severity=role_spec.severity,
                role=role_name,
                role_label=role_spec.label,
                new_name=raw,
                selected_observation_id=obs_id,
                support_count=int(meta["support_count"]),
                support_sources=list(meta["support_sources"]),
                previous_names=prev_names if dtype == "ROLE_HOLDER_CHANGED" else [],
                expected_count=expected,
                observed_count=observed_count,
                reason=reason,
                exact_variant_support=int(meta["exact_variant_support"]),
            ))

    return decisions, review
