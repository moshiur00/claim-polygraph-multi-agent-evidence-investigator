"""Deterministic verdict-label constraints derived from the argument ledger."""

from claim_polygraph_ng.domain import (
    ArgumentLedger,
    ChallengeSeverity,
    JudgmentPolicyTrace,
    JudgmentReasonCode,
    PropositionResolution,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.domain.social_constraints import SocialEvidencePolicyResult

JUDGMENT_POLICY_VERSION = "judgment-policy-v1"

_ALLOWED = {
    PropositionResolution.SUPPORTED: (VerdictLabel.SUPPORTED,),
    PropositionResolution.CONTRADICTED: (
        VerdictLabel.CONTRADICTED,
        VerdictLabel.OUTDATED,
        VerdictLabel.MISLEADING,
    ),
    PropositionResolution.QUALIFIED: (
        VerdictLabel.MIXED,
        VerdictLabel.MISLEADING,
    ),
    PropositionResolution.UNRESOLVED: (
        VerdictLabel.UNSUPPORTED,
        VerdictLabel.UNVERIFIABLE,
    ),
}
_DEFAULT = {
    PropositionResolution.SUPPORTED: VerdictLabel.SUPPORTED,
    PropositionResolution.CONTRADICTED: VerdictLabel.CONTRADICTED,
    PropositionResolution.QUALIFIED: VerdictLabel.MIXED,
    PropositionResolution.UNRESOLVED: VerdictLabel.UNVERIFIABLE,
}
_INCOMPATIBLE_REASON = {
    PropositionResolution.SUPPORTED: JudgmentReasonCode.LABEL_INCOMPATIBLE_WITH_SUPPORTED,
    PropositionResolution.CONTRADICTED: JudgmentReasonCode.LABEL_INCOMPATIBLE_WITH_CONTRADICTED,
    PropositionResolution.QUALIFIED: JudgmentReasonCode.LABEL_INCOMPATIBLE_WITH_QUALIFIED,
    PropositionResolution.UNRESOLVED: JudgmentReasonCode.LABEL_INCOMPATIBLE_WITH_UNRESOLVED,
}


def enforce_judgment_policy(
    proposed: Verdict,
    ledger: ArgumentLedger,
    social_policy: SocialEvidencePolicyResult | None = None,
) -> tuple[Verdict, JudgmentPolicyTrace]:
    """Preserve valid proposals and constrain invalid label/evidence combinations."""
    if proposed.claim_id != ledger.claim_id:
        raise ValueError("verdict and argument ledger must reference the same claim")
    if social_policy is not None and social_policy.claim_id != ledger.claim_id:
        raise ValueError("social policy and argument ledger must reference the same claim")
    resolutions = {
        argument.resolution
        for argument in ledger.arguments
        if next(
            item.material
            for item in ledger.propositions
            if item.proposition_id == argument.proposition_id
        )
    }
    if not resolutions:
        raise ValueError("judgment policy requires at least one material proposition")
    mixed_material = len(resolutions) > 1
    if mixed_material:
        allowed = (VerdictLabel.MIXED,)
        default = VerdictLabel.MIXED
        mismatch_reason = JudgmentReasonCode.MIXED_MATERIAL_RESOLUTIONS
    else:
        resolution = next(iter(resolutions))
        allowed = _ALLOWED[resolution]
        default = _DEFAULT[resolution]
        mismatch_reason = _INCOMPATIBLE_REASON[resolution]

    blocking = any(
        finding.severity is ChallengeSeverity.BLOCKING
        for finding in ledger.challenge_findings
    )
    changed = proposed.label not in allowed
    enforced_label = default if changed else proposed.label
    reason_codes = [
        mismatch_reason if changed else JudgmentReasonCode.LABEL_ALLOWED
    ]
    if blocking:
        reason_codes.append(JudgmentReasonCode.BLOCKING_CHALLENGE)
    social_review = bool(social_policy and social_policy.requires_human_review)
    if social_review:
        reason_codes.append(JudgmentReasonCode.SOCIAL_EVIDENCE_CONSTRAINT)
    review_required = proposed.human_review_required or changed or blocking or social_review
    rationale_parts = []
    if changed:
        rationale_parts.append(
            f"Proposed label {proposed.label.value} is incompatible with ledger "
            f"resolution; enforced {enforced_label.value}."
        )
    else:
        rationale_parts.append(
            f"Proposed label {proposed.label.value} is allowed by the ledger resolution."
        )
    if blocking:
        rationale_parts.append("At least one blocking challenger finding requires review.")
    if social_review:
        rationale_parts.append(
            "Social-evidence use or corroboration constraints require review."
        )
    rationale = " ".join(rationale_parts)
    review_reason = proposed.review_reason
    if review_required:
        review_reason = " ".join(item for item in (review_reason, rationale) if item)
    enforced = Verdict.model_validate(
        {
            **proposed.model_dump(),
            "label": enforced_label,
            "human_review_required": review_required,
            "review_reason": review_reason,
        }
    )
    return enforced, JudgmentPolicyTrace(
        claim_id=ledger.claim_id,
        verdict_id=proposed.verdict_id,
        proposed_label=proposed.label,
        enforced_label=enforced_label,
        allowed_labels=allowed,
        changed=changed,
        human_review_required=review_required,
        reason_codes=tuple(reason_codes),
        rationale=rationale,
    )
