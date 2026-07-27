"""Tests for exact, fail-closed numerical verification."""

from decimal import Decimal
from uuid import uuid4

from claim_polygraph_ng.analysis.numerical_verification import (
    NumericalEvidenceOperand,
    NumericalVerificationRequest,
    RankOrder,
    verify_numerical_assertion,
)
from claim_polygraph_ng.domain import (
    AssertionVerificationState,
    NormalizedNumericValue,
    NumericComparator,
    NumericDimension,
    NumericOperation,
)


def _value(value, unit=None, dimension=NumericDimension.DIMENSIONLESS, **kwargs):
    return NormalizedNumericValue(
        value=Decimal(str(value)),
        unit=unit,
        dimension=dimension,
        **kwargs,
    )


def _operand(value, unit=None, dimension=NumericDimension.DIMENSIONLESS):
    return NumericalEvidenceOperand(
        evidence_id=uuid4(),
        value=_value(value, unit, dimension),
    )


def _request(operation, expected, operands, **kwargs):
    return NumericalVerificationRequest(
        claim_id=uuid4(),
        claim_text_span="Project-authored numerical assertion.",
        comparator=kwargs.pop("comparator", NumericComparator.EQUAL),
        operation=operation,
        expected_values=expected,
        operands=operands,
        **kwargs,
    )


def test_direct_unit_conversion_and_tolerance() -> None:
    result = verify_numerical_assertion(
        _request(
            NumericOperation.DIRECT,
            (
                _value(
                    "1.00",
                    "kilometre",
                    NumericDimension.DISTANCE,
                    tolerance=Decimal("0.01"),
                ),
            ),
            (_operand("1001", "metre", NumericDimension.DISTANCE),),
        )
    )

    assert result.state is AssertionVerificationState.VERIFIED
    assert result.normalized_result is not None
    assert result.normalized_result.value == Decimal("1.001")


def test_sum_difference_ratio_and_ranges() -> None:
    summed = verify_numerical_assertion(
        _request(
            NumericOperation.SUM,
            (_value(3, "hour", NumericDimension.DURATION),),
            (
                _operand(60, "minute", NumericDimension.DURATION),
                _operand(2, "hour", NumericDimension.DURATION),
            ),
        )
    )
    difference = verify_numerical_assertion(
        _request(
            NumericOperation.DIFFERENCE,
            (_value(500, "metre", NumericDimension.DISTANCE),),
            (
                _operand(2, "kilometre", NumericDimension.DISTANCE),
                _operand(1500, "metre", NumericDimension.DISTANCE),
            ),
        )
    )
    ratio = verify_numerical_assertion(
        _request(
            NumericOperation.RATIO,
            (_value(2),),
            (
                _operand(2, "kilometre", NumericDimension.DISTANCE),
                _operand(1000, "metre", NumericDimension.DISTANCE),
            ),
        )
    )
    ranged = verify_numerical_assertion(
        _request(
            NumericOperation.DIRECT,
            (
                _value(99, "kilopascal", NumericDimension.PRESSURE),
                _value(102, "kilopascal", NumericDimension.PRESSURE),
            ),
            (_operand("101.325", "kilopascal", NumericDimension.PRESSURE),),
            comparator=NumericComparator.BETWEEN_INCLUSIVE,
        )
    )

    assert all(
        item.state is AssertionVerificationState.VERIFIED
        for item in (summed, difference, ratio, ranged)
    )


def test_percentage_change_percentage_points_and_rounding() -> None:
    percentage = verify_numerical_assertion(
        _request(
            NumericOperation.PERCENTAGE_CHANGE,
            (_value(10, "percent", NumericDimension.PERCENTAGE),),
            (_operand(100), _operand(110)),
        )
    )
    points = verify_numerical_assertion(
        _request(
            NumericOperation.PERCENTAGE_POINT_CHANGE,
            (_value(5, "percentage_point", NumericDimension.PERCENTAGE),),
            (
                _operand(40, "percent", NumericDimension.PERCENTAGE),
                _operand(45, "percent", NumericDimension.PERCENTAGE),
            ),
        )
    )
    rounded = verify_numerical_assertion(
        _request(
            NumericOperation.RATIO,
            (_value("0.33", tolerance=Decimal("0.001")),),
            (_operand(1), _operand(3)),
            decimal_places=2,
        )
    )

    assert percentage.state is AssertionVerificationState.VERIFIED
    assert points.state is AssertionVerificationState.VERIFIED
    assert rounded.state is AssertionVerificationState.VERIFIED
    assert rounded.normalized_result is not None
    assert rounded.normalized_result.value == Decimal("0.33")


def test_complete_rank_and_contradiction() -> None:
    ranked = verify_numerical_assertion(
        _request(
            NumericOperation.RANK,
            (_value(2, "rank", NumericDimension.COUNT),),
            (
                _operand(10, "million", NumericDimension.COUNT),
                _operand(8, "million", NumericDimension.COUNT),
                _operand(6, "million", NumericDimension.COUNT),
            ),
            target_operand_index=1,
            ranking_complete=True,
            rank_order=RankOrder.DESCENDING,
        )
    )
    contradicted = verify_numerical_assertion(
        _request(
            NumericOperation.DIRECT,
            (_value(366, "day", NumericDimension.DURATION),),
            (_operand(365, "day", NumericDimension.DURATION),),
        )
    )

    assert ranked.state is AssertionVerificationState.VERIFIED
    assert contradicted.state is AssertionVerificationState.CONTRADICTED


def test_missing_incomplete_and_unsafe_inputs_fail_closed() -> None:
    missing = verify_numerical_assertion(
        _request(NumericOperation.DIRECT, (_value(1),), ())
    )
    incomplete_rank = verify_numerical_assertion(
        _request(
            NumericOperation.RANK,
            (_value(1, "rank", NumericDimension.COUNT),),
            (_operand(10, "item", NumericDimension.COUNT),),
            target_operand_index=0,
            ranking_complete=False,
        )
    )
    zero_baseline = verify_numerical_assertion(
        _request(
            NumericOperation.PERCENTAGE_CHANGE,
            (_value(10, "percent", NumericDimension.PERCENTAGE),),
            (_operand(0), _operand(1)),
        )
    )
    currency = verify_numerical_assertion(
        _request(
            NumericOperation.DIRECT,
            (_value(100, "EUR", NumericDimension.CURRENCY),),
            (_operand(100, "USD", NumericDimension.CURRENCY),),
        )
    )

    assert missing.state is AssertionVerificationState.INSUFFICIENT
    assert incomplete_rank.state is AssertionVerificationState.INSUFFICIENT
    assert zero_baseline.state is AssertionVerificationState.ERROR
    assert currency.state is AssertionVerificationState.ERROR
