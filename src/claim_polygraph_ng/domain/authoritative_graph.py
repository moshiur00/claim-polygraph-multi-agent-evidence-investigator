"""Versioned durable state for the unified authoritative investigation graph."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.graph import (
    DurableAssignmentReference,
    DurableComponentReference,
    DurableEvidenceFamilyReference,
    DurableRequirementReference,
    DurableResultReference,
    DurableUnresolvedQuestion,
)
from claim_polygraph_ng.domain.operations import ArtifactReference, AuthoritativeOperation
from claim_polygraph_ng.domain.research import ResearchBudget, ResearchConsumption
from claim_polygraph_ng.domain.verification import AssertionConstructionState


def graph_utc_now() -> datetime:
    return datetime.now(UTC)


class AuthoritativeGraphPhase(StrEnum):
    CREATED = "created"
    CLAIM_ANALYSIS = "claim_analysis"
    PLANNING = "planning"
    RESEARCH = "research"
    VERIFICATION = "verification"
    ARGUMENTS = "arguments"
    JUDGMENT = "judgment"
    CITATION_ASSURANCE = "citation_assurance"
    READINESS = "readiness"
    REVIEW = "review"
    FINALIZATION = "finalization"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaidOperationReceiptStatus(StrEnum):
    RESERVED = "reserved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_PERMANENT = "failed_permanent"
    CANCELLED = "cancelled"
    AMBIGUOUS = "ambiguous"


class PaidOperationReceiptReference(DomainModel):
    receipt_id: UUID
    operation: AuthoritativeOperation
    provider: str = Field(min_length=2, max_length=200)
    canonical_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: PaidOperationReceiptStatus
    result_artifact: ArtifactReference | None = None


class GraphFailureReference(DomainModel):
    failure_id: UUID
    operation: AuthoritativeOperation
    retryable: bool
    error_type: str = Field(min_length=2, max_length=200)
    safe_summary: str = Field(min_length=2, max_length=1_000)
    attempt_number: int = Field(ge=1)


def empty_research_consumption() -> ResearchConsumption:
    return ResearchConsumption(
        completed_rounds=0,
        role_activations=0,
        search_calls=0,
        fetched_pages=0,
        model_calls=0,
        total_tokens=0,
        duration_seconds=0,
        estimated_cost_usd=0,
    )


class AuthoritativeInvestigationGraphState(DomainModel):
    """Compact checkpoint containing references, routing and durable consumption."""

    schema_version: int = Field(default=1, ge=1, le=1)
    graph_version: str = Field(
        default="authoritative-investigation-graph-v1",
        pattern=r"^authoritative-investigation-graph-v1$",
    )
    thread_id: str = Field(min_length=1, max_length=200)
    investigation_id: UUID
    parent_investigation_id: UUID | None = None
    parent_claim_id: UUID | None = None
    phase: AuthoritativeGraphPhase = AuthoritativeGraphPhase.CREATED
    checkpoint_sequence: int = Field(default=0, ge=0)
    completed_operations: tuple[AuthoritativeOperation, ...] = ()
    operation_versions: dict[AuthoritativeOperation, int] = Field(default_factory=dict)
    artifacts: tuple[ArtifactReference, ...] = Field(default=(), max_length=2_000)
    components: tuple[DurableComponentReference, ...] = Field(default=(), max_length=32)
    requirements: tuple[DurableRequirementReference, ...] = Field(default=(), max_length=128)
    assignments: tuple[DurableAssignmentReference, ...] = Field(default=(), max_length=100)
    research_results: tuple[DurableResultReference, ...] = Field(default=(), max_length=100)
    evidence_families: tuple[DurableEvidenceFamilyReference, ...] = Field(
        default=(), max_length=250
    )
    approved_evidence_ids: tuple[UUID, ...] = Field(default=(), max_length=1_000)
    verification_construction_ids: tuple[UUID, ...] = Field(default=(), max_length=128)
    verification_construction_states: dict[UUID, AssertionConstructionState] = Field(
        default_factory=dict
    )
    defender_result_id: UUID | None = None
    challenger_result_id: UUID | None = None
    reconciled_ledger_ref: ArtifactReference | None = None
    proposed_verdict_ref: ArtifactReference | None = None
    enforced_verdict_ref: ArtifactReference | None = None
    citation_assurance_ref: ArtifactReference | None = None
    readiness_ref: ArtifactReference | None = None
    review_request_ids: tuple[UUID, ...] = ()
    review_decision_ids: tuple[UUID, ...] = ()
    budget: ResearchBudget = Field(default_factory=ResearchBudget)
    consumption: ResearchConsumption = Field(default_factory=empty_research_consumption)
    paid_receipts: tuple[PaidOperationReceiptReference, ...] = Field(
        default=(), max_length=500
    )
    unresolved_questions: tuple[DurableUnresolvedQuestion, ...] = Field(
        default=(), max_length=250
    )
    failures: tuple[GraphFailureReference, ...] = Field(default=(), max_length=100)
    final_report_ref: ArtifactReference | None = None
    publication_decision_ref: ArtifactReference | None = None
    publication_blocked: bool = False
    publication_blocking_reasons: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=graph_utc_now)
    updated_at: datetime = Field(default_factory=graph_utc_now)

    @model_validator(mode="after")
    def validate_checkpoint_references(self) -> AuthoritativeInvestigationGraphState:
        _unique(self.completed_operations, "completed operations")
        if set(self.operation_versions) != set(self.completed_operations):
            raise ValueError("every completed operation requires exactly one version")
        if any(version < 1 for version in self.operation_versions.values()):
            raise ValueError("operation versions must be positive")
        artifact_keys = tuple(
            (item.artifact_type, item.artifact_id) for item in self.artifacts
        )
        _unique(artifact_keys, "artifact references")
        if any(item.investigation_id != self.investigation_id for item in self.artifacts):
            raise ValueError("all artifact references must belong to the investigation")
        artifact_ids = {item.artifact_id for item in self.artifacts}
        for reference in (
            self.reconciled_ledger_ref,
            self.proposed_verdict_ref,
            self.enforced_verdict_ref,
            self.citation_assurance_ref,
            self.readiness_ref,
            self.final_report_ref,
            self.publication_decision_ref,
        ):
            if reference is not None and reference.artifact_id not in artifact_ids:
                raise ValueError("named artifact references must exist in the artifact inventory")

        component_ids = _unique(
            tuple(item.component_id for item in self.components), "component IDs"
        )
        requirements = {item.requirement_id: item for item in self.requirements}
        if len(requirements) != len(self.requirements):
            raise ValueError("requirement IDs must be unique")
        if any(item.component_id not in component_ids for item in self.requirements):
            raise ValueError("requirements must reference known components")
        assignments = {item.assignment_id: item for item in self.assignments}
        if len(assignments) != len(self.assignments):
            raise ValueError("assignment IDs must be unique")
        for assignment in self.assignments:
            if assignment.component_id not in component_ids:
                raise ValueError("assignments must reference known components")
            if not set(assignment.requirement_ids) <= set(requirements):
                raise ValueError("assignments must reference known requirements")
        _unique(tuple(item.result_id for item in self.research_results), "research result IDs")
        for result in self.research_results:
            assignment = assignments.get(result.assignment_id)
            if assignment is None or assignment.component_id != result.component_id:
                raise ValueError("research results must reference matching assignments")
            if not set(result.unresolved_requirement_ids) <= set(requirements):
                raise ValueError("results must reference known requirements")
        _unique(
            tuple(item.family_id for item in self.evidence_families),
            "evidence family IDs",
        )
        _unique(self.approved_evidence_ids, "approved evidence IDs")
        if not set(self.approved_evidence_ids) <= artifact_ids:
            raise ValueError("approved evidence IDs must exist in the artifact inventory")
        _unique(self.verification_construction_ids, "verification construction IDs")
        if set(self.verification_construction_states) != set(
            self.verification_construction_ids
        ):
            raise ValueError(
                "every verification construction requires exactly one durable state"
            )
        if (
            self.defender_result_id is not None
            and self.defender_result_id == self.challenger_result_id
        ):
            raise ValueError("defender and challenger results must be independent")
        _unique(self.review_request_ids, "review request IDs")
        _unique(self.review_decision_ids, "review decision IDs")
        _unique(tuple(item.receipt_id for item in self.paid_receipts), "paid receipt IDs")
        if any(
            item.result_artifact is not None
            and item.result_artifact.artifact_id not in artifact_ids
            for item in self.paid_receipts
        ):
            raise ValueError("paid receipt results must exist in the artifact inventory")
        _unique(tuple(item.failure_id for item in self.failures), "failure IDs")
        _unique(
            tuple(item.question_id for item in self.unresolved_questions),
            "unresolved question IDs",
        )
        if self.consumption.completed_rounds > self.budget.maximum_rounds:
            raise ValueError("completed research rounds exceed budget")
        if self.consumption.search_calls > self.budget.maximum_search_calls:
            raise ValueError("search consumption exceeds budget")
        if self.consumption.model_calls > self.budget.maximum_model_calls:
            raise ValueError("model consumption exceeds budget")
        if (
            self.budget.maximum_total_tokens > 0
            and self.consumption.total_tokens > self.budget.maximum_total_tokens
        ):
            raise ValueError("token consumption exceeds budget")
        if self.consumption.duration_seconds > self.budget.maximum_duration_seconds:
            raise ValueError("duration consumption exceeds budget")
        if self.consumption.role_activations > (
            self.budget.maximum_role_activations_per_component
            * max(1, len(self.components))
        ):
            raise ValueError("role activation consumption exceeds budget")
        if self.consumption.fetched_pages > (
            self.budget.maximum_pages_per_component * max(1, len(self.components))
        ):
            raise ValueError("page-fetch consumption exceeds budget")
        if self.consumption.estimated_cost_usd > self.budget.maximum_cost_usd:
            raise ValueError("cost consumption exceeds budget")
        if self.phase is AuthoritativeGraphPhase.COMPLETE and (
            AuthoritativeOperation.FINALIZE_REPORT not in self.completed_operations
            or self.final_report_ref is None
        ):
            raise ValueError("complete state requires finalization and a report reference")
        if self.publication_blocked != bool(self.publication_blocking_reasons):
            raise ValueError("publication blocking requires explicit reasons")
        return self


def _unique(values: tuple, label: str) -> set:
    unique = set(values)
    if len(unique) != len(values):
        raise ValueError(f"{label} must be unique")
    return unique
