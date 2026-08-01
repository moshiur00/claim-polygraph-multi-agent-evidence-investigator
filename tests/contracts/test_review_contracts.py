"""Validation tests for durable human-review contracts."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    ReviewDecision,
    ReviewDecisionKind,
    VerdictLabel,
    VerificationConstructionDisposition,
)


def test_only_revision_decision_accepts_a_revised_verdict() -> None:
    with pytest.raises(ValidationError, match="only revise"):
        ReviewDecision(
            kind=ReviewDecisionKind.APPROVE,
            reviewer_identity="Reviewer One",
            rationale="Evidence supports the provisional verdict.",
            revised_verdict=VerdictLabel.MIXED,
        )

    with pytest.raises(ValidationError, match="only revise"):
        ReviewDecision(
            kind=ReviewDecisionKind.REVISE,
            reviewer_identity="Reviewer One",
            rationale="Evidence requires a qualified verdict.",
        )


def test_verification_construction_dispositions_are_typed_and_bounded() -> None:
    construction_id = uuid4()
    accepted = ReviewDecision(
        kind=ReviewDecisionKind.APPROVE,
        reviewer_identity="Reviewer One",
        rationale="The extracted operands match the cited passage.",
        verification_construction_id=construction_id,
        verification_disposition=VerificationConstructionDisposition.ACCEPT,
    )
    assert accepted.verification_construction_id == construction_id

    with pytest.raises(ValidationError, match="requires request_evidence"):
        ReviewDecision(
            kind=ReviewDecisionKind.APPROVE,
            reviewer_identity="Reviewer One",
            rationale="More evidence is required.",
            verification_construction_id=construction_id,
            verification_disposition=(
                VerificationConstructionDisposition.REQUEST_EVIDENCE
            ),
        )

    with pytest.raises(ValidationError, match="corrected operands"):
        ReviewDecision(
            kind=ReviewDecisionKind.APPROVE,
            reviewer_identity="Reviewer One",
            rationale="The subject needs correction.",
            verification_construction_id=construction_id,
            verification_disposition=VerificationConstructionDisposition.ACCEPT,
            corrected_left_subject="Corrected subject",
        )


def test_reviewed_correction_requires_content_and_preserves_evidence_binding() -> None:
    construction_id = uuid4()
    evidence_id = uuid4()
    decision = ReviewDecision(
        kind=ReviewDecisionKind.REVISE,
        reviewer_identity="Md Moshiur Rahman",
        rationale="The typed operand needs correction.",
        revised_verdict=VerdictLabel.MIXED,
        verification_construction_id=construction_id,
        verification_disposition=VerificationConstructionDisposition.CORRECT,
        corrected_claim_text_span="District A has a higher rate than District B.",
        corrected_value="62",
        corrected_unit="percent",
        corrected_evidence_ids=(evidence_id,),
    )

    assert decision.corrected_evidence_ids == (evidence_id,)

    with pytest.raises(ValidationError, match="at least one correction"):
        ReviewDecision(
            kind=ReviewDecisionKind.REVISE,
            reviewer_identity="Md Moshiur Rahman",
            rationale="No correction was actually supplied.",
            revised_verdict=VerdictLabel.MIXED,
            verification_construction_id=construction_id,
            verification_disposition=VerificationConstructionDisposition.CORRECT,
        )
