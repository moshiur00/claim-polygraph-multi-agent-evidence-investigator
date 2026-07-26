"""Enumerations shared by investigation artifacts."""

from enum import StrEnum


class ClaimType(StrEnum):
    """Broad claim shapes used for routing and evaluation."""

    FACTUAL = "factual"
    NUMERICAL = "numerical"
    TEMPORAL = "temporal"
    COMPARATIVE = "comparative"
    CAUSAL = "causal"
    SCIENTIFIC = "scientific"
    LEGAL = "legal"
    HISTORICAL = "historical"
    PREDICTION = "prediction"
    OTHER = "other"


class ResearchPath(StrEnum):
    """Available evidence-research paths."""

    PRIMARY = "primary"
    GENERAL = "general"
    FACT_CHECK = "fact_check"
    ACADEMIC = "academic"
    CONTRADICTION = "contradiction"


class SourceType(StrEnum):
    """Source categories used by planning and quality assessment."""

    OFFICIAL = "official"
    PRIMARY_DOCUMENT = "primary_document"
    DATASET = "dataset"
    LAW_OR_REGULATION = "law_or_regulation"
    ACADEMIC = "academic"
    NEWS = "news"
    FACT_CHECK = "fact_check"
    ORGANIZATION = "organization"
    EXPERT = "expert"
    OTHER = "other"


class EvidenceStance(StrEnum):
    """Relationship between an evidence passage and a claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    CONTEXT = "context"
    IRRELEVANT = "irrelevant"


class ExtractionStatus(StrEnum):
    """Outcome of extracting evidence from a source."""

    EXTRACTED = "extracted"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class RightsStatus(StrEnum):
    """Recorded copyright or reuse status; unknown is the safe default."""

    UNKNOWN = "unknown"
    LICENSED = "licensed"
    PUBLIC_DOMAIN = "public_domain"
    PERMISSION_CONFIRMED = "permission_confirmed"
    LEGAL_EXCEPTION_ASSERTED = "legal_exception_asserted"


class ContentRetention(StrEnum):
    """How much retrieved source content may be stored durably."""

    METADATA_ONLY = "metadata_only"
    EVIDENCE_PASSAGES_ONLY = "evidence_passages_only"


class VerdictLabel(StrEnum):
    """Nuanced verdict taxonomy."""

    SUPPORTED = "supported"
    MOSTLY_SUPPORTED = "mostly_supported"
    MIXED = "mixed"
    MISLEADING = "misleading"
    OUTDATED = "outdated"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


class SupportLevel(StrEnum):
    """Sentence-level citation support."""

    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class AuditIssue(StrEnum):
    """Material citation and report issues."""

    MISSING_CITATION = "missing_citation"
    CITATION_MISMATCH = "citation_mismatch"
    PARTIAL_SUPPORT = "partial_support"
    NUMERICAL_MISMATCH = "numerical_mismatch"
    TEMPORAL_MISMATCH = "temporal_mismatch"
    OVERSTATEMENT = "overstatement"
    SOURCE_NOT_APPROVED = "source_not_approved"
