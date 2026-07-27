from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_manifest import load_provenance_benchmark
from claim_polygraph_ng.evaluation.phase5_source_quality import (
    evaluate_source_quality_structure,
)


def test_locked_fixture_quality_structure_is_complete_and_conservative():
    root = Path(__file__).parents[2]
    benchmark = load_provenance_benchmark(root / "benchmarks/phase5_provenance_fixtures_v1.json")

    result = evaluate_source_quality_structure(benchmark)

    assert result.valid
    assert result.source_count == 24
    assert result.complete_assessment_rate == 1
    assert result.explained_dimension_rate == 1
    assert result.unknown_preservation_rate == 1
    assert result.aggregate_score_count == 0
