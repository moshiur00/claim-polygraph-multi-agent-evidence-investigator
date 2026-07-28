"""Run the frozen Stage 7.8 authoritative-versus-LangGraph comparison."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase7_frozen import (
    evaluate_phase7_frozen,
    export_phase7_frozen,
)

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks/initial_claims_v1.json"
BASELINE = ROOT / "artifacts/evaluations/phase6-stage6.0-baseline-v1.json"
OUTPUT = ROOT / "artifacts/evaluations/phase7-stage7.8-frozen-comparison-v1.json"


def main() -> int:
    result = evaluate_phase7_frozen(BENCHMARK, BASELINE)
    export_phase7_frozen(result, OUTPUT)
    print(f"Cases: {result.case_count}")
    print(f"Verdict equivalence: {result.verdict_equivalence_rate:.2%}")
    print(
        "Reviewed-label accuracy: "
        f"{result.wrapper_reviewed_label_accuracy:.2%} "
        f"(baseline {result.authoritative_reviewed_label_accuracy:.2%})"
    )
    print(f"Artifact preservation: {result.artifact_preservation_rate:.2%}")
    print(f"Required-review recall: {result.required_review_recall:.2%}")
    print(f"Citation accuracy: {result.citation_accuracy:.2%}")
    print(f"Duplicate paid operations: {result.duplicate_paid_operations}")
    print(f"Deterministic latency overhead: {result.deterministic_latency_overhead_ratio:.2%}")
    print(f"Promotion gate passed: {result.promotion_gate_passed}")
    print(f"Artifact: {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0 if result.promotion_gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
