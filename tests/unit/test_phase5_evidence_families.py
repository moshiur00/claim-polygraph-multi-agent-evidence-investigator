from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_evidence_families import (
    evaluate_evidence_families,
)
from claim_polygraph_ng.evaluation.phase5_manifest import load_provenance_benchmark


def test_locked_fixture_exposes_one_ambiguous_false_independence():
    root = Path(__file__).parents[2]
    benchmark = load_provenance_benchmark(root / "benchmarks/phase5_provenance_fixtures_v1.json")

    result = evaluate_evidence_families(
        benchmark, required_accuracy=0.9, maximum_false_independent_rate=0.05
    )

    assert result.family_accuracy == 11 / 12
    assert result.family_accuracy_gate_passed
    assert result.false_independent_count == 1
    assert result.expected_dependent_count == 9
    assert result.false_independent_rate == 1 / 9
    assert not result.false_independence_gate_passed
    assert not result.valid
    ambiguous = next(item for item in result.results if item.case_id == "PROV-012")
    assert ambiguous.dependency_status.value == "unknown"
    assert not ambiguous.predicted_same_family
    assert "Stage 5.7" in result.next_action
