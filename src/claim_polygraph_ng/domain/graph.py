"""Typed contracts for the optional Phase 7 LangGraph workflow."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.models import VerdictLabel


class GraphNode(StrEnum):
    """Bounded nodes exposed by the Stage 7 investigation graph."""

    NORMALIZE = "normalize"
    RESEARCH = "research"
    CONSOLIDATE = "consolidate"
    VERIFY_CONTEXT = "verify_context"
    BUILD_ARGUMENT_LEDGER = "build_argument_ledger"
    DRAFT_VERDICT = "draft_verdict"
    AUDIT_CITATIONS = "audit_citations"
    ASSESS_READINESS = "assess_readiness"
    ROUTE_REVIEW = "route_review"
    INTERRUPT_FOR_REVIEW = "interrupt_for_review"
    REQUEST_MORE_EVIDENCE = "request_more_evidence"
    REJECT = "reject"
    FINALIZE = "finalize"


class GraphRoute(StrEnum):
    """Declared route selected after deterministic readiness assessment."""

    FINALIZE = "finalize"
    HUMAN_REVIEW = "human_review"


class GraphRunStatus(StrEnum):
    """Externally visible result of one fixture graph invocation."""

    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"


class ReviewDecisionKind(StrEnum):
    """Supported human decisions for a durable review interruption."""

    APPROVE = "approve"
    REVISE = "revise"
    REQUEST_EVIDENCE = "request_evidence"
    REJECT = "reject"


class DurableGraphStatus(StrEnum):
    """Persisted externally visible status of the durable graph."""

    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"
    REJECTED = "rejected"


class GraphExecutionBudget(DomainModel):
    """Hard Stage 7.1 limits; fixture mode permits no provider operation."""

    maximum_steps: int = Field(default=12, ge=1, le=100)
    maximum_model_calls: int = Field(default=0, ge=0, le=100)
    maximum_search_calls: int = Field(default=0, ge=0, le=100)
    maximum_cost_usd: float = Field(default=0.0, ge=0, le=1_000)


class FixtureGraphRequest(DomainModel):
    """Approved evidence and verdict replayed by the zero-cost graph."""

    graph_run_id: UUID = Field(default_factory=uuid4)
    claim_text: str = Field(min_length=3, max_length=10_000)
    approved_evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    authoritative_verdict: VerdictLabel
    review_required: bool = False
    review_reason: str | None = Field(default=None, min_length=3, max_length=1_000)
    budget: GraphExecutionBudget = Field(default_factory=GraphExecutionBudget)

    @model_validator(mode="after")
    def validate_review_and_fixture_budget(self) -> "FixtureGraphRequest":
        if len(set(self.approved_evidence_ids)) != len(self.approved_evidence_ids):
            raise ValueError("approved evidence IDs must be unique")
        if self.review_required != (self.review_reason is not None):
            raise ValueError("only review-required requests need a review reason")
        if (
            self.budget.maximum_model_calls
            or self.budget.maximum_search_calls
            or self.budget.maximum_cost_usd
        ):
            raise ValueError("the Stage 7.1 fixture graph must remain zero-cost")
        return self


class GraphRouteDecision(DomainModel):
    """Auditable deterministic route decision."""

    route: GraphRoute
    reason: str = Field(min_length=3, max_length=1_000)


class ReviewInterruptPayload(DomainModel):
    """JSON-safe payload surfaced by LangGraph's real interrupt primitive."""

    thread_id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=3, max_length=1_000)
    claim_text: str = Field(min_length=3, max_length=10_000)
    provisional_verdict: VerdictLabel
    approved_evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    route_reason: str = Field(min_length=3, max_length=1_000)
    allowed_decisions: tuple[ReviewDecisionKind, ...] = (
        ReviewDecisionKind.APPROVE,
        ReviewDecisionKind.REVISE,
        ReviewDecisionKind.REQUEST_EVIDENCE,
        ReviewDecisionKind.REJECT,
    )


class ReviewDecision(DomainModel):
    """Immutable typed value supplied through ``Command(resume=...)``."""

    decision_id: UUID = Field(default_factory=uuid4)
    kind: ReviewDecisionKind
    reviewer_identity: str = Field(min_length=3, max_length=300)
    rationale: str = Field(min_length=3, max_length=5_000)
    revised_verdict: VerdictLabel | None = None

    @model_validator(mode="after")
    def revision_requires_label(self) -> "ReviewDecision":
        if (self.kind is ReviewDecisionKind.REVISE) != (
            self.revised_verdict is not None
        ):
            raise ValueError("only revise decisions require a revised verdict")
        return self


class DurableGraphSnapshot(DomainModel):
    """Validated state returned before and after durable resume."""

    thread_id: str = Field(min_length=1, max_length=200)
    status: DurableGraphStatus
    authoritative_verdict: VerdictLabel
    final_verdict: VerdictLabel | None = None
    approved_evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    completed_nodes: tuple[GraphNode, ...]
    operation_counts: dict[GraphNode, int]
    interrupt: ReviewInterruptPayload | None = None
    applied_decision_id: UUID | None = None
    reviewer_identity: str | None = None
    checkpointed: bool = True

    @model_validator(mode="after")
    def validate_durable_status(self) -> "DurableGraphSnapshot":
        if self.status is DurableGraphStatus.REVIEW_REQUIRED:
            if self.interrupt is None or self.final_verdict is not None:
                raise ValueError("review-required state needs an interrupt and no final verdict")
        elif self.interrupt is not None:
            raise ValueError("only review-required state may expose an interrupt")
        if self.status is DurableGraphStatus.COMPLETED and self.final_verdict is None:
            raise ValueError("completed durable graph requires a final verdict")
        if any(count != 1 for count in self.operation_counts.values()):
            raise ValueError("durable fixture nodes may execute at most once")
        return self


class FixtureGraphResult(DomainModel):
    """Validated output proving equivalence and evidence containment."""

    graph_run_id: UUID
    status: GraphRunStatus
    authoritative_verdict: VerdictLabel
    approved_evidence_ids: tuple[UUID, ...]
    consumed_evidence_ids: tuple[UUID, ...]
    completed_nodes: tuple[GraphNode, ...]
    route_decision: GraphRouteDecision
    model_calls: int = Field(default=0, ge=0)
    search_calls: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def enforce_fixture_boundaries(self) -> "FixtureGraphResult":
        if set(self.consumed_evidence_ids) - set(self.approved_evidence_ids):
            raise ValueError("graph consumed evidence outside the approved packet")
        if (
            self.model_calls
            or self.search_calls
            or self.estimated_cost_usd
        ):
            raise ValueError("fixture result cannot contain provider usage")
        if len(self.completed_nodes) != len(set(self.completed_nodes)):
            raise ValueError("fixture graph nodes must execute at most once")
        expected = (
            GraphRunStatus.REVIEW_REQUIRED
            if self.route_decision.route is GraphRoute.HUMAN_REVIEW
            else GraphRunStatus.COMPLETED
        )
        if self.status is not expected:
            raise ValueError("graph status does not match its route decision")
        return self
