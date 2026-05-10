from __future__ import annotations

from datetime import datetime

from pydantic import model_validator

from core.schemas.common import Confidence, EventStatus, RelationType, StrictSchemaModel, StrictStr


class CandidateRelation(StrictSchemaModel):
    """Candidate cross-module relation; never a confirmed identity by itself."""

    relation_id: StrictStr
    media_id: StrictStr
    entity_a_type: StrictStr
    entity_a_id: StrictStr
    entity_b_type: StrictStr
    entity_b_id: StrictStr
    relation_type: RelationType
    confidence: Confidence
    source_signals: list[StrictStr]
    evidence_ids: list[StrictStr]
    status: EventStatus
    created_by_module: StrictStr
    created_at: datetime

    @model_validator(mode="after")
    def require_evidence_for_high_confidence(self) -> "CandidateRelation":
        if self.confidence >= 0.8 and not self.evidence_ids:
            raise ValueError("high-confidence candidate relations require evidence_ids")
        return self
