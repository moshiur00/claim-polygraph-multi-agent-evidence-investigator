"""Stage 9.4 authoritative LangGraph skeleton integration tests."""

import asyncio
from itertools import pairwise

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.domain import ArtifactType, ReviewRoutingDecision, ReviewTrigger
from claim_polygraph_ng.domain.authoritative_graph import AuthoritativeGraphPhase
from claim_polygraph_ng.domain.operations import AuthoritativeOperation
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.persistence.authoritative_graph import (
    SQLiteAuthoritativeGraphCheckpointRepository,
)
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


def test_fixture_graph_calls_all_operations_and_checkpoints_each_one(tmp_path) -> None:
    investigations = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    service = InvestigationService(
        repository=investigations,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    state_path = tmp_path / "authoritative-state.db"
    with AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "langgraph.db",
        state_checkpoint_path=state_path,
    ) as workflow:
        result = asyncio.run(
            workflow.run_to_completion("The fixture programme reduced waste.")
        )

    assert result.state.phase is AuthoritativeGraphPhase.COMPLETE
    assert set(result.state.completed_operations) == set(AuthoritativeOperation)
    assert len(result.state.completed_operations) == len(AuthoritativeOperation)
    assert result.state.final_report_ref is not None
    assert result.report.investigation.status.value == "completed"
    assert result.report.verdict == investigations.list_artifacts(
        result.state.investigation_id,
        result.state.enforced_verdict_ref.artifact_type,
        type(result.report.verdict),
    )[0]
    history = SQLiteAuthoritativeGraphCheckpointRepository(state_path).history(
        result.state.thread_id
    )
    assert len(history) == 18
    assert tuple(item.checkpoint_sequence for item in history) == tuple(range(18))
    assert all(
        set(previous.completed_operations) <= set(current.completed_operations)
        for previous, current in pairwise(history)
    )


def test_fixture_graph_is_zero_cost_and_uses_real_review_interrupt(tmp_path) -> None:
    class ReviewRoutedService(InvestigationService):
        @staticmethod
        def route_review(verdict, readiness, assurance):
            return True

    investigations = SQLiteInvestigationRepository(tmp_path / "review-investigations.db")
    service = ReviewRoutedService(
        repository=investigations,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    with AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "review-langgraph.db",
        state_checkpoint_path=tmp_path / "review-state.db",
    ) as workflow:
        result = asyncio.run(workflow.run_to_completion("A review-routed fixture claim."))

    assert result.state.review_decision_ids
    assert result.state.consumption.model_calls == 0
    assert result.state.consumption.search_calls == 0
    assert result.state.consumption.estimated_cost_usd == 0


def test_submission_review_policy_is_typed_persisted_and_selective(tmp_path) -> None:
    investigations = SQLiteInvestigationRepository(tmp_path / "policy-investigations.db")
    service = InvestigationService(
        repository=investigations,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    with AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "policy-langgraph.db",
        state_checkpoint_path=tmp_path / "policy-state.db",
        require_human_review=True,
    ) as workflow:
        pending = asyncio.run(workflow.start("A submission requesting human review."))

    assert pending.interrupt is not None
    decisions = investigations.list_artifacts(
        pending.state.investigation_id,
        ArtifactType.REVIEW_ROUTING,
        ReviewRoutingDecision,
    )
    assert len(decisions) == 1
    assert decisions[0].review_required
    assert ReviewTrigger.VERDICT_REQUESTED_REVIEW in decisions[0].triggers
