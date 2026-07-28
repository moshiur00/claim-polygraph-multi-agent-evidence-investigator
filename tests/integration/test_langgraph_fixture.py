"""Equivalence and containment tests for the optional fixture graph."""

import inspect
from uuid import uuid4

import pytest

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.application.langgraph_fixture import (
    FixtureLangGraphWorkflow,
    LangGraphFeatureDisabledError,
)
from claim_polygraph_ng.domain.graph import (
    FixtureGraphRequest,
    GraphExecutionBudget,
    GraphNode,
    GraphRoute,
    GraphRunStatus,
)
from claim_polygraph_ng.domain.models import VerdictLabel


def _request(*, review_required: bool = False) -> FixtureGraphRequest:
    return FixtureGraphRequest(
        claim_text="The Great Wall is visible from the Moon with the unaided eye.",
        approved_evidence_ids=(uuid4(), uuid4(), uuid4()),
        authoritative_verdict=VerdictLabel.CONTRADICTED,
        review_required=review_required,
        review_reason=(
            "An absolute visibility statement requires human confirmation."
            if review_required
            else None
        ),
    )


def test_graph_is_disabled_by_default() -> None:
    with pytest.raises(LangGraphFeatureDisabledError, match="remains authoritative"):
        FixtureLangGraphWorkflow().invoke(_request())


def test_authoritative_service_has_no_langgraph_dependency() -> None:
    source = inspect.getsource(InvestigationService)

    assert "LangGraph" not in source
    assert "FixtureLangGraphWorkflow" not in source


def test_fixture_graph_preserves_verdict_and_evidence_packet() -> None:
    request = _request()

    result = FixtureLangGraphWorkflow(enabled=True).invoke(request)

    assert result.status is GraphRunStatus.COMPLETED
    assert result.authoritative_verdict is request.authoritative_verdict
    assert result.consumed_evidence_ids == request.approved_evidence_ids
    assert result.route_decision.route is GraphRoute.FINALIZE
    assert result.completed_nodes[-1] is GraphNode.FINALIZE
    assert result.model_calls == result.search_calls == 0
    assert result.estimated_cost_usd == 0


def test_fixture_graph_routes_to_bounded_review_placeholder() -> None:
    result = FixtureLangGraphWorkflow(enabled=True).invoke(
        _request(review_required=True)
    )

    assert result.status is GraphRunStatus.REVIEW_REQUIRED
    assert result.route_decision.route is GraphRoute.HUMAN_REVIEW
    assert result.completed_nodes[-1] is GraphNode.INTERRUPT_FOR_REVIEW
    assert GraphNode.FINALIZE not in result.completed_nodes


def test_fixture_graph_enforces_step_budget() -> None:
    request = _request().model_copy(
        update={"budget": GraphExecutionBudget(maximum_steps=3)}
    )

    with pytest.raises(RuntimeError, match="maximum step budget"):
        FixtureLangGraphWorkflow(enabled=True).invoke(request)
