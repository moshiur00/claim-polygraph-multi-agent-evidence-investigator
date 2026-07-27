"""Monotonicity tests for judgment-readiness features."""

from uuid import uuid4

from claim_polygraph_ng.analysis.readiness import calculate_judgment_readiness
from claim_polygraph_ng.domain import (
    ArgumentLedger,
    AuditIssue,
    ChallengeFinding,
    ChallengeKind,
    ChallengeSeverity,
    JudgmentReadinessState,
    MaterialProposition,
    PropositionArgument,
    PropositionResolution,
    SentenceAudit,
    SupportLevel,
)

_RANK = {
    JudgmentReadinessState.READY: 2,
    JudgmentReadinessState.QUALIFIED: 1,
    JudgmentReadinessState.HUMAN_REVIEW_REQUIRED: 0,
}


def _ledger(*, resolution=PropositionResolution.SUPPORTED, severity=None):
    claim_id, proposition_id, evidence_id = uuid4(), uuid4(), uuid4()
    findings = (
        (
            ChallengeFinding(
                finding_id="challenge-1234567890abcdef",
                proposition_id=proposition_id,
                kind=ChallengeKind.MISSING_COUNTEREVIDENCE,
                severity=severity,
                rationale="The packet has an explicit challenger condition.",
            ),
        )
        if severity
        else ()
    )
    ledger = ArgumentLedger(
        claim_id=claim_id,
        approved_evidence_ids=(evidence_id,),
        propositions=(
            MaterialProposition(
                proposition_id=proposition_id,
                claim_id=claim_id,
                text="A project-authored material proposition.",
            ),
        ),
        arguments=(
            PropositionArgument(
                proposition_id=proposition_id,
                resolution=resolution,
                supporting_evidence_ids=(evidence_id,)
                if resolution is not PropositionResolution.UNRESOLVED
                else (),
                unresolved_reasons=(
                    ("Approved evidence does not resolve the proposition.",)
                    if resolution is PropositionResolution.UNRESOLVED
                    else ()
                ),
            ),
        ),
        challenge_findings=findings,
    )
    audit = SentenceAudit(
        sentence="The report sentence is fully supported.",
        cited_evidence_ids=(evidence_id,),
        support_level=SupportLevel.FULL,
    )
    return ledger, audit


def test_complete_packet_is_ready_and_has_no_confidence_score() -> None:
    ledger, audit = _ledger()
    readiness = calculate_judgment_readiness(ledger=ledger, audits=(audit,))

    assert readiness.state is JudgmentReadinessState.READY
    assert readiness.material_coverage == 1
    assert readiness.verification_completeness == 1
    assert readiness.confidence_score is None


def test_removing_resolution_cannot_improve_readiness() -> None:
    complete, audit = _ledger()
    degraded, degraded_audit = _ledger(resolution=PropositionResolution.UNRESOLVED)
    before = calculate_judgment_readiness(ledger=complete, audits=(audit,))
    after = calculate_judgment_readiness(ledger=degraded, audits=(degraded_audit,))

    assert _RANK[after.state] <= _RANK[before.state]
    assert after.state is JudgmentReadinessState.HUMAN_REVIEW_REQUIRED


def test_adding_challenges_or_questions_cannot_improve_readiness() -> None:
    base, audit = _ledger()
    caution, caution_audit = _ledger(severity=ChallengeSeverity.CAUTION)
    blocking, blocking_audit = _ledger(severity=ChallengeSeverity.BLOCKING)
    ready = calculate_judgment_readiness(ledger=base, audits=(audit,))
    qualified = calculate_judgment_readiness(ledger=caution, audits=(caution_audit,))
    review = calculate_judgment_readiness(ledger=blocking, audits=(blocking_audit,))
    questions = calculate_judgment_readiness(
        ledger=base, audits=(audit,), unresolved_question_count=1
    )

    assert _RANK[qualified.state] <= _RANK[ready.state]
    assert _RANK[review.state] <= _RANK[qualified.state]
    assert _RANK[questions.state] <= _RANK[ready.state]


def test_losing_full_citation_audit_requires_review() -> None:
    ledger, audit = _ledger()
    ready = calculate_judgment_readiness(ledger=ledger, audits=(audit,))
    partial = SentenceAudit(
        sentence="The report sentence is only partially supported.",
        support_level=SupportLevel.PARTIAL,
        issue_type=AuditIssue.MISSING_CITATION,
        explanation="A material citation is missing.",
    )
    degraded = calculate_judgment_readiness(ledger=ledger, audits=(partial,))

    assert _RANK[degraded.state] <= _RANK[ready.state]
    assert degraded.state is JudgmentReadinessState.HUMAN_REVIEW_REQUIRED
