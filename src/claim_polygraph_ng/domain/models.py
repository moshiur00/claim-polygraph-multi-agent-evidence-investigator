"""Typed artifacts exchanged across the investigation workflow."""

from datetime import date, datetime
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, Field, computed_field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import (
    AuditIssue,
    ClaimType,
    ComponentStatus,
    ContentRetention,
    EvidenceStance,
    ExtractionStatus,
    ResearchPath,
    RightsStatus,
    SourceType,
    SupportLevel,
    VerdictLabel,
)

Score = float


class AtomicClaim(DomainModel):
    """A contextualized, independently checkable claim."""

    claim_id: UUID = Field(default_factory=uuid4)
    parent_claim_id: UUID | None = None
    text: str = Field(min_length=3, max_length=2_000)
    claim_type: ClaimType = ClaimType.FACTUAL
    entities: tuple[str, ...] = ()
    quantities: tuple[str, ...] = ()
    reference_date: date | None = None
    geography: str | None = Field(default=None, max_length=200)
    ambiguities: tuple[str, ...] = ()
    retained_context: tuple[str, ...] = ()
    checkworthiness: Score = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def parent_must_differ(self) -> "AtomicClaim":
        """A claim cannot be its own parent."""
        if self.parent_claim_id == self.claim_id:
            raise ValueError("parent_claim_id must differ from claim_id")
        return self


