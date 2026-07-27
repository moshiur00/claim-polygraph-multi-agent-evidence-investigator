from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_canonicalization import (
    evaluate_canonicalization,
)
from claim_polygraph_ng.evaluation.phase5_manifest import load_provenance_benchmark


def test_locked_fixture_meets_canonical_precision_gate():
    root = Path(__file__).parents[2]
    benchmark = load_provenance_benchmark(root / "benchmarks/phase5_provenance_fixtures_v1.json")

    result = evaluate_canonicalization(benchmark, required_precision=1.0)

    assert result.valid
    assert result.pair_count == 12
    assert result.precision == 1.0
    assert result.false_positive_count == 0
    assert result.true_positive_count == 3
    assert result.false_negative_count == 1
    assert result.recall == 0.75
    assert next(item for item in result.results if item.case_id == "PROV-003").correct is False
