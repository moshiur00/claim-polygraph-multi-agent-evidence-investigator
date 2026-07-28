"""Durable reconstruction of bounded multi-agent state across process restart."""

from uuid import uuid4

from claim_polygraph_ng.application import DurableFixtureLangGraphWorkflow
from claim_polygraph_ng.domain import (
    DurableAssignmentReference,
    DurableComponentReference,
    DurableMultiAgentGraphState,
    DurableRequirementReference,
    DurableResultReference,
    FixtureGraphRequest,
    ResearchBudget,
    ResearchConsumption,
    ResearchRequirementKind,
    ResearchRole,
    VerdictLabel,
)


def test_research_round_reconstructs_after_restart_without_duplicate_operations(
    tmp_path,
) -> None:
    investigation_id = uuid4()
    component_id = uuid4()
    requirement_id = uuid4()
    assignment_id = uuid4()
    evidence_id = uuid4()
    source_id = uuid4()
    research_state = DurableMultiAgentGraphState(
        investigation_id=investigation_id,
        parent_claim_id=component_id,
        components=(
            DurableComponentReference(
                component_id=component_id,
                parent_claim_id=component_id,
                claim_summary="The agency reported 42 cases in 2025.",
            ),
        ),
        requirements=(
            DurableRequirementReference(
                requirement_id=requirement_id,
                component_id=component_id,
                kind=ResearchRequirementKind.COMPONENT_COVERAGE,
                rationale_summary="The component requires direct evidence.",
            ),
        ),
        assignments=(
            DurableAssignmentReference(
                assignment_id=assignment_id,
                component_id=component_id,
                role=ResearchRole.PRIMARY_SOURCE,
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
            ),
        ),
        stored_source_ids=(source_id,),
        stored_evidence_ids=(evidence_id,),
        budget=ResearchBudget(maximum_model_calls=0, maximum_cost_usd=0),
        consumption=ResearchConsumption(
            completed_rounds=1,
            role_activations=1,
            search_calls=1,
            fetched_pages=1,
            model_calls=0,
            estimated_cost_usd=0,
        ),
    )
    request = FixtureGraphRequest(
        graph_run_id=investigation_id,
        claim_text="The agency reported 42 cases in 2025.",
        approved_evidence_ids=(evidence_id,),
        authoritative_verdict=VerdictLabel.SUPPORTED,
        research_state=research_state,
    )
    database = tmp_path / "durable-research.db"

    with DurableFixtureLangGraphWorkflow(database, enabled=True) as first_process:
        completed = first_process.start(request)

    with DurableFixtureLangGraphWorkflow(database, enabled=True) as restarted:
        reconstructed = restarted.snapshot(str(investigation_id))

    assert completed.research_state == research_state
    assert reconstructed == completed
    assert reconstructed.research_state is not None
    assert reconstructed.research_state.assignments[0].assignment_id == assignment_id
    assert set(reconstructed.operation_counts.values()) == {1}
