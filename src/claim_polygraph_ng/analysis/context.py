"""Bounded deterministic checks for numerical and temporal context."""

import re

from claim_polygraph_ng.analysis.comparative_verification import (
    is_qualitative_comparison,
)
from claim_polygraph_ng.analysis.temporal_construction import (
    is_temporal_comparison,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    ContextValueObservation,
    ContextValueOrigin,
    ContextVerification,
    Evidence,
    InvestigationPlan,
    NumericalContextCheck,
    Source,
    TemporalContextCheck,
    VerificationIssueFinding,
    VerificationIssueSeverity,
    VerificationReadinessImpact,
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
    declared_quantity_values = {
        number
        for quantity in claim.quantities
        for number in _values(quantity)
    }
    claim_values = _values(claim.text) | declared_quantity_values
    evidence_values = _values(evidence_text)
    claim_observations = list(
        _value_observations(claim.text, origin=ContextValueOrigin.CLAIM)
    )
    observed_claim_values = {item.normalized_text for item in claim_observations}
    claim_observations.extend(
        ContextValueObservation(
            raw_text=value,
            normalized_text=value.replace(",", "."),
            origin=ContextValueOrigin.CLAIM,
        )
        for value in sorted(declared_quantity_values - observed_claim_values)
    )
    evidence_observations = tuple(
        observation
        for item in evidence
        for observation in _value_observations(
            item.passage,
            origin=ContextValueOrigin.EVIDENCE,
            evidence_id=item.evidence_id,
            source_id=item.source_id,
        )
    )
    claim_units = _units(claim.text)
    evidence_units = _units(evidence_text)
    exactness = tuple(sorted(set(_EXACTNESS_PATTERN.findall(claim.text.casefold()))))
    numerical_required = plan.requires_numerical_check or bool(claim_values)
    numerical_issues: list[str] = []
    numerical_findings: list[VerificationIssueFinding] = []
    scope_findings: list[VerificationIssueFinding] = []
    if numerical_required and not claim_values and not is_qualitative_comparison(claim.text):
        issue = "No explicit numerical value was extracted from the claim."
        numerical_issues.append(issue)
        numerical_findings.append(
            _finding(
                "claim_value_missing",
                issue,
                "Identify the exact claimed value, unit, and comparison before verification.",
                severity=VerificationIssueSeverity.BLOCKING,
                impact=VerificationReadinessImpact.HUMAN_REVIEW,
            )
        )
    if numerical_required and not evidence_values:
        issue = "Evidence passages contain no explicit numerical values."
        numerical_issues.append(issue)
        numerical_findings.append(
            _finding(
                "evidence_value_missing",
                issue,
                "Retrieve an approved passage containing the value and unit required by the claim.",
                severity=VerificationIssueSeverity.BLOCKING,
                impact=VerificationReadinessImpact.HUMAN_REVIEW,
            )
        )
    if claim_values and not claim_values.intersection(evidence_values):
        issue = "No claim value appears verbatim in the evidence passages."
        numerical_issues.append(issue)
        numerical_findings.append(
            _finding(
                "claim_evidence_value_mismatch",
                issue,
                (
                    "Normalize compatible values and units or obtain direct evidence "
                    "for the claimed value."
                ),
                severity=VerificationIssueSeverity.CAUTION,
                impact=VerificationReadinessImpact.HUMAN_REVIEW,
                evidence_ids=tuple(item.evidence_id for item in evidence),
            )
        )
    missing_units = claim_units - evidence_units
    if missing_units:
        issue = "Evidence does not repeat claim units: " + ", ".join(sorted(missing_units)) + "."
        numerical_issues.append(issue)
        numerical_findings.append(
            _finding(
                "claim_unit_missing_from_evidence",
                issue,
                (
                    "Confirm compatible dimensions and perform an allowlisted unit "
                    "conversion if appropriate."
                ),
                severity=VerificationIssueSeverity.CAUTION,
                impact=VerificationReadinessImpact.HUMAN_REVIEW,
                evidence_ids=tuple(item.evidence_id for item in evidence),
            )
        )
    if exactness:
        issue = "Universal wording requires a claim-scope review: " + ", ".join(exactness) + "."
        scope_findings.append(
            _finding(
                "absolute_wording_requires_verification",
                issue,
                "Review the universal wording against eligible evidence, or narrow the claim.",
                severity=VerificationIssueSeverity.CAUTION,
                impact=VerificationReadinessImpact.READINESS_SIGNAL,
            )
        )
    numerical_status = _status(
        numerical_required,
        numerical_issues,
        has_evidence=bool(claim_values and evidence_values),
    )

    reference_date = claim.reference_date
    temporal_required = plan.requires_temporal_check or bool(
        reference_date
        or _CURRENT_PATTERN.search(claim.text)
        or is_temporal_comparison(claim.text)
    )
    publication_dates = tuple(
        sorted(source.publication_date for source in sources if source.publication_date is not None)
    )
    temporal_issues: list[str] = []
    temporal_findings: list[VerificationIssueFinding] = []
    if (
        temporal_required
        and reference_date is None
        and not is_temporal_comparison(claim.text)
    ):
        issue = "Time-sensitive wording has no explicit reference date."
        temporal_issues.append(issue)
        temporal_findings.append(
            _finding(
                "reference_date_missing",
                issue,
                "Specify the date at which the claimed status should be evaluated.",
                severity=VerificationIssueSeverity.BLOCKING,
                impact=VerificationReadinessImpact.HUMAN_REVIEW,
            )
        )
    if temporal_required and not publication_dates:
        issue = "Retrieved sources provide no publication dates."
        temporal_issues.append(issue)
        temporal_findings.append(
            _finding(
                "source_dates_missing",
                issue,
                "Retrieve dated evidence and distinguish publication dates from effective dates.",
                severity=VerificationIssueSeverity.BLOCKING,
                impact=VerificationReadinessImpact.HUMAN_REVIEW,
                evidence_ids=tuple(item.evidence_id for item in evidence),
            )
        )
    if reference_date is not None:
        postdated = tuple(value for value in publication_dates if value > reference_date)
        if postdated:
            issue = (
                "Some sources postdate the claim reference date: "
                + ", ".join(value.isoformat() for value in postdated)
                + "."
            )
            temporal_issues.append(issue)
            temporal_findings.append(
                _finding(
                    "source_postdates_reference",
                    issue,
                    (
                        "Confirm the source is explicitly retrospective before using it "
                        "for the earlier date."
                    ),
                    severity=VerificationIssueSeverity.CAUTION,
                    impact=VerificationReadinessImpact.HUMAN_REVIEW,
                    evidence_ids=tuple(item.evidence_id for item in evidence),
                )
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
            claim_observations=tuple(claim_observations),
            evidence_observations=evidence_observations,
            findings=tuple(numerical_findings),
        ),
        temporal=TemporalContextCheck(
            required=temporal_required,
            status=temporal_status,
            reference_date=reference_date,
            source_publication_dates=publication_dates,
            issues=tuple(temporal_issues),
            findings=tuple(temporal_findings),
        ),
        scope_findings=tuple(scope_findings),
        limitations=(
            "Checks compare explicit strings and source metadata; they do not perform unit "
            "conversion, statistical validation, or historical database lookup.",
            "A qualified result is a review signal, not proof that the claim is false.",
        ),
    )


def _values(value: str) -> set[str]:
    return {match.group(0).replace(",", ".") for match in _NUMBER_PATTERN.finditer(value)}


def _value_observations(
    value: str,
    *,
    origin: ContextValueOrigin,
    evidence_id=None,
    source_id=None,
) -> tuple[ContextValueObservation, ...]:
    units = tuple(sorted(_units(value)))
    unit_hint = units[0] if len(units) == 1 else None
    return tuple(
        ContextValueObservation(
            raw_text=match.group(0),
            normalized_text=match.group(0).replace(",", "."),
            origin=origin,
            evidence_id=evidence_id,
            source_id=source_id,
            start_char=match.start(),
            end_char=match.end(),
            unit_hint=unit_hint,
        )
        for match in _NUMBER_PATTERN.finditer(value)
    )


def _finding(
    code: str,
    message: str,
    recommended_action: str,
    *,
    severity: VerificationIssueSeverity,
    impact: VerificationReadinessImpact,
    evidence_ids=(),
) -> VerificationIssueFinding:
    return VerificationIssueFinding(
        code=code,
        severity=severity,
        message=message,
        recommended_action=recommended_action,
        readiness_impact=impact,
        evidence_ids=tuple(dict.fromkeys(evidence_ids)),
    )


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
