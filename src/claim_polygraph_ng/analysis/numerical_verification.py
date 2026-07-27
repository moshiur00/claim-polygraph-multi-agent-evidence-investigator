"""Exact, allowlisted numerical verification with evidence-bound operands."""

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from claim_polygraph_ng.domain import (
    AssertionVerificationState,
    NormalizedNumericValue,
    NumericalAssertionVerification,
    NumericComparator,
    NumericDimension,
    NumericOperation,
)
from claim_polygraph_ng.domain.base import DomainModel

NUMERICAL_VERIFIER_VERSION = "numerical-verifier-v1"


class RankOrder(StrEnum):
    """Direction used by a complete ranking input."""

    DESCENDING = "descending"
    ASCENDING = "ascending"


class NumericalEvidenceOperand(DomainModel):
    """One exact operand taken from an approved evidence passage."""

    evidence_id: UUID
    value: NormalizedNumericValue
    label: str | None = Field(default=None, min_length=1, max_length=500)


class NumericalVerificationRequest(DomainModel):
    """Typed input for one deterministic numerical verification."""

    claim_id: UUID
    claim_text_span: str = Field(min_length=1, max_length=2_000)
    comparator: NumericComparator
    operation: NumericOperation = NumericOperation.DIRECT
    expected_values: tuple[NormalizedNumericValue, ...] = Field(min_length=1, max_length=2)
    operands: tuple[NumericalEvidenceOperand, ...]
    decimal_places: int | None = Field(default=None, ge=0, le=18)
    target_operand_index: int | None = Field(default=None, ge=0)
    rank_order: RankOrder = RankOrder.DESCENDING
    ranking_complete: bool = False

    @model_validator(mode="after")
    def validate_request_shape(self) -> "NumericalVerificationRequest":
        range_comparators = {
            NumericComparator.BETWEEN_INCLUSIVE,
            NumericComparator.BETWEEN_EXCLUSIVE,
        }
        expected_count = 2 if self.comparator in range_comparators else 1
        if len(self.expected_values) != expected_count:
            raise ValueError(f"{self.comparator.value} requires {expected_count} expected value(s)")
        if self.operation is NumericOperation.RANK:
            if self.target_operand_index is None:
                raise ValueError("rank verification requires target_operand_index")
            if self.target_operand_index >= len(self.operands):
                raise ValueError("target_operand_index is outside the operands")
        elif self.target_operand_index is not None:
            raise ValueError("target_operand_index applies only to rank verification")
        return self


def verify_numerical_assertion(
    request: NumericalVerificationRequest,
) -> NumericalAssertionVerification:
    """Calculate and compare one assertion, returning uncertainty instead of guessing."""
    expression = _expression(request)
    evidence_ids = tuple(dict.fromkeys(item.evidence_id for item in request.operands))
    if not request.operands:
        return _unresolved(
            request,
            AssertionVerificationState.INSUFFICIENT,
            expression,
            "No evidence-bound numerical operands were supplied.",
        )
    if request.operation is NumericOperation.RANK and not request.ranking_complete:
        return _unresolved(
            request,
            AssertionVerificationState.INSUFFICIENT,
            expression,
            "Ranking inputs are not declared complete.",
        )
    try:
        result = _calculate(request)
        if request.decimal_places is not None:
            quantum = Decimal(1).scaleb(-request.decimal_places)
            result = result.model_copy(
                update={"value": result.value.quantize(quantum, rounding=ROUND_HALF_EVEN)}
            )
        matches = _compare(result, request.comparator, request.expected_values)
    except NumericalVerificationError as exc:
        return _unresolved(
            request,
            AssertionVerificationState.ERROR,
            expression,
            str(exc),
        )
    return NumericalAssertionVerification(
        claim_id=request.claim_id,
        claim_text_span=request.claim_text_span,
        comparator=request.comparator,
        operation=request.operation,
        expected_values=request.expected_values,
        evidence_ids=evidence_ids,
        state=(
            AssertionVerificationState.VERIFIED
            if matches
            else AssertionVerificationState.CONTRADICTED
        ),
        normalized_result=result,
        expression=expression if request.operation is not NumericOperation.DIRECT else None,
        rounding_rule=(
            f"round_half_even_to_{request.decimal_places}_decimal_places"
            if request.decimal_places is not None
            else None
        ),
        limitations=(
            "Only evidence-bound operands and allowlisted deterministic operations were used.",
            f"Verifier version: {NUMERICAL_VERIFIER_VERSION}.",
        ),
    )


class NumericalVerificationError(ValueError):
    """Raised internally when deterministic verification cannot safely proceed."""


