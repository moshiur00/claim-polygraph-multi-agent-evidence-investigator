"""Deterministic human-review routing tests."""

from uuid import uuid4

from claim_polygraph_ng.analysis import (
    audit_structured_assertions,
    route_human_review,
)
from claim_polygraph_ng.domain import (
    Evidence,
    EvidenceStance,
    JudgmentReadinessState,
    ProvenanceRequirementState,
    ReviewPriority,
    ReviewRiskLevel,
    ReviewRoutingContext,
    ReviewTrigger,
    StructuredReportAssertion,
)


def _packet(*, supported: bool, critical: bool = False):
    claim_id = uuid4()
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage="The official record ended the emergency status in May 2023.",
        stance=EvidenceStance.CONTRADICTS,
        relevance_score=1,
    )
    assertion = StructuredReportAssertion(
        claim_id=claim_id,
        sentence="The emergency status ended in May 2023.",
        cited_evidence_ids=(evidence.evidence_id,) if supported else (),
        asserted_stance=EvidenceStance.CONTRADICTS,
        required_phrases=("ended the emergency status", "May 2023"),
        critical=critical,
    )
    packet = audit_structured_assertions(
        claim_id=claim_id,
        assertions=(assertion,),
        evidence=(evidence,),
        approved_evidence_ids=(evidence.evidence_id,),
    )
    return claim_id, packet


def test_clean_low_risk_packet_does_not_route() -> None:
    claim_id, packet = _packet(supported=True)
    decision = route_human_review(
        ReviewRoutingContext(
            claim_id=claim_id,
            risk_level=ReviewRiskLevel.LOW,
            citation_assurance=packet,
            readiness_state=JudgmentReadinessState.READY,
            provenance_state=ProvenanceRequirementState.MET,
        )
    )

    assert not decision.review_required
    assert decision.triggers == ()
    assert decision.priority is ReviewPriority.STANDARD


def test_critical_citation_failure_routes_at_critical_priority() -> None:
    claim_id, packet = _packet(supported=False, critical=True)
    decision = route_human_review(
        ReviewRoutingContext(
            claim_id=claim_id,
            risk_level=ReviewRiskLevel.LOW,
            citation_assurance=packet,
            readiness_state=JudgmentReadinessState.READY,
            provenance_state=ProvenanceRequirementState.MET,
        )
    )

    assert decision.review_required
    assert decision.priority is ReviewPriority.CRITICAL
    assert ReviewTrigger.CRITICAL_CITATION_FAILURE in decision.triggers
    assert ReviewTrigger.MATERIAL_CITATION_FAILURE in decision.triggers


def test_non_citation_diagnostics_are_all_auditable_triggers() -> None:
    claim_id, packet = _packet(supported=True)
    decision = route_human_review(
        ReviewRoutingContext(
            claim_id=claim_id,
            risk_level=ReviewRiskLevel.HIGH,
            citation_assurance=packet,
            readiness_state=JudgmentReadinessState.HUMAN_REVIEW_REQUIRED,
            provenance_state=ProvenanceRequirementState.UNCERTAIN,
            critical_verification_unresolved=True,
            policy_disagreement=True,
            blocking_challenge_count=1,
            verdict_requested_review=True,
        )
    )

    assert decision.review_required
    assert set(decision.triggers) == {
        ReviewTrigger.CRITICAL_VERIFICATION_UNRESOLVED,
        ReviewTrigger.READINESS_REQUIRES_REVIEW,
        ReviewTrigger.PROVENANCE_UNCERTAIN,
        ReviewTrigger.POLICY_DISAGREEMENT,
        ReviewTrigger.BLOCKING_CHALLENGE,
        ReviewTrigger.VERDICT_REQUESTED_REVIEW,
        ReviewTrigger.HIGH_RISK,
    }
