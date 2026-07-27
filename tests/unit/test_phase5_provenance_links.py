from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_manifest import load_provenance_benchmark
from claim_polygraph_ng.evaluation.phase5_provenance_links import (
    evaluate_provenance_links,
)


def test_locked_fixture_meets_explicit_link_precision_gate():
    root = Path(__file__).parents[2]
    benchmark = load_provenance_benchmark(root / "benchmarks/phase5_provenance_fixtures_v1.json")

    result = evaluate_provenance_links(benchmark)

    assert result.valid
    assert result.pair_count == 12
    assert result.true_positive_count == 3
    assert result.false_positive_count == 0
    assert result.false_negative_count == 0
    assert result.precision == 1
    assert result.recall == 1
    assert result.offsets_valid
    assert result.retrieval_call_count == 0
    assert result.unresolved_link_count == result.extracted_link_count
