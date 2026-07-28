"""Stage 7.4 append-only review-ledger integration tests."""

import sqlite3
from uuid import uuid4

import pytest

from claim_polygraph_ng.domain.graph import ReviewDecisionKind
from claim_polygraph_ng.domain.models import VerdictLabel
from claim_polygraph_ng.domain.review import (
    ApprovalDecision,
    ApprovalRecord,
    AuthoritativeChangeKind,
    ReviewerDecisionRecord,
    ReviewFinding,
    ReviewFindingKind,
    ReviewRequest,
    VerdictRevision,
)
from claim_polygraph_ng.persistence.review import (
    ReviewConcurrencyError,
    ReviewPolicyError,
    SQLiteReviewLedger,
)


def _request() -> ReviewRequest:
    return ReviewRequest(
        investigation_id=uuid4(),
        graph_thread_id=str(uuid4()),
        claim_id=uuid4(),
        reason="Citation assurance requires review.",
        created_by="Citation router",
    )


def _decision(request: ReviewRequest) -> ReviewerDecisionRecord:
    return ReviewerDecisionRecord(
        decision_id=uuid4(),
        request_id=request.request_id,
        kind=ReviewDecisionKind.REVISE,
        reviewer_identity="Md Moshiur Rahman",
        rationale="The evidence supports a narrower verdict.",
        proposed_verdict=VerdictLabel.MIXED,
    )


def test_complete_review_is_append_only_replayable_and_hash_chained(tmp_path) -> None:
    path = tmp_path / "review.db"
    ledger = SQLiteReviewLedger(path)
    ledger.initialize()
    request = ledger.create_request(_request())
    finding = ReviewFinding(
        request_id=request.request_id,
        kind=ReviewFindingKind.CONTEXT,
        summary="The temporal qualifier is material.",
        evidence_ids=(uuid4(),),
        recorded_by="Deterministic challenger",
    )
    ledger.add_finding(finding, expected_sequence=1)
    decision = _decision(request)
    ledger.record_decision(decision, expected_sequence=2)
    approval = ApprovalRecord(
        request_id=request.request_id,
        decision_record_id=decision.record_id,
        approver_identity="Md Rashedul Islam",
        decision=ApprovalDecision.APPROVE,
        rationale="The proposed revision follows the reviewed evidence.",
    )
    ledger.record_approval(approval, expected_sequence=3)
    original_id = uuid4()
    revision = VerdictRevision(
        request_id=request.request_id,
        decision_record_id=decision.record_id,
        approval_id=approval.approval_id,
        original_verdict_id=original_id,
        original_verdict=VerdictLabel.SUPPORTED,
        revised_verdict=VerdictLabel.MIXED,
        change_kind=AuthoritativeChangeKind.INVESTIGATION_VERDICT,
        rationale="Preserve the original and append the approved revision.",
    )
    ledger.record_revision(revision, expected_sequence=4)

    replayed = SQLiteReviewLedger(path).load(request.request_id)
    assert replayed.chain_valid
    assert [event.sequence for event in replayed.events] == [1, 2, 3, 4, 5]
    assert replayed.revisions[0].original_verdict_id == original_id
    assert replayed.revisions[0].original_verdict is VerdictLabel.SUPPORTED

    with (
        sqlite3.connect(path) as connection,
        pytest.raises(sqlite3.IntegrityError, match="append-only"),
    ):
        connection.execute(
            "UPDATE verdict_revisions SET payload = '{}' WHERE entity_id = ?",
            (str(revision.revision_id),),
        )


def test_stale_writer_and_same_person_approval_are_rejected(tmp_path) -> None:
    ledger = SQLiteReviewLedger(tmp_path / "review.db")
    ledger.initialize()
    request = ledger.create_request(_request())
    decision = _decision(request)
    with pytest.raises(ReviewConcurrencyError, match="stale"):
        ledger.record_decision(decision, expected_sequence=0)
    ledger.record_decision(decision, expected_sequence=1)
    approval = ApprovalRecord(
        request_id=request.request_id,
        decision_record_id=decision.record_id,
        approver_identity="md moshiur rahman",
        decision=ApprovalDecision.APPROVE,
        rationale="Self approval must not be accepted.",
    )
    with pytest.raises(ReviewPolicyError, match="distinct"):
        ledger.record_approval(approval, expected_sequence=2)


def test_decision_replay_is_idempotent_but_authoritative_revision_needs_approval(
    tmp_path,
) -> None:
    ledger = SQLiteReviewLedger(tmp_path / "review.db")
    ledger.initialize()
    request = ledger.create_request(_request())
    decision = _decision(request)
    assert ledger.record_decision(decision, expected_sequence=1) == decision
    assert ledger.record_decision(decision, expected_sequence=999) == decision
    revision = VerdictRevision(
        request_id=request.request_id,
        decision_record_id=decision.record_id,
        original_verdict_id=uuid4(),
        original_verdict=VerdictLabel.SUPPORTED,
        revised_verdict=VerdictLabel.MIXED,
        change_kind=AuthoritativeChangeKind.BENCHMARK_TRUTH,
        rationale="An authoritative benchmark change requires separation of duties.",
    )
    with pytest.raises(ReviewPolicyError, match="require approval"):
        ledger.record_revision(revision, expected_sequence=2)
