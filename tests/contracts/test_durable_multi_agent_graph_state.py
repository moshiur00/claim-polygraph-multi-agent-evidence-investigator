"""Stage 8.3 durable multi-agent graph-state contracts."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    DurableAssignmentReference,
    DurableComponentReference,
    DurableEvidenceFamilyReference,
    DurableMultiAgentGraphState,
    DurableRequirementReference,
    DurableResultReference,
    DurableUnresolvedQuestion,
    ResearchBudget,
    ResearchConsumption,
    ResearchRequirementKind,
    ResearchRole,
    reconstruct_multi_agent_graph_state,
)


def _state() -> DurableMultiAgentGraphState:
    investigation_id = uuid4()
    parent_claim_id = uuid4()
    component_id = uuid4()
    requirement_id = uuid4()
    assignment_id = uuid4()
    source_id = uuid4()
    evidence_id = uuid4()
    return DurableMultiAgentGraphState(
        investigation_id=investigation_id,
        parent_claim_id=parent_claim_id,
        components=(
            DurableComponentReference(
                component_id=component_id,
                parent_claim_id=parent_claim_id,
                claim_summary="The programme reduced emissions in 2024.",
            ),
        ),
        requirements=(
            DurableRequirementReference(
                requirement_id=requirement_id,
                component_id=component_id,
                kind=ResearchRequirementKind.INDEPENDENT_CORROBORATION,
                rationale_summary="Independent corroboration is required.",
            ),
        ),
        assignments=(
            DurableAssignmentReference(
                assignment_id=assignment_id,
                component_id=component_id,
                role=ResearchRole.GENERAL_EVIDENCE,
                round_number=1,
                requirement_ids=(requirement_id,),
            ),
        ),
        results=(
            DurableResultReference(
                result_id=uuid4(),
                assignment_id=assignment_id,
                component_id=component_id,
                source_ids=(source_id,),
                evidence_ids=(evidence_id,),
                unresolved_requirement_ids=(requirement_id,),
            ),
        ),
        stored_source_ids=(source_id,),
        stored_evidence_ids=(evidence_id,),
        evidence_families=(
            DurableEvidenceFamilyReference(
                family_id=uuid4(),
                source_ids=(source_id,),
                evidence_ids=(evidence_id,),
                grouping_summary="One publisher family remains represented.",
            ),
        ),
        budget=ResearchBudget(maximum_model_calls=1, maximum_cost_usd=0.1),
        consumption=ResearchConsumption(
            completed_rounds=1,
            role_activations=1,
            search_calls=1,
            fetched_pages=1,
            model_calls=0,
            estimated_cost_usd=0,
        ),
        unresolved_questions=(
            DurableUnresolvedQuestion(
                component_id=component_id,
                requirement_ids=(requirement_id,),
                question_summary="Can a second independent publisher corroborate this?",
            ),
        ),
    )


def test_state_reconstructs_without_provider_or_repository_objects() -> None:
    state = _state()
    payload = state.model_dump(mode="json")

    assert reconstruct_multi_agent_graph_state(payload) == state
    assert "claim_summary" in str(payload)
    assert "query_ids" not in str(payload)
    assert "permissions" not in str(payload)


def test_assignment_must_reference_matching_component_requirement() -> None:
    state = _state()
    payload = state.model_dump(mode="python")
    payload["assignments"][0]["requirement_ids"] = (uuid4(),)

    with pytest.raises(ValidationError, match="assignment requirements"):
        DurableMultiAgentGraphState.model_validate(payload)


def test_results_and_families_cannot_invent_stored_evidence() -> None:
    state = _state()
    payload = state.model_dump(mode="python")
    payload["stored_evidence_ids"] = ()

    with pytest.raises(ValidationError, match="stored evidence"):
        DurableMultiAgentGraphState.model_validate(payload)


def test_consumption_cannot_exceed_declared_budget() -> None:
    state = _state()
    payload = state.model_dump(mode="python")
    payload["consumption"]["search_calls"] = state.budget.maximum_search_calls + 1

    with pytest.raises(ValidationError, match="search consumption"):
        DurableMultiAgentGraphState.model_validate(payload)
