"""Typed contracts for local benchmark datasets and evaluation results."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, Field, model_validator

from claim_polygraph_ng.domain import (
    ClaimType,
    EvidenceStance,
    ModelCallUsage,
    SourceType,
    VerdictLabel,
)
from claim_polygraph_ng.domain.base import DomainModel


class EvaluationCategory(StrEnum):
    """Required dimensions in the initial representative claim set."""

    NUMERICAL = "numerical"
    SCIENTIFIC_MEDICAL = "scientific_medical"
    POLITICAL_POLICY = "political_policy"
    CORPORATE = "corporate"
    HISTORICAL = "historical"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    AMBIGUOUS = "ambiguous"
    OUTDATED = "outdated"
    DERIVATIVE_REPORTING = "derivative_reporting"


class AnnotationStatus(StrEnum):
    """Whether expected outcomes have received human review."""

    DRAFT = "draft"
    AI_REVIEWED = "ai_reviewed"
    REVIEWED = "reviewed"


class RetrievalQueryStrategy(StrEnum):
    """Non-oracle query-generation strategies available for retrieval ablations."""

    CLAIM_ONLY = "claim_only"
    BALANCED = "balanced"
    GUARDED_FUSION = "guarded_fusion"
    QUALITY_RERANK = "quality_rerank"


class RiskLevel(StrEnum):
    """Consequence level used to stratify the benchmark."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BenchmarkEvidenceAnnotation(DomainModel):
    """Short, reviewable evidence excerpt from an identified source."""

    annotation_id: str = Field(pattern=r"^E[0-9]+$")
    source_url: AnyHttpUrl
    source_title: str = Field(min_length=3, max_length=500)
    publisher: str = Field(min_length=2, max_length=300)
    source_type: SourceType
    stance: EvidenceStance
    excerpt: str = Field(min_length=3, max_length=500)
    evidence_summary: str = Field(min_length=10, max_length=1_000)
    publication_date: date | None = None
    accessed_at: date
    independence_note: str = Field(min_length=10, max_length=1_000)


class AIReviewAnnotation(DomainModel):
    """First-pass LLM assessment of a supplied benchmark packet."""

    recommended_verdict: VerdictLabel
    rationale: str = Field(min_length=20, max_length=3_000)
    resolved_interpretation: str = Field(min_length=10, max_length=2_000)
    evidence_sufficient: bool
    evidence_strengths: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    independence_concerns: tuple[str, ...]
    temporal_or_numerical_checks: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)


class AIReviewCritique(DomainModel):
    """Second-pass LLM challenge to a provisional annotation."""

    agrees_with_verdict: bool
    recommended_verdict: VerdictLabel
    critique: str = Field(min_length=20, max_length=3_000)
    unsupported_or_overstated_points: tuple[str, ...]
    missing_checks: tuple[str, ...]
    evidence_sufficient: bool
    confidence: float = Field(ge=0.0, le=1.0)


class AIAssistedReviewRecord(DomainModel):
    """Auditable, explicitly non-human benchmark review provenance."""

    reviewed_at: datetime
    annotator_model: str = Field(min_length=1, max_length=200)
    critic_model: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=100)
    source_verification_scope: Literal["provided_packet_only"]
    annotation: AIReviewAnnotation
    critique: AIReviewCritique
    provisional_verdict: VerdictLabel
    disagreements: tuple[str, ...]
    usage: tuple[ModelCallUsage, ...]
    requires_human_review: Literal[True] = True


