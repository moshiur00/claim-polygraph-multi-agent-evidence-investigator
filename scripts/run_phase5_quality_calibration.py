"""Evaluate the human-reviewable Stage 5.2 calibration set."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_quality_calibration import (
    evaluate_source_quality_calibration,
    export_source_quality_calibration_result,
    load_source_quality_calibration,
)

ROOT = Path(__file__).parents[1]


def main() -> int:
    calibration = load_source_quality_calibration(
        ROOT / "benchmarks/phase5_source_quality_calibration_v1.json"
    )
    result = evaluate_source_quality_calibration(calibration)
    output = export_source_quality_calibration_result(
        result, ROOT / "artifacts/evaluations/phase5-stage5.2-quality-calibration.json"
    )
    print(f"Cases: {result.case_count}")
    print(f"Dimensions: {result.dimension_count}")
    print(f"Agreement: {result.agreement:.2%}")
    print(f"Agreement gate: {result.agreement_gate_passed}")
    print(f"Human review gate: {result.human_review_gate_passed}")
    print(f"Valid: {result.valid}")
    print(f"Artifact: {output}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