_LINEAR_UNITS: dict[NumericDimension, dict[str, Decimal]] = {
    NumericDimension.DISTANCE: {
        "millimetre": Decimal("0.001"),
        "centimetre": Decimal("0.01"),
        "metre": Decimal("1"),
        "kilometre": Decimal("1000"),
    },
    NumericDimension.DURATION: {
        "second": Decimal("1"),
        "minute": Decimal("60"),
        "hour": Decimal("3600"),
        "day": Decimal("86400"),
        "year_julian": Decimal("31557600"),
    },
    NumericDimension.MASS: {
        "gram": Decimal("1"),
        "kilogram": Decimal("1000"),
    },
    NumericDimension.PRESSURE: {
        "pascal": Decimal("1"),
        "kilopascal": Decimal("1000"),
        "atmosphere": Decimal("101325"),
    },
    NumericDimension.PERCENTAGE: {
        "percent": Decimal("1"),
        "percentage_point": Decimal("1"),
    },
}


def _calculate(request: NumericalVerificationRequest) -> NormalizedNumericValue:
    operation = request.operation
    operands = request.operands
    target = request.expected_values[0]
    if operation is NumericOperation.DIRECT:
        _require_count(operands, 1, operation)
        return _convert(operands[0].value, target)
    if operation in {NumericOperation.SUM, NumericOperation.DIFFERENCE}:
        if operation is NumericOperation.SUM and len(operands) < 1:
            raise NumericalVerificationError("sum requires at least one operand")
        if operation is NumericOperation.DIFFERENCE:
            _require_count(operands, 2, operation)
        converted = [_convert(item.value, target).value for item in operands]
        value = (
            sum(converted, Decimal(0))
            if operation is NumericOperation.SUM
            else converted[0] - converted[1]
        )
        return _result(value, target)
    if operation is NumericOperation.RATIO:
        _require_count(operands, 2, operation)
        left, right = (_canonical(item.value) for item in operands)
        if operands[0].value.dimension != operands[1].value.dimension:
            raise NumericalVerificationError("ratio operands require compatible dimensions")
        if right == 0:
            raise NumericalVerificationError("ratio denominator cannot be zero")
        return NormalizedNumericValue(value=left / right)
    if operation is NumericOperation.PERCENTAGE_CHANGE:
        _require_count(operands, 2, operation)
        old, new = _compatible_canonical_pair(operands)
        if old == 0:
            raise NumericalVerificationError("percentage-change baseline cannot be zero")
        return NormalizedNumericValue(
            value=(new - old) / abs(old) * Decimal(100),
            unit="percent",
            dimension=NumericDimension.PERCENTAGE,
        )
    if operation is NumericOperation.PERCENTAGE_POINT_CHANGE:
        _require_count(operands, 2, operation)
        if any(item.value.dimension is not NumericDimension.PERCENTAGE for item in operands):
            raise NumericalVerificationError(
                "percentage-point change requires percentage operands"
            )
        old = _convert_percentage(operands[0].value)
        new = _convert_percentage(operands[1].value)
        return NormalizedNumericValue(
            value=new - old,
            unit="percentage_point",
            dimension=NumericDimension.PERCENTAGE,
        )
    if operation is NumericOperation.RANK:
        assert request.target_operand_index is not None
        dimensions = {item.value.dimension for item in operands}
        if len(dimensions) != 1 or NumericDimension.UNKNOWN in dimensions:
            raise NumericalVerificationError("ranking operands require one known dimension")
        comparison_unit = operands[0].value
        comparable = [_convert(item.value, comparison_unit).value for item in operands]
        target_value = comparable[request.target_operand_index]
        ordered = sorted(
            comparable,
            reverse=request.rank_order is RankOrder.DESCENDING,
        )
        rank = ordered.index(target_value) + 1
        return NormalizedNumericValue(
            value=Decimal(rank),
            unit="rank",
            dimension=NumericDimension.COUNT,
        )
    raise NumericalVerificationError(f"unsupported operation: {operation.value}")


def _compare(
    result: NormalizedNumericValue,
    comparator: NumericComparator,
    expected_values: tuple[NormalizedNumericValue, ...],
) -> bool:
    expected = tuple(_convert(item, result).value for item in expected_values)
    actual = result.value
    tolerance = expected_values[0].tolerance or Decimal(0)
    if comparator is NumericComparator.EQUAL:
        return abs(actual - expected[0]) <= tolerance
    if comparator is NumericComparator.GREATER_THAN:
        return actual > expected[0]
    if comparator is NumericComparator.GREATER_THAN_OR_EQUAL:
        return actual >= expected[0]
    if comparator is NumericComparator.LESS_THAN:
        return actual < expected[0]
    if comparator is NumericComparator.LESS_THAN_OR_EQUAL:
        return actual <= expected[0]
    if comparator is NumericComparator.BETWEEN_INCLUSIVE:
        return expected[0] <= actual <= expected[1]
    if comparator is NumericComparator.BETWEEN_EXCLUSIVE:
        return expected[0] < actual < expected[1]
    raise NumericalVerificationError(f"unsupported comparator: {comparator.value}")


