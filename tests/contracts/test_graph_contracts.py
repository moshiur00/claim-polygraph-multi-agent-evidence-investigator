"""Contract tests for the Stage 7 LangGraph boundary."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain.graph import (
    FixtureGraphRequest,
    GraphExecutionBudget,
)
from claim_polygraph_ng.domain.models import VerdictLabel


def test_fixture_request_requires_unique_approved_evidence() -> None:
    evidence_id = uuid4()

    with pytest.raises(ValidationError, match="must be unique"):
        FixtureGraphRequest(
            claim_text="A reviewed fixture claim.",
            approved_evidence_ids=(evidence_id, evidence_id),
            authoritative_verdict=VerdictLabel.SUPPORTED,
        )


def test_fixture_request_rejects_provider_budget() -> None:
    with pytest.raises(ValidationError, match="zero-cost"):
        FixtureGraphRequest(
            claim_text="A reviewed fixture claim.",
            approved_evidence_ids=(uuid4(),),
            authoritative_verdict=VerdictLabel.SUPPORTED,
            budget=GraphExecutionBudget(maximum_model_calls=1),
        )


def test_review_reason_and_route_flag_are_consistent() -> None:
    with pytest.raises(ValidationError, match="review reason"):
        FixtureGraphRequest(
            claim_text="A reviewed fixture claim.",
            approved_evidence_ids=(uuid4(),),
            authoritative_verdict=VerdictLabel.MIXED,
            review_required=True,
        )
