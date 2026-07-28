"""SQLite-backed LangGraph interruption and idempotent resume for Stage 7.2."""

from collections.abc import Callable
from itertools import pairwise
from pathlib import Path
from time import perf_counter
from typing import Any, TypedDict

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, StateSnapshot, interrupt

from claim_polygraph_ng.domain.citation import ReviewRoutingDecision
from claim_polygraph_ng.domain.graph import (
    DurableGraphSnapshot,
    DurableGraphStatus,
    DurableMultiAgentGraphState,
    FixtureGraphRequest,
    GraphNode,
    ReviewDecision,
    ReviewDecisionKind,
    ReviewInterruptPayload,
)
from claim_polygraph_ng.domain.models import VerdictLabel
from claim_polygraph_ng.domain.telemetry import MetricName, SpanKind
from claim_polygraph_ng.persistence.sqlite_runtime import connect_sqlite, enable_wal
from claim_polygraph_ng.telemetry import TelemetryCollector


class ExistingGraphThreadError(RuntimeError):
    """Raised when a caller tries to start an already checkpointed thread."""


class GraphResumeError(RuntimeError):
    """Raised when no matching durable interruption can be resumed."""


class DuplicateReviewDecisionError(RuntimeError):
    """Raised when a completed thread receives a different decision."""


class _DurableState(TypedDict):
    thread_id: str
    claim_text: str
    approved_evidence_ids: list[str]
    authoritative_verdict: str
    final_verdict: str | None
    review_required: bool
    review_reason: str | None
    maximum_steps: int
    status: str
    completed_nodes: list[str]
    operation_counts: dict[str, int]
    decision_kind: str | None
    applied_decision_id: str | None
    reviewer_identity: str | None
    research_state: dict[str, Any] | None


_PRE_REVIEW_NODES = (
    GraphNode.NORMALIZE,
    GraphNode.RESEARCH,
    GraphNode.CONSOLIDATE,
    GraphNode.VERIFY_CONTEXT,
    GraphNode.BUILD_ARGUMENT_LEDGER,
    GraphNode.DRAFT_VERDICT,
    GraphNode.AUDIT_CITATIONS,
    GraphNode.ASSESS_READINESS,
    GraphNode.ROUTE_REVIEW,
)


