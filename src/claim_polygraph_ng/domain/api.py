"""Typed HTTP API contracts for the Phase 7 console."""

from uuid import UUID

from pydantic import Field

from claim_polygraph_ng.domain.authoritative_graph import (
    AuthoritativeInvestigationGraphState,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.evidence_disposition import (
    EvidenceDispositionInput,
    EvidenceDispositionRecord,
)
from claim_polygraph_ng.domain.graph import (
    DurableGraphSnapshot,
    FixtureGraphRequest,
    ReviewDecision,
    ReviewInterruptPayload,
)
from claim_polygraph_ng.domain.jobs import DurableJob, JobAuditEvent
from claim_polygraph_ng.domain.review import (
    ApprovalRecord,
    ReviewAuditTrail,
    ReviewRequest,
    VerdictRevision,
)


class StartGraphRunRequest(DomainModel):
    investigation_id: UUID
    claim_id: UUID
    graph: FixtureGraphRequest
    review_created_by: str = Field(default="Deterministic review router", min_length=3)


class StartGraphRunResponse(DomainModel):
    graph: DurableGraphSnapshot
    review: ReviewRequest | None = None


class SubmitDecisionRequest(DomainModel):
    expected_sequence: int = Field(ge=1)
    decision: ReviewDecision


class SubmitDecisionResponse(DomainModel):
    graph: DurableGraphSnapshot
    review: ReviewAuditTrail


class SubmitApprovalRequest(DomainModel):
    expected_sequence: int = Field(ge=1)
    approval: ApprovalRecord


class SubmitRevisionRequest(DomainModel):
    expected_sequence: int = Field(ge=1)
    revision: VerdictRevision


class ApiStatus(DomainModel):
    status: str
    api_version: str = "9.10"
    orchestrator: str
    authoritative_service: str = "InvestigationService"
    retrieval_provider: str = "deterministic"
    live_research: bool = False
    model_provider: str = "deterministic"


class CreateInvestigationRequest(DomainModel):
    claim: str = Field(min_length=3, max_length=10_000)
    idempotency_key: str | None = Field(default=None, min_length=3, max_length=300)


class InvestigationJobResponse(DomainModel):
    """Durable asynchronous investigation submission and current state."""

    job: DurableJob
    investigation_id: UUID | None = None
    events: tuple[JobAuditEvent, ...] = ()


class InvestigationUsageSummary(DomainModel):
    """Measured structured-model usage attributed to one investigation."""

    model_calls: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    unpriced_model_calls: int = Field(default=0, ge=0)


class AuthoritativeJobResponse(DomainModel):
    """One truthful view of job, graph, review and publication state."""

    job: DurableJob
    thread_id: str
    investigation_id: UUID | None = None
    graph: AuthoritativeInvestigationGraphState | None = None
    interruption: ReviewInterruptPayload | None = None
    review: ReviewAuditTrail | None = None
    publication_status: str
    verdict: str | None = None
    report_available: bool = False
    usage: InvestigationUsageSummary | None = None
    events: tuple[JobAuditEvent, ...] = ()


class AuthoritativeReviewRequest(DomainModel):
    """Decision used to resume the same authoritative graph and durable job."""

    decision: ReviewDecision
    approver_identity: str | None = Field(default=None, min_length=3, max_length=300)


class SubmitEvidenceDispositionRequest(DomainModel):
    """Distinctly approved, append-only evidence-use decision."""

    disposition: EvidenceDispositionInput
    reviewer_identity: str = Field(min_length=3, max_length=300)
    approver_identity: str = Field(min_length=3, max_length=300)


class EvidenceDispositionResponse(DomainModel):
    record: EvidenceDispositionRecord