class ClaimDecomposition(DomainModel):
    """Selective, context-preserving material components for one parent claim."""

    decomposition_id: UUID = Field(default_factory=uuid4)
    root_claim: AtomicClaim
    requires_decomposition: bool
    components: tuple[AtomicClaim, ...] = Field(min_length=1, max_length=8)
    rationale: str = Field(min_length=10, max_length=5_000)

    @model_validator(mode="after")
    def validate_components(self) -> "ClaimDecomposition":
        if not self.requires_decomposition and len(self.components) != 1:
            raise ValueError("an atomic claim must have exactly one material component")
        component_ids = [component.claim_id for component in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("component claim identifiers must be unique")
        normalized_texts = [
            " ".join(component.text.casefold().split()) for component in self.components
        ]
        if len(normalized_texts) != len(set(normalized_texts)):
            raise ValueError("component claim texts must be unique")
        for component in self.components:
            if component.parent_claim_id != self.root_claim.claim_id:
                raise ValueError("every component must reference the root claim")
            if component.text == self.root_claim.text and self.requires_decomposition:
                raise ValueError("a decomposed component cannot merely repeat the root claim")
        return self


class ComponentOutcome(DomainModel):
    """Coverage and conclusion state for one material component."""

    claim_id: UUID
    status: ComponentStatus
    verdict_id: UUID | None = None
    verdict_label: VerdictLabel | None = None
    evidence_ids: tuple[UUID, ...] = ()
    unresolved_reason: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_outcome(self) -> "ComponentOutcome":
        if self.status is ComponentStatus.COMPLETED:
            if self.verdict_id is None or self.verdict_label is None:
                raise ValueError("completed components require a verdict")
        elif self.verdict_id is not None or self.verdict_label is not None:
            raise ValueError("only completed components may contain a verdict")
        if self.status in {ComponentStatus.UNRESOLVED, ComponentStatus.FAILED}:
            if not self.unresolved_reason:
                raise ValueError("unresolved or failed components require a reason")
        elif self.unresolved_reason is not None:
            raise ValueError("only unresolved or failed components may contain a reason")
        return self


class ClaimCoverage(DomainModel):
    """Material-component coverage gate for a complex investigation."""

    coverage_id: UUID = Field(default_factory=uuid4)
    root_claim_id: UUID
    outcomes: tuple[ComponentOutcome, ...] = Field(min_length=1, max_length=8)

    @computed_field
    @property
    def completed_count(self) -> int:
        return sum(outcome.status is ComponentStatus.COMPLETED for outcome in self.outcomes)

    @computed_field
    @property
    def explicitly_unresolved_count(self) -> int:
        return sum(
            outcome.status in {ComponentStatus.UNRESOLVED, ComponentStatus.FAILED}
            for outcome in self.outcomes
        )

    @computed_field
    @property
    def material_coverage_rate(self) -> float:
        covered = self.completed_count + self.explicitly_unresolved_count
        return round(covered / len(self.outcomes), 4)

    @model_validator(mode="after")
    def require_unique_components(self) -> "ClaimCoverage":
        claim_ids = [outcome.claim_id for outcome in self.outcomes]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("coverage outcomes must reference unique components")
        return self


class InvestigationPlan(DomainModel):
    """Bounded research requirements for one atomic claim."""

    claim_id: UUID
    required_research_paths: tuple[ResearchPath, ...]
    required_source_types: tuple[SourceType, ...] = ()
    minimum_independent_families: int = Field(default=2, ge=1, le=10)
    requires_numerical_check: bool = False
    requires_temporal_check: bool = False
    maximum_research_rounds: int = Field(default=2, ge=1, le=5)
    maximum_search_calls: int = Field(default=6, ge=1, le=50)
    maximum_pages_fetched: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def require_balanced_research(self) -> "InvestigationPlan":
        """Every plan must deliberately search for contradictory evidence."""
        paths = set(self.required_research_paths)
        if not paths:
            raise ValueError("at least one research path is required")
        if ResearchPath.CONTRADICTION not in paths:
            raise ValueError("contradiction research is required")
        if not paths.intersection({ResearchPath.PRIMARY, ResearchPath.GENERAL}):
            raise ValueError("primary or general research is required")
        return self


class Source(DomainModel):
    """Canonical metadata for a retrieved source."""

    source_id: UUID = Field(default_factory=uuid4)
    url: AnyHttpUrl
    canonical_url: AnyHttpUrl
    title: str = Field(min_length=1, max_length=1_000)
    source_type: SourceType
    publisher: str | None = Field(default=None, max_length=500)
    author: str | None = Field(default=None, max_length=500)
    publication_date: date | None = None
    retrieved_at: datetime
    content_hash: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    extraction_status: ExtractionStatus
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    rights_basis: str | None = Field(default=None, max_length=2_000)
    rights_reference_url: AnyHttpUrl | None = None
    content_retention: ContentRetention = ContentRetention.EVIDENCE_PASSAGES_ONLY

    @model_validator(mode="after")
    def documented_rights_require_a_basis(self) -> "Source":
        if self.rights_status is not RightsStatus.UNKNOWN and not self.rights_basis:
            raise ValueError("documented rights status requires rights_basis")
        return self


class Evidence(DomainModel):
    """An exact source passage evaluated against one claim."""

    evidence_id: UUID = Field(default_factory=uuid4)
    claim_id: UUID
    source_id: UUID
    chunk_id: UUID | None = None
    passage: str = Field(min_length=1, max_length=20_000)
    passage_start_char: int | None = Field(default=None, ge=0)
    passage_end_char: int | None = Field(default=None, gt=0)
    context: str | None = Field(default=None, max_length=40_000)
    stance: EvidenceStance
    relevance_score: Score = Field(ge=0.0, le=1.0)
    retrieval_score: Score | None = Field(default=None, ge=0.0)
    entailment_score: Score | None = Field(default=None, ge=0.0, le=1.0)
    extraction_status: ExtractionStatus = ExtractionStatus.EXTRACTED
    temporal_compatibility: Score | None = Field(default=None, ge=0.0, le=1.0)
    evidence_family_id: UUID | None = None

    @model_validator(mode="after")
    def extracted_evidence_must_be_relevant(self) -> "Evidence":
        """An item explicitly marked irrelevant cannot have strong relevance."""
        if self.stance is EvidenceStance.IRRELEVANT and self.relevance_score > 0.5:
            raise ValueError("irrelevant evidence cannot have relevance_score above 0.5")
        offsets = (self.passage_start_char, self.passage_end_char)
        if self.chunk_id is None and any(value is not None for value in offsets):
            raise ValueError("passage offsets require a chunk_id")
        if self.chunk_id is not None:
            if any(value is None for value in offsets):
                raise ValueError("chunk evidence requires passage offsets")
            assert self.passage_start_char is not None
            assert self.passage_end_char is not None
            if self.passage_end_char - self.passage_start_char != len(self.passage):
                raise ValueError("passage offsets must match passage length")
        return self


class SourceAssessment(DomainModel):
    """Explainable source-quality features; not a verdict by itself."""

    source_id: UUID
    authority: Score = Field(ge=0.0, le=1.0)
    primary_status: Score = Field(ge=0.0, le=1.0)
    relevance: Score = Field(ge=0.0, le=1.0)
    recency: Score = Field(ge=0.0, le=1.0)
    transparency: Score = Field(ge=0.0, le=1.0)
    independence: Score = Field(ge=0.0, le=1.0)
    reputation: Score = Field(ge=0.0, le=1.0)
    conflict_penalty: Score = Field(ge=0.0, le=1.0)
    justification: str = Field(min_length=10, max_length=5_000)

    @computed_field
    @property
    def overall_feature(self) -> float:
        """Initial deterministic feature; weights remain an evaluation hypothesis."""
        positive = (
            0.18 * self.authority
            + 0.16 * self.primary_status
            + 0.18 * self.relevance
            + 0.10 * self.recency
            + 0.10 * self.transparency
            + 0.14 * self.independence
            + 0.14 * self.reputation
        )
        return round(max(0.0, positive * (1.0 - self.conflict_penalty)), 4)


class Verdict(DomainModel):
    """Versioned conclusion grounded in approved evidence identifiers."""

    verdict_id: UUID = Field(default_factory=uuid4)
    version: int = Field(default=1, ge=1)
    claim_id: UUID
    label: VerdictLabel
    confidence: Score | None = Field(default=None, ge=0.0, le=1.0)
    concise_explanation: str = Field(min_length=10, max_length=1_000)
    detailed_reasoning: str = Field(min_length=10, max_length=20_000)
    decisive_evidence_ids: tuple[UUID, ...] = ()
    contradictory_evidence_ids: tuple[UUID, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    conditions_that_could_change_verdict: tuple[str, ...] = ()
    human_review_required: bool = False
    review_reason: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_review_and_evidence(self) -> "Verdict":
        """Require review rationale and prevent evidence-free definitive verdicts."""
        if self.human_review_required and not self.review_reason:
            raise ValueError("review_reason is required when human review is required")

        evidence_ids = set(self.decisive_evidence_ids) | set(self.contradictory_evidence_ids)
        evidence_optional = {
            VerdictLabel.UNSUPPORTED,
            VerdictLabel.UNVERIFIABLE,
        }
        if self.label not in evidence_optional and not evidence_ids:
            raise ValueError("this verdict label requires at least one evidence identifier")
        return self


class SentenceAudit(DomainModel):
    """Citation support result for one material report sentence."""

    sentence_id: UUID = Field(default_factory=uuid4)
    sentence: str = Field(min_length=1, max_length=5_000)
    cited_evidence_ids: tuple[UUID, ...] = ()
    support_level: SupportLevel
    issue_type: AuditIssue | None = None
    explanation: str | None = Field(default=None, max_length=5_000)
    suggested_revision: str | None = Field(default=None, max_length=5_000)

    @model_validator(mode="after")
    def validate_support_result(self) -> "SentenceAudit":
        """Keep support level, citations, and issue reporting consistent."""
        if self.support_level is SupportLevel.FULL:
            if not self.cited_evidence_ids:
                raise ValueError("fully supported sentences require cited evidence")
            if self.issue_type is not None:
                raise ValueError("fully supported sentences cannot have an audit issue")
        else:
            if self.issue_type is None:
                raise ValueError("partial or unsupported sentences require an audit issue")
            if not self.explanation:
                raise ValueError("audit issues require an explanation")
        return self