class DurableFixtureLangGraphWorkflow:
    """Own one strict SQLite checkpointer and a compiled durable fixture graph."""

    def __init__(
        self,
        checkpoint_path: str | Path,
        *,
        enabled: bool = False,
        telemetry: TelemetryCollector | None = None,
    ) -> None:
        self._enabled = enabled
        self._path = Path(checkpoint_path)
        self._telemetry = telemetry
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = connect_sqlite(
            str(self._path),
            check_same_thread=False,
        )
        try:
            enable_wal(self._connection)
            serializer = JsonPlusSerializer(allowed_msgpack_modules=())
            self._checkpointer = SqliteSaver(self._connection, serde=serializer)
            self._graph = _build_durable_graph(self._checkpointer, telemetry)
        except Exception:
            self._connection.close()
            raise

    def __enter__(self) -> "DurableFixtureLangGraphWorkflow":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the owned SQLite connection."""
        self._connection.close()

    def start(
        self,
        request: FixtureGraphRequest,
        *,
        routing: ReviewRoutingDecision | None = None,
    ) -> DurableGraphSnapshot:
        """Start once and return either an interrupt or a terminal result."""
        self._ensure_enabled()
        thread_id = str(request.graph_run_id)
        config = _config(thread_id)
        existing = self._graph.get_state(config)
        if existing.values:
            raise ExistingGraphThreadError(f"graph thread already exists: {thread_id}")
        initial: _DurableState = {
            "thread_id": thread_id,
            "claim_text": request.claim_text,
            "approved_evidence_ids": [
                str(evidence_id) for evidence_id in request.approved_evidence_ids
            ],
            "authoritative_verdict": request.authoritative_verdict.value,
            "final_verdict": None,
            "review_required": (
                routing.review_required if routing is not None else request.review_required
            ),
            "review_reason": (
                routing.reason
                if routing is not None and routing.review_required
                else request.review_reason
            ),
            "maximum_steps": request.budget.maximum_steps,
            "status": DurableGraphStatus.REVIEW_REQUIRED.value,
            "completed_nodes": [],
            "operation_counts": {},
            "decision_kind": None,
            "applied_decision_id": None,
            "reviewer_identity": None,
            "research_state": (
                request.research_state.model_dump(mode="json")
                if request.research_state is not None
                else None
            ),
        }
        self._graph.invoke(initial, config=config)
        return self.snapshot(thread_id)

    def resume(
        self, thread_id: str, decision: ReviewDecision
    ) -> DurableGraphSnapshot:
        """Resume exactly once; replaying the accepted decision is idempotent."""
        self._ensure_enabled()
        config = _config(thread_id)
        before = self._graph.get_state(config)
        if not before.values:
            raise GraphResumeError(f"unknown graph thread: {thread_id}")
        applied = before.values.get("applied_decision_id")
        if applied is not None:
            if applied == str(decision.decision_id):
                return _to_snapshot(before)
            raise DuplicateReviewDecisionError(
                "the graph thread already has a different accepted decision"
            )
        if not before.interrupts:
            raise GraphResumeError("graph thread has no pending human interruption")
        self._graph.invoke(
            Command(resume=decision.model_dump(mode="json")),
            config=config,
        )
        return self.snapshot(thread_id)

    def snapshot(self, thread_id: str) -> DurableGraphSnapshot:
        """Reconstruct the latest typed state from SQLite."""
        self._ensure_enabled()
        state = self._graph.get_state(_config(thread_id))
        if not state.values:
            raise GraphResumeError(f"unknown graph thread: {thread_id}")
        return _to_snapshot(state)

    def _ensure_enabled(self) -> None:
        if not self._enabled:
            raise GraphResumeError(
                "durable LangGraph is disabled; InvestigationService remains authoritative"
            )


def _build_durable_graph(
    checkpointer: SqliteSaver, telemetry: TelemetryCollector | None = None
):
    builder = StateGraph(_DurableState)
    for node in _PRE_REVIEW_NODES:
        handler = _route_review if node is GraphNode.ROUTE_REVIEW else _record(node)
        builder.add_node(node.value, _observed_node(node, handler, telemetry))
    builder.add_node(GraphNode.INTERRUPT_FOR_REVIEW.value, _human_review)
    builder.add_node(
        GraphNode.FINALIZE.value,
        _observed_node(GraphNode.FINALIZE, _finalize, telemetry),
    )
    builder.add_node(
        GraphNode.REQUEST_MORE_EVIDENCE.value,
        _observed_node(GraphNode.REQUEST_MORE_EVIDENCE, _request_evidence, telemetry),
    )
    builder.add_node(
        GraphNode.REJECT.value,
        _observed_node(GraphNode.REJECT, _reject, telemetry),
    )
    builder.add_edge(START, GraphNode.NORMALIZE.value)
    for current, following in pairwise(_PRE_REVIEW_NODES):
        builder.add_edge(current.value, following.value)
    builder.add_conditional_edges(
        GraphNode.ROUTE_REVIEW.value,
        _after_route,
        {
            "review": GraphNode.INTERRUPT_FOR_REVIEW.value,
            "finalize": GraphNode.FINALIZE.value,
        },
    )
    builder.add_conditional_edges(
        GraphNode.INTERRUPT_FOR_REVIEW.value,
        _after_review,
        {
            "finalize": GraphNode.FINALIZE.value,
            "request_evidence": GraphNode.REQUEST_MORE_EVIDENCE.value,
            "reject": GraphNode.REJECT.value,
        },
    )
    builder.add_edge(GraphNode.FINALIZE.value, END)
    builder.add_edge(GraphNode.REQUEST_MORE_EVIDENCE.value, END)
    builder.add_edge(GraphNode.REJECT.value, END)
    return builder.compile(checkpointer=checkpointer)


def _observed_node(
    node: GraphNode,
    handler: Callable[[_DurableState], dict[str, Any]],
    telemetry: TelemetryCollector | None,
) -> Callable[[_DurableState], dict[str, Any]]:
    if telemetry is None:
        return handler

    def observed(state: _DurableState) -> dict[str, Any]:
        started = perf_counter()
        try:
            with telemetry.span(
                f"langgraph.{node.value}",
                SpanKind.LANGGRAPH,
                attributes={"graph.node": node.value},
            ):
                return handler(state)
        finally:
            telemetry.metric(
                MetricName.LANGGRAPH_NODE_LATENCY_MS,
                (perf_counter() - started) * 1_000,
                "ms",
                attributes={"graph.node": node.value},
            )

    return observed


def _record(node: GraphNode) -> Callable[[_DurableState], dict[str, Any]]:
    def run(state: _DurableState) -> dict[str, Any]:
        return _node_update(state, node)

    return run


def _route_review(state: _DurableState) -> dict[str, Any]:
    return _node_update(state, GraphNode.ROUTE_REVIEW)


def _after_route(state: _DurableState) -> str:
    return "review" if state["review_required"] else "finalize"


def _human_review(state: _DurableState) -> dict[str, Any]:
    payload = ReviewInterruptPayload(
        thread_id=state["thread_id"],
        question="Confirm the final verdict or choose another review action.",
        claim_text=state["claim_text"],
        provisional_verdict=VerdictLabel(state["authoritative_verdict"]),
        approved_evidence_ids=tuple(state["approved_evidence_ids"]),
        route_reason=state["review_reason"] or "Human confirmation is required.",
    )
    raw_decision = interrupt(payload.model_dump(mode="json"))
    decision = ReviewDecision.model_validate(raw_decision)
    update = _node_update(state, GraphNode.INTERRUPT_FOR_REVIEW)
    update.update(
        {
            "decision_kind": decision.kind.value,
            "applied_decision_id": str(decision.decision_id),
            "reviewer_identity": decision.reviewer_identity,
            "final_verdict": (
                decision.revised_verdict.value
                if decision.revised_verdict is not None
                else state["authoritative_verdict"]
            ),
        }
    )
    return update


def _after_review(state: _DurableState) -> str:
    if state["decision_kind"] == ReviewDecisionKind.REQUEST_EVIDENCE.value:
        return "request_evidence"
    if state["decision_kind"] == ReviewDecisionKind.REJECT.value:
        return "reject"
    return "finalize"


def _finalize(state: _DurableState) -> dict[str, Any]:
    update = _node_update(state, GraphNode.FINALIZE)
    update.update(
        {
            "status": DurableGraphStatus.COMPLETED.value,
            "final_verdict": state["final_verdict"] or state["authoritative_verdict"],
        }
    )
    return update


def _request_evidence(state: _DurableState) -> dict[str, Any]:
    update = _node_update(state, GraphNode.REQUEST_MORE_EVIDENCE)
    update["status"] = DurableGraphStatus.MORE_EVIDENCE_REQUIRED.value
    update["final_verdict"] = None
    return update


def _reject(state: _DurableState) -> dict[str, Any]:
    update = _node_update(state, GraphNode.REJECT)
    update["status"] = DurableGraphStatus.REJECTED.value
    update["final_verdict"] = None
    return update


def _node_update(state: _DurableState, node: GraphNode) -> dict[str, Any]:
    history = [*state["completed_nodes"], node.value]
    if len(history) > state["maximum_steps"]:
        raise RuntimeError("durable graph exceeded its maximum step budget")
    counts = dict(state["operation_counts"])
    counts[node.value] = counts.get(node.value, 0) + 1
    return {
        "completed_nodes": history,
        "operation_counts": counts,
    }


def _config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def _to_snapshot(state: StateSnapshot) -> DurableGraphSnapshot:
    values = state.values
    interrupt_payload = (
        ReviewInterruptPayload.model_validate(state.interrupts[0].value)
        if state.interrupts
        else None
    )
    return DurableGraphSnapshot(
        thread_id=values["thread_id"],
        status=DurableGraphStatus(values["status"]),
        authoritative_verdict=VerdictLabel(values["authoritative_verdict"]),
        final_verdict=(
            VerdictLabel(values["final_verdict"])
            if values.get("final_verdict") is not None
            else None
        ),
        approved_evidence_ids=tuple(values["approved_evidence_ids"]),
        completed_nodes=tuple(GraphNode(node) for node in values["completed_nodes"]),
        operation_counts={
            GraphNode(node): count
            for node, count in values["operation_counts"].items()
        },
        interrupt=interrupt_payload,
        applied_decision_id=values.get("applied_decision_id"),
        reviewer_identity=values.get("reviewer_identity"),
        research_state=(
            DurableMultiAgentGraphState.model_validate(values["research_state"])
            if values.get("research_state") is not None
            else None
        ),
    )
