"""Offline contract and freeze tests for Verification Construction V3.0."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.evaluation.v3_manifest import (
    V3BenchmarkCase,
    V3ConstructionGoldLabel,
    V3DatasetSplit,
    V3EvidenceSpan,
    V3ExperimentBudget,
    V3FrozenArtifact,
    V3SamplingPolicy,
    V3StageZeroManifest,
    load_v3_manifest,
    verify_v3_manifest,
)


def test_repository_v3_stage_zero_manifest_is_frozen_and_valid() -> None:
    root = Path(__file__).parents[2]
    manifest = load_v3_manifest(
        root
        / "artifacts/evaluations/verification-construction-v3-stage0-manifest-v1.json"
    )

    audit = verify_v3_manifest(manifest, root)

    assert audit.valid
    assert audit.checked_artifact_count == 3
    assert manifest.sampling_policy.target_case_count == 60
    assert manifest.sampling_policy.split_quotas[V3DatasetSplit.HELD_OUT] == 20
    assert manifest.budget.stage_v3_0_model_calls == 0
    assert manifest.budget.stage_v3_0_network_calls == 0
    assert manifest.budget.search_calls_allowed == 0
    assert manifest.model_provider_selected is False
    assert manifest.promotion_thresholds.minimum_evidence_span_validity == 1
    assert manifest.promotion_thresholds.maximum_unsafe_accepted_constructions == 0
    assert manifest.promotion_thresholds.maximum_duplicate_paid_operations == 0


def test_sampling_policy_rejects_quota_drift() -> None:
    policy = _sampling_policy()
    payload = policy.model_dump(mode="json")
    payload["split_quotas"]["held_out"] = 19

    with pytest.raises(ValidationError, match="split quotas"):
        V3SamplingPolicy.model_validate(payload)


def test_stage_zero_budget_rejects_any_model_or_network_call() -> None:
    with pytest.raises(ValidationError, match="offline and zero-cost"):
        V3ExperimentBudget(
            stage_v3_0_model_calls=1,
            stage_v3_0_network_calls=0,
            maximum_assisted_calls_per_eligible_case=1,
            maximum_input_tokens_per_call=6000,
            maximum_output_tokens_per_call=800,
            maximum_total_model_calls=25,
            maximum_total_cost_usd=0.75,
            maximum_cost_per_recovered_assertion_usd=0.05,
            search_calls_allowed=0,
            retries_after_valid_paid_receipt=0,
        )


def test_constructible_gold_case_requires_exact_spans_and_distinct_approval() -> None:
    evidence_id = str(uuid4())
    case = V3BenchmarkCase(
        case_id="V3-001",
        split=V3DatasetSplit.DEVELOPMENT,
        claim_text="District A has a higher rate than District B.",
        evidence_packet_path="benchmarks/packets/v3-001.json",
        dimension="percentage",
        gold_label=V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
        gold_claim_span="higher rate",
        gold_evidence_spans=(
            V3EvidenceSpan(
                evidence_id=evidence_id,
                start_char=10,
                end_char=20,
                quoted_text="62 percent",
            ),
        ),
        expected_verification_state="verified",
        annotator_identity="Md Moshiur Rahman",
        distinct_approver_identity="Md Rashedul Islam",
    )
    assert case.gold_evidence_spans[0].evidence_id == evidence_id

    payload = case.model_dump(mode="json")
    payload["distinct_approver_identity"] = payload["annotator_identity"]
    with pytest.raises(ValidationError, match="distinct approver"):
        V3BenchmarkCase.model_validate(payload)

    payload = case.model_dump(mode="json")
    payload["gold_evidence_spans"] = []
    with pytest.raises(ValidationError, match="constructible cases"):
        V3BenchmarkCase.model_validate(payload)


def test_manifest_hash_audit_detects_post_freeze_change(tmp_path: Path) -> None:
    artifact = tmp_path / "plan.md"
    artifact.write_text("frozen", encoding="utf-8")
    manifest = _minimal_manifest(
        V3FrozenArtifact(
            artifact_id="plan",
            path="plan.md",
            sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        )
    )
    assert verify_v3_manifest(manifest, tmp_path).valid

    artifact.write_text("changed", encoding="utf-8")
    audit = verify_v3_manifest(manifest, tmp_path)
    assert not audit.valid
    assert audit.errors == ("plan: SHA-256 mismatch",)


def test_auxiliary_sampling_policy_matches_manifest() -> None:
    root = Path(__file__).parents[2]
    policy_payload = json.loads(
        (
            root
            / "artifacts/evaluations/verification-construction-v3-sampling-policy-v1.json"
        ).read_text(encoding="utf-8")
    )
    policy_payload.pop("policy_id")
    manifest = load_v3_manifest(
        root
        / "artifacts/evaluations/verification-construction-v3-stage0-manifest-v1.json"
    )
    for field in V3SamplingPolicy.model_fields:
        assert policy_payload[field] == manifest.sampling_policy.model_dump(
            mode="json"
        )[field]


def _sampling_policy() -> V3SamplingPolicy:
    return V3SamplingPolicy(
        target_case_count=60,
        split_quotas={"development": 20, "calibration": 20, "held_out": 20},
        dimension_quotas={"all": 60},
        construction_label_quotas={
            "deterministic_constructible": 30,
            "fallback_eligible": 15,
            "unconstructible": 10,
            "not_applicable": 5,
        },
        source_class_quotas={"all": 60},
        minimum_distinct_evidence_families=40,
        maximum_cases_per_origin_family=2,
        random_seed=20260730,
        selection_frozen_before_model_calls=True,
    )


def _minimal_manifest(artifact: V3FrozenArtifact) -> V3StageZeroManifest:
    production = load_v3_manifest(
        Path(__file__).parents[2]
        / "artifacts/evaluations/verification-construction-v3-stage0-manifest-v1.json"
    )
    return production.model_copy(update={"artifacts": (artifact,)})
