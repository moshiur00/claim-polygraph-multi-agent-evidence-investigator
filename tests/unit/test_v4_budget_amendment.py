"""V4 synthetic-canary budget amendment governance."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.evaluation.v4_budget_amendment import (
    V4CanaryBudgetAmendment,
    verify_v4_budget_amendment,
)


def _payload() -> dict:
    root = Path(__file__).parents[2]
    manifest = root / "artifacts/evaluations/verification-construction-v4-stage0-manifest-v1.json"
    import hashlib

    return {
        "amendment_id": ("verification-construction-v4-canary-budget-amendment-v1"),
        "status": "frozen",
        "predecessor_manifest_path": manifest.relative_to(root).as_posix(),
        "predecessor_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "effective_budget": {
            "maximum_synthetic_canary_calls": 4,
            "maximum_development_calls": 18,
            "maximum_calibration_calls": 20,
            "maximum_held_out_calls": 20,
            "maximum_total_calls": 62,
            "maximum_input_tokens_per_call": 6000,
            "maximum_output_tokens_per_call": 900,
            "maximum_total_cost_usd": 1.25,
            "retries_after_valid_paid_receipt": 0,
        },
        "synthetic_calls_consumed": 3,
        "synthetic_calls_remaining": 1,
        "consumed_cost_usd": 0.00086085,
        "final_canary_authorized": True,
        "final_canary_maximum_calls": 1,
        "authorization_scope": "One final fresh temporal canary with no retry.",
        "model_calls_during_amendment": 0,
        "network_calls_during_amendment": 0,
        "paid_operations_during_amendment": 0,
    }


def test_amendment_preserves_total_calls_and_cost() -> None:
    amendment = V4CanaryBudgetAmendment.model_validate(_payload())

    assert amendment.effective_budget.maximum_total_calls == 62
    assert amendment.effective_budget.maximum_total_cost_usd == 1.25
    assert amendment.synthetic_calls_remaining == 1


def test_amendment_rejects_hidden_budget_expansion() -> None:
    payload = _payload()
    payload["effective_budget"]["maximum_development_calls"] = 20

    with pytest.raises(ValidationError, match="allocations must equal"):
        V4CanaryBudgetAmendment.model_validate(payload)


def test_amendment_rejects_retry_or_extra_final_call() -> None:
    payload = _payload()
    payload["final_canary_maximum_calls"] = 2

    with pytest.raises(ValidationError):
        V4CanaryBudgetAmendment.model_validate(payload)


def test_frozen_amendment_and_hash_validate() -> None:
    root = Path(__file__).parents[2]
    path = (
        root / "artifacts/evaluations/verification-construction-v4-canary-budget-amendment-v1.json"
    )
    amendment = V4CanaryBudgetAmendment.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert verify_v4_budget_amendment(amendment, root) == ()
