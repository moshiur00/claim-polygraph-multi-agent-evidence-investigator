"""Typed sentence-level citation assurance and review-routing contracts."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import EvidenceStance
from claim_polygraph_ng.domain.provenance import ProvenanceRequirementState
from claim_polygraph_ng.domain.readiness import JudgmentReadinessState


class CitationAssuranceStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    CONTRADICTORY = "contradictory"
    OUT_OF_PACKET = "out_of_packet"


class CitationIssueCode(StrEnum):
    MISSING_CITATION = "missing_citation"
    OUT_OF_PACKET = "out_of_packet"
    MISSING_REQUIRED_PHRASE = "missing_required_phrase"
    STANCE_MISMATCH = "stance_mismatch"
    EVIDENCE_RECORD_MISSING = "evidence_record_missing"


class StructuredReportAssertion(DomainModel):
    """One material report sentence with deterministic support expectations."""

    assertion_id: UUID = Field(default_factory=uuid4)
    claim_id: UUID
    sentence: str = Field(min_length=3, max_length=5_000)
    cited_evidence_ids: tuple[UUID, ...] = ()
    asserted_stance: EvidenceStance
    required_phrases: tuple[str, ...] = Field(min_length=1, max_length=20)
    material: bool = True
    critical: bool = False

    @model_validator(mode="after")
    def validate_required_phrases(self) -> "StructuredReportAssertion":
        normalized = tuple(" ".join(item.casefold().split()) for item in self.required_phrases)
        if any(not item for item in normalized):
            raise ValueError("required phrases cannot be blank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("required phrases must be unique after normalization")
        return self


class AssertionEvidenceLink(DomainModel):
    """Exact approved passage connected to one report assertion."""

    evidence_id: UUID
    passage: str = Field(min_length=1, max_length=40_000)
    stance: EvidenceStance
    matched_phrases: tuple[str, ...] = ()


class CitationAssuranceFinding(DomainModel):
    """Deterministic result for one structured report assertion."""

    assertion_id: UUID
    sentence: str
    material: bool
    critical: bool
    status: CitationAssuranceStatus
    links: tuple[AssertionEvidenceLink, ...] = ()
    missing_phrases: tuple[str, ...] = ()
    issue_codes: tuple[CitationIssueCode, ...] = ()
    explanation: str = Field(min_length=3, max_length=5_000)

    @model_validator(mode="after")
    def supported_finding_has_no_issue(self) -> "CitationAssuranceFinding":
        if self.status is CitationAssuranceStatus.SUPPORTED:
            if not self.links or self.missing_phrases or self.issue_codes:
                raise ValueError("supported assertions need links and no unresolved issue")
        elif not self.issue_codes:
            raise ValueError("non-supported assertions require an issue code")
        return self


class CitationAssurancePacket(DomainModel):
    """Claim-level deterministic citation assurance summary."""

    claim_id: UUID
    approved_evidence_ids: tuple[UUID, ...]
    findings: tuple[CitationAssuranceFinding, ...] = Field(min_length=1)
    supported_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    unsupported_count: int = Field(ge=0)
    contradictory_count: int = Field(ge=0)
    out_of_packet_count: int = Field(ge=0)
    full_support_rate: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_aggregates(self) -> "CitationAssurancePacket":
        statuses = [item.status for item in self.findings]
        expected = {
            CitationAssuranceStatus.SUPPORTED: self.supported_count,
            CitationAssuranceStatus.PARTIAL: self.partial_count,
            CitationAssuranceStatus.UNSUPPORTED: self.unsupported_count,
            CitationAssuranceStatus.CONTRADICTORY: self.contradictory_count,
            CitationAssuranceStatus.OUT_OF_PACKET: self.out_of_packet_count,
        }
        if any(statuses.count(status) != count for status, count in expected.items()):
            raise ValueError("citation assurance counts do not match findings")
        if abs(self.full_support_rate - self.supported_count / len(self.findings)) > 1e-9:
            raise ValueError("full support rate does not match findings")
        return self


class ReviewRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewPriority(StrEnum):
    STANDARD = "standard"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewTrigger(StrEnum):
    CRITICAL_CITATION_FAILURE = "critical_citation_failure"
    MATERIAL_CITATION_FAILURE = "material_citation_failure"
    OUT_OF_PACKET_CITATION = "out_of_packet_citation"
    CRITICAL_VERIFICATION_UNRESOLVED = "critical_verification_unresolved"
    READINESS_REQUIRES_REVIEW = "readiness_requires_review"
    PROVENANCE_UNCERTAIN = "provenance_uncertain"
    POLICY_DISAGREEMENT = "policy_disagreement"
    BLOCKING_CHALLENGE = "blocking_challenge"
    VERDICT_REQUESTED_REVIEW = "verdict_requested_review"
    HIGH_RISK = "high_risk"


class ReviewRoutingContext(DomainModel):
    """Deterministic inputs allowed to affect human-review routing."""

    claim_id: UUID
    risk_level: ReviewRiskLevel
    citation_assurance: CitationAssurancePacket
    readiness_state: JudgmentReadinessState
    provenance_state: ProvenanceRequirementState
    critical_verification_unresolved: bool = False
    policy_disagreement: bool = False
    blocking_challenge_count: int = Field(default=0, ge=0)
    verdict_requested_review: bool = False

    @model_validator(mode="after")
    def packet_matches_claim(self) -> "ReviewRoutingContext":
        if self.citation_assurance.claim_id != self.claim_id:
            raise ValueError("citation assurance packet must match the routing claim")
        return self


class ReviewRoutingDecision(DomainModel):
    """Auditable deterministic review decision, never a verdict."""

    claim_id: UUID
    review_required: bool
    priority: ReviewPriority
    triggers: tuple[ReviewTrigger, ...]
    reason: str = Field(min_length=3, max_length=5_000)

    @model_validator(mode="after")
    def triggers_match_decision(self) -> "ReviewRoutingDecision":
        if self.review_required != bool(self.triggers):
            raise ValueError("review-required decisions must have one or more triggers")
        return self
