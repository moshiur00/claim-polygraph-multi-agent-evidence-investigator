"""Run the offline Stage 5.6 evidence-family evaluation."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_evidence_families import (
    evaluate_evidence_families,
    export_evidence_family_evaluation,
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
    result = evaluate_evidence_families(
        benchmark,
        required_accuracy=manifest.thresholds.family_accuracy,
        maximum_false_independent_rate=manifest.thresholds.maximum_false_independent_rate,
    )
    output = export_evidence_family_evaluation(
        result, ROOT / "artifacts/evaluations/phase5-stage5.6-evidence-families.json"
    )
    print(f"Accuracy: {result.family_accuracy:.2%}")
    print(f"False-independent rate: {result.false_independent_rate:.2%}")
    print(f"Accuracy gate: {result.family_accuracy_gate_passed}")
    print(f"False-independence gate: {result.false_independence_gate_passed}")
    print(f"Valid: {result.valid}")
    print(f"Next: {result.next_action}")
    print(f"Artifact: {output}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
