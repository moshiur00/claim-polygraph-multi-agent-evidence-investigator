"""Regression tests for pre-fan-out shared research budgets."""

from uuid import uuid4

from claim_polygraph_ng.application.langgraph_research import (
    _apply_shared_candidate_budget,
)
from claim_polygraph_ng.domain import (
    ROLE_PERMISSIONS,
    ResearchAssignment,
    ResearchBudget,
    ResearchRole,
)
from claim_polygraph_ng.domain.research import MultiAgentWorkflowCheckpoint


def test_shared_page_and_model_budget_is_allocated_before_concurrent_fan_out() -> None:
    investigation_id = uuid4()
    component_id = uuid4()
    roles = (
        ResearchRole.PRIMARY_SOURCE,
        ResearchRole.GENERAL_EVIDENCE,
        ResearchRole.CHALLENGER,
        ResearchRole.ACADEMIC,
    )
    assignments = tuple(
        ResearchAssignment(
            investigation_id=investigation_id,
            parent_claim_id=component_id,
            component_id=component_id,
            claim_text="Sharks can smell a drop of blood from miles away.",
            role=role,
            round_number=1,
            requirement_ids=(uuid4(),),
            permissions=ROLE_PERMISSIONS[role],
            query_limit=2,
            candidate_limit_per_query=10,
        )
        for role in roles
    )
    checkpoint = MultiAgentWorkflowCheckpoint.model_construct(
        budget=ResearchBudget(
            maximum_pages_per_component=12,
            maximum_model_calls=12,
        ),
        results=(),
    )

    bounded = _apply_shared_candidate_budget(checkpoint, assignments)

    assert len(bounded) == 4
    assert [item.candidate_limit_per_query for item in bounded] == [3, 3, 3, 3]
    assert sum(item.candidate_limit_per_query for item in bounded) == 12
