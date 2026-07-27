"""Explainable source-quality dimensions without a universal trust score."""

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from claim_polygraph_ng.domain import SourceType
from claim_polygraph_ng.domain.base import DomainModel

SOURCE_QUALITY_VERSION = "dimensions-v1"


class QualityFinding(StrEnum):
    """Direction of one source-quality finding."""

    FAVORABLE = "favorable"
    MIXED = "mixed"
    UNFAVORABLE = "unfavorable"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class SourceQualityDimension(StrEnum):
    """Explicit dimensions that must never be collapsed into truth."""

    AUTHORITY = "authority"
    DIRECTNESS = "directness"
    METHODOLOGICAL_TRANSPARENCY = "methodological_transparency"
    EDITORIAL_ACCOUNTABILITY = "editorial_accountability"
    CITATION_TRANSPARENCY = "citation_transparency"
    TEMPORAL_RELEVANCE = "temporal_relevance"
    DOMAIN_RELEVANCE = "domain_relevance"
    CONFLICT_OF_INTEREST = "conflict_of_interest"


class DimensionAssessment(DomainModel):
    """One auditable quality observation."""

    dimension: SourceQualityDimension
    finding: QualityFinding
    reason: str = Field(min_length=1)
    signals: tuple[str, ...] = ()


class SourceQualityMetadata(DomainModel):
    """Optional, explicitly observed metadata used by deterministic rules."""

    source_id: UUID | None = None
    source_type: SourceType
    publisher_identified: bool
    author_identified: bool
    publication_date: date | None = None
    domain_relevance_confirmed: bool | None = None
    institutional_authority_confirmed: bool | None = None
    primary_for_assertion: bool | None = None
    methodology_disclosed: bool | None = None
    citations_disclosed: bool | None = None
    editorial_policy_disclosed: bool | None = None
    correction_policy_disclosed: bool | None = None
    conflict_disclosed: bool | None = None
    interested_party: bool | None = None
    temporally_compatible: bool | None = None


class SourceQualityAssessment(DomainModel):
    """Versioned dimension set; deliberately has no aggregate score."""

    source_id: UUID | None = None
    assessment_version: str = SOURCE_QUALITY_VERSION
    dimensions: tuple[DimensionAssessment, ...] = Field(min_length=8, max_length=8)
    limitations: tuple[str, ...]


def assess_source_quality(metadata: SourceQualityMetadata) -> SourceQualityAssessment:
    """Assess only observed metadata and preserve unknowns."""
    dimensions = (
        _authority(metadata),
        _boolean_dimension(
            SourceQualityDimension.DIRECTNESS,
            metadata.primary_for_assertion,
            "The source is primary for the material assertion.",
            "The source is secondary for the material assertion.",
            "Whether the source is primary for this assertion is not established.",
        ),
        _boolean_dimension(
            SourceQualityDimension.METHODOLOGICAL_TRANSPARENCY,
            metadata.methodology_disclosed,
            "The source discloses a method relevant to the assertion.",
            "The source makes a method-dependent assertion without disclosing its method.",
            "Methodological disclosure was not assessed from the available metadata.",
        ),
        _accountability(metadata),
        _boolean_dimension(
            SourceQualityDimension.CITATION_TRANSPARENCY,
            metadata.citations_disclosed,
            "The source identifies the material references behind its assertion.",
            "The source does not identify material references behind its assertion.",
            "Citation disclosure is unknown from the available metadata.",
        ),
        _boolean_dimension(
            SourceQualityDimension.TEMPORAL_RELEVANCE,
            metadata.temporally_compatible,
            "The publication timing is compatible with the claim context.",
            "The publication timing is incompatible with the claim context.",
            "Temporal compatibility was not established.",
        ),
        _boolean_dimension(
            SourceQualityDimension.DOMAIN_RELEVANCE,
            metadata.domain_relevance_confirmed,
            "The source has demonstrated relevance to the claim domain.",
            "The source is outside the demonstrated claim domain.",
            "Domain relevance was not established.",
        ),
        _conflict(metadata),
    )
    return SourceQualityAssessment(
        source_id=metadata.source_id,
        dimensions=dimensions,
        limitations=(
            "These dimensions describe evidence conditions and do not determine truth.",
            "Unknown findings must not be converted into unfavorable or favorable findings.",
            "Publisher or source type alone is insufficient to accept or reject evidence.",
        ),
    )


