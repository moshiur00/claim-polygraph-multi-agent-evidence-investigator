"""Deterministic evidence analysis."""

from claim_polygraph_ng.analysis.aggregation import (
    aggregate_component_label,
    constrain_parent_verdict,
)
from claim_polygraph_ng.analysis.argument_ledger import build_argument_ledger
from claim_polygraph_ng.analysis.canonicalization import (
    CANONICALIZATION_VERSION,
    CanonicalizationReason,
    CanonicalizationResult,
    canonicalize_doi,
    canonicalize_url,
)
from claim_polygraph_ng.analysis.citation_assurance import (
    assure_full_report,
    audit_structured_assertions,
)
from claim_polygraph_ng.analysis.consolidation import consolidate_evidence
from claim_polygraph_ng.analysis.context import verify_claim_context
from claim_polygraph_ng.analysis.evidence_families import (
    EVIDENCE_FAMILY_VERSION,
    DependencyStatus,
    EvidenceFamilyInference,
    FamilySourceRecord,
    InferredEvidenceFamily,
    SourceDependencyEdge,
    infer_evidence_families,
)
from claim_polygraph_ng.analysis.exact_duplicates import (
    EXACT_FINGERPRINT_VERSION,
    ContentFingerprint,
    ExactDuplicateCluster,
    cluster_exact_duplicates,
    fingerprint_content,
    normalize_exact_content,
)
from claim_polygraph_ng.analysis.independence import analyze_source_independence
from claim_polygraph_ng.analysis.independence_features import (
    INDEPENDENCE_FEATURE_VERSION,
    IndependenceFeatures,
    IndependenceRequirementState,
    calculate_independence_features,
)
from claim_polygraph_ng.analysis.judgment_policy import (
    JUDGMENT_POLICY_VERSION,
    enforce_judgment_policy,
)
from claim_polygraph_ng.analysis.near_duplicates import (
    NEAR_DUPLICATE_VERSION,
    NearDuplicateAssessment,
    NearDuplicateLabel,
    NearDuplicateSignals,
    assess_near_duplicate,
)
from claim_polygraph_ng.analysis.numerical_verification import (
    NUMERICAL_VERIFIER_VERSION,
    NumericalEvidenceOperand,
    NumericalVerificationRequest,
    RankOrder,
    verify_numerical_assertion,
)
from claim_polygraph_ng.analysis.provenance_links import (
    PROVENANCE_LINK_VERSION,
    ExtractedProvenanceLink,
    ProvenanceLinkType,
    extract_provenance_links,
)
from claim_polygraph_ng.analysis.readiness import (
    READINESS_VERSION,
    calculate_judgment_readiness,
)
from claim_polygraph_ng.analysis.research_routing import (
    route_research_roles,
    route_targeted_research_roles,
)
from claim_polygraph_ng.analysis.review_routing import route_human_review
from claim_polygraph_ng.analysis.source_quality import (
    SOURCE_QUALITY_VERSION,
    DimensionAssessment,
    QualityFinding,
    SourceQualityAssessment,
    SourceQualityDimension,
    SourceQualityMetadata,
    assess_source_quality,
)
from claim_polygraph_ng.analysis.stance import (
    EvidenceStanceProfile,
    deterministic_stance_label,
    stance_profile,
)
from claim_polygraph_ng.analysis.sufficiency import (
    assess_evidence_sufficiency,
    calculate_evidence_gain,
    satisfied_requirement_ids,
    targeted_roles,
)
from claim_polygraph_ng.analysis.temporal_verification import (
    TEMPORAL_VERIFIER_VERSION,
    TemporalEvidenceFact,
    TemporalFactStatus,
    TemporalVerificationRequest,
    verify_temporal_assertion,
)
from claim_polygraph_ng.analysis.verification_bridge import bridge_legacy_verification

__all__ = [
    "CANONICALIZATION_VERSION",
    "EVIDENCE_FAMILY_VERSION",
    "EXACT_FINGERPRINT_VERSION",
    "INDEPENDENCE_FEATURE_VERSION",
    "JUDGMENT_POLICY_VERSION",
    "NEAR_DUPLICATE_VERSION",
    "NUMERICAL_VERIFIER_VERSION",
    "PROVENANCE_LINK_VERSION",
    "READINESS_VERSION",
    "SOURCE_QUALITY_VERSION",
    "TEMPORAL_VERIFIER_VERSION",
    "CanonicalizationReason",
    "CanonicalizationResult",
    "ContentFingerprint",
    "DependencyStatus",
    "DimensionAssessment",
    "EvidenceFamilyInference",
    "EvidenceStanceProfile",
    "ExactDuplicateCluster",
    "ExtractedProvenanceLink",
    "FamilySourceRecord",
    "IndependenceFeatures",
    "IndependenceRequirementState",
    "InferredEvidenceFamily",
    "NearDuplicateAssessment",
    "NearDuplicateLabel",
    "NearDuplicateSignals",
    "NumericalEvidenceOperand",
    "NumericalVerificationRequest",
    "ProvenanceLinkType",
    "QualityFinding",
    "RankOrder",
    "SourceDependencyEdge",
    "SourceQualityAssessment",
    "SourceQualityDimension",
    "SourceQualityMetadata",
    "TemporalEvidenceFact",
    "TemporalFactStatus",
    "TemporalVerificationRequest",
    "aggregate_component_label",
    "analyze_source_independence",
    "assess_evidence_sufficiency",
    "assess_near_duplicate",
    "assess_source_quality",
    "assure_full_report",
    "audit_structured_assertions",
    "bridge_legacy_verification",
    "build_argument_ledger",
    "calculate_evidence_gain",
    "calculate_independence_features",
    "calculate_judgment_readiness",
    "canonicalize_doi",
    "canonicalize_url",
    "cluster_exact_duplicates",
    "consolidate_evidence",
    "constrain_parent_verdict",
    "deterministic_stance_label",
    "enforce_judgment_policy",
    "extract_provenance_links",
    "fingerprint_content",
    "infer_evidence_families",
    "normalize_exact_content",
    "route_human_review",
    "route_research_roles",
    "route_targeted_research_roles",
    "satisfied_requirement_ids",
    "stance_profile",
    "targeted_roles",
    "verify_claim_context",
    "verify_numerical_assertion",
    "verify_temporal_assertion",
]