class BenchmarkCase(DomainModel):
    """One benchmark claim and its reviewable annotations."""

    case_id: str = Field(pattern=r"^CPNG-[0-9]{3}$")
    claim: str = Field(min_length=3, max_length=2_000)
    categories: tuple[EvaluationCategory, ...] = Field(min_length=1)
    expected_claim_type: ClaimType
    risk_level: RiskLevel
    reference_date: date | None = None
    geography: str | None = Field(default=None, max_length=200)
    annotation_status: AnnotationStatus = AnnotationStatus.DRAFT
    ai_review: AIAssistedReviewRecord | None = None
    proposed_verdict: VerdictLabel | None = None
    proposed_rationale: str | None = Field(default=None, min_length=10, max_length=2_000)
    candidate_evidence: tuple[BenchmarkEvidenceAnnotation, ...] = ()
    expected_verdict: VerdictLabel | None = None
    annotation_notes: tuple[str, ...] = ()
    reviewed_by: str | None = Field(default=None, min_length=2, max_length=200)
    reviewed_at: date | None = None

    @model_validator(mode="after")
    def validate_annotations(self) -> "BenchmarkCase":
        if len(self.categories) != len(set(self.categories)):
            raise ValueError("benchmark categories must be unique")
        evidence_ids = [item.annotation_id for item in self.candidate_evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("candidate evidence annotation_id values must be unique")
        if self.proposed_verdict is not None:
            if not self.proposed_rationale:
                raise ValueError("proposed verdicts require a rationale")
            if not self.candidate_evidence:
                raise ValueError("proposed verdicts require candidate evidence")
        if self.annotation_status is AnnotationStatus.REVIEWED:
            if self.expected_verdict is None:
                raise ValueError("reviewed cases require an expected verdict")
            if not self.candidate_evidence:
                raise ValueError("reviewed cases require candidate evidence")
            if not self.reviewed_by or self.reviewed_at is None:
                raise ValueError("reviewed cases require reviewer identity and review date")
        if self.annotation_status is AnnotationStatus.AI_REVIEWED:
            if self.ai_review is None:
                raise ValueError("AI-reviewed cases require explicit AI review provenance")
            if self.expected_verdict is not None:
                raise ValueError("AI-reviewed cases cannot define a human expected verdict")
            if self.reviewed_by is not None or self.reviewed_at is not None:
                raise ValueError("AI-reviewed cases cannot contain human review metadata")
        return self


class BenchmarkDataset(DomainModel):
    """Versioned collection of benchmark claims."""

    dataset_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    version: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=10, max_length=2_000)
    created_at: date
    cases: tuple[BenchmarkCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def case_identifiers_must_be_unique(self) -> "BenchmarkDataset":
        identifiers = [case.case_id for case in self.cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("benchmark case_id values must be unique")
        return self


class EvaluationCaseResult(DomainModel):
    """Observed structural result for one benchmark claim."""

    case_id: str
    completed: bool
    investigation_id: UUID | None = None
    verdict_label: VerdictLabel | None = None
    expected_verdict: VerdictLabel | None = None
    verdict_matches: bool | None = None
    ai_provisional_verdict: VerdictLabel | None = None
    verdict_matches_ai_provisional: bool | None = None
    source_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    full_audit_count: int = Field(ge=0)
    audit_count: int = Field(ge=0)
    duration_seconds: float = Field(ge=0.0)
    metered_model_call_count: int = Field(default=0, ge=0)
    priced_model_call_count: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_model_cost_usd: float = Field(default=0.0, ge=0.0)
    error_type: str | None = None
    error_message: str | None = None


class EvaluationSummary(DomainModel):
    """Aggregate deterministic or real-retrieval benchmark result."""

    dataset_id: str
    dataset_version: int
    provider_mode: str
    started_at: datetime
    duration_seconds: float = Field(ge=0.0)
    case_count: int = Field(ge=1)
    reviewed_case_count: int = Field(ge=0)
    ai_reviewed_case_count: int = Field(default=0, ge=0)
    completed_case_count: int = Field(ge=0)
    completion_rate: float = Field(ge=0.0, le=1.0)
    mean_sources_per_completed_case: float = Field(ge=0.0)
    mean_evidence_per_completed_case: float = Field(ge=0.0)
    citation_full_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    verdict_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_provisional_comparison_count: int = Field(default=0, ge=0)
    ai_provisional_agreement_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    metered_model_call_count: int = Field(default=0, ge=0)
    priced_model_call_count: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_model_cost_usd: float = Field(default=0.0, ge=0.0)
    mean_estimated_model_cost_per_completed_case_usd: float = Field(default=0.0, ge=0.0)
    verdict_distribution: dict[str, int]
    results: tuple[EvaluationCaseResult, ...]
    limitations: tuple[str, ...]


class RetrievalReferenceResult(DomainModel):
    """Match outcomes for one reviewed evidence source."""

    annotation_id: str
    source_url: AnyHttpUrl
    source_type: SourceType
    exact_url_rank: int | None = Field(default=None, ge=1)
    reviewed_host_rank: int | None = Field(default=None, ge=1)
    lexical_rank: int | None = Field(default=None, ge=1)
    best_lexical_score: float = Field(ge=0.0, le=1.0)


class RetrievalCandidate(DomainModel):
    """One ranked SearXNG candidate retained for metric auditability."""

    rank: int = Field(ge=1)
    url: AnyHttpUrl
    title: str
    snippet: str | None = None
    source_type: SourceType
    publisher: str | None = None
    fusion_score: float = Field(ge=0.0)
    query_ranks: dict[str, int]
    quality_score: float = Field(ge=0.0, le=1.0)
    quality_features: dict[str, float]


class RetrievalCaseResult(DomainModel):
    """Search-candidate retrieval metrics for one benchmark claim."""

    case_id: str
    queries: tuple[str, ...]
    query_errors: dict[str, str]
    result_count: int = Field(ge=0)
    reference_count: int = Field(ge=0)
    exact_url_hit_count: int = Field(ge=0)
    reviewed_host_hit_count: int = Field(ge=0)
    lexical_hit_count: int = Field(ge=0)
    first_exact_url_rank: int | None = Field(default=None, ge=1)
    first_reviewed_host_rank: int | None = Field(default=None, ge=1)
    reciprocal_rank_exact_url: float = Field(ge=0.0, le=1.0)
    reciprocal_rank_reviewed_host: float = Field(ge=0.0, le=1.0)
    candidates: tuple[RetrievalCandidate, ...]
    references: tuple[RetrievalReferenceResult, ...]
    duration_seconds: float = Field(ge=0.0)
    error_type: str | None = None
    error_message: str | None = None


class RetrievalEvaluationSummary(DomainModel):
    """Aggregate claim-only SearXNG retrieval-quality baseline."""

    dataset_id: str
    dataset_version: int
    provider_id: str
    query_strategy: RetrievalQueryStrategy
    started_at: datetime
    duration_seconds: float = Field(ge=0.0)
    case_count: int = Field(ge=1)
    completed_case_count: int = Field(ge=0)
    completion_rate: float = Field(ge=0.0, le=1.0)
    top_k: int = Field(ge=1, le=20)
    search_call_count: int = Field(ge=0)
    lexical_threshold: float = Field(ge=0.0, le=1.0)
    reference_count: int = Field(ge=0)
    exact_url_recall_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    reviewed_host_recall_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    lexical_proxy_recall_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    exact_url_mrr: float = Field(ge=0.0, le=1.0)
    reviewed_host_mrr: float = Field(ge=0.0, le=1.0)
    case_success_at_k: float = Field(ge=0.0, le=1.0)
    reviewed_primary_host_recall_at_k: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    mean_candidate_quality_score: float = Field(ge=0.0, le=1.0)
    low_quality_candidate_rate: float = Field(ge=0.0, le=1.0)
    unique_host_rate: float = Field(ge=0.0, le=1.0)
    results: tuple[RetrievalCaseResult, ...]
    limitations: tuple[str, ...]


class RetrievalSnapshotCandidate(DomainModel):
    """One normalized search result stored before strategy-level fusion."""

    url: AnyHttpUrl
    title: str
    snippet: str | None = None
    source_type: SourceType
    publisher: str | None = None


class RetrievalSnapshotQuery(DomainModel):
    """Captured provider response for one exact query string."""

    query: str
    results: tuple[RetrievalSnapshotCandidate, ...]
    error_type: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def results_and_errors_are_exclusive(self) -> "RetrievalSnapshotQuery":
        if self.error_type is not None and self.results:
            raise ValueError("failed snapshot queries cannot contain results")
        if (self.error_type is None) != (self.error_message is None):
            raise ValueError("snapshot query errors require both type and message")
        return self


class RetrievalSearchSnapshot(DomainModel):
    """Versioned raw search-candidate pool for deterministic replay."""

    snapshot_version: Literal[1] = 1
    dataset_id: str
    dataset_version: int
    provider_id: str
    captured_at: datetime
    top_k: int = Field(ge=1, le=20)
    queries: tuple[RetrievalSnapshotQuery, ...]

    @model_validator(mode="after")
    def queries_must_be_unique(self) -> "RetrievalSearchSnapshot":
        values = [item.query for item in self.queries]
        if len(values) != len(set(values)):
            raise ValueError("retrieval snapshot queries must be unique")
        return self


class PageReferenceMatch(DomainModel):
    """Best ranked passage for one reviewed evidence target on one page."""

    annotation_id: str
    lexical_score: float = Field(ge=0.0, le=1.0)
    passage_rank: int | None = Field(default=None, ge=1)
    passage_text: str | None = Field(default=None, max_length=5_000)
    lexical_match: bool


class PageFetchEvaluationResult(DomainModel):
    """Fetch, extraction, and passage-ranking outcome for one candidate."""

    case_id: str
    candidate_rank: int = Field(ge=1)
    requested_url: AnyHttpUrl
    final_url: AnyHttpUrl | None = None
    fetched: bool
    extracted: bool
    content_type: str | None = None
    byte_length: int = Field(default=0, ge=0)
    readable_character_count: int = Field(default=0, ge=0)
    chunk_count: int = Field(default=0, ge=0)
    ranked_passage_count: int = Field(default=0, ge=0)
    best_passage_score: float = Field(default=0.0, ge=0.0)
    best_passage_text: str | None = Field(default=None, max_length=5_000)
    content_hash: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    duplicate_of_url: AnyHttpUrl | None = None
    reference_matches: tuple[PageReferenceMatch, ...] = ()
    matched_reference_ids: tuple[str, ...] = ()
    best_reference_lexical_score: float = Field(ge=0.0, le=1.0)
    error_type: str | None = None
    error_message: str | None = None


class PageFetchCaseResult(DomainModel):
    """Aggregate page and passage outcomes for one benchmark claim."""

    case_id: str
    attempted_count: int = Field(ge=0)
    fetched_count: int = Field(ge=0)
    extracted_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    reference_count: int = Field(ge=0)
    matched_reference_count: int = Field(ge=0)
    first_matching_candidate_rank: int | None = Field(default=None, ge=1)
    pages: tuple[PageFetchEvaluationResult, ...]


class PageFetchEvaluationSummary(DomainModel):
    """Aggregate page-access, extraction, and lexical-passage baseline."""

    dataset_id: str
    dataset_version: int
    retrieval_input: str
    retrieval_strategy: RetrievalQueryStrategy
    fetcher_id: str
    started_at: datetime
    duration_seconds: float = Field(ge=0.0)
    case_count: int = Field(ge=1)
    candidate_top_n: int = Field(ge=1, le=10)
    passage_top_k: int = Field(ge=1, le=20)
    passage_lexical_threshold: float = Field(ge=0.0, le=1.0)
    attempted_page_count: int = Field(ge=0)
    fetched_page_count: int = Field(ge=0)
    extracted_page_count: int = Field(ge=0)
    duplicate_page_count: int = Field(ge=0)
    fetch_success_rate: float = Field(ge=0.0, le=1.0)
    extraction_success_rate: float = Field(ge=0.0, le=1.0)
    duplicate_content_rate: float = Field(ge=0.0, le=1.0)
    reference_count: int = Field(ge=0)
    matched_reference_count: int = Field(ge=0)
    passage_lexical_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    case_passage_success_rate: float = Field(ge=0.0, le=1.0)
    results: tuple[PageFetchCaseResult, ...]
    limitations: tuple[str, ...]


class SemanticPassageJudgment(DomainModel):
    """Structured comparison of a retrieved passage with reviewed evidence meaning."""

    relationship: Literal["equivalent", "partial", "not_equivalent"]
    rationale: str = Field(min_length=20, max_length=2_000)
    matched_points: tuple[str, ...]
    missing_or_conflicting_points: tuple[str, ...]


class SemanticPassageReferenceResult(DomainModel):
    """One bounded semantic recovery attempt for an unmatched reference."""

    case_id: str
    annotation_id: str
    source_url: AnyHttpUrl
    candidate_url: AnyHttpUrl | None = None
    lexical_score: float = Field(ge=0.0, le=1.0)
    passage_rank: int | None = Field(default=None, ge=1)
    evaluated: bool
    judgment: SemanticPassageJudgment | None = None
    error_type: str | None = None
    error_message: str | None = None


class SemanticPassageEvaluationSummary(DomainModel):
    """Aggregate semantic recovery over lexically unmatched evidence targets."""

    dataset_id: str
    dataset_version: int
    page_evaluation_input: str
    provider_id: str
    model: str
    prompt_version: str
    started_at: datetime
    duration_seconds: float = Field(ge=0.0)
    reference_count: int = Field(ge=0)
    lexical_match_count: int = Field(ge=0)
    semantic_candidate_count: int = Field(ge=0)
    evaluated_count: int = Field(ge=0)
    equivalent_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    not_equivalent_count: int = Field(ge=0)
    combined_match_count: int = Field(ge=0)
    combined_passage_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    metered_model_call_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_model_cost_usd: float = Field(ge=0.0)
    results: tuple[SemanticPassageReferenceResult, ...]
    limitations: tuple[str, ...]
