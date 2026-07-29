"""Deterministic, monotonic judgment-readiness calculation."""

from claim_polygraph_ng.domain import (
    ArgumentLedger,
    AssertionVerificationState,
    ChallengeSeverity,
    InvestigationProvenance,
    JudgmentReadiness,
    JudgmentReadinessState,
    PropositionResolution,
    ReadinessReasonCode,
    SentenceAudit,
    SocialRiskSeverity,
    SupportLevel,
    VerificationPacketV2,
)
from claim_polygraph_ng.domain.social_constraints import SocialEvidencePolicyResult

READINESS_VERSION = "judgment-readiness-v1"


def calculate_judgment_readiness(
    *,
    ledger: ArgumentLedger,
    verification: VerificationPacketV2 | None = None,
    provenance: InvestigationProvenance | None = None,
    audits: tuple[SentenceAudit, ...] = (),
    unresolved_question_count: int = 0,
    social_policy: SocialEvidencePolicyResult | None = None,
) -> JudgmentReadiness:
    """Calculate readiness from observable artifact conditions only."""
    material_ids = {
        item.proposition_id for item in ledger.propositions if item.material
    }
    material_arguments = tuple(
        item for item in ledger.arguments if item.proposition_id in material_ids
    )
    resolved = sum(
        item.resolution is not PropositionResolution.UNRESOLVED
        for item in material_arguments
    )
    material_count = len(material_arguments)
    coverage = resolved / material_count if material_count else 0
    supporting = {
        evidence_id
        for item in material_arguments
        for evidence_id in item.supporting_evidence_ids
    }
    counter = {
        evidence_id
        for item in material_arguments
        for evidence_id in (
            *item.contradictory_evidence_ids,
            *item.qualifying_evidence_ids,
        )
    }
    assertions = (
        (*verification.numerical_assertions, *verification.temporal_assertions)
        if verification
        else ()
    )
    completed_states = {
        AssertionVerificationState.VERIFIED,
        AssertionVerificationState.CONTRADICTED,
        AssertionVerificationState.QUALIFIED,
        AssertionVerificationState.NOT_APPLICABLE,
    }
    completed = sum(item.state in completed_states for item in assertions)
    verification_completeness = completed / len(assertions) if assertions else 1
    critical_verification = any(
        item.state in {
            AssertionVerificationState.INSUFFICIENT,
            AssertionVerificationState.ERROR,
        }
        for item in assertions
    )
    citation_complete = bool(audits) and all(
        item.support_level is SupportLevel.FULL for item in audits
    )
    blocking = sum(
        item.severity is ChallengeSeverity.BLOCKING
        for item in ledger.challenge_findings
    )
    nonblocking = len(ledger.challenge_findings) - blocking
    quality_unknown = (
        sum(
            dimension.finding == "unknown"
            for source in provenance.source_quality
            for dimension in source.dimensions
        )
        if provenance
        else 0
    )
    social_risks = provenance.social_risk_findings if provenance else ()
    blocking_social_risks = sum(
        item.severity is SocialRiskSeverity.BLOCKING for item in social_risks
    )
    caution_social_risks = sum(
        item.severity is SocialRiskSeverity.CAUTION for item in social_risks
    )
    social_policy_findings = social_policy.findings if social_policy else ()
    blocking_social_policy = sum(
        item.severity is SocialRiskSeverity.BLOCKING
        for item in social_policy_findings
    )
    reasons = []
    hard_failure = False
    if resolved < material_count or not material_count:
        reasons.append(ReadinessReasonCode.MATERIAL_PROPOSITION_UNRESOLVED)
        hard_failure = True
    if critical_verification:
        reasons.append(ReadinessReasonCode.CRITICAL_VERIFICATION_UNRESOLVED)
        hard_failure = True
    if not citation_complete:
        reasons.append(ReadinessReasonCode.CITATION_AUDIT_INCOMPLETE)
        hard_failure = True
    if blocking:
        reasons.append(ReadinessReasonCode.BLOCKING_CHALLENGE)
        hard_failure = True
    if blocking_social_risks:
        reasons.append(ReadinessReasonCode.BLOCKING_SOCIAL_EVIDENCE_RISK)
        hard_failure = True
    if blocking_social_policy:
        reasons.append(ReadinessReasonCode.SOCIAL_ARGUMENT_POLICY_BLOCKED)
        hard_failure = True
    qualified = any(
        item.resolution is PropositionResolution.QUALIFIED
        for item in material_arguments
    )
    if qualified:
        reasons.append(ReadinessReasonCode.QUALIFIED_PROPOSITION)
    provenance_uncertain = bool(
        provenance
        and (
            provenance.requirement_state.value != "met"
            or provenance.unresolved_dependency_count
        )
    )
    if provenance_uncertain:
        reasons.append(ReadinessReasonCode.PROVENANCE_UNCERTAIN)
    if nonblocking:
        reasons.append(ReadinessReasonCode.NONBLOCKING_CHALLENGE)
    if quality_unknown:
        reasons.append(ReadinessReasonCode.SOURCE_QUALITY_UNKNOWN)
    if caution_social_risks:
        reasons.append(ReadinessReasonCode.SOCIAL_EVIDENCE_RISK)
    if social_policy and social_policy.requires_human_review:
        reasons.append(ReadinessReasonCode.SOCIAL_ARGUMENT_POLICY_REVIEW)
    if unresolved_question_count:
        reasons.append(ReadinessReasonCode.UNRESOLVED_QUESTIONS)
    if hard_failure:
        state = JudgmentReadinessState.HUMAN_REVIEW_REQUIRED
    elif (
        qualified
        or provenance_uncertain
        or nonblocking
        or quality_unknown
        or caution_social_risks
        or bool(social_policy and social_policy.requires_human_review)
        or unresolved_question_count
    ):
        state = JudgmentReadinessState.QUALIFIED
    else:
        state = JudgmentReadinessState.READY
        reasons.append(ReadinessReasonCode.COMPLETE)
    return JudgmentReadiness(
        claim_id=ledger.claim_id,
        state=state,
        material_proposition_count=material_count,
        resolved_material_proposition_count=resolved,
        material_coverage=coverage,
        supporting_evidence_count=len(supporting),
        counterevidence_count=len(counter),
        confirmed_independent_lower_bound=(
            provenance.confirmed_independent_lower_bound if provenance else None
        ),
        possible_independent_upper_bound=(
            provenance.possible_independent_upper_bound if provenance else None
        ),
        unresolved_dependency_count=(
            provenance.unresolved_dependency_count if provenance else 0
        ),
        verification_assertion_count=len(assertions),
        completed_verification_count=completed,
        verification_completeness=verification_completeness,
        source_quality_unknown_count=quality_unknown,
        citation_audit_complete=citation_complete,
        blocking_challenge_count=blocking,
        nonblocking_challenge_count=nonblocking,
        unresolved_question_count=unresolved_question_count,
        reason_codes=tuple(reasons),
        limitations=(
            "Readiness describes packet completeness and does not estimate claim truth.",
            "No benchmark verdict label or confidence target is an input.",
            f"Feature version: {READINESS_VERSION}.",
        ),
        social_risk_finding_count=len(social_risks),
        blocking_social_risk_count=blocking_social_risks,
        social_policy_finding_count=len(social_policy_findings),
        blocking_social_policy_finding_count=blocking_social_policy,
    )
