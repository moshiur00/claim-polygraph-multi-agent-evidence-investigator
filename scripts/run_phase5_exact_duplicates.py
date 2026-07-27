"""Run the offline Stage 5.3 exact-duplicate evaluation."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_exact_duplicates import (
    evaluate_exact_duplicates,
    export_exact_duplicate_evaluation,
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
    result = evaluate_exact_duplicates(
        benchmark,
        required_precision=manifest.thresholds.exact_duplicate_precision,
        required_recall=manifest.thresholds.exact_duplicate_recall,
    )
    output = export_exact_duplicate_evaluation(
        result, ROOT / "artifacts/evaluations/phase5-stage5.3-exact-duplicates.json"
    )
    print(f"Sources: {result.source_count}")
    print(f"Clusters: {result.cluster_count}")
    print(f"Precision: {result.precision}")
    print(f"Recall: {result.recall}")
    print(f"Valid: {result.valid}")
    print(f"Artifact: {output}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
