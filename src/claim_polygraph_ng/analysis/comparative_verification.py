"""Bounded construction of qualitative numerical comparisons."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, UUID, uuid5

from claim_polygraph_ng.analysis.numerical_verification import (
    NumericalEvidenceOperand,
    NumericalVerificationRequest,
    verify_numerical_assertion,
)
from claim_polygraph_ng.domain import (
    AssertionConstructionState,
    AtomicClaim,
    ComparativeAssertionConstruction,
    Evidence,
    NormalizedNumericValue,
    NumericalAssertionVerification,
    NumericComparator,
    NumericDimension,
    VerificationIssueFinding,
    VerificationIssueSeverity,
    VerificationReadinessImpact,
)

COMPARATIVE_CONSTRUCTOR_VERSION = "comparative-constructor-v1"

_COMPARISON_PATTERN = re.compile(
    r"^\s*(?P<left>.+?)\s+(?:is|are|was|were)\s+"
    r"(?P<term>more expensive|cheaper|hotter|colder|older|newer|faster|slower|greater|larger|"
    r"smaller|higher|lower|longer|shorter|heavier|lighter)\s+than\s+"
    r"(?P<right>.+?)[.!?]?\s*$",
    re.IGNORECASE,
)
_PROPERTY_COMPARISON_PATTERN = re.compile(
    r"^\s*(?P<left>.+?)\s+(?:has|had)\s+(?:a\s+)?"
    r"(?P<term>higher|lower|greater|smaller|larger)\s+"
    r"(?P<property>percentage|rate|count|pressure|speed)\s+than\s+"
    r"(?P<right>.+?)[.!?]?\s*$",
    re.IGNORECASE,
)
_TEMPERATURE_PATTERN = re.compile(
    r"(?<![\w.])(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*°?\s*"
    r"(?P<unit>[cCfFkK])\b"
)
_DURATION_PATTERN = re.compile(
    r"(?<![\w.])(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>years?|days?|hours?)\b",
    re.IGNORECASE,
)
_DISTANCE_PATTERN = re.compile(
    r"(?<![\w.])(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>kilometres?|kilometers?|km|metres?|meters?|m)\b",
    re.IGNORECASE,
)
_MASS_PATTERN = re.compile(
    r"(?<![\w.])(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>kilograms?|kg|grams?|g)\b",
    re.IGNORECASE,
)
_PERCENTAGE_PATTERN = re.compile(
    r"(?<![\w.])(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>%|percent(?:age)?(?:\s+points?)?)",
    re.IGNORECASE,
)
_PRESSURE_PATTERN = re.compile(
    r"(?<![\w.])(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>kilopascals?|kpa|pascals?|pa|atmospheres?|atm)\b",
    re.IGNORECASE,
)
_SPEED_PATTERN = re.compile(
    r"(?<![\w.])(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>kilometres?\s+per\s+hour|kilometers?\s+per\s+hour|km/h|"
    r"metres?\s+per\s+second|meters?\s+per\s+second|m/s|"
    r"miles?\s+per\s+hour|mph)\b",
    re.IGNORECASE,
)
_COUNT_PATTERN = re.compile(
    r"(?<![\w.])(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s+"
    r"(?P<unit>people|persons?|items?|cases?|members?|votes?|units?)\b",
    re.IGNORECASE,
)
_CURRENCY_PREFIX_PATTERN = re.compile(
    r"(?P<unit>[$€£])\s*(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)"
)
_CURRENCY_SUFFIX_PATTERN = re.compile(
    r"(?<![\w.])(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>usd|eur|gbp|dollars?|euros?|pounds?)\b",
    re.IGNORECASE,
)
_TERM_POLICY = {
    "hotter": ("temperature", NumericComparator.GREATER_THAN, NumericDimension.TEMPERATURE),
    "colder": ("temperature", NumericComparator.LESS_THAN, NumericDimension.TEMPERATURE),
    "older": ("age", NumericComparator.GREATER_THAN, NumericDimension.DURATION),
    "newer": ("age", NumericComparator.LESS_THAN, NumericDimension.DURATION),
    "faster": ("speed", NumericComparator.GREATER_THAN, NumericDimension.SPEED),
    "slower": ("speed", NumericComparator.LESS_THAN, NumericDimension.SPEED),
    "more expensive": (
        "currency",
        NumericComparator.GREATER_THAN,
        NumericDimension.CURRENCY,
    ),
    "cheaper": ("currency", NumericComparator.LESS_THAN, NumericDimension.CURRENCY),
    "greater": ("value", NumericComparator.GREATER_THAN, NumericDimension.UNKNOWN),
    "larger": ("value", NumericComparator.GREATER_THAN, NumericDimension.UNKNOWN),
    "smaller": ("value", NumericComparator.LESS_THAN, NumericDimension.UNKNOWN),
    "higher": ("value", NumericComparator.GREATER_THAN, NumericDimension.UNKNOWN),
    "lower": ("value", NumericComparator.LESS_THAN, NumericDimension.UNKNOWN),
    "longer": ("length", NumericComparator.GREATER_THAN, NumericDimension.DISTANCE),
    "shorter": ("length", NumericComparator.LESS_THAN, NumericDimension.DISTANCE),
    "heavier": ("mass", NumericComparator.GREATER_THAN, NumericDimension.MASS),
    "lighter": ("mass", NumericComparator.LESS_THAN, NumericDimension.MASS),
}
_PROPERTY_DIMENSIONS = {
    "percentage": NumericDimension.PERCENTAGE,
    "rate": NumericDimension.PERCENTAGE,
    "count": NumericDimension.COUNT,
    "pressure": NumericDimension.PRESSURE,
    "speed": NumericDimension.SPEED,
}
_PROPERTY_COMPARATORS = {
    "higher": NumericComparator.GREATER_THAN,
    "greater": NumericComparator.GREATER_THAN,
    "larger": NumericComparator.GREATER_THAN,
    "lower": NumericComparator.LESS_THAN,
    "smaller": NumericComparator.LESS_THAN,
}
_STOPWORDS = {
    "a",
    "an",
    "are",
    "earth",
    "is",
    "of",
    "the",
    "than",
    "was",
    "were",
}


@dataclass(frozen=True)
class _Candidate:
    evidence_id: UUID
    value: NormalizedNumericValue
    sentence: str


def construct_comparative_assertion(
    *,
    claim: AtomicClaim,
    evidence: tuple[Evidence, ...],
) -> tuple[
    ComparativeAssertionConstruction | None,
    NumericalAssertionVerification | None,
    VerificationIssueFinding | None,
]:
    """Construct and verify a supported comparison without guessing operands."""
    match = _COMPARISON_PATTERN.match(claim.text)
    property_match = _PROPERTY_COMPARISON_PATTERN.match(claim.text)
    match = match or property_match
    if match is None:
        return None, None, None

    left = match.group("left").strip()
    right = match.group("right").strip()
    term = match.group("term").casefold()
    if property_match is not None:
        compared_property = property_match.group("property").casefold()
        comparator = _PROPERTY_COMPARATORS[term]
        dimension = _PROPERTY_DIMENSIONS[compared_property]
    else:
        compared_property, comparator, dimension = _TERM_POLICY[term]
    construction_id = uuid5(
        NAMESPACE_URL,
        f"{claim.claim_id}/comparative/{left}/{term}/{right}",
    )
    if dimension not in {
        NumericDimension.TEMPERATURE,
        NumericDimension.DURATION,
        NumericDimension.DISTANCE,
        NumericDimension.MASS,
        NumericDimension.PERCENTAGE,
        NumericDimension.PRESSURE,
        NumericDimension.SPEED,
        NumericDimension.COUNT,
        NumericDimension.CURRENCY,
    }:
        return _failed(
            construction_id=construction_id,
            claim=claim,
            left=left,
            right=right,
            compared_property=compared_property,
            comparator=comparator,
            dimension=dimension,
            code="unsupported_comparison_dimension",
            message=(
                f"The '{term} than' comparison was detected, but its measurement "
                "dimension cannot yet be established deterministically."
            ),
            action=(
                "Specify the compared measure and unit, or route the comparison "
                "through a reviewed typed-construction step."
            ),
        )

    bound = _bind_measure_operands(
        left=left,
        right=right,
        dimension=dimension,
        evidence=evidence,
    )
    if bound is None:
        return _failed(
            construction_id=construction_id,
            claim=claim,
            left=left,
            right=right,
            compared_property=compared_property,
            comparator=comparator,
            dimension=dimension,
            code="comparative_evidence_operands_missing",
            message=(
                "The comparison was detected, but compatible evidence-bound "
                f"{dimension.value} values for both subjects were not found together."
            ),
            action=(
                "Retrieve an approved passage that identifies both subjects and "
                "states compatible values or an explicit equality."
            ),
        )

    left_candidate, right_candidate = bound
    assertion_id = uuid5(NAMESPACE_URL, f"{construction_id}/assertion")
    verified = verify_numerical_assertion(
        NumericalVerificationRequest(
            claim_id=claim.claim_id,
            claim_text_span=claim.text,
            comparator=comparator,
            expected_values=(right_candidate.value,),
            operands=(
                NumericalEvidenceOperand(
                    evidence_id=left_candidate.evidence_id,
                    value=left_candidate.value,
                    label=left,
                ),
            ),
        )
    )
    evidence_ids = tuple(
        dict.fromkeys((left_candidate.evidence_id, right_candidate.evidence_id))
    )
    verified = verified.model_copy(
        update={
            "assertion_id": assertion_id,
            "evidence_ids": evidence_ids,
            "expression": f"{left} {comparator.value} {right}",
            "limitations": (
                *verified.limitations,
                "Comparative subjects were bound only within one passage sentence.",
                f"Constructor version: {COMPARATIVE_CONSTRUCTOR_VERSION}.",
            ),
        }
    )
    construction = ComparativeAssertionConstruction(
        construction_id=construction_id,
        claim_id=claim.claim_id,
        claim_text_span=claim.text,
        left_subject=left,
        right_subject=right,
        compared_property=compared_property,
        comparator=comparator,
        dimension=dimension,
        state=AssertionConstructionState.CONSTRUCTED,
        assertion_id=assertion_id,
        evidence_ids=evidence_ids,
        explanation=(
            "Both comparative operands were bound to compatible values in an "
            "approved evidence sentence."
        ),
    )
    return construction, verified, None


def is_qualitative_comparison(value: str) -> bool:
    """Return whether the bounded comparative grammar recognizes the claim."""
    return (
        _COMPARISON_PATTERN.match(value) is not None
        or _PROPERTY_COMPARISON_PATTERN.match(value) is not None
    )


def _bind_measure_operands(
    *,
    left: str,
    right: str,
    dimension: NumericDimension,
    evidence: tuple[Evidence, ...],
) -> tuple[_Candidate, _Candidate] | None:
    left_terms = _subject_terms(left)
    right_terms = _subject_terms(right)
    for item in evidence:
        for sentence in _sentences(item.passage):
            normalized = sentence.casefold()
            if not _mentions(normalized, left_terms) or not _mentions(
                normalized, right_terms
            ):
                continue
            candidates = _measure_candidates(sentence, item.evidence_id, dimension)
            if len(candidates) >= 2:
                return candidates[0], candidates[1]
            if (
                dimension is NumericDimension.TEMPERATURE
                and len(candidates) == 1
                and re.search(
                r"\b(as hot as|roughly (?:that|the temperature) of|same temperature as)\b",
                normalized,
                )
            ):
                return candidates[0], candidates[0]
    return None


def _measure_candidates(
    sentence: str,
    evidence_id: UUID,
    dimension: NumericDimension,
) -> tuple[_Candidate, ...]:
    if dimension is NumericDimension.TEMPERATURE:
        pattern = _TEMPERATURE_PATTERN
    elif dimension is NumericDimension.DURATION:
        pattern = _DURATION_PATTERN
    elif dimension is NumericDimension.DISTANCE:
        pattern = _DISTANCE_PATTERN
    elif dimension is NumericDimension.MASS:
        pattern = _MASS_PATTERN
    elif dimension is NumericDimension.PERCENTAGE:
        pattern = _PERCENTAGE_PATTERN
    elif dimension is NumericDimension.PRESSURE:
        pattern = _PRESSURE_PATTERN
    elif dimension is NumericDimension.SPEED:
        pattern = _SPEED_PATTERN
    elif dimension is NumericDimension.COUNT:
        pattern = _COUNT_PATTERN
    elif dimension is NumericDimension.CURRENCY:
        return _currency_candidates(sentence, evidence_id)
    else:
        return ()
    candidates: list[_Candidate] = []
    for match in pattern.finditer(sentence):
        try:
            value = Decimal(match.group("value").replace(",", ""))
        except InvalidOperation:
            continue
        unit_code = match.group("unit").casefold()
        unit = _canonical_unit(unit_code, dimension)
        candidates.append(
            _Candidate(
                evidence_id=evidence_id,
                value=NormalizedNumericValue(
                    value=value,
                    unit=unit,
                    dimension=dimension,
                ),
                sentence=sentence,
            )
        )
    return tuple(candidates)


def _canonical_unit(value: str, dimension: NumericDimension) -> str:
    if dimension is NumericDimension.TEMPERATURE:
        return {"c": "celsius", "f": "fahrenheit", "k": "kelvin"}[value]
    aliases = {
        "year": "year_julian",
        "years": "year_julian",
        "day": "day",
        "days": "day",
        "hour": "hour",
        "hours": "hour",
        "kilometre": "kilometre",
        "kilometres": "kilometre",
        "kilometer": "kilometre",
        "kilometers": "kilometre",
        "km": "kilometre",
        "metre": "metre",
        "metres": "metre",
        "meter": "metre",
        "meters": "metre",
        "m": "metre",
        "kilogram": "kilogram",
        "kilograms": "kilogram",
        "kg": "kilogram",
        "gram": "gram",
        "grams": "gram",
        "g": "gram",
        "%": "percent",
        "percent": "percent",
        "percentage": "percent",
        "percentage point": "percentage_point",
        "percentage points": "percentage_point",
        "kilopascal": "kilopascal",
        "kilopascals": "kilopascal",
        "kpa": "kilopascal",
        "pascal": "pascal",
        "pascals": "pascal",
        "pa": "pascal",
        "atmosphere": "atmosphere",
        "atmospheres": "atmosphere",
        "atm": "atmosphere",
        "kilometre per hour": "kilometre_per_hour",
        "kilometres per hour": "kilometre_per_hour",
        "kilometer per hour": "kilometre_per_hour",
        "kilometers per hour": "kilometre_per_hour",
        "km/h": "kilometre_per_hour",
        "metre per second": "metre_per_second",
        "metres per second": "metre_per_second",
        "meter per second": "metre_per_second",
        "meters per second": "metre_per_second",
        "m/s": "metre_per_second",
        "mile per hour": "mile_per_hour",
        "miles per hour": "mile_per_hour",
        "mph": "mile_per_hour",
        "person": "person",
        "persons": "person",
        "people": "person",
        "item": "item",
        "items": "item",
        "case": "case",
        "cases": "case",
        "member": "member",
        "members": "member",
        "vote": "vote",
        "votes": "vote",
        "unit": "unit",
        "units": "unit",
    }
    return aliases[value]


def _currency_candidates(
    sentence: str,
    evidence_id: UUID,
) -> tuple[_Candidate, ...]:
    matches = [
        *(
            (match.start(), match.group("value"), match.group("unit"))
            for match in _CURRENCY_PREFIX_PATTERN.finditer(sentence)
        ),
        *(
            (match.start(), match.group("value"), match.group("unit"))
            for match in _CURRENCY_SUFFIX_PATTERN.finditer(sentence)
        ),
    ]
    aliases = {
        "$": "USD",
        "usd": "USD",
        "dollar": "USD",
        "dollars": "USD",
        "€": "EUR",
        "eur": "EUR",
        "euro": "EUR",
        "euros": "EUR",
        "£": "GBP",
        "gbp": "GBP",
        "pound": "GBP",
        "pounds": "GBP",
    }
    candidates = []
    for _, raw_value, raw_unit in sorted(matches):
        candidates.append(
            _Candidate(
                evidence_id=evidence_id,
                value=NormalizedNumericValue(
                    value=Decimal(raw_value.replace(",", "")),
                    unit=aliases[raw_unit.casefold()],
                    dimension=NumericDimension.CURRENCY,
                ),
                sentence=sentence,
            )
        )
    return tuple(candidates)


def _subject_terms(value: str) -> tuple[str, ...]:
    terms = re.findall(r"[a-z]+", value.casefold().replace("'s", ""))
    meaningful = tuple(term for term in terms if term not in _STOPWORDS and len(term) > 2)
    return meaningful or tuple(terms)


def _mentions(sentence: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", sentence) for term in terms)


def _sentences(value: str) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", " ", value)
    return tuple(
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    )


def _failed(
    *,
    construction_id: UUID,
    claim: AtomicClaim,
    left: str,
    right: str,
    compared_property: str,
    comparator: NumericComparator,
    dimension: NumericDimension,
    code: str,
    message: str,
    action: str,
) -> tuple[
    ComparativeAssertionConstruction,
    None,
    VerificationIssueFinding,
]:
    construction = ComparativeAssertionConstruction(
        construction_id=construction_id,
        claim_id=claim.claim_id,
        claim_text_span=claim.text,
        left_subject=left,
        right_subject=right,
        compared_property=compared_property,
        comparator=comparator,
        dimension=dimension,
        state=AssertionConstructionState.FAILED,
        failure_code=code,
        explanation=message,
    )
    finding = VerificationIssueFinding(
        code=code,
        severity=VerificationIssueSeverity.BLOCKING,
        message=message,
        recommended_action=action,
        readiness_impact=VerificationReadinessImpact.HUMAN_REVIEW,
    )
    return construction, None, finding
