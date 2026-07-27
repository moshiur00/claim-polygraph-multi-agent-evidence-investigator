"""Exhaustive tests for deterministic verdict-label constraints."""

from uuid import uuid4

import pytest

from claim_polygraph_ng.analysis.judgment_policy import enforce_judgment_policy
from claim_polygraph_ng.domain import (
    ArgumentLedger,
    ChallengeFinding,
    ChallengeKind,
    ChallengeSeverity,
    JudgmentReasonCode,
    MaterialProposition,
    PropositionArgument,
    PropositionResolution,
    Verdict,
    VerdictLabel,
)

ALLOWED = {
    PropositionResolution.SUPPORTED: {VerdictLabel.SUPPORTED},
    PropositionResolution.CONTRADICTED: {
        VerdictLabel.CONTRADICTED,
        VerdictLabel.OUTDATED,
        VerdictLabel.MISLEADING,
    },
    PropositionResolution.QUALIFIED: {
        VerdictLabel.MIXED,
        VerdictLabel.MISLEADING,
    },
    PropositionResolution.UNRESOLVED: {
        VerdictLabel.UNSUPPORTED,
        VerdictLabel.UNVERIFIABLE,
    },
}


def _ledger(resolution, *, blocking=False):
    claim_id, proposition_id, evidence_id = uuid4(), uuid4(), uuid4()
    findings = (
        (
            ChallengeFinding(
                finding_id="challenge-1234567890abcdef",
                proposition_id=proposition_id,
                kind=ChallengeKind.INCOMPLETE_NUMERICAL_CONTEXT,
                severity=ChallengeSeverity.BLOCKING,
                rationale="A required numerical assertion remains unresolved.",
            ),
        )
        if blocking
        else ()
    )
    return ArgumentLedger(
        claim_id=claim_id,
        approved_evidence_ids=(evidence_id,),
        propositions=(
            MaterialProposition(
                proposition_id=proposition_id,
                claim_id=claim_id,
                text="A material project-authored proposition.",
            ),
        ),
        arguments=(
            PropositionArgument(
                proposition_id=proposition_id,
                resolution=resolution,
                supporting_evidence_ids=(evidence_id,),
            ),
        ),
        challenge_findings=findings,
    )


def _verdict(claim_id, label):
    evidence_id = uuid4()
    return Verdict(
        claim_id=claim_id,
        label=label,
        concise_explanation="A sufficiently detailed provisional explanation.",
        detailed_reasoning="A sufficiently detailed provisional reasoning statement.",
        decisive_evidence_ids=(evidence_id,),
    )


@pytest.mark.parametrize("resolution", tuple(PropositionResolution))
@pytest.mark.parametrize("label", tuple(VerdictLabel))
def test_exhaustive_resolution_label_matrix(resolution, label) -> None:
    ledger = _ledger(resolution)
    proposed = _verdict(ledger.claim_id, label)

    enforced, trace = enforce_judgment_policy(proposed, ledger)

    if label in ALLOWED[resolution]:
        assert enforced.label is label
        assert not trace.changed
        assert trace.reason_codes == (JudgmentReasonCode.LABEL_ALLOWED,)
    else:
        assert enforced.label in ALLOWED[resolution]
        assert trace.changed
        assert enforced.human_review_required
        assert enforced.review_reason


def test_blocking_finding_preserves_allowed_label_but_requires_review() -> None:
    ledger = _ledger(PropositionResolution.SUPPORTED, blocking=True)
    proposed = _verdict(ledger.claim_id, VerdictLabel.SUPPORTED)

    enforced, trace = enforce_judgment_policy(proposed, ledger)

    assert enforced.label is VerdictLabel.SUPPORTED
    assert not trace.changed
    assert enforced.human_review_required
    assert JudgmentReasonCode.BLOCKING_CHALLENGE in trace.reason_codes


def test_policy_rejects_cross_claim_verdict() -> None:
    ledger = _ledger(PropositionResolution.SUPPORTED)
    with pytest.raises(ValueError, match="same claim"):
        enforce_judgment_policy(
            _verdict(uuid4(), VerdictLabel.SUPPORTED),
            ledger,
        )
