"""Deterministic calibration metrics for reviewed construction fixtures."""

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel


class VerificationCalibrationMetrics(DomainModel):
    """Precision-oriented metrics kept distinct from verdict confidence."""

    case_count: int = Field(ge=1)
    constructible_case_count: int = Field(ge=0)
    correct_construction_count: int = Field(ge=0)
    unsafe_construction_count: int = Field(ge=0)
    correct_outcome_count: int = Field(ge=0)
    construction_recall: float = Field(ge=0, le=1)
    construction_precision: float = Field(ge=0, le=1)
    outcome_accuracy: float = Field(ge=0, le=1)


def calculate_verification_calibration(
    outcomes: tuple[tuple[bool, str | None, bool, str | None], ...],
) -> VerificationCalibrationMetrics:
    """Calculate metrics from observed/gold construction and outcome tuples."""
    if not outcomes:
        raise ValueError("verification calibration requires at least one case")
    constructible = sum(expected_constructed for _, _, expected_constructed, _ in outcomes)
    observed_constructed = sum(observed for observed, _, _, _ in outcomes)
    correct_constructions = sum(
        observed and expected
        for observed, _, expected, _ in outcomes
    )
    unsafe = sum(
        observed and not expected
        for observed, _, expected, _ in outcomes
    )
    outcome_cases = [
        (observed_state, expected_state)
        for observed, observed_state, expected, expected_state in outcomes
        if observed and expected and expected_state is not None
    ]
    correct_outcomes = sum(observed == expected for observed, expected in outcome_cases)
    return VerificationCalibrationMetrics(
        case_count=len(outcomes),
        constructible_case_count=constructible,
        correct_construction_count=correct_constructions,
        unsafe_construction_count=unsafe,
        correct_outcome_count=correct_outcomes,
        construction_recall=(
            correct_constructions / constructible if constructible else 1
        ),
        construction_precision=(
            correct_constructions / observed_constructed
            if observed_constructed
            else 1
        ),
        outcome_accuracy=(
            correct_outcomes / len(outcome_cases) if outcome_cases else 1
        ),
    )
