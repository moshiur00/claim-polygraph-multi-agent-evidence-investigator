"""Deterministic, explainable human-review routing."""

from claim_polygraph_ng.domain.citation import (
    CitationAssuranceStatus,
    ReviewPriority,
    ReviewRiskLevel,
    ReviewRoutingContext,
    ReviewRoutingDecision,
    ReviewTrigger,
)
from claim_polygraph_ng.domain.provenance import ProvenanceRequirementState
from claim_polygraph_ng.domain.readiness import JudgmentReadinessState


def route_human_review(context: ReviewRoutingContext) -> ReviewRoutingDecision:
    """Route conservatively from typed diagnostics without changing the verdict."""
    triggers: list[ReviewTrigger] = []
    findings = context.citation_assurance.findings
    failed = {
        CitationAssuranceStatus.PARTIAL,
        CitationAssuranceStatus.UNSUPPORTED,
        CitationAssuranceStatus.CONTRADICTORY,
        CitationAssuranceStatus.OUT_OF_PACKET,
    }
    if any(item.critical and item.status in failed for item in findings):
        triggers.append(ReviewTrigger.CRITICAL_CITATION_FAILURE)
    if any(item.material and item.status in failed for item in findings):
        triggers.append(ReviewTrigger.MATERIAL_CITATION_FAILURE)
    if any(
        item.status is CitationAssuranceStatus.OUT_OF_PACKET for item in findings
    ):
        triggers.append(ReviewTrigger.OUT_OF_PACKET_CITATION)
    if context.critical_verification_unresolved:
        triggers.append(ReviewTrigger.CRITICAL_VERIFICATION_UNRESOLVED)
    if context.readiness_state is JudgmentReadinessState.HUMAN_REVIEW_REQUIRED:
        triggers.append(ReviewTrigger.READINESS_REQUIRES_REVIEW)
    if context.provenance_state is ProvenanceRequirementState.UNCERTAIN:
        triggers.append(ReviewTrigger.PROVENANCE_UNCERTAIN)
    if context.policy_disagreement:
        triggers.append(ReviewTrigger.POLICY_DISAGREEMENT)
    if context.blocking_challenge_count:
        triggers.append(ReviewTrigger.BLOCKING_CHALLENGE)
    if context.verdict_requested_review:
        triggers.append(ReviewTrigger.VERDICT_REQUESTED_REVIEW)
    if context.risk_level in {ReviewRiskLevel.HIGH, ReviewRiskLevel.CRITICAL}:
        triggers.append(ReviewTrigger.HIGH_RISK)

    ordered = tuple(dict.fromkeys(triggers))
    priority = _priority(context, ordered)
    reason = (
        "Human review required: " + ", ".join(item.value for item in ordered) + "."
        if ordered
        else "No deterministic review trigger is present."
    )
    return ReviewRoutingDecision(
        claim_id=context.claim_id,
        review_required=bool(ordered),
        priority=priority,
        triggers=ordered,
        reason=reason,
    )


def _priority(
    context: ReviewRoutingContext, triggers: tuple[ReviewTrigger, ...]
) -> ReviewPriority:
    if (
        context.risk_level is ReviewRiskLevel.CRITICAL
        or ReviewTrigger.CRITICAL_CITATION_FAILURE in triggers
        or ReviewTrigger.CRITICAL_VERIFICATION_UNRESOLVED in triggers
    ):
        return ReviewPriority.CRITICAL
    if context.risk_level is ReviewRiskLevel.HIGH or len(triggers) >= 2:
        return ReviewPriority.HIGH
    return ReviewPriority.STANDARD
