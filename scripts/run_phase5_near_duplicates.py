"""Run the offline Stage 5.4 derivative evaluation."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_manifest import (
    load_phase5_manifest,
    load_provenance_benchmark,
)
from claim_polygraph_ng.evaluation.phase5_near_duplicates import (
    evaluate_near_duplicates,
    export_near_duplicate_evaluation,
)

ROOT = Path(__file__).parents[1]


def main() -> int:
    manifest = load_phase5_manifest(
        ROOT / "artifacts/evaluations/phase5-source-intelligence-manifest-v1.json"
    )
    benchmark = load_provenance_benchmark(ROOT / "benchmarks/phase5_provenance_fixtures_v1.json")
    result = evaluate_near_duplicates(
        benchmark,
        required_precision=manifest.thresholds.derivative_precision,
        required_recall=manifest.thresholds.derivative_recall,
    )
    output = export_near_duplicate_evaluation(
        result, ROOT / "artifacts/evaluations/phase5-stage5.4-near-duplicates.json"
    )
    print(f"Evaluated/excluded pairs: {result.evaluated_pair_count}/{result.excluded_pair_count}")
    print(f"Precision: {result.precision}")
    print(f"Recall: {result.recall}")
    print(f"Automatic independence use: {result.automatic_independence_use_allowed}")
    print(f"Valid: {result.valid}")
    print(f"Artifact: {output}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
