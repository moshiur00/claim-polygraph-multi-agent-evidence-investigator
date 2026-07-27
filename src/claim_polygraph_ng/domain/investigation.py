"""Investigation lifecycle, research, and trace contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, Field, JsonValue, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import ResearchPath, SourceType
from claim_polygraph_ng.domain.models import (
    AtomicClaim,
    Evidence,
    InvestigationPlan,
    SentenceAudit,
    Source,
    Verdict,
)
from claim_polygraph_ng.domain.provenance import IndependenceAnalysis
from claim_polygraph_ng.domain.verification import ContextVerification


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class InvestigationStatus(StrEnum):
    """Persisted execution state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvestigationStage(StrEnum):
    """Coarse stages shown in traces and status responses."""

    CREATED = "created"
    CLAIM_ANALYSIS = "claim_analysis"
    PLANNING = "planning"
    RESEARCH = "research"
    EVIDENCE_ANALYSIS = "evidence_analysis"
    JUDGMENT = "judgment"
    CITATION_AUDIT = "citation_audit"
    COMPLETE = "complete"
    FAILED = "failed"


class ComplexCheckpointStage(StrEnum):
    """Persisted progress through a complex-claim investigation."""

    CREATED = "created"
    DECOMPOSED = "decomposed"
    COMPONENTS = "components"
    AGGREGATED = "aggregated"
    AUDITED = "audited"
    COMPLETE = "complete"


class TraceEventType(StrEnum):
    """Observable workflow events."""

    INVESTIGATION_CREATED = "investigation_created"
    STATUS_CHANGED = "status_changed"
    STAGE_STARTED = "stage_started"
    ARTIFACT_CREATED = "artifact_created"
    PROVIDER_CALLED = "provider_called"
    MODEL_USAGE_RECORDED = "model_usage_recorded"
    PROVIDER_FAILED = "provider_failed"
    INVESTIGATION_COMPLETED = "investigation_completed"
    INVESTIGATION_FAILED = "investigation_failed"


class ArtifactType(StrEnum):
    """Stored artifact categories."""

    CLAIM = "claim"
    PLAN = "plan"
    SOURCE = "source"
    CHUNK = "chunk"
    EVIDENCE = "evidence"
    INDEPENDENCE = "independence"
    CONTEXT_VERIFICATION = "context_verification"
    VERDICT = "verdict"
    AUDIT = "audit"
    DECOMPOSITION = "decomposition"
    COVERAGE = "coverage"
    CHECKPOINT = "checkpoint"


class ModelTask(StrEnum):
    """Logical structured-generation tasks."""

    NORMALIZE_CLAIM = "normalize_claim"
    DECOMPOSE_CLAIM = "decompose_claim"
    PLAN_INVESTIGATION = "plan_investigation"
    CLASSIFY_EVIDENCE = "classify_evidence"
    JUDGE_EVIDENCE = "judge_evidence"
    AUDIT_SENTENCE = "audit_sentence"
    REVIEW_ANNOTATION = "review_annotation"
    REVIEW_CRITIQUE = "review_critique"
    EVALUATE_PASSAGE = "evaluate_passage"


class ModelCallUsage(DomainModel):
    """Measured usage and estimated price for one structured model call."""

    provider_id: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    task: ModelTask
    duration_seconds: float = Field(ge=0.0)
    input_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    pricing_version: str | None = Field(default=None, max_length=100)
    output_valid: bool = False

    @model_validator(mode="after")
    def cached_tokens_cannot_exceed_input(self) -> "ModelCallUsage":
        if (
            self.input_tokens is not None
            and self.cached_input_tokens is not None
            and self.cached_input_tokens > self.input_tokens
        ):
            raise ValueError("cached_input_tokens cannot exceed input_tokens")
        return self


