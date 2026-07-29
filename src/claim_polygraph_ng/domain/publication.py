"""Deterministic publication decision derived from authoritative artifacts."""

from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.citation import FullReportCitationAssurance, PublicationGateStatus
from claim_polygraph_ng.domain.enums import VerdictLabel
from claim_polygraph_ng.domain.judgment import JudgmentPolicyTrace
from claim_polygraph_ng.domain.models import Verdict
from claim_polygraph_ng.domain.readiness import (
    JudgmentReadiness,
    JudgmentReadinessState,
)
from claim_polygraph_ng.domain.social_constraints import SocialEvidencePolicyResult


class AuthoritativePublicationStatus(StrEnum):
    READY = "ready"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


class AuthoritativePublicationDecision(DomainModel):
    decision_id: UUID
    investigation_id: UUID
    claim_id: UUID
    proposed_label: VerdictLabel
    enforced_label: VerdictLabel
    judgment_policy_applied: bool
    citation_revision_count: int = Field(ge=0)
    citation_support_rate: float = Field(ge=0, le=1)
    unsupported_critical_assertion_count: int = Field(ge=0)
    readiness_state: JudgmentReadinessState
    status: AuthoritativePublicationStatus
    publication_allowed: bool
    human_review_required: bool
    reason_codes: tuple[str, ...] = Field(min_length=1)
    blocking_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_decision(self) -> "AuthoritativePublicationDecision":
        if self.publication_allowed != (
            self.status is AuthoritativePublicationStatus.READY
        ):
            raise ValueError("publication permission must match ready status")
        if self.status is AuthoritativePublicationStatus.BLOCKED and not (
            self.blocking_reasons
        ):
            raise ValueError("blocked publication requires reasons")
        if self.status is AuthoritativePublicationStatus.REVIEW_REQUIRED and not (
            self.human_review_required
        ):
            raise ValueError("review-required publication must route review")
        return self


def decide_publication(
    *,
    investigation_id: UUID,
    proposed_verdict: Verdict,
    enforced_verdict: Verdict,
    policy: JudgmentPolicyTrace,
    assurance: FullReportCitationAssurance,
    readiness: JudgmentReadiness,
    social_policy: SocialEvidencePolicyResult | None = None,
) -> AuthoritativePublicationDecision:
    """Fail closed on citation failures, then route remaining review conditions."""
    if len(
        {
            proposed_verdict.claim_id,
            enforced_verdict.claim_id,
            policy.claim_id,
            assurance.claim_id,
            readiness.claim_id,
            *( (social_policy.claim_id,) if social_policy is not None else () ),
        }
    ) != 1:
        raise ValueError("publication inputs must reference one claim")
    reasons = list(assurance.blocking_reasons)
    reason_codes = []
    if social_policy is not None and social_policy.publication_blocked:
        status = AuthoritativePublicationStatus.BLOCKED
        reason_codes.append("social_evidence_policy_blocked")
        reasons.extend(social_policy.blocking_reasons)
    elif assurance.publication_status is PublicationGateStatus.BLOCKED:
        status = AuthoritativePublicationStatus.BLOCKED
        reason_codes.append("citation_assurance_blocked")
    elif (
        enforced_verdict.human_review_required
        or policy.human_review_required
        or readiness.state is JudgmentReadinessState.HUMAN_REVIEW_REQUIRED
        or bool(social_policy and social_policy.requires_human_review)
    ):
        status = AuthoritativePublicationStatus.REVIEW_REQUIRED
        reason_codes.append("authoritative_review_required")
    else:
        status = AuthoritativePublicationStatus.READY
        reason_codes.append("all_publication_gates_passed")
    review = status is not AuthoritativePublicationStatus.READY
    if status is AuthoritativePublicationStatus.REVIEW_REQUIRED:
        reasons.append("Human approval is required before publication.")
    identity = (
        f"{investigation_id}:{proposed_verdict.verdict_id}:"
        f"{enforced_verdict.verdict_id}:{status.value}"
    )
    return AuthoritativePublicationDecision(
        decision_id=uuid5(NAMESPACE_URL, f"publication:{identity}"),
        investigation_id=investigation_id,
        claim_id=enforced_verdict.claim_id,
        proposed_label=proposed_verdict.label,
        enforced_label=enforced_verdict.label,
        judgment_policy_applied=policy.applied,
        citation_revision_count=len(assurance.revisions),
        citation_support_rate=assurance.final_audit.full_support_rate,
        unsupported_critical_assertion_count=assurance.critical_failure_count,
        readiness_state=readiness.state,
        status=status,
        publication_allowed=status is AuthoritativePublicationStatus.READY,
        human_review_required=review,
        reason_codes=tuple(reason_codes),
        blocking_reasons=tuple(reasons),
    )
