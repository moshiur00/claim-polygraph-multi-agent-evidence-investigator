"""Typed contracts for the optional Phase 7 LangGraph workflow."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.argument import ArgumentLedger
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.models import VerdictLabel
from claim_polygraph_ng.domain.research import (
    ResearchBudget,
    ResearchConsumption,
    ResearchRequirementKind,
    ResearchRole,
)


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


class VerificationConstructionDisposition(StrEnum):
    """Reviewer disposition for one persisted assertion-construction attempt."""

    ACCEPT = "accept"
    CORRECT = "correct"
    NOT_APPLICABLE = "not_applicable"
    REQUEST_EVIDENCE = "request_evidence"


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


class DurableComponentReference(DomainModel):
    """Bounded component identity retained in a graph checkpoint."""

    component_id: UUID
    parent_claim_id: UUID
    claim_summary: str = Field(min_length=3, max_length=500)


class DurableRequirementReference(DomainModel):
    """Research requirement identity without embedding a mutable artifact."""

    requirement_id: UUID
    component_id: UUID
    kind: ResearchRequirementKind
    rationale_summary: str = Field(min_length=3, max_length=500)


class DurableAssignmentReference(DomainModel):
    """Coordinator assignment reference sufficient for deterministic recovery."""

    assignment_id: UUID
    component_id: UUID
    role: ResearchRole
    round_number: int = Field(ge=1, le=5)
    requirement_ids: tuple[UUID, ...] = Field(min_length=1, max_length=16)


class DurableResultReference(DomainModel):
    """Stored role-result references; evidence text remains outside graph state."""

    result_id: UUID
    assignment_id: UUID
    component_id: UUID
    source_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    evidence_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    unresolved_requirement_ids: tuple[UUID, ...] = Field(default=(), max_length=16)
    failure_summary: str | None = Field(default=None, max_length=500)


class DurableEvidenceFamilyReference(DomainModel):
    """Evidence-family membership using only persisted artifact identifiers."""

    family_id: UUID
    source_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)
    evidence_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)
    grouping_summary: str = Field(min_length=3, max_length=500)


class DurableUnresolvedQuestion(DomainModel):
    """Bounded open question carried into a later research round or review."""

    question_id: UUID = Field(default_factory=uuid4)
    component_id: UUID
    requirement_ids: tuple[UUID, ...] = Field(default=(), max_length=16)
    question_summary: str = Field(min_length=3, max_length=500)


class DurableMultiAgentGraphState(DomainModel):
    """Compact, cross-reference-validated multi-agent checkpoint payload."""

    schema_version: int = Field(default=1, ge=1, le=1)
    investigation_id: UUID
    parent_claim_id: UUID
    components: tuple[DurableComponentReference, ...] = Field(min_length=1, max_length=8)
    requirements: tuple[DurableRequirementReference, ...] = Field(default=(), max_length=64)
    assignments: tuple[DurableAssignmentReference, ...] = Field(default=(), max_length=35)
    results: tuple[DurableResultReference, ...] = Field(default=(), max_length=35)
    stored_source_ids: tuple[UUID, ...] = Field(default=(), max_length=500)
    stored_evidence_ids: tuple[UUID, ...] = Field(default=(), max_length=500)
    approved_evidence_ids: tuple[UUID, ...] = Field(default=(), max_length=500)
    argument_role_result_ids: tuple[UUID, ...] = Field(default=(), max_length=2)
    reconciled_argument_ledger: ArgumentLedger | None = None
    evidence_families: tuple[DurableEvidenceFamilyReference, ...] = Field(
        default=(), max_length=100
    )
    budget: ResearchBudget = Field(default_factory=ResearchBudget)
    consumption: ResearchConsumption = Field(
        default_factory=lambda: ResearchConsumption(
            completed_rounds=0,
            role_activations=0,
            search_calls=0,
            fetched_pages=0,
            model_calls=0,
            estimated_cost_usd=0,
        )
    )
    unresolved_questions: tuple[DurableUnresolvedQuestion, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def validate_research_references(self) -> "DurableMultiAgentGraphState":
        component_ids = _unique_ids(self.components, "component_id", "component")
        if any(item.parent_claim_id != self.parent_claim_id for item in self.components):
            raise ValueError("every component must reference the parent claim")

        requirements = _indexed(self.requirements, "requirement_id", "research requirement")
        if any(item.component_id not in component_ids for item in self.requirements):
            raise ValueError("research requirements must reference known components")

        assignments = _indexed(self.assignments, "assignment_id", "assignment")
        for assignment in self.assignments:
            if assignment.component_id not in component_ids:
                raise ValueError("assignments must reference known components")
            for requirement_id in assignment.requirement_ids:
                requirement = requirements.get(requirement_id)
                if requirement is None or requirement.component_id != assignment.component_id:
                    raise ValueError("assignment requirements must exist and match its component")

        source_ids = _unique_values(self.stored_source_ids, "stored source")
        evidence_ids = _unique_values(self.stored_evidence_ids, "stored evidence")
        approved_evidence_ids = _unique_values(self.approved_evidence_ids, "approved evidence")
        if not approved_evidence_ids <= evidence_ids:
            raise ValueError("approved evidence must reference stored evidence")
        _unique_values(self.argument_role_result_ids, "argument role result")
        if self.reconciled_argument_ledger is not None:
            if self.reconciled_argument_ledger.claim_id not in component_ids:
                raise ValueError("reconciled ledger must reference a known component")
            if set(self.reconciled_argument_ledger.approved_evidence_ids) != (
                approved_evidence_ids
            ):
                raise ValueError("reconciled ledger must use exactly the approved evidence packet")
        _unique_ids(self.results, "result_id", "result")
        for result in self.results:
            assignment = assignments.get(result.assignment_id)
            if assignment is None or assignment.component_id != result.component_id:
                raise ValueError("results must reference a matching assignment")
            if not set(result.source_ids) <= source_ids:
                raise ValueError("result source IDs must reference stored sources")
            if not set(result.evidence_ids) <= evidence_ids:
                raise ValueError("result evidence IDs must reference stored evidence")
            if not set(result.unresolved_requirement_ids) <= set(requirements):
                raise ValueError("unresolved result requirements must reference known requirements")

        _unique_ids(self.evidence_families, "family_id", "evidence family")
        for family in self.evidence_families:
            if not set(family.source_ids) <= source_ids:
                raise ValueError("evidence families must reference stored sources")
            if not set(family.evidence_ids) <= evidence_ids:
                raise ValueError("evidence families must reference stored evidence")

        _unique_ids(self.unresolved_questions, "question_id", "unresolved question")
        for question in self.unresolved_questions:
            if question.component_id not in component_ids:
                raise ValueError("unresolved questions must reference known components")
            if not set(question.requirement_ids) <= set(requirements):
                raise ValueError("unresolved questions must reference known requirements")

        if self.consumption.completed_rounds > self.budget.maximum_rounds:
            raise ValueError("completed rounds exceed the research budget")
        if self.consumption.search_calls > self.budget.maximum_search_calls:
            raise ValueError("search consumption exceeds the research budget")
        if self.consumption.model_calls > self.budget.maximum_model_calls:
            raise ValueError("model consumption exceeds the research budget")
        if (
            self.budget.maximum_total_tokens > 0
            and self.consumption.total_tokens > self.budget.maximum_total_tokens
        ):
            raise ValueError("token consumption exceeds the research budget")
        if self.consumption.duration_seconds > self.budget.maximum_duration_seconds:
            raise ValueError("duration consumption exceeds the research budget")
        if self.consumption.role_activations > (
            self.budget.maximum_role_activations_per_component * len(self.components)
        ):
            raise ValueError("role activations exceed the research budget")
        if self.consumption.fetched_pages > (
            self.budget.maximum_pages_per_component * len(self.components)
        ):
            raise ValueError("fetched pages exceed the research budget")
        if self.consumption.estimated_cost_usd > self.budget.maximum_cost_usd:
            raise ValueError("cost consumption exceeds the research budget")
        return self


class FixtureGraphRequest(DomainModel):
    """Approved evidence and verdict replayed by the zero-cost graph."""

    graph_run_id: UUID = Field(default_factory=uuid4)
    claim_text: str = Field(min_length=3, max_length=10_000)
    approved_evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    authoritative_verdict: VerdictLabel
    review_required: bool = False
    review_reason: str | None = Field(default=None, min_length=3, max_length=1_000)
    budget: GraphExecutionBudget = Field(default_factory=GraphExecutionBudget)
    research_state: DurableMultiAgentGraphState | None = None

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
        if self.research_state is not None:
            if self.research_state.investigation_id != self.graph_run_id:
                raise ValueError("research state must reference the graph investigation")
            if not set(self.research_state.approved_evidence_ids) <= set(
                self.approved_evidence_ids
            ):
                raise ValueError("research-state approvals must remain inside the approved packet")
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
    approved_evidence_ids: tuple[UUID, ...] = ()
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
    verification_construction_id: UUID | None = None
    verification_disposition: VerificationConstructionDisposition | None = None
    corrected_left_subject: str | None = Field(default=None, min_length=1, max_length=500)
    corrected_right_subject: str | None = Field(default=None, min_length=1, max_length=500)
    corrected_comparator: str | None = Field(
        default=None,
        pattern=r"^[a-z_]+$",
        max_length=100,
    )
    corrected_claim_text_span: str | None = Field(
        default=None,
        min_length=1,
        max_length=2_000,
    )
    corrected_value: str | None = Field(default=None, min_length=1, max_length=200)
    corrected_unit: str | None = Field(default=None, min_length=1, max_length=100)
    corrected_evidence_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def revision_requires_label(self) -> "ReviewDecision":
        if (self.kind is ReviewDecisionKind.REVISE) != (self.revised_verdict is not None):
            raise ValueError("only revise decisions require a revised verdict")
        has_disposition = self.verification_disposition is not None
        if has_disposition != (self.verification_construction_id is not None):
            raise ValueError(
                "verification disposition and construction ID must be supplied together"
            )
        corrections = (
            self.corrected_left_subject,
            self.corrected_right_subject,
            self.corrected_comparator,
            self.corrected_claim_text_span,
            self.corrected_value,
            self.corrected_unit,
            *self.corrected_evidence_ids,
        )
        if any(corrections) and (
            self.verification_disposition
            is not VerificationConstructionDisposition.CORRECT
        ):
            raise ValueError("corrected operands require the correct disposition")
        if len(set(self.corrected_evidence_ids)) != len(
            self.corrected_evidence_ids
        ):
            raise ValueError("corrected evidence IDs must be unique")
        if (
            self.verification_disposition
            is VerificationConstructionDisposition.CORRECT
            and not any(corrections)
        ):
            raise ValueError("correct disposition requires at least one correction")
        if (
            self.verification_disposition
            is VerificationConstructionDisposition.REQUEST_EVIDENCE
            and self.kind is not ReviewDecisionKind.REQUEST_EVIDENCE
        ):
            raise ValueError("request-evidence disposition requires request_evidence")
        if self.verification_disposition in {
            VerificationConstructionDisposition.ACCEPT,
            VerificationConstructionDisposition.NOT_APPLICABLE,
        } and self.kind is not ReviewDecisionKind.APPROVE:
            raise ValueError("accept and not-applicable dispositions require approval")
        if (
            self.verification_disposition
            is VerificationConstructionDisposition.CORRECT
            and self.kind is not ReviewDecisionKind.REVISE
        ):
            raise ValueError("correct disposition requires a revise decision")
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
    research_state: DurableMultiAgentGraphState | None = None
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


def reconstruct_multi_agent_graph_state(
    payload: dict[str, object],
) -> DurableMultiAgentGraphState:
    """Rebuild and validate a checkpoint without provider or repository calls."""

    return DurableMultiAgentGraphState.model_validate(payload)


def _indexed(items, field: str, label: str) -> dict[UUID, object]:
    values = {getattr(item, field): item for item in items}
    if len(values) != len(items):
        raise ValueError(f"{label} IDs must be unique")
    return values


def _unique_ids(items, field: str, label: str) -> set[UUID]:
    return set(_indexed(items, field, label))


def _unique_values(items: tuple[UUID, ...], label: str) -> set[UUID]:
    values = set(items)
    if len(values) != len(items):
        raise ValueError(f"{label} IDs must be unique")
    return values


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
        if self.model_calls or self.search_calls or self.estimated_cost_usd:
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
