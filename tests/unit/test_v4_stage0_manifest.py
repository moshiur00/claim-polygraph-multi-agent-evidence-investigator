"""Contract tests for the zero-cost V4.0 governance freeze."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.evaluation.v4_manifest import (
    V4Budget,
    V4StageZeroManifest,
    verify_v4_manifest,
)


ROOT = Path(__file__).parents[2]
MANIFEST = (
    ROOT
    / "artifacts/evaluations/"
    "verification-construction-v4-stage0-manifest-v1.json"
)


def test_v4_stage0_manifest_is_valid_and_content_addressed() -> None:
    manifest = V4StageZeroManifest.model_validate_json(
        MANIFEST.read_text(encoding="utf-8")
    )
    assert verify_v4_manifest(manifest, ROOT) == ()
    assert manifest.status == "frozen"


def test_v4_stage0_is_zero_cost_and_collects_no_evaluation_data() -> None:
    manifest = V4StageZeroManifest.model_validate_json(
        MANIFEST.read_text(encoding="utf-8")
    )
    assert not manifest.provider_selected
    assert (
        manifest.model_calls
        == manifest.network_calls
        == manifest.search_calls
        == manifest.paid_operations
        == 0
    )
    assert (
        manifest.fresh_calibration_cases_collected
        == manifest.fresh_held_out_cases_collected
        == 0
    )


def test_v4_budget_rejects_nonzero_stage_zero_activity() -> None:
    payload = {
        "stage_v4_0_model_calls": 1,
        "stage_v4_0_network_calls": 0,
        "stage_v4_0_search_calls": 0,
        "stage_v4_0_paid_operations": 0,
        "maximum_synthetic_canary_calls": 2,
        "maximum_development_calls": 20,
        "maximum_calibration_calls": 20,
        "maximum_held_out_calls": 20,
        "maximum_total_calls": 62,
        "maximum_input_tokens_per_call": 6000,
        "maximum_output_tokens_per_call": 900,
        "maximum_total_cost_usd": 1.25,
        "maximum_cost_per_recovered_assertion_usd": 0.05,
        "retries_after_valid_paid_receipt": 0,
    }
    with pytest.raises(ValidationError):
        V4Budget.model_validate(payload)


def test_v4_policy_permanently_retires_v3_held_out_data() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    policy_path = ROOT / manifest["dataset_nonreuse_policy"]["path"]
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    held_out = policy["v3_held_out"]
    assert held_out["category_level_failure_lessons"] == "permitted"
    assert all(
        value == "prohibited"
        for key, value in held_out.items()
        if key != "category_level_failure_lessons"
    )


def test_v4_offline_gates_are_fail_closed() -> None:
    manifest = V4StageZeroManifest.model_validate_json(
        MANIFEST.read_text(encoding="utf-8")
    )
    gates = manifest.offline_promotion_gates
    assert gates.minimum_constructible_eligibility_recall == 1
    assert gates.minimum_negative_exclusion_precision == 1
    assert gates.minimum_compound_operand_preservation == 1
    assert gates.minimum_exact_span_validity == 1
    assert gates.minimum_schema_validity == 1
    assert gates.maximum_unsafe_accepted_constructions == 0
    assert gates.minimum_human_review_routing_recall == 1
    assert gates.maximum_duplicate_paid_operations == 0
    assert gates.minimum_failed_response_cost_observability == 1
    assert gates.maximum_v3_held_out_texts_loaded == 0
