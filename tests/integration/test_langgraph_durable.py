"""Durable interruption, restart, and idempotent resume tests."""

from uuid import uuid4

import pytest

from claim_polygraph_ng.application import (
    DuplicateReviewDecisionError,
    DurableFixtureLangGraphWorkflow,
    ExistingGraphThreadError,
    GraphResumeError,
)
from claim_polygraph_ng.domain import (
    DurableGraphStatus,
    FixtureGraphRequest,
    GraphExecutionBudget,
    GraphNode,
    ReviewDecision,
    ReviewDecisionKind,
    ReviewPriority,
    ReviewRoutingDecision,
    ReviewTrigger,
    VerdictLabel,
)


def _request(*, review_required: bool = True) -> FixtureGraphRequest:
    return FixtureGraphRequest(
        claim_text="The Great Wall is visible from the Moon with the unaided eye.",
        approved_evidence_ids=(uuid4(), uuid4(), uuid4()),
        authoritative_verdict=VerdictLabel.CONTRADICTED,
        review_required=review_required,
        review_reason=(
            "The absolute statement requires explicit human confirmation."
            if review_required
            else None
        ),
    )


def _decision(
    *,
    kind: ReviewDecisionKind = ReviewDecisionKind.APPROVE,
    revised_verdict: VerdictLabel | None = None,
) -> ReviewDecision:
    return ReviewDecision(
        kind=kind,
        reviewer_identity="Md Moshiur Rahman",
        rationale="The exact passages support this review decision.",
        revised_verdict=revised_verdict,
    )


def test_real_interrupt_is_checkpointed_with_json_payload(tmp_path) -> None:
    database = tmp_path / "graph.db"
    request = _request()

    with DurableFixtureLangGraphWorkflow(database, enabled=True) as workflow:
        paused = workflow.start(request)

    assert database.is_file()
    assert paused.status is DurableGraphStatus.REVIEW_REQUIRED
    assert paused.interrupt is not None
    assert paused.interrupt.thread_id == str(request.graph_run_id)
    assert paused.interrupt.approved_evidence_ids == request.approved_evidence_ids
    assert GraphNode.INTERRUPT_FOR_REVIEW not in paused.completed_nodes
    assert set(paused.operation_counts.values()) == {1}


def test_restart_resume_reuses_every_pre_interrupt_operation(tmp_path) -> None:
    database = tmp_path / "graph.db"
    request = _request()
    with DurableFixtureLangGraphWorkflow(database, enabled=True) as first_process:
        paused = first_process.start(request)
    decision = _decision()

    with DurableFixtureLangGraphWorkflow(database, enabled=True) as restarted:
        reconstructed = restarted.snapshot(str(request.graph_run_id))
        completed = restarted.resume(str(request.graph_run_id), decision)

    assert reconstructed == paused
    assert completed.status is DurableGraphStatus.COMPLETED
    assert completed.final_verdict is request.authoritative_verdict
    assert completed.applied_decision_id == decision.decision_id
    assert completed.interrupt is None
    for node, count in paused.operation_counts.items():
        assert completed.operation_counts[node] == count == 1
    assert completed.operation_counts[GraphNode.INTERRUPT_FOR_REVIEW] == 1
    assert completed.operation_counts[GraphNode.FINALIZE] == 1


def test_same_decision_resume_is_idempotent(tmp_path) -> None:
    database = tmp_path / "graph.db"
    request = _request()
    decision = _decision()

    with DurableFixtureLangGraphWorkflow(database, enabled=True) as workflow:
        workflow.start(request)
        first = workflow.resume(str(request.graph_run_id), decision)
        replayed = workflow.resume(str(request.graph_run_id), decision)

    assert replayed == first


def test_different_second_decision_is_rejected(tmp_path) -> None:
    database = tmp_path / "graph.db"
    request = _request()

    with DurableFixtureLangGraphWorkflow(database, enabled=True) as workflow:
        workflow.start(request)
        workflow.resume(str(request.graph_run_id), _decision())

        with pytest.raises(DuplicateReviewDecisionError, match="different"):
            workflow.resume(str(request.graph_run_id), _decision())


def test_revise_and_request_evidence_routes_are_typed(tmp_path) -> None:
    revise_request = _request()
    evidence_request = _request()
    with DurableFixtureLangGraphWorkflow(tmp_path / "graph.db", enabled=True) as workflow:
        workflow.start(revise_request)
        revised = workflow.resume(
            str(revise_request.graph_run_id),
            _decision(
                kind=ReviewDecisionKind.REVISE,
                revised_verdict=VerdictLabel.MIXED,
            ),
        )
        workflow.start(evidence_request)
        more_evidence = workflow.resume(
            str(evidence_request.graph_run_id),
            _decision(kind=ReviewDecisionKind.REQUEST_EVIDENCE),
        )

    assert revised.status is DurableGraphStatus.COMPLETED
    assert revised.final_verdict is VerdictLabel.MIXED
    assert more_evidence.status is DurableGraphStatus.MORE_EVIDENCE_REQUIRED
    assert more_evidence.final_verdict is None
    assert more_evidence.completed_nodes[-1] is GraphNode.REQUEST_MORE_EVIDENCE


def test_start_and_resume_guards_are_explicit(tmp_path) -> None:
    database = tmp_path / "graph.db"
    request = _request()
    disabled = DurableFixtureLangGraphWorkflow(database)
    with pytest.raises(GraphResumeError, match="disabled"):
        disabled.start(request)
    disabled.close()

    with DurableFixtureLangGraphWorkflow(database, enabled=True) as workflow:
        workflow.start(request)
        with pytest.raises(ExistingGraphThreadError, match="already exists"):
            workflow.start(request)
        with pytest.raises(GraphResumeError, match="unknown"):
            workflow.resume(str(uuid4()), _decision())


def test_durable_graph_enforces_step_budget(tmp_path) -> None:
    request = _request().model_copy(
        update={"budget": GraphExecutionBudget(maximum_steps=3)}
    )

    with DurableFixtureLangGraphWorkflow(
        tmp_path / "graph.db", enabled=True
    ) as workflow, pytest.raises(RuntimeError, match="maximum step budget"):
        workflow.start(request)


def test_deterministic_routing_overrides_manual_fixture_flag(tmp_path) -> None:
    request = _request(review_required=False)
    routing = ReviewRoutingDecision(
        claim_id=uuid4(),
        review_required=True,
        priority=ReviewPriority.CRITICAL,
        triggers=(ReviewTrigger.CRITICAL_CITATION_FAILURE,),
        reason="Human review required: critical_citation_failure.",
    )

    with DurableFixtureLangGraphWorkflow(
        tmp_path / "graph.db", enabled=True
    ) as workflow:
        paused = workflow.start(request, routing=routing)

    assert paused.status is DurableGraphStatus.REVIEW_REQUIRED
    assert paused.interrupt is not None
    assert paused.interrupt.route_reason == routing.reason
