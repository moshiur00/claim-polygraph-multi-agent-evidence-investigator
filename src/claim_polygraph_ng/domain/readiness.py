"""Explainable judgment-readiness features without a truth probability."""

from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class JudgmentReadinessState(StrEnum):
    READY = "ready"
    QUALIFIED = "qualified"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class ReadinessReasonCode(StrEnum):
    COMPLETE = "complete"
    MATERIAL_PROPOSITION_UNRESOLVED = "material_proposition_unresolved"
    CRITICAL_VERIFICATION_UNRESOLVED = "critical_verification_unresolved"
    CITATION_AUDIT_INCOMPLETE = "citation_audit_incomplete"
    BLOCKING_CHALLENGE = "blocking_challenge"
    QUALIFIED_PROPOSITION = "qualified_proposition"
    PROVENANCE_UNCERTAIN = "provenance_uncertain"
    NONBLOCKING_CHALLENGE = "nonblocking_challenge"
    SOURCE_QUALITY_UNKNOWN = "source_quality_unknown"
    SOCIAL_EVIDENCE_RISK = "social_evidence_risk"
    BLOCKING_SOCIAL_EVIDENCE_RISK = "blocking_social_evidence_risk"
    SOCIAL_ARGUMENT_POLICY_REVIEW = "social_argument_policy_review"
    SOCIAL_ARGUMENT_POLICY_BLOCKED = "social_argument_policy_blocked"
    UNRESOLVED_QUESTIONS = "unresolved_questions"


class JudgmentReadiness(DomainModel):
    claim_id: UUID
    readiness_version: str = Field(
        default="judgment-readiness-v1", pattern=r"^judgment-readiness-v1$"
    )
    state: JudgmentReadinessState
    material_proposition_count: int = Field(ge=0)
    resolved_material_proposition_count: int = Field(ge=0)
    material_coverage: float = Field(ge=0, le=1)
    supporting_evidence_count: int = Field(ge=0)
    counterevidence_count: int = Field(ge=0)
    confirmed_independent_lower_bound: int | None = Field(default=None, ge=0)
    possible_independent_upper_bound: int | None = Field(default=None, ge=0)
    unresolved_dependency_count: int = Field(ge=0)
    verification_assertion_count: int = Field(ge=0)
    completed_verification_count: int = Field(ge=0)
    verification_completeness: float = Field(ge=0, le=1)
    source_quality_unknown_count: int = Field(ge=0)
    citation_audit_complete: bool
    blocking_challenge_count: int = Field(ge=0)
    nonblocking_challenge_count: int = Field(ge=0)
    unresolved_question_count: int = Field(ge=0)
    reason_codes: tuple[ReadinessReasonCode, ...] = Field(min_length=1)
    confidence_score: None = None
    limitations: tuple[str, ...]
    social_risk_finding_count: int = Field(default=0, ge=0)
    blocking_social_risk_count: int = Field(default=0, ge=0)
    social_policy_finding_count: int = Field(default=0, ge=0)
    blocking_social_policy_finding_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "JudgmentReadiness":
        if self.resolved_material_proposition_count > self.material_proposition_count:
            raise ValueError("resolved propositions cannot exceed material propositions")
        if self.completed_verification_count > self.verification_assertion_count:
            raise ValueError("completed verification cannot exceed assertion count")
        return self
