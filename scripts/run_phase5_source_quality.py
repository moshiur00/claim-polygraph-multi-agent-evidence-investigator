"""Run the zero-cost Stage 5.2 structural evaluation."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_manifest import load_provenance_benchmark
from claim_polygraph_ng.evaluation.phase5_source_quality import (
    evaluate_source_quality_structure,
    export_source_quality_evaluation,
)

ROOT = Path(__file__).parents[1]


def main() -> int:
    benchmark = load_provenance_benchmark(ROOT / "benchmarks/phase5_provenance_fixtures_v1.json")
    result = evaluate_source_quality_structure(benchmark)
    output = export_source_quality_evaluation(
        result, ROOT / "artifacts/evaluations/phase5-stage5.2-source-quality.json"
    )
    print(f"Sources: {result.source_count}")
    print(f"Complete: {result.complete_assessment_rate:.2%}")
    print(f"Explained: {result.explained_dimension_rate:.2%}")
    print(f"Unknowns preserved: {result.unknown_preservation_rate:.2%}")
    print(f"Aggregate scores: {result.aggregate_score_count}")
    print(f"Valid: {result.valid}")
    print(f"Artifact: {output}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
