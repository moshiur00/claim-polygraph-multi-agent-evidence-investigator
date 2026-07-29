"""Stage 9.9 durable human-review paths in the authoritative graph."""

import asyncio

import pytest

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.application.langgraph_durable import (
    DuplicateReviewDecisionError,
)
from claim_polygraph_ng.domain import (
    ReviewDecision,
    ReviewDecisionKind,
    VerdictLabel,
)
from claim_polygraph_ng.domain.authoritative_graph import AuthoritativeGraphPhase
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


class _ReviewRoutedService(InvestigationService):
    @staticmethod
    def route_review(verdict, readiness, assurance):
        return True


def test_approval_resumes_same_thread_and_is_idempotent(tmp_path) -> None:
    workflow, ledger = _workflow(tmp_path, "approve")
    pending = asyncio.run(workflow.start("Approval review fixture claim."))
    assert pending.interrupt is not None
    operations_before = pending.state.completed_operations
    receipts_before = pending.state.paid_receipts
    decision = ReviewDecision(
        kind=ReviewDecisionKind.APPROVE,
        reviewer_identity="Primary Reviewer",
        rationale="The reviewed packet and verdict are acceptable.",
    )

    completed = asyncio.run(
        workflow.resume(
            pending.state.thread_id,
            decision,
            approver_identity="Distinct Approver",
        )
    )
    replayed = asyncio.run(
        workflow.resume(
            pending.state.thread_id,
            decision,
            approver_identity="Distinct Approver",
        )
    )

    assert completed.state.phase is AuthoritativeGraphPhase.COMPLETE
    assert completed.report is not None
    assert replayed.state == completed.state
    assert set(operations_before) <= set(completed.state.completed_operations)
    assert len(completed.state.completed_operations) == len(
        set(completed.state.completed_operations)
    )
    assert completed.state.paid_receipts == receipts_before
    trail = ledger.find_by_thread(pending.state.thread_id)
    assert trail is not None and trail.chain_valid
    assert len(trail.decisions) == len(trail.approvals) == 1
    assert completed.report.publication_decision.publication_allowed


def test_revision_is_approved_reaudited_and_persisted_without_research_replay(
    tmp_path,
) -> None:
    workflow, ledger = _workflow(tmp_path, "revise")
    pending = asyncio.run(workflow.start("Revision review fixture claim."))
    assert pending.interrupt is not None
    revised_label = (
        VerdictLabel.UNSUPPORTED
        if pending.interrupt.provisional_verdict is not VerdictLabel.UNSUPPORTED
        else VerdictLabel.UNVERIFIABLE
    )
    decision = ReviewDecision(
        kind=ReviewDecisionKind.REVISE,
        reviewer_identity="Revision Reviewer",
        rationale="The evidence supports a more conservative taxonomy label.",
        revised_verdict=revised_label,
    )

    completed = asyncio.run(
        workflow.resume(
            pending.state.thread_id,
            decision,
            approver_identity="Revision Approver",
        )
    )

    assert completed.report is not None
    assert completed.report.verdict.label is revised_label
    assert completed.report.verdict.version == 2
    assert completed.report.full_report_assurance.claim_id == (
        completed.report.claim.claim_id
    )
    assert completed.state.paid_receipts == pending.state.paid_receipts
    trail = ledger.find_by_thread(pending.state.thread_id)
    assert trail is not None and trail.chain_valid
    assert len(trail.decisions) == len(trail.approvals) == len(trail.revisions) == 1
    assert trail.revisions[0].revised_verdict is revised_label


@pytest.mark.parametrize(
    ("kind", "phase"),
    (
        (ReviewDecisionKind.REQUEST_EVIDENCE, AuthoritativeGraphPhase.REVIEW),
        (ReviewDecisionKind.REJECT, AuthoritativeGraphPhase.CANCELLED),
    ),
)
def test_more_evidence_and_rejection_end_without_finalization_or_replay(
    tmp_path,
    kind,
    phase,
) -> None:
    workflow, ledger = _workflow(tmp_path, kind.value)
    pending = asyncio.run(workflow.start(f"{kind.value} review fixture claim."))
    decision = ReviewDecision(
        kind=kind,
        reviewer_identity="Routing Reviewer",
        rationale=f"The correct review disposition is {kind.value}.",
    )

    routed = asyncio.run(workflow.resume(pending.state.thread_id, decision))

    assert routed.state.phase is phase
    assert routed.report is None
    assert routed.state.paid_receipts == pending.state.paid_receipts
    assert routed.state.completed_operations == pending.state.completed_operations
    trail = ledger.find_by_thread(pending.state.thread_id)
    assert trail is not None and trail.chain_valid
    assert len(trail.decisions) == 1
    assert not trail.approvals
    with pytest.raises(DuplicateReviewDecisionError):
        asyncio.run(
            workflow.resume(
                pending.state.thread_id,
                ReviewDecision(
                    kind=ReviewDecisionKind.APPROVE,
                    reviewer_identity="Another Reviewer",
                    rationale="A conflicting second decision must be rejected.",
                ),
                approver_identity="Another Approver",
            )
        )


def _workflow(tmp_path, suffix):
    investigations = SQLiteInvestigationRepository(
        tmp_path / f"{suffix}-investigations.db"
    )
    ledger = SQLiteReviewLedger(tmp_path / f"{suffix}-review.db")
    workflow = AuthoritativeFixtureLangGraphWorkflow(
        service=_ReviewRoutedService(
            repository=investigations,
            model_provider=DeterministicModelProvider(),
            search_provider=DeterministicSearchProvider(),
        ),
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / f"{suffix}-langgraph.db",
        state_checkpoint_path=tmp_path / f"{suffix}-state.db",
        review_ledger=ledger,
    )
    return workflow, ledger
