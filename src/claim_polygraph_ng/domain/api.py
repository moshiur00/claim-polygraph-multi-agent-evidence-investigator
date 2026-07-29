"""Typed HTTP API contracts for the Phase 7 console."""

from uuid import UUID

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.graph import (
    DurableGraphSnapshot,
    FixtureGraphRequest,
    ReviewDecision,
)
from claim_polygraph_ng.domain.review import (
    ApprovalRecord,
    ReviewAuditTrail,
    ReviewRequest,
    VerdictRevision,
)
from claim_polygraph_ng.domain.jobs import DurableJob, JobAuditEvent


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
    api_version: str = "8.1"
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
