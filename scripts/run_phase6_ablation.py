"""Run the frozen offline Stage 6.8 ablation."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase6_ablation import (
    export_phase6_ablation,
    run_phase6_frozen_ablation,
)

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts/evaluations"


def main() -> int:
    evaluation = run_phase6_frozen_ablation(
        benchmark_path=ROOT / "benchmarks/initial_claims_v1.json",
        baseline_path=ARTIFACTS / "phase6-stage6.0-baseline-v1.json",
        numerical_evaluation_path=ARTIFACTS / "phase6-stage6.2-numerical-v1.json",
        temporal_evaluation_path=ARTIFACTS / "phase6-stage6.3-temporal-v1.json",
    )
    export_phase6_ablation(
        evaluation, ARTIFACTS / "phase6-stage6.8-frozen-ablation-v1.json"
    )
    print(f"Cases: {evaluation.case_count}")
    print(f"Baseline accuracy: {evaluation.baseline_accuracy:.2%}")
    print(f"Full policy accuracy: {evaluation.full_policy_accuracy:.2%}")
    print(f"Improved: {evaluation.improved_case_count}")
    print(f"Regressed: {evaluation.regressed_case_count}")
    print(f"Overrides: {evaluation.policy_override_count}")
    print(f"Promotion gate passed: {evaluation.promotion_gate_passed}")
    return 0 if evaluation.promotion_gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
