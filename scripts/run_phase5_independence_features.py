"""Run the offline Stage 5.8 uncertainty-bound evaluation."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_independence_features import (
    evaluate_independence_features,
    export_independence_feature_evaluation,
)
from claim_polygraph_ng.evaluation.phase5_manifest import (
    load_phase5_manifest,
    load_provenance_benchmark,
)

ROOT = Path(__file__).parents[1]


def main() -> int:
    manifest = load_phase5_manifest(
        ROOT / "artifacts/evaluations/phase5-source-intelligence-manifest-v1.json"
    )
    benchmark = load_provenance_benchmark(ROOT / "benchmarks/phase5_provenance_fixtures_v1.json")
    result = evaluate_independence_features(
        benchmark,
        required_family_accuracy=manifest.thresholds.family_accuracy,
        maximum_false_independent_rate=manifest.thresholds.maximum_false_independent_rate,
    )
    output = export_independence_feature_evaluation(
        result, ROOT / "artifacts/evaluations/phase5-stage5.8-independence-features.json"
    )
    print(f"Family accuracy: {result.family_accuracy:.2%}")
    print(f"False confirmed independence: {result.false_confirmed_independent_rate:.2%}")
    print(f"Unknowns counted as confirmed: {result.unknown_pairs_counted_as_confirmed}")
    print(f"Valid: {result.valid}")
    print(f"Artifact: {output}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
