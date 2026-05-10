from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.schemas import CandidateRelation


def valid_relation() -> dict:
    return {
        "relation_id": "rel-1",
        "media_id": "media-1",
        "entity_a_type": "face_cluster",
        "entity_a_id": "face-cluster-1",
        "entity_b_type": "kj_name",
        "entity_b_id": "name-1",
        "relation_type": "face_matches_kj_name_candidate",
        "confidence": 0.82,
        "source_signals": ["screen_text", "face_track"],
        "evidence_ids": ["ev-1"],
        "status": "needs_review",
        "created_by_module": "relation_builder",
        "created_at": datetime.now(timezone.utc),
    }


def test_candidate_relation_valid() -> None:
    relation = CandidateRelation(**valid_relation())
    assert relation.relation_type == "face_matches_kj_name_candidate"


def test_candidate_relation_rejects_invalid_relation_type() -> None:
    data = valid_relation()
    data["relation_type"] = "identity"
    with pytest.raises(ValidationError):
        CandidateRelation(**data)


def test_candidate_relation_rejects_confidence_above_one() -> None:
    data = valid_relation()
    data["confidence"] = 1.2
    with pytest.raises(ValidationError):
        CandidateRelation(**data)


def test_candidate_relation_rejects_invalid_status() -> None:
    data = valid_relation()
    data["status"] = "done"
    with pytest.raises(ValidationError):
        CandidateRelation(**data)


def test_candidate_relation_rejects_high_confidence_without_evidence() -> None:
    data = valid_relation()
    data["evidence_ids"] = []
    with pytest.raises(ValidationError):
        CandidateRelation(**data)
