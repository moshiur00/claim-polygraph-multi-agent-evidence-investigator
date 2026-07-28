"""Immutable human-review and approval contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.graph import ReviewDecisionKind
from claim_polygraph_ng.domain.models import VerdictLabel


def _now() -> datetime:
    return datetime.now(UTC)


class ReviewFindingKind(StrEnum):
    CITATION = "citation"
    CONTEXT = "context"
    PROVENANCE = "provenance"
    VERDICT = "verdict"
    OTHER = "other"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class AuthoritativeChangeKind(StrEnum):
    INVESTIGATION_VERDICT = "investigation_verdict"
    BENCHMARK_TRUTH = "benchmark_truth"


class ReviewAuditAction(StrEnum):
    REQUEST_CREATED = "request_created"
    FINDING_ADDED = "finding_added"
    DECISION_RECORDED = "decision_recorded"
    APPROVAL_RECORDED = "approval_recorded"
    REVISION_RECORDED = "revision_recorded"


class ReviewRequest(DomainModel):
    request_id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    graph_thread_id: str = Field(min_length=1, max_length=200)
    claim_id: UUID
    reason: str = Field(min_length=3, max_length=2_000)
    created_by: str = Field(min_length=3, max_length=300)
    created_at: datetime = Field(default_factory=_now)


class ReviewFinding(DomainModel):
    finding_id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    kind: ReviewFindingKind
    summary: str = Field(min_length=3, max_length=5_000)
    evidence_ids: tuple[UUID, ...] = ()
    recorded_by: str = Field(min_length=3, max_length=300)
    created_at: datetime = Field(default_factory=_now)


class ReviewerDecisionRecord(DomainModel):
    record_id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    request_id: UUID
    kind: ReviewDecisionKind
    reviewer_identity: str = Field(min_length=3, max_length=300)
    rationale: str = Field(min_length=3, max_length=5_000)
    proposed_verdict: VerdictLabel | None = None
    created_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def validate_revision(self) -> "ReviewerDecisionRecord":
        if (self.kind is ReviewDecisionKind.REVISE) != (self.proposed_verdict is not None):
            raise ValueError("only revise decisions require a proposed verdict")
        return self


class ApprovalRecord(DomainModel):
    approval_id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    decision_record_id: UUID
    approver_identity: str = Field(min_length=3, max_length=300)
    decision: ApprovalDecision
    rationale: str = Field(min_length=3, max_length=5_000)
    created_at: datetime = Field(default_factory=_now)


class VerdictRevision(DomainModel):
    revision_id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    decision_record_id: UUID
    approval_id: UUID | None = None
    original_verdict_id: UUID
    original_verdict: VerdictLabel
    revised_verdict: VerdictLabel
    change_kind: AuthoritativeChangeKind
    rationale: str = Field(min_length=3, max_length=5_000)
    created_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def require_real_change(self) -> "VerdictRevision":
        if self.original_verdict is self.revised_verdict:
            raise ValueError("a verdict revision must change the verdict label")
        return self


class ReviewAuditEvent(DomainModel):
    request_id: UUID
    sequence: int = Field(ge=1)
    action: ReviewAuditAction
    entity_id: UUID
    actor_identity: str = Field(min_length=3, max_length=300)
    occurred_at: datetime
    payload_json: str
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_event_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewAuditTrail(DomainModel):
    request: ReviewRequest
    findings: tuple[ReviewFinding, ...] = ()
    decisions: tuple[ReviewerDecisionRecord, ...] = ()
    approvals: tuple[ApprovalRecord, ...] = ()
    revisions: tuple[VerdictRevision, ...] = ()
    events: tuple[ReviewAuditEvent, ...] = ()
    chain_valid: bool
