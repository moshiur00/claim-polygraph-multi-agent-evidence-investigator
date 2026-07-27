"""Run the offline Stage 6.2 numerical-operation gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase6_numerical import (
    evaluate_numerical_benchmark,
    export_numerical_evaluation,
    load_numerical_benchmark,
)

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks/phase6_numerical_operations_v1.json"
OUTPUT = ROOT / "artifacts/evaluations/phase6-stage6.2-numerical-v1.json"


def main() -> int:
    evaluation = evaluate_numerical_benchmark(load_numerical_benchmark(BENCHMARK))
    export_numerical_evaluation(evaluation, OUTPUT)
    print(f"Cases: {evaluation.case_count}")
    print(f"Passed: {evaluation.passed_count}")
    print(f"Accuracy: {evaluation.accuracy:.2%}")
    print(f"False resolved incomplete: {evaluation.false_resolved_incomplete_count}")
    print(f"Out-of-packet references: {evaluation.out_of_packet_reference_count}")
    print(f"Gate passed: {evaluation.gate_passed}")
    return 0 if evaluation.gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