def _convert(
    value: NormalizedNumericValue,
    target: NormalizedNumericValue,
) -> NormalizedNumericValue:
    if value.dimension != target.dimension:
        raise NumericalVerificationError(
            f"incompatible dimensions: {value.dimension.value} and {target.dimension.value}"
        )
    if value.dimension is NumericDimension.UNKNOWN:
        raise NumericalVerificationError("unknown dimensions cannot be converted")
    if value.dimension in {NumericDimension.DIMENSIONLESS, NumericDimension.COUNT}:
        if value.unit != target.unit:
            raise NumericalVerificationError("unitless/count units must match exactly")
        return _result(_canonical(value) / target.scale, target)
    if value.dimension is NumericDimension.CURRENCY:
        if value.unit != target.unit:
            raise NumericalVerificationError("currency conversion requires an external rate")
        return _result(_canonical(value) / target.scale, target)
    if value.dimension is NumericDimension.TEMPERATURE:
        kelvin = _temperature_to_kelvin(value)
        converted = _kelvin_to_temperature(kelvin, target.unit)
        return _result(converted / target.scale, target)
    units = _LINEAR_UNITS.get(value.dimension)
    if units is None or value.unit not in units or target.unit not in units:
        raise NumericalVerificationError(
            f"unit conversion is not allowlisted: {value.unit} to {target.unit}"
        )
    base = value.value * value.scale * units[value.unit]
    return _result(base / (target.scale * units[target.unit]), target)


def _canonical(value: NormalizedNumericValue) -> Decimal:
    if value.dimension is NumericDimension.TEMPERATURE:
        return _temperature_to_kelvin(value)
    if value.dimension in {
        NumericDimension.DIMENSIONLESS,
        NumericDimension.COUNT,
        NumericDimension.CURRENCY,
    }:
        return value.value * value.scale
    units = _LINEAR_UNITS.get(value.dimension)
    if units is None or value.unit not in units:
        raise NumericalVerificationError(f"unit is not allowlisted: {value.unit}")
    return value.value * value.scale * units[value.unit]


def _temperature_to_kelvin(value: NormalizedNumericValue) -> Decimal:
    scaled = value.value * value.scale
    if value.unit == "kelvin":
        return scaled
    if value.unit == "celsius":
        return scaled + Decimal("273.15")
    if value.unit == "fahrenheit":
        return (scaled - Decimal(32)) * Decimal(5) / Decimal(9) + Decimal("273.15")
    raise NumericalVerificationError(f"temperature unit is not allowlisted: {value.unit}")


def _kelvin_to_temperature(value: Decimal, unit: str | None) -> Decimal:
    if unit == "kelvin":
        return value
    if unit == "celsius":
        return value - Decimal("273.15")
    if unit == "fahrenheit":
        return (value - Decimal("273.15")) * Decimal(9) / Decimal(5) + Decimal(32)
    raise NumericalVerificationError(f"temperature unit is not allowlisted: {unit}")


def _convert_percentage(value: NormalizedNumericValue) -> Decimal:
    if value.unit not in {"percent", "percentage_point"}:
        raise NumericalVerificationError("percentage unit is not allowlisted")
    return value.value * value.scale


def _compatible_canonical_pair(
    operands: tuple[NumericalEvidenceOperand, ...],
) -> tuple[Decimal, Decimal]:
    if operands[0].value.dimension != operands[1].value.dimension:
        raise NumericalVerificationError("operands require compatible dimensions")
    converted = _convert(operands[1].value, operands[0].value)
    return _canonical(operands[0].value), _canonical(converted)


def _require_count(
    operands: tuple[NumericalEvidenceOperand, ...],
    count: int,
    operation: NumericOperation,
) -> None:
    if len(operands) != count:
        raise NumericalVerificationError(
            f"{operation.value} requires exactly {count} operand(s)"
        )


def _result(value: Decimal, template: NormalizedNumericValue) -> NormalizedNumericValue:
    try:
        if not value.is_finite():
            raise NumericalVerificationError("calculation result must be finite")
    except InvalidOperation as exc:
        raise NumericalVerificationError("calculation result is invalid") from exc
    return NormalizedNumericValue(
        value=value,
        unit=template.unit,
        dimension=template.dimension,
        scale=template.scale,
        tolerance=template.tolerance,
    )


def _expression(request: NumericalVerificationRequest) -> str:
    refs = ", ".join(str(item.evidence_id) for item in request.operands) or "none"
    return f"{request.operation.value}({refs})"


def _unresolved(
    request: NumericalVerificationRequest,
    state: AssertionVerificationState,
    expression: str,
    issue: str,
) -> NumericalAssertionVerification:
    return NumericalAssertionVerification(
        claim_id=request.claim_id,
        claim_text_span=request.claim_text_span,
        comparator=request.comparator,
        operation=request.operation,
        expected_values=request.expected_values,
        evidence_ids=tuple(dict.fromkeys(item.evidence_id for item in request.operands)),
        state=state,
        expression=expression if request.operation is not NumericOperation.DIRECT else None,
        issues=(issue,),
        limitations=(
            "No numerical result was accepted because deterministic verification "
            "could not safely complete.",
            f"Verifier version: {NUMERICAL_VERIFIER_VERSION}.",
        ),
    )
