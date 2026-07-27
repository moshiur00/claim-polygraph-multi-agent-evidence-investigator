"""Run the offline Stage 5.5 explicit-link evaluation."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_manifest import load_provenance_benchmark
from claim_polygraph_ng.evaluation.phase5_provenance_links import (
    evaluate_provenance_links,
    export_provenance_link_evaluation,
)

ROOT = Path(__file__).parents[1]


def main() -> int:
    benchmark = load_provenance_benchmark(ROOT / "benchmarks/phase5_provenance_fixtures_v1.json")
    result = evaluate_provenance_links(benchmark)
    output = export_provenance_link_evaluation(
        result, ROOT / "artifacts/evaluations/phase5-stage5.5-provenance-links.json"
    )
    print(f"Pairs: {result.pair_count}")
    print(f"Links: {result.extracted_link_count}")
    print(f"Precision: {result.precision}")
    print(f"Recall: {result.recall}")
    print(f"Offsets valid: {result.offsets_valid}")
    print(f"Retrieval calls: {result.retrieval_call_count}")
    print(f"Valid: {result.valid}")
    print(f"Artifact: {output}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
