from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_exact_duplicates import (
    evaluate_exact_duplicates,
)
from claim_polygraph_ng.evaluation.phase5_manifest import load_provenance_benchmark


def test_locked_fixture_meets_exact_duplicate_gates():
    root = Path(__file__).parents[2]
    benchmark = load_provenance_benchmark(root / "benchmarks/phase5_provenance_fixtures_v1.json")

    result = evaluate_exact_duplicates(benchmark, required_precision=1, required_recall=1)

    assert result.valid
    assert result.source_count == 24
    assert result.cluster_count == 4
    assert result.true_positive_count == 4
    assert result.false_positive_count == 0
    assert result.false_negative_count == 0
    assert result.precision == 1
    assert result.recall == 1
