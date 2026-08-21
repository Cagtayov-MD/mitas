from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Observation:
    observation_id: str
    source: str
    sequence: int
    raw_text: str


@dataclass
class AnnotatedObservation:
    observation: Observation
    role: str | None = None
    is_role_heading: bool = False
    known_person_id: str | None = None
    known_name: str | None = None
    known_role: str | None = None
    known_score: float = 0.0
    review_reason: str | None = None


@dataclass
class UnknownCluster:
    role: str
    observations: list[AnnotatedObservation] = field(default_factory=list)

    @property
    def sources(self) -> set[str]:
        return {x.observation.source for x in self.observations}

    @property
    def support_count(self) -> int:
        return len(self.sources)
