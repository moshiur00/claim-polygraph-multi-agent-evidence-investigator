"""Typed, bounded contracts for Phase 4 specialist research roles."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import ClaimType, EvidenceStance, SourceType
from claim_polygraph_ng.domain.models import AtomicClaim, Evidence, SentenceAudit, Source, Verdict
from claim_polygraph_ng.domain.provenance import EvidenceConsolidation, IndependenceAnalysis


class ResearchRole(StrEnum):
    """Closed set of orchestration roles; roles cannot create new roles."""

    COORDINATOR = "coordinator"
    PRIMARY_SOURCE = "primary_source"
    GENERAL_EVIDENCE = "general_evidence"
    CHALLENGER = "challenger"
    ACADEMIC = "academic"
    FACT_CHECK = "fact_check"
    SUFFICIENCY_CONTROLLER = "sufficiency_controller"


class ResearchPermission(StrEnum):
    """Explicit capabilities that may be granted to one role."""

    PLAN = "plan"
    SEARCH = "search"
    REQUEST_FETCH = "request_fetch"
    CLASSIFY_EVIDENCE = "classify_evidence"
    CONSOLIDATE = "consolidate"
    ASSESS_SUFFICIENCY = "assess_sufficiency"


class ResearchRequirementKind(StrEnum):
    """Material evidence needs used by deterministic routing."""

    COMPONENT_COVERAGE = "component_coverage"
    PRIMARY_SOURCE = "primary_source"
    INDEPENDENT_CORROBORATION = "independent_corroboration"
    CONTRADICTION_OR_QUALIFICATION = "contradiction_or_qualification"
    ACADEMIC_EVIDENCE = "academic_evidence"
    PRIOR_FACT_CHECK = "prior_fact_check"
    TEMPORAL_CONTEXT = "temporal_context"
    NUMERICAL_CONTEXT = "numerical_context"


class ResearchBudget(DomainModel):
    """Hard role-level limits checked before execution."""

    maximum_rounds: int = Field(default=2, ge=1, le=5)
    maximum_concurrent_roles: int = Field(default=3, ge=1, le=7)
    maximum_role_activations_per_component: int = Field(default=4, ge=3, le=7)
    maximum_queries_per_role_per_round: int = Field(default=2, ge=1, le=10)
    maximum_search_calls: int = Field(default=24, ge=1, le=500)
    maximum_candidates_per_query: int = Field(default=10, ge=1, le=50)
    maximum_pages_per_component: int = Field(default=12, ge=1, le=100)
    maximum_model_calls: int = Field(default=12, ge=0, le=100)
    maximum_total_tokens: int = Field(default=0, ge=0, le=10_000_000)
    maximum_duration_seconds: float = Field(default=300.0, gt=0, le=86_400)
    maximum_cost_usd: float = Field(default=0.0, ge=0.0, le=1_000.0)


class ResearchRequirement(DomainModel):
    """One auditable evidence requirement for a material component."""

    requirement_id: UUID = Field(default_factory=uuid4)
    component_id: UUID
    kind: ResearchRequirementKind
    required_source_types: tuple[SourceType, ...] = ()
    required_stances: tuple[EvidenceStance, ...] = ()
    minimum_independent_families: int = Field(default=1, ge=1, le=10)
    rationale: str = Field(min_length=10, max_length=2_000)


ROLE_PERMISSIONS: dict[ResearchRole, frozenset[ResearchPermission]] = {
    ResearchRole.COORDINATOR: frozenset({ResearchPermission.PLAN, ResearchPermission.CONSOLIDATE}),
    ResearchRole.PRIMARY_SOURCE: frozenset(
        {
            ResearchPermission.SEARCH,
            ResearchPermission.REQUEST_FETCH,
            ResearchPermission.CLASSIFY_EVIDENCE,
        }
    ),
    ResearchRole.GENERAL_EVIDENCE: frozenset(
        {
            ResearchPermission.SEARCH,
            ResearchPermission.REQUEST_FETCH,
            ResearchPermission.CLASSIFY_EVIDENCE,
        }
    ),
    ResearchRole.CHALLENGER: frozenset(
        {
            ResearchPermission.SEARCH,
            ResearchPermission.REQUEST_FETCH,
            ResearchPermission.CLASSIFY_EVIDENCE,
        }
    ),
    ResearchRole.ACADEMIC: frozenset(
        {
            ResearchPermission.SEARCH,
            ResearchPermission.REQUEST_FETCH,
            ResearchPermission.CLASSIFY_EVIDENCE,
        }
    ),
    ResearchRole.FACT_CHECK: frozenset(
        {
            ResearchPermission.SEARCH,
            ResearchPermission.REQUEST_FETCH,
            ResearchPermission.CLASSIFY_EVIDENCE,
        }
    ),
    ResearchRole.SUFFICIENCY_CONTROLLER: frozenset({ResearchPermission.ASSESS_SUFFICIENCY}),
}


class ResearchAssignment(DomainModel):
    """Coordinator-issued task with immutable scope and permissions."""

    assignment_id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    parent_claim_id: UUID
    component_id: UUID
    claim_text: str = Field(min_length=3, max_length=2_000)
    retained_context: tuple[str, ...] = ()
    role: ResearchRole
    round_number: int = Field(ge=1, le=5)
    requirement_ids: tuple[UUID, ...] = Field(min_length=1)
    permissions: frozenset[ResearchPermission]
    query_limit: int = Field(ge=1, le=10)
    candidate_limit_per_query: int = Field(ge=1, le=50)

    @model_validator(mode="after")
    def enforce_role_permissions(self) -> "ResearchAssignment":
        if self.role in {
            ResearchRole.COORDINATOR,
            ResearchRole.SUFFICIENCY_CONTROLLER,
        }:
            raise ValueError("control roles cannot receive research assignments")
        if self.permissions != ROLE_PERMISSIONS[self.role]:
            raise ValueError("assignment permissions must exactly match the role policy")
        if len(set(self.requirement_ids)) != len(self.requirement_ids):
            raise ValueError("assignment requirement IDs must be unique")
        return self


class ResearchQuery(DomainModel):
    """A role-proposed query; query text is not evidence."""

    query_id: UUID = Field(default_factory=uuid4)
    assignment_id: UUID
    component_id: UUID
    role: ResearchRole
    text: str = Field(min_length=3, max_length=1_000)
    query_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResearchResult(DomainModel):
    """Typed role result referencing only stored candidates and evidence."""

    result_id: UUID = Field(default_factory=uuid4)
    assignment_id: UUID
    role: ResearchRole
    component_id: UUID
    query_ids: tuple[UUID, ...]
    candidate_ids: tuple[UUID, ...] = ()
    source_ids: tuple[UUID, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    unresolved_requirement_ids: tuple[UUID, ...] = ()
    search_call_count: int = Field(ge=0)
    fetch_call_count: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    token_count: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    duration_seconds: float = Field(ge=0.0)
    failure_reason: str | None = Field(default=None, max_length=2_000)


class EvidenceGain(DomainModel):
    """Material additions from a completed research round."""

    newly_covered_component_ids: tuple[UUID, ...] = ()
    newly_satisfied_requirement_ids: tuple[UUID, ...] = ()
    new_independent_family_ids: tuple[UUID, ...] = ()
    new_challenge_evidence_ids: tuple[UUID, ...] = ()
    resolved_context_requirement_ids: tuple[UUID, ...] = ()

    @property
    def material_gain_count(self) -> int:
        return sum(
            len(values)
            for values in (
                self.newly_covered_component_ids,
                self.newly_satisfied_requirement_ids,
                self.new_independent_family_ids,
                self.new_challenge_evidence_ids,
                self.resolved_context_requirement_ids,
            )
        )


class EvidenceProgressSnapshot(DomainModel):
    """Set-valued progress features that cannot be inflated by duplicates."""

    covered_component_ids: frozenset[UUID] = frozenset()
    satisfied_requirement_ids: frozenset[UUID] = frozenset()
    independent_family_ids: frozenset[UUID] = frozenset()
    challenge_evidence_ids: frozenset[UUID] = frozenset()
    resolved_context_requirement_ids: frozenset[UUID] = frozenset()


class ResearchRound(DomainModel):
    """Durable record of one bounded set of compatible assignments."""

    round_id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    round_number: int = Field(ge=1, le=5)
    assignment_ids: tuple[UUID, ...] = Field(min_length=1)
    result_ids: tuple[UUID, ...] = ()
    started_at: datetime
    completed_at: datetime | None = None
    gain: EvidenceGain | None = None


class SufficiencyDecision(StrEnum):
    """Closed routing outcomes for the evidence-sufficiency controller."""

    SUFFICIENT = "sufficient"
    CONTINUE_MISSING_PRIMARY = "continue_missing_primary"
    CONTINUE_MISSING_INDEPENDENT = "continue_missing_independent"
    CONTINUE_MISSING_CHALLENGE = "continue_missing_challenge"
    CONTINUE_MISSING_COMPONENT = "continue_missing_component"
    CONTINUE_CONTEXT_MISMATCH = "continue_context_mismatch"
    STOP_BUDGET_EXHAUSTED = "stop_budget_exhausted"
    STOP_DIMINISHING_RETURN = "stop_diminishing_return"
    STOP_UNRESOLVABLE = "stop_unresolvable"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class SufficiencyAssessment(DomainModel):
    """Auditable decision about whether another round is permitted."""

    assessment_id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    component_id: UUID
    round_number: int = Field(ge=1, le=5)
    decision: SufficiencyDecision
    satisfied_requirement_ids: tuple[UUID, ...] = ()
    missing_requirement_ids: tuple[UUID, ...] = ()
    rationale: str = Field(min_length=10, max_length=2_000)
    deterministic: bool = True


class ResearchConsumption(DomainModel):
    """Observed usage checked before another research operation is allowed."""

    completed_rounds: int = Field(ge=0, le=5)
    role_activations: int = Field(ge=0, le=100)
    search_calls: int = Field(ge=0)
    fetched_pages: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    total_tokens: int = Field(default=0, ge=0)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    estimated_cost_usd: float = Field(ge=0.0)


class ResearchRoundAudit(DomainModel):
    """Immutable controller record for one completed and assessed round."""

    round_id: UUID = Field(default_factory=uuid4)
    round_number: int = Field(ge=1, le=5)
    assignment_ids: tuple[UUID, ...] = Field(min_length=1)
    result_ids: tuple[UUID, ...] = Field(min_length=1)
    progress: EvidenceProgressSnapshot
    gain: EvidenceGain
    consumption: ResearchConsumption
    assessment: SufficiencyAssessment
    routing_rationale: tuple[str, ...] = ()


class RoleResearchMetric(DomainModel):
    """Per-role material gain, usage and latency from one fan-out."""

    assignment_id: UUID
    role: ResearchRole
    successful: bool
    source_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    retained_evidence_count: int = Field(ge=0)
    independent_family_gain: int = Field(ge=0)
    search_calls: int = Field(ge=0)
    fetch_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    token_count: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)


class MultiAgentFanOutReport(DomainModel):
    """Authority-isolated output of the LangGraph research map/reduce subgraph."""

    investigation_id: UUID
    parent_claim_id: UUID
    component_id: UUID
    assignments: tuple[ResearchAssignment, ...] = Field(min_length=1, max_length=35)
    results: tuple[ResearchResult, ...] = Field(min_length=1, max_length=35)
    consolidation: EvidenceConsolidation
    role_metrics: tuple[RoleResearchMetric, ...] = Field(min_length=1, max_length=35)
    consumption: ResearchConsumption
    rounds: tuple[ResearchRoundAudit, ...] = Field(min_length=1, max_length=5)
    final_assessment: SufficiencyAssessment
    human_review_required: bool
    human_review_reason: str | None = Field(default=None, max_length=2_000)
    unresolved_requirement_ids: tuple[UUID, ...] = ()
    duplicate_result_references_removed: int = Field(ge=0)
    authoritative_output_applied: bool = False

    @model_validator(mode="after")
    def validate_fan_out_identity(self) -> "MultiAgentFanOutReport":
        assignment_ids = {item.assignment_id for item in self.assignments}
        if len(assignment_ids) != len(self.assignments):
            raise ValueError("fan-out assignment IDs must be unique")
        if {item.assignment_id for item in self.results} != assignment_ids:
            raise ValueError("fan-out requires exactly one terminal result per assignment")
        if {item.assignment_id for item in self.role_metrics} != assignment_ids:
            raise ValueError("fan-out requires exactly one metric per assignment")
        if self.rounds[-1].assessment != self.final_assessment:
            raise ValueError("final assessment must equal the last round assessment")
        if self.human_review_required != (
            self.final_assessment.decision is not SufficiencyDecision.SUFFICIENT
        ):
            raise ValueError("human-review escalation must reflect terminal sufficiency")
        if self.human_review_required != bool(self.human_review_reason):
            raise ValueError("human-review escalation requires exactly one reason")
        if self.authoritative_output_applied:
            raise ValueError("research fan-out cannot apply an authoritative output")
        return self


class SufficiencyContext(DomainModel):
    """Complete deterministic input to the evidence-sufficiency controller."""

    investigation_id: UUID
    component_id: UUID
    requirements: tuple[ResearchRequirement, ...] = Field(min_length=1)
    sources: tuple[Source, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    independence: IndependenceAnalysis | None = None
    attempted_roles: frozenset[ResearchRole] = frozenset()
    resolved_context_requirement_ids: frozenset[UUID] = frozenset()
    unresolvable_requirement_ids: frozenset[UUID] = frozenset()
    last_round_gain: EvidenceGain | None = None
    consumption: ResearchConsumption
    budget: ResearchBudget
    human_review_reason: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_sufficiency_references(self) -> "SufficiencyContext":
        requirement_ids = {item.requirement_id for item in self.requirements}
        if any(item.component_id != self.component_id for item in self.requirements):
            raise ValueError("sufficiency requirements must reference the component")
        if not self.resolved_context_requirement_ids <= requirement_ids:
            raise ValueError("resolved context IDs must reference declared requirements")
        if not self.unresolvable_requirement_ids <= requirement_ids:
            raise ValueError("unresolvable IDs must reference declared requirements")
        if any(item.claim_id != self.component_id for item in self.evidence):
            raise ValueError("sufficiency evidence must reference the component")
        return self


class MultiAgentResearchTrace(DomainModel):
    """Top-level Phase 4 research provenance."""

    schema_version: int = Field(default=1, ge=1)
    investigation_id: UUID
    parent_claim_id: UUID
    requirement_ids: tuple[UUID, ...]
    round_ids: tuple[UUID, ...]
    final_evidence_ids: tuple[UUID, ...]
    final_assessment_id: UUID | None = None
    total_search_calls: int = Field(ge=0)
    total_fetch_calls: int = Field(ge=0)
    total_model_calls: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    duration_seconds: float = Field(ge=0.0)


class ResearchRoutingRequest(DomainModel):
    """Structured facts available to the deterministic router."""

    investigation_id: UUID
    parent_claim_id: UUID
    component_id: UUID
    claim_text: str = Field(min_length=3, max_length=2_000)
    retained_context: tuple[str, ...] = ()
    claim_types: frozenset[ClaimType] = frozenset({ClaimType.FACTUAL})
    requirements: tuple[ResearchRequirement, ...] = Field(min_length=1)
    prior_fact_check_likely: bool = False
    round_number: int = Field(default=1, ge=1, le=5)
    budget: ResearchBudget = Field(default_factory=ResearchBudget)

    @model_validator(mode="after")
    def requirements_match_component(self) -> "ResearchRoutingRequest":
        if any(item.component_id != self.component_id for item in self.requirements):
            raise ValueError("all routing requirements must reference the component")
        if len({item.requirement_id for item in self.requirements}) != len(self.requirements):
            raise ValueError("routing requirement IDs must be unique")
        return self


class ResearchRoute(DomainModel):
    """Deterministically selected research assignments and deferred roles."""

    assignments: tuple[ResearchAssignment, ...]
    deferred_roles: tuple[ResearchRole, ...] = ()
    rationale: tuple[str, ...]

    @model_validator(mode="after")
    def unique_active_roles(self) -> "ResearchRoute":
        roles = [assignment.role for assignment in self.assignments]
        if len(roles) != len(set(roles)):
            raise ValueError("each research role may be activated at most once per route")
        if set(roles) & set(self.deferred_roles):
            raise ValueError("an active role cannot also be deferred")
        return self


class MultiAgentWorkflowStage(StrEnum):
    """Durable coordinator stages for the minimum multi-agent workflow."""

    PLANNED = "planned"
    RESEARCHED = "researched"
    CONSOLIDATED = "consolidated"
    ASSESSED = "assessed"
    COMPLETE = "complete"


class MultiAgentWorkflowCheckpoint(DomainModel):
    """Complete resumable coordinator state stored after each material stage."""

    investigation_id: UUID
    claim: AtomicClaim
    requirements: tuple[ResearchRequirement, ...]
    budget: ResearchBudget
    stage: MultiAgentWorkflowStage
    assignments: tuple[ResearchAssignment, ...]
    results: tuple[ResearchResult, ...] = ()
    rounds: tuple[ResearchRoundAudit, ...] = ()
    pending_routing_rationale: tuple[str, ...] = ()
    role_metrics: tuple[RoleResearchMetric, ...] = ()
    duplicate_result_references_removed: int = Field(default=0, ge=0)
    consolidation: EvidenceConsolidation | None = None
    assessment: SufficiencyAssessment | None = None
    verdict: Verdict | None = None
    audit: SentenceAudit | None = None


class MultiAgentInvestigationReport(DomainModel):
    """Output of the minimum Phase 4 workflow."""

    investigation_id: UUID
    claim: AtomicClaim
    requirements: tuple[ResearchRequirement, ...]
    assignments: tuple[ResearchAssignment, ...]
    results: tuple[ResearchResult, ...]
    consolidation: EvidenceConsolidation
    assessment: SufficiencyAssessment
    verdict: Verdict
    audit: SentenceAudit
