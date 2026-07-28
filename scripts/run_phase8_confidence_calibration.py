"""Evaluate the current feature-complete calibration inventory without model calls."""

from pathlib import Path

from claim_polygraph_ng.domain import ConfidenceCalibrationDataset
from claim_polygraph_ng.evaluation import evaluate_confidence_calibration


def main() -> None:
    root = Path(__file__).parents[1]
    dataset = ConfidenceCalibrationDataset.model_validate_json(
        (root / "benchmarks/phase8_confidence_calibration_eligible_v1.json").read_text(
            encoding="utf-8"
        )
    )
    result = evaluate_confidence_calibration(
        dataset,
        reviewed_candidate_count=20,
        excluded_incomplete_feature_count=20,
        compatible_public_case_count=0,
    )
    target = root / "artifacts/evaluations/phase8-stage8.9-confidence-calibration-v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        f"Status: {result.status.value}; "
        f"confidence available: {str(result.confidence_available).lower()}"
    )


if __name__ == "__main__":
    main()
