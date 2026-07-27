"""Run the offline Stage 6.3 temporal-relation gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase6_temporal import (
    evaluate_temporal_benchmark,
    export_temporal_evaluation,
    load_temporal_benchmark,
)

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks/phase6_temporal_relations_v1.json"
OUTPUT = ROOT / "artifacts/evaluations/phase6-stage6.3-temporal-v1.json"


def main() -> int:
    evaluation = evaluate_temporal_benchmark(load_temporal_benchmark(BENCHMARK))
    export_temporal_evaluation(evaluation, OUTPUT)
    print(f"Cases: {evaluation.case_count}")
    print(f"Passed: {evaluation.passed_count}")
    print(f"Accuracy: {evaluation.accuracy:.2%}")
    print(f"False resolved incomplete: {evaluation.false_resolved_incomplete_count}")
    print(f"Out-of-packet references: {evaluation.out_of_packet_reference_count}")
    print(f"Gate passed: {evaluation.gate_passed}")
    return 0 if evaluation.gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
