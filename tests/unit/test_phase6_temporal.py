"""Tests for the Stage 6.3 temporal evaluation gate."""

from claim_polygraph_ng.evaluation.phase6_temporal import (
    evaluate_temporal_benchmark,
    load_temporal_benchmark,
)


def test_project_temporal_fixture_passes_locked_gate() -> None:
    benchmark = load_temporal_benchmark("benchmarks/phase6_temporal_relations_v1.json")
    evaluation = evaluate_temporal_benchmark(benchmark)

    assert evaluation.case_count == 20
    assert evaluation.accuracy == 1
    assert evaluation.false_resolved_incomplete_count == 0
    assert evaluation.out_of_packet_reference_count == 0
    assert evaluation.gate_passed
