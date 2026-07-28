"""Validation tests for durable human-review contracts."""

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    ReviewDecision,
    ReviewDecisionKind,
    VerdictLabel,
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
