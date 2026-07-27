"""Tests for the Stage 6.2 numerical evaluation gate."""

import json

from claim_polygraph_ng.evaluation.phase6_numerical import (
    evaluate_numerical_benchmark,
    export_numerical_evaluation,
    load_numerical_benchmark,
)


def test_project_numerical_fixture_passes_locked_gate(tmp_path) -> None:
    benchmark = load_numerical_benchmark("benchmarks/phase6_numerical_operations_v1.json")

    evaluation = evaluate_numerical_benchmark(benchmark)
    exported = export_numerical_evaluation(evaluation, tmp_path / "numerical.json")

    assert evaluation.case_count == 20
    assert evaluation.accuracy == 1
    assert evaluation.false_resolved_incomplete_count == 0
    assert evaluation.out_of_packet_reference_count == 0
    assert evaluation.gate_passed
    assert json.loads(exported.read_text(encoding="utf-8"))["gate_passed"] is True
