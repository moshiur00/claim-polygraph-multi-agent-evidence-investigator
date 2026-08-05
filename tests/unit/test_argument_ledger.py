"""Tests for deterministic argument-ledger construction."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.analysis.argument_ledger import build_argument_ledger
from claim_polygraph_ng.domain import (
    ArgumentLedger,
    AssertionVerificationState,
    AtomicClaim,
    ChallengeKind,
    Evidence,
    EvidenceStance,
    NormalizedNumericValue,
    NumericalAssertionVerification,
    NumericComparator,
    PropositionResolution,
    VerificationPacketV2,
)


def _evidence(claim, stance):
    return Evidence(
        claim_id=claim.claim_id,
        source_id=uuid4(),
        passage=f"Project-authored {stance.value} passage with sufficient detail.",
        stance=stance,
        relevance_score=0 if stance is EvidenceStance.IRRELEVANT else 1,
    )


def test_ledger_maps_stances_and_absolute_wording_challenge() -> None:
    claim = AtomicClaim(text="Every adult has exactly 206 bones.", checkworthiness=1)
    supporting = _evidence(claim, EvidenceStance.SUPPORTS)
    qualifying = _evidence(claim, EvidenceStance.QUALIFIES)
    ledger = build_argument_ledger(claim=claim, evidence=(supporting, qualifying))

    argument = ledger.arguments[0]
    assert argument.resolution is PropositionResolution.QUALIFIED
    assert argument.supporting_evidence_ids == (supporting.evidence_id,)
    assert ChallengeKind.ABSOLUTE_WORDING in {
        item.kind for item in ledger.challenge_findings
    }


def test_verification_and_missing_counterevidence_create_bounded_findings() -> None:
    claim = AtomicClaim(
        text="The treatment causes improvement for every person.", checkworthiness=1
    )
    support = _evidence(claim, EvidenceStance.SUPPORTS)
    assertion = NumericalAssertionVerification(
        claim_id=claim.claim_id,
        claim_text_span="improvement",
        comparator=NumericComparator.EQUAL,
        expected_values=(NormalizedNumericValue(value=Decimal("1")),),
        state=AssertionVerificationState.INSUFFICIENT,
        issues=("No numerical outcome was supplied.",),
    )
    verification = VerificationPacketV2(
        claim_id=claim.claim_id,
        approved_evidence_ids=(support.evidence_id,),
        numerical_assertions=(assertion,),
    )
    ledger = build_argument_ledger(
        claim=claim, evidence=(support,), verification=verification
    )
    kinds = {item.kind for item in ledger.challenge_findings}

    assert {
        ChallengeKind.CAUSAL_OVERREACH,
        ChallengeKind.POPULATION_TO_INDIVIDUAL,
        ChallengeKind.MISSING_COUNTEREVIDENCE,
        ChallengeKind.INCOMPLETE_NUMERICAL_CONTEXT,
    }.issubset(kinds)


def test_ledger_is_deterministic_and_rejects_mutated_evidence_reference() -> None:
    claim = AtomicClaim(text="The programme reduced waste.", checkworthiness=1)
    evidence = _evidence(claim, EvidenceStance.SUPPORTS)
    first = build_argument_ledger(claim=claim, evidence=(evidence,))
    second = build_argument_ledger(claim=claim, evidence=(evidence,))

    assert first == second
    payload = first.model_dump()
    payload["arguments"][0]["supporting_evidence_ids"] = [uuid4()]
    with pytest.raises(ValidationError, match="approved evidence"):
        ArgumentLedger.model_validate(payload)


def test_irrelevant_evidence_does_not_resolve_proposition() -> None:
    claim = AtomicClaim(text="The programme reduced waste.", checkworthiness=1)
    irrelevant = _evidence(claim, EvidenceStance.IRRELEVANT)
    ledger = build_argument_ledger(claim=claim, evidence=(irrelevant,))

    assert ledger.arguments[0].resolution is PropositionResolution.UNRESOLVED
    assert ledger.arguments[0].unresolved_reasons


def test_contaminated_evidence_remains_outside_argument_resolution() -> None:
    claim = AtomicClaim(text="Water expands when it freezes.", checkworthiness=1)
    contaminated = Evidence(
        claim_id=claim.claim_id,
        source_id=uuid4(),
        passage=(
            "Skip to main content User account menu Log in Subscribe Product directory. "
            "Water expands when it freezes. Privacy policy All rights reserved."
        ),
        stance=EvidenceStance.SUPPORTS,
        relevance_score=1,
    )

    ledger = build_argument_ledger(claim=claim, evidence=(contaminated,))

    assert contaminated.evidence_id not in ledger.approved_evidence_ids
    assert ledger.arguments[0].resolution is PropositionResolution.UNRESOLVED
    assert ledger.arguments[0].supporting_evidence_ids == ()
    insufficient = next(
        item
        for item in ledger.challenge_findings
        if item.kind is ChallengeKind.INSUFFICIENT_ELIGIBLE_EVIDENCE
    )
    assert insufficient.severity.value == "blocking"
    assert ChallengeKind.MISSING_COUNTEREVIDENCE not in {
        item.kind for item in ledger.challenge_findings
    }
