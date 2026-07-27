"""Regression tests for the frozen Phase 6 ablation decision."""

from claim_polygraph_ng.evaluation.phase6_ablation import run_phase6_frozen_ablation


def test_unsafe_policy_fails_frozen_promotion_gate() -> None:
    evaluation = run_phase6_frozen_ablation(
        benchmark_path="benchmarks/initial_claims_v1.json",
        baseline_path="artifacts/evaluations/phase6-stage6.0-baseline-v1.json",
        numerical_evaluation_path=(
            "artifacts/evaluations/phase6-stage6.2-numerical-v1.json"
        ),
        temporal_evaluation_path=(
            "artifacts/evaluations/phase6-stage6.3-temporal-v1.json"
        ),
    )

    assert evaluation.baseline_accuracy == 0.9
    assert evaluation.full_policy_accuracy == 0.65
    assert evaluation.improved_case_count == 0
    assert evaluation.regressed_case_count == 5
    assert not evaluation.promotion_gate_passed