def _authority(metadata: SourceQualityMetadata) -> DimensionAssessment:
    if metadata.institutional_authority_confirmed is True:
        return DimensionAssessment(
            dimension=SourceQualityDimension.AUTHORITY,
            finding=QualityFinding.FAVORABLE,
            reason="Applicable institutional authority is explicitly confirmed.",
            signals=(metadata.source_type.value,),
        )
    if metadata.institutional_authority_confirmed is False:
        return DimensionAssessment(
            dimension=SourceQualityDimension.AUTHORITY,
            finding=QualityFinding.UNFAVORABLE,
            reason="The source lacks authority for the material assertion.",
            signals=(metadata.source_type.value,),
        )
    return DimensionAssessment(
        dimension=SourceQualityDimension.AUTHORITY,
        finding=QualityFinding.UNKNOWN,
        reason="Source type does not establish claim-specific authority.",
        signals=(metadata.source_type.value,),
    )


def _accountability(metadata: SourceQualityMetadata) -> DimensionAssessment:
    observed = (
        metadata.editorial_policy_disclosed is True and metadata.correction_policy_disclosed is True
    )
    explicitly_absent = (
        metadata.editorial_policy_disclosed is False
        and metadata.correction_policy_disclosed is False
    )
    if observed:
        finding = QualityFinding.FAVORABLE
        reason = "Editorial responsibility and a correction policy are disclosed."
    elif explicitly_absent:
        finding = QualityFinding.UNFAVORABLE
        reason = "Neither editorial responsibility nor a correction policy is disclosed."
    else:
        finding = QualityFinding.UNKNOWN
        reason = "Editorial and correction accountability is not fully established."
    signals = tuple(
        signal
        for signal, present in (
            ("publisher_identified", metadata.publisher_identified),
            ("author_identified", metadata.author_identified),
        )
        if present
    )
    return DimensionAssessment(
        dimension=SourceQualityDimension.EDITORIAL_ACCOUNTABILITY,
        finding=finding,
        reason=reason,
        signals=signals,
    )


def _conflict(metadata: SourceQualityMetadata) -> DimensionAssessment:
    if metadata.interested_party is True:
        return DimensionAssessment(
            dimension=SourceQualityDimension.CONFLICT_OF_INTEREST,
            finding=QualityFinding.UNFAVORABLE,
            reason="The source is an interested party for the material assertion.",
            signals=("interested_party",),
        )
    if metadata.conflict_disclosed is True:
        return DimensionAssessment(
            dimension=SourceQualityDimension.CONFLICT_OF_INTEREST,
            finding=QualityFinding.MIXED,
            reason="A potential conflict is disclosed and must be considered explicitly.",
            signals=("conflict_disclosed",),
        )
    return DimensionAssessment(
        dimension=SourceQualityDimension.CONFLICT_OF_INTEREST,
        finding=QualityFinding.UNKNOWN,
        reason="Absence of a known conflict is not evidence that no conflict exists.",
    )


def _boolean_dimension(
    dimension: SourceQualityDimension,
    value: bool | None,
    favorable_reason: str,
    unfavorable_reason: str,
    unknown_reason: str,
) -> DimensionAssessment:
    finding = (
        QualityFinding.FAVORABLE
        if value is True
        else QualityFinding.UNFAVORABLE
        if value is False
        else QualityFinding.UNKNOWN
    )
    reason = (
        favorable_reason
        if value is True
        else unfavorable_reason
        if value is False
        else unknown_reason
    )
    return DimensionAssessment(dimension=dimension, finding=finding, reason=reason)
