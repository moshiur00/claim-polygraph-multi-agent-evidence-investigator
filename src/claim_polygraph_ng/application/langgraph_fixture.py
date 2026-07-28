"""Feature-flagged, zero-cost LangGraph wrapper for Stage 7.1."""

from collections.abc import Callable
from itertools import pairwise
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from claim_polygraph_ng.domain.graph import (
    FixtureGraphRequest,
    FixtureGraphResult,
    GraphNode,
    GraphRoute,
    GraphRouteDecision,
    GraphRunStatus,
)
from claim_polygraph_ng.domain.models import VerdictLabel


class LangGraphFeatureDisabledError(RuntimeError):
    """Raised when the optional graph is invoked without explicit enablement."""


class _FixtureState(TypedDict):
    graph_run_id: UUID
    claim_text: str
    approved_evidence_ids: tuple[UUID, ...]
    consumed_evidence_ids: tuple[UUID, ...]
    authoritative_verdict: VerdictLabel
    review_required: bool
    review_reason: str | None
    maximum_steps: int
    completed_nodes: tuple[GraphNode, ...]
    route: GraphRoute | None
    route_reason: str | None


_LINEAR_NODES = (
    GraphNode.NORMALIZE,
    GraphNode.RESEARCH,
    GraphNode.CONSOLIDATE,
    GraphNode.VERIFY_CONTEXT,
    GraphNode.BUILD_ARGUMENT_LEDGER,
    GraphNode.DRAFT_VERDICT,
    GraphNode.AUDIT_CITATIONS,
    GraphNode.ASSESS_READINESS,
)


class FixtureLangGraphWorkflow:
    """Isolated graph that replays approved data without provider access."""

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = enabled
        self._graph = _build_graph()

    def invoke(self, request: FixtureGraphRequest) -> FixtureGraphResult:
        """Run the fixture graph while preserving the authoritative verdict."""
        if not self._enabled:
            raise LangGraphFeatureDisabledError(
                "LangGraph is disabled; the existing investigation service remains authoritative"
            )
        initial: _FixtureState = {
            "graph_run_id": request.graph_run_id,
            "claim_text": request.claim_text,
            "approved_evidence_ids": request.approved_evidence_ids,
            "consumed_evidence_ids": (),
            "authoritative_verdict": request.authoritative_verdict,
            "review_required": request.review_required,
            "review_reason": request.review_reason,
            "maximum_steps": request.budget.maximum_steps,
            "completed_nodes": (),
            "route": None,
            "route_reason": None,
        }
        final = self._graph.invoke(initial)
        route = final["route"]
        reason = final["route_reason"]
        if route is None or reason is None:
            raise RuntimeError("fixture graph ended without a route decision")
        return FixtureGraphResult(
            graph_run_id=final["graph_run_id"],
            status=(
                GraphRunStatus.REVIEW_REQUIRED
                if route is GraphRoute.HUMAN_REVIEW
                else GraphRunStatus.COMPLETED
            ),
            authoritative_verdict=final["authoritative_verdict"],
            approved_evidence_ids=final["approved_evidence_ids"],
            consumed_evidence_ids=final["consumed_evidence_ids"],
            completed_nodes=final["completed_nodes"],
            route_decision=GraphRouteDecision(route=route, reason=reason),
            limitations=(
                "Stage 7.1 uses frozen fixture data and no checkpoint persistence.",
                "The graph is optional and does not replace InvestigationService.",
            ),
        )


def _build_graph():
    builder = StateGraph(_FixtureState)
    for node in _LINEAR_NODES:
        builder.add_node(node.value, _record_node(node))
    builder.add_node(GraphNode.ROUTE_REVIEW.value, _route_review)
    builder.add_node(
        GraphNode.INTERRUPT_FOR_REVIEW.value,
        _record_node(GraphNode.INTERRUPT_FOR_REVIEW),
    )
    builder.add_node(GraphNode.FINALIZE.value, _record_node(GraphNode.FINALIZE))
    builder.add_edge(START, GraphNode.NORMALIZE.value)
    for current, following in pairwise(_LINEAR_NODES):
        builder.add_edge(current.value, following.value)
    builder.add_edge(GraphNode.ASSESS_READINESS.value, GraphNode.ROUTE_REVIEW.value)
    builder.add_conditional_edges(
        GraphNode.ROUTE_REVIEW.value,
        _select_route,
        {
            GraphRoute.HUMAN_REVIEW.value: GraphNode.INTERRUPT_FOR_REVIEW.value,
            GraphRoute.FINALIZE.value: GraphNode.FINALIZE.value,
        },
    )
    builder.add_edge(GraphNode.INTERRUPT_FOR_REVIEW.value, END)
    builder.add_edge(GraphNode.FINALIZE.value, END)
    return builder.compile()


def _record_node(node: GraphNode) -> Callable[[_FixtureState], dict]:
    def run(state: _FixtureState) -> dict:
        history = state["completed_nodes"] + (node,)
        if len(history) > state["maximum_steps"]:
            raise RuntimeError("fixture graph exceeded its maximum step budget")
        update: dict = {"completed_nodes": history}
        if node is GraphNode.RESEARCH:
            update["consumed_evidence_ids"] = state["approved_evidence_ids"]
        return update

    return run


def _route_review(state: _FixtureState) -> dict:
    history = state["completed_nodes"] + (GraphNode.ROUTE_REVIEW,)
    if len(history) > state["maximum_steps"]:
        raise RuntimeError("fixture graph exceeded its maximum step budget")
    if state["review_required"]:
        return {
            "completed_nodes": history,
            "route": GraphRoute.HUMAN_REVIEW,
            "route_reason": state["review_reason"],
        }
    return {
        "completed_nodes": history,
        "route": GraphRoute.FINALIZE,
        "route_reason": "The fixture declares no unresolved condition requiring review.",
    }


def _select_route(state: _FixtureState) -> str:
    route = state["route"]
    if route is None:
        raise RuntimeError("route node did not produce a route")
    return route.value
