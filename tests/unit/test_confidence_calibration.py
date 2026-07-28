"""Stage 8.9 empirical calibration, leakage and promotion tests."""

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    CalibrationCase,
    CalibrationFeatureVector,
    CalibrationSplit,
    CalibrationStatus,
    ConfidenceCalibrationDataset,
)
from claim_polygraph_ng.evaluation import evaluate_confidence_calibration


def test_repository_scale_dataset_is_explicitly_insufficient() -> None:
    dataset = ConfidenceCalibrationDataset(
        dataset_id="reviewed-internal-claims",
        version=1,
        cases=tuple(_case(index, total=20) for index in range(20)),
    )

    result = evaluate_confidence_calibration(dataset)

    assert result.status is CalibrationStatus.INSUFFICIENT_DATA
    assert not result.confidence_available
    assert result.selected_calibrator is None
    assert result.compared_metrics == ()
    assert result.insufficiency_reasons
    assert result.readiness_remains_distinct


def test_sufficient_separable_dataset_uses_held_out_evaluation() -> None:
    dataset = ConfidenceCalibrationDataset(
        dataset_id="synthetic-calibration-contract-fixture",
        version=1,
        cases=tuple(_case(index, total=210) for index in range(210)),
    )

    first = evaluate_confidence_calibration(dataset)
    second = evaluate_confidence_calibration(dataset)

    assert first == second
    assert first.status is CalibrationStatus.PROMOTED
    assert first.confidence_available
    assert first.selected_calibrator is not None
    assert len(first.compared_metrics) == 3
    assert first.evaluation_case_count == 60
    assert all(item.evaluation_count == 60 for item in first.compared_metrics)
    assert all(len(item.reliability_bins) == 10 for item in first.compared_metrics)


def test_sufficient_but_uninformative_features_are_not_promoted() -> None:
    cases = tuple(
        _case(index, total=210).model_copy(
            update={
                "features": CalibrationFeatureVector(
                    evidence_quality=0.5,
                    independent_family_count=1,
                    contradiction_balance=0,
                    citation_support_rate=0.5,
                    unresolved_verification_rate=0.5,
                    retrieval_coverage=0.5,
                    model_disagreement=0.5,
                )
            }
        )
        for index in range(210)
    )

    result = evaluate_confidence_calibration(
        ConfidenceCalibrationDataset(
            dataset_id="uninformative-contract-fixture",
            version=1,
            cases=cases,
        )
    )

    assert result.status is CalibrationStatus.NOT_PROMOTED
    assert not result.confidence_available
    assert result.selected_calibrator is None
    assert result.compared_metrics


def test_claim_group_cannot_leak_across_fit_and_evaluation() -> None:
    fit = _case(0, total=210)
    evaluation = _case(180, total=210).model_copy(update={"group_id": fit.group_id})

    with pytest.raises(ValidationError, match="cannot cross"):
        ConfidenceCalibrationDataset(
            dataset_id="leaking-fixture",
            version=1,
            cases=(fit, evaluation),
        )


def _case(index: int, *, total: int) -> CalibrationCase:
    evaluation_start = total - 60 if total >= 200 else max(1, total - 5)
    correct = index % 2 == 0
    high = 0.95 if correct else 0.05
    return CalibrationCase(
        case_id=f"CAL-{index:04d}",
        group_id=f"GROUP-{index:04d}",
        domain=("science", "law", "public-health")[index % 3],
        predicted_label=("supported", "contradicted")[index % 2],
        reference_label=("supported", "contradicted")[index % 2],
        correct=correct,
        split=(CalibrationSplit.EVALUATION if index >= evaluation_start else CalibrationSplit.FIT),
        features=CalibrationFeatureVector(
            evidence_quality=high,
            independent_family_count=3 if correct else 0,
            contradiction_balance=0 if correct else 1,
            citation_support_rate=high,
            unresolved_verification_rate=0.0 if correct else 1.0,
            retrieval_coverage=high,
            model_disagreement=0.0 if correct else 1.0,
        ),
    )
