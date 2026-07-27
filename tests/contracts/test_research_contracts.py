from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    ROLE_PERMISSIONS,
    EvidenceStance,
    ResearchAssignment,
    ResearchPermission,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchRole,
)


def test_research_assignment_round_trip_preserves_role_and_permissions() -> None:
    assignment = ResearchAssignment(
        investigation_id=uuid4(),
        parent_claim_id=uuid4(),
        component_id=uuid4(),
        claim_text="The submitted material claim.",
        role=ResearchRole.CHALLENGER,
        round_number=1,
        requirement_ids=(uuid4(),),
        permissions=ROLE_PERMISSIONS[ResearchRole.CHALLENGER],
        query_limit=2,
        candidate_limit_per_query=10,
    )

    restored = ResearchAssignment.model_validate_json(assignment.model_dump_json())

    assert restored == assignment
    assert restored.role is ResearchRole.CHALLENGER
    assert ResearchPermission.SEARCH in restored.permissions
    assert ResearchPermission.PLAN not in restored.permissions


def test_assignment_rejects_control_role_and_permission_escalation() -> None:
    common = {
        "investigation_id": uuid4(),
        "parent_claim_id": uuid4(),
        "component_id": uuid4(),
        "claim_text": "The submitted material claim.",
        "round_number": 1,
        "requirement_ids": (uuid4(),),
        "query_limit": 2,
        "candidate_limit_per_query": 10,
    }
    with pytest.raises(ValidationError, match="control roles"):
        ResearchAssignment(
            **common,
            role=ResearchRole.COORDINATOR,
            permissions=ROLE_PERMISSIONS[ResearchRole.COORDINATOR],
        )
    with pytest.raises(ValidationError, match="exactly match"):
        ResearchAssignment(
            **common,
            role=ResearchRole.GENERAL_EVIDENCE,
            permissions=frozenset(
                {
                    *ROLE_PERMISSIONS[ResearchRole.GENERAL_EVIDENCE],
                    ResearchPermission.PLAN,
                }
            ),
        )


def test_requirement_serializes_typed_stances() -> None:
    requirement = ResearchRequirement(
        component_id=uuid4(),
        kind=ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION,
        required_stances=(EvidenceStance.CONTRADICTS, EvidenceStance.QUALIFIES),
        rationale="A challenge path is mandatory for balanced research.",
    )

    payload = requirement.model_dump(mode="json")

    assert payload["kind"] == "contradiction_or_qualification"
    assert payload["required_stances"] == ["contradicts", "qualifies"]
