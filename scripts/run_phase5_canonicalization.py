"""Run the offline Stage 5.1 canonicalization evaluation."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_canonicalization import (
    evaluate_canonicalization,
    export_canonicalization_evaluation,
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
    evaluation = evaluate_canonicalization(
        benchmark, required_precision=manifest.thresholds.canonical_precision
    )
    output = export_canonicalization_evaluation(
        evaluation,
        ROOT / "artifacts/evaluations/phase5-stage5.1-canonicalization.json",
    )
    print(f"Pairs: {evaluation.pair_count}")
    print(f"Precision: {evaluation.precision}")
    print(f"Recall: {evaluation.recall}")
    print(f"Valid: {evaluation.valid}")
    print(f"Artifact: {output}")
    return 0 if evaluation.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
