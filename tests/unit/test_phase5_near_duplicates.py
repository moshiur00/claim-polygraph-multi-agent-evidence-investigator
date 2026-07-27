from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_manifest import load_provenance_benchmark
from claim_polygraph_ng.evaluation.phase5_near_duplicates import (
    evaluate_near_duplicates,
)


def test_locked_fixture_meets_derivative_precision_and_recall_gates():
    root = Path(__file__).parents[2]
    benchmark = load_provenance_benchmark(root / "benchmarks/phase5_provenance_fixtures_v1.json")

    result = evaluate_near_duplicates(benchmark, required_precision=0.95, required_recall=0.9)

    assert result.valid
    assert result.evaluated_pair_count == 6
    assert result.excluded_pair_count == 6
    assert result.true_positive_count == 3
    assert result.false_positive_count == 0
    assert result.false_negative_count == 0
    assert result.precision == 1
    assert result.recall == 1
    assert result.automatic_independence_use_allowed