class Investigation(DomainModel):
    """Top-level investigation record."""

    investigation_id: UUID = Field(default_factory=uuid4)
    parent_investigation_id: UUID | None = None
    component_claim_id: UUID | None = None
    input_claim: str = Field(min_length=3, max_length=10_000)
    status: InvestigationStatus = InvestigationStatus.PENDING
    stage: InvestigationStage = InvestigationStage.CREATED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    failure_reason: str | None = Field(default=None, max_length=5_000)

    @model_validator(mode="after")
    def validate_terminal_state(self) -> "Investigation":
        """Keep failure details and terminal stages consistent."""
        if self.status is InvestigationStatus.FAILED:
            if self.stage is not InvestigationStage.FAILED:
                raise ValueError("failed investigations must use the failed stage")
            if not self.failure_reason:
                raise ValueError("failed investigations require a failure reason")
        elif self.failure_reason is not None:
            raise ValueError("only failed investigations may have a failure reason")

        if (
            self.status is InvestigationStatus.COMPLETED
            and self.stage is not InvestigationStage.COMPLETE
        ):
            raise ValueError("completed investigations must use the complete stage")
        if self.parent_investigation_id is None and self.component_claim_id is not None:
            raise ValueError("component_claim_id requires parent_investigation_id")
        if self.parent_investigation_id == self.investigation_id:
            raise ValueError("an investigation cannot be its own parent")
        return self


class ComponentExecution(DomainModel):
    """Durable link from a material component to its child investigation."""

    claim_id: UUID
    investigation_id: UUID


class ComponentFailure(DomainModel):
    """Exhausted component failure retained in parent coverage."""

    claim_id: UUID
    investigation_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=5_000)


class ComplexWorkflowCheckpoint(DomainModel):
    """Idempotent resume state for a complex investigation."""

    checkpoint_id: UUID
    stage: ComplexCheckpointStage
    decomposition_id: UUID | None = None
    completed_components: tuple[ComponentExecution, ...] = ()
    failed_components: tuple[ComponentFailure, ...] = ()

    @model_validator(mode="after")
    def validate_component_links(self) -> "ComplexWorkflowCheckpoint":
        claim_ids = [item.claim_id for item in self.completed_components]
        investigation_ids = [item.investigation_id for item in self.completed_components]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("checkpoint component claim IDs must be unique")
        if len(investigation_ids) != len(set(investigation_ids)):
            raise ValueError("checkpoint child investigation IDs must be unique")
        failed_claim_ids = [item.claim_id for item in self.failed_components]
        if len(failed_claim_ids) != len(set(failed_claim_ids)):
            raise ValueError("checkpoint failed component claim IDs must be unique")
        if set(claim_ids) & set(failed_claim_ids):
            raise ValueError("a component cannot be both completed and failed")
        if self.stage is not ComplexCheckpointStage.CREATED and self.decomposition_id is None:
            raise ValueError("post-creation checkpoints require a decomposition ID")
        return self


class TraceEvent(DomainModel):
    """One persisted, user-visible workflow event."""

    event_id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    event_type: TraceEventType
    stage: InvestigationStage
    occurred_at: datetime = Field(default_factory=utc_now)
    message: str = Field(min_length=1, max_length=1_000)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class SearchRequest(DomainModel):
    """Provider-independent search request."""

    claim_id: UUID
    query: str = Field(min_length=3, max_length=1_000)
    research_path: ResearchPath
    maximum_results: int = Field(default=3, ge=1, le=20)


class SearchResult(DomainModel):
    """Provider-independent candidate returned by search."""

    url: AnyHttpUrl
    title: str = Field(min_length=1, max_length=1_000)
    snippet: str | None = Field(default=None, max_length=10_000)
    inline_content: str | None = Field(default=None, max_length=40_000)
    source_type: SourceType
    publisher: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_candidate_text(self) -> "SearchResult":
        """A result needs a snippet or deterministic inline content."""
        if not self.snippet and not self.inline_content:
            raise ValueError("search results require a snippet or inline content")
        return self


class InvestigationReport(DomainModel):
    """Complete typed result returned by the application service."""

    investigation: Investigation
    claim: AtomicClaim
    plan: InvestigationPlan
    sources: tuple[Source, ...]
    evidence: tuple[Evidence, ...]
    independence_analysis: IndependenceAnalysis | None = None
    context_verification: ContextVerification | None = None
    verdict: Verdict
    audits: tuple[SentenceAudit, ...]


class ComplexInvestigationReport(DomainModel):
    """Audited parent result with every material child investigation."""

    investigation: Investigation
    decomposition: "ClaimDecomposition"
    component_reports: tuple[InvestigationReport, ...]
    coverage: "ClaimCoverage"
    verdict: Verdict
    audits: tuple[SentenceAudit, ...]


from claim_polygraph_ng.domain.models import ClaimCoverage, ClaimDecomposition  # noqa: E402

ComplexInvestigationReport.model_rebuild()
