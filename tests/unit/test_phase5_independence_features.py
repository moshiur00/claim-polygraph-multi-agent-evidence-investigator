from pathlib import Path

from claim_polygraph_ng.analysis.independence_features import (
    IndependenceRequirementState,
)
from claim_polygraph_ng.evaluation.phase5_independence_features import (
    evaluate_independence_features,
)
from claim_polygraph_ng.evaluation.phase5_manifest import load_provenance_benchmark


def test_locked_fixture_does_not_count_unknown_as_confirmed_independence():
    root = Path(__file__).parents[2]
    benchmark = load_provenance_benchmark(root / "benchmarks/phase5_provenance_fixtures_v1.json")

    result = evaluate_independence_features(
        benchmark,
        required_family_accuracy=0.9,
        maximum_false_independent_rate=0.05,
    )

    assert result.valid
    assert result.family_accuracy == 11 / 12
    assert result.false_confirmed_independent_count == 0
    assert result.false_confirmed_independent_rate == 0
    assert result.unknown_pairs_counted_as_confirmed == 0
    ambiguous = next(item for item in result.results if item.case_id == "PROV-012")
    assert ambiguous.lower_bound == 1
    assert ambiguous.upper_bound == 2
    assert ambiguous.requirement_state is IndependenceRequirementState.UNCERTAIN
