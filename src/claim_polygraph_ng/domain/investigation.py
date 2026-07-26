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


class TraceEventType(StrEnum):
    """Observable workflow events."""

    INVESTIGATION_CREATED = "investigation_created"
    STATUS_CHANGED = "status_changed"
    STAGE_STARTED = "stage_started"
    ARTIFACT_CREATED = "artifact_created"
    PROVIDER_CALLED = "provider_called"
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
    VERDICT = "verdict"
    AUDIT = "audit"


class ModelTask(StrEnum):
    """Logical structured-generation tasks."""

    NORMALIZE_CLAIM = "normalize_claim"
    PLAN_INVESTIGATION = "plan_investigation"
    CLASSIFY_EVIDENCE = "classify_evidence"
    JUDGE_EVIDENCE = "judge_evidence"
    AUDIT_SENTENCE = "audit_sentence"


class Investigation(DomainModel):
    """Top-level investigation record."""

    investigation_id: UUID = Field(default_factory=uuid4)
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
    verdict: Verdict
    audits: tuple[SentenceAudit, ...]
