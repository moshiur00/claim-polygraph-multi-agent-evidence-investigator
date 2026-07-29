"""Evidence-family, source-independence, and consolidation artifacts."""

from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.models import Evidence, Source


class ConsolidationReason(StrEnum):
    """Auditable deterministic reasons for merging one stored record."""

    CANONICAL_URL = "canonical_url"
    EXACT_NORMALIZED_PASSAGE = "exact_normalized_passage"


class ConsolidationDecision(DomainModel):
    """One conservative many-to-one record consolidation."""

    representative_id: UUID
    merged_ids: tuple[UUID, ...] = Field(min_length=1)
    reasons: tuple[ConsolidationReason, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def representative_is_not_merged(self) -> "ConsolidationDecision":
        if self.representative_id in self.merged_ids:
            raise ValueError("representative_id cannot also be a merged_id")
        if len(set(self.merged_ids)) != len(self.merged_ids):
            raise ValueError("merged IDs must be unique")
        return self


class EvidenceFamily(DomainModel):
    """Sources grouped because they may not be independent confirmations."""

    family_id: UUID
    source_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    hostnames: tuple[str, ...]
    publishers: tuple[str, ...] = ()
    grouping_reasons: tuple[str, ...]

    @model_validator(mode="after")
    def family_must_have_members(self) -> "EvidenceFamily":
        if not self.source_ids or not self.evidence_ids:
            raise ValueError("evidence families require sources and evidence")
        return self


class IndependenceAnalysis(DomainModel):
    """Auditable deterministic evidence-family analysis."""

    claim_id: UUID
    required_independent_families: int = Field(ge=1, le=10)
    families: tuple[EvidenceFamily, ...]
    limitations: tuple[str, ...] = ()

    @property
    def independent_family_count(self) -> int:
        return len(self.families)

    @property
    def requirement_met(self) -> bool:
        return self.independent_family_count >= self.required_independent_families


class ProvenanceRequirementState(StrEnum):
    """Whether conservative independence bounds settle the requirement."""

    MET = "met"
    NOT_MET = "not_met"
    UNCERTAIN = "uncertain"


class SocialRiskSeverity(StrEnum):
    """Readiness impact of one deterministic social-evidence risk."""

    INFO = "info"
    CAUTION = "caution"
    BLOCKING = "blocking"


class SocialRiskCode(StrEnum):
    """Typed social-evidence conditions surfaced to readiness and review."""

    IDENTITY_UNRESOLVED = "identity_unresolved"
    ACCOUNT_UNAUTHENTICATED = "account_unauthenticated"
    AUTHORITY_SCOPE_MISSING = "authority_scope_missing"
    ORIGIN_UNRESOLVED = "origin_unresolved"
    SHARED_ORIGIN_REPETITION = "shared_origin_repetition"
    SCREENSHOT_OR_COPY = "screenshot_or_copy"
    UNAVAILABLE_WITHOUT_VERIFIED_ARCHIVE = "unavailable_without_verified_archive"
    INELIGIBLE_SOCIAL_EVIDENCE_USED = "ineligible_social_evidence_used"
    UNAUTHORIZED_DECISIVE_USE = "unauthorized_decisive_use"
    SOCIAL_ONLY_EVIDENCE_PACKET = "social_only_evidence_packet"
    ENGAGEMENT_SIGNAL_IGNORED = "engagement_signal_ignored"
    PLATFORM_BADGE_IGNORED = "platform_badge_ignored"


class SocialRiskFinding(DomainModel):
    """One source-scoped or packet-scoped social-evidence safeguard."""

    code: SocialRiskCode
    severity: SocialRiskSeverity
    reason: str = Field(min_length=10, max_length=2_000)
    source_id: UUID | None = None
    evidence_ids: tuple[UUID, ...] = ()


class ProvenanceDependency(DomainModel):
    """One persisted pairwise source-dependency observation."""

    left_source_id: UUID
    right_source_id: UUID
    status: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    reasons: tuple[str, ...] = Field(min_length=1)


class ProvenanceFamily(DomainModel):
    """One persisted source family inferred for this investigation."""

    family_id: str = Field(min_length=1)
    source_ids: tuple[UUID, ...] = Field(min_length=1)
    grouping_reasons: tuple[str, ...] = ()


class ProvenanceQualityDimension(DomainModel):
    """One explainable source-quality dimension."""

    dimension: str = Field(min_length=1)
    finding: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    signals: tuple[str, ...] = ()


class ProvenanceSourceQuality(DomainModel):
    """Persisted quality observations for one source, without an aggregate score."""

    source_id: UUID
    dimensions: tuple[ProvenanceQualityDimension, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = ()
    ignored_signals: tuple[str, ...] = ()


class InvestigationProvenance(DomainModel):
    """Optional provenance packet produced after evidence consolidation."""

    claim_id: UUID
    provenance_version: str = "investigation-provenance-v1"
    source_ids: tuple[UUID, ...]
    families: tuple[ProvenanceFamily, ...]
    dependencies: tuple[ProvenanceDependency, ...]
    source_quality: tuple[ProvenanceSourceQuality, ...]
    confirmed_independent_lower_bound: int = Field(ge=0)
    possible_independent_upper_bound: int = Field(ge=0)
    unresolved_dependency_count: int = Field(ge=0)
    required_independent_families: int = Field(ge=1)
    requirement_state: ProvenanceRequirementState
    limitations: tuple[str, ...]
    social_risk_findings: tuple[SocialRiskFinding, ...] = ()

    @model_validator(mode="after")
    def validate_bounds_and_references(self) -> "InvestigationProvenance":
        if self.confirmed_independent_lower_bound > self.possible_independent_upper_bound:
            raise ValueError("confirmed lower bound cannot exceed possible upper bound")
        known = set(self.source_ids)
        referenced = {
            source_id for family in self.families for source_id in family.source_ids
        }
        referenced.update(
            source_id
            for dependency in self.dependencies
            for source_id in (dependency.left_source_id, dependency.right_source_id)
        )
        referenced.update(item.source_id for item in self.source_quality)
        referenced.update(
            item.source_id
            for item in self.social_risk_findings
            if item.source_id is not None
        )
        if not referenced.issubset(known):
            raise ValueError("provenance records must reference stored source IDs")
        return self


class EvidenceConsolidation(DomainModel):
    """Order-invariant consolidated packet with explicit merge provenance."""

    claim_id: UUID
    sources: tuple[Source, ...]
    evidence: tuple[Evidence, ...]
    independence: IndependenceAnalysis
    source_decisions: tuple[ConsolidationDecision, ...] = ()
    evidence_decisions: tuple[ConsolidationDecision, ...] = ()
    input_source_count: int = Field(ge=0)
    input_evidence_count: int = Field(ge=0)

    @property
    def removed_source_count(self) -> int:
        return self.input_source_count - len(self.sources)

    @property
    def removed_evidence_count(self) -> int:
        return self.input_evidence_count - len(self.evidence)
