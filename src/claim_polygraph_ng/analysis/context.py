"""Bounded deterministic checks for numerical and temporal context."""

import re

from claim_polygraph_ng.domain import (
    AtomicClaim,
    ContextVerification,
    Evidence,
    InvestigationPlan,
    NumericalContextCheck,
    Source,
    TemporalContextCheck,
    VerificationStatus,
)

_NUMBER_PATTERN = re.compile(r"(?<![\w-])[+-]?\d+(?:[.,]\d+)?%?")
_EXACTNESS_PATTERN = re.compile(r"\b(exactly|every|always|all|never|only)\b", re.IGNORECASE)
_CURRENT_PATTERN = re.compile(
    r"\b(current|currently|today|now|still|as of|no longer)\b",
    re.IGNORECASE,
)
_UNITS = {
    "celsius": ("°c", "degrees c", "degree c", "celsius"),
    "days": ("day", "days"),
    "hours": ("hour", "hours"),
    "kelvin": (" kelvin", " k "),
    "kilometres": ("kilometre", "kilometres", "kilometer", "kilometers", " km"),
    "metres": ("metre", "metres", "meter", "meters"),
    "percent": ("%", "percent", "percentage"),
    "pressure": ("kpa", "pascal", "atmosphere", "atm"),
    "years": ("year", "years"),
}


def verify_claim_context(
    *,
    claim: AtomicClaim,
    plan: InvestigationPlan,
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
) -> ContextVerification:
    """Compare explicit claim context with bounded evidence metadata and passages."""
    evidence_text = "\n".join(item.passage for item in evidence)
    claim_values = _values(claim.text) | set(claim.quantities)
    evidence_values = _values(evidence_text)
    claim_units = _units(claim.text)
    evidence_units = _units(evidence_text)
    exactness = tuple(sorted(set(_EXACTNESS_PATTERN.findall(claim.text.casefold()))))
    numerical_required = plan.requires_numerical_check or bool(claim_values)
    numerical_issues: list[str] = []
    if numerical_required and not evidence_values:
        numerical_issues.append("Evidence passages contain no explicit numerical values.")
    if claim_values and not claim_values.intersection(evidence_values):
        numerical_issues.append("No claim value appears verbatim in the evidence passages.")
    missing_units = claim_units - evidence_units
    if missing_units:
        numerical_issues.append(
            "Evidence does not repeat claim units: " + ", ".join(sorted(missing_units)) + "."
        )
    if exactness:
        numerical_issues.append(
            "Absolute wording requires explicit verification: " + ", ".join(exactness) + "."
        )
    numerical_status = _status(
        numerical_required,
        numerical_issues,
        has_evidence=bool(evidence_values),
    )

    reference_date = claim.reference_date
    temporal_required = plan.requires_temporal_check or bool(
        reference_date or _CURRENT_PATTERN.search(claim.text)
    )
    publication_dates = tuple(
        sorted(
            source.publication_date
            for source in sources
            if source.publication_date is not None
        )
    )
    temporal_issues: list[str] = []
    if temporal_required and reference_date is None:
        temporal_issues.append("Time-sensitive wording has no explicit reference date.")
    if temporal_required and not publication_dates:
        temporal_issues.append("Retrieved sources provide no publication dates.")
    if reference_date is not None:
        postdated = tuple(value for value in publication_dates if value > reference_date)
        if postdated:
            temporal_issues.append(
                "Some sources postdate the claim reference date: "
                + ", ".join(value.isoformat() for value in postdated)
                + "."
            )
    temporal_status = _status(
        temporal_required,
        temporal_issues,
        has_evidence=bool(publication_dates),
    )

    return ContextVerification(
        claim_id=claim.claim_id,
        numerical=NumericalContextCheck(
            required=numerical_required,
            status=numerical_status,
            claim_values=tuple(sorted(claim_values)),
            evidence_values=tuple(sorted(evidence_values)),
            claim_units=tuple(sorted(claim_units)),
            evidence_units=tuple(sorted(evidence_units)),
            exactness_terms=exactness,
            issues=tuple(numerical_issues),
        ),
        temporal=TemporalContextCheck(
            required=temporal_required,
            status=temporal_status,
            reference_date=reference_date,
            source_publication_dates=publication_dates,
            issues=tuple(temporal_issues),
        ),
        limitations=(
            "Checks compare explicit strings and source metadata; they do not perform unit "
            "conversion, statistical validation, or historical database lookup.",
            "A qualified result is a review signal, not proof that the claim is false.",
        ),
    )


def _values(value: str) -> set[str]:
    return {match.group(0).replace(",", ".") for match in _NUMBER_PATTERN.finditer(value)}


def _units(value: str) -> set[str]:
    normalized = f" {value.casefold()} "
    return {
        unit
        for unit, variants in _UNITS.items()
        if any(variant in normalized for variant in variants)
    }


def _status(
    required: bool,
    issues: list[str],
    *,
    has_evidence: bool,
) -> VerificationStatus:
    if not required:
        return VerificationStatus.NOT_REQUIRED
    if not has_evidence:
        return VerificationStatus.INSUFFICIENT
    if issues:
        return VerificationStatus.QUALIFIED
    return VerificationStatus.PASSED
