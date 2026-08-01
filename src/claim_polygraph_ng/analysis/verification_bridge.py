"""Fail-closed bridge from legacy context checks to the Phase 6 packet."""

from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.analysis.comparative_verification import (
    construct_comparative_assertion,
)
from claim_polygraph_ng.analysis.temporal_construction import (
    construct_temporal_comparison,
)
from claim_polygraph_ng.domain import (
    AssertionVerificationState,
    AtomicClaim,
    ContextVerification,
    DatePrecision,
    Evidence,
    NormalizedNumericValue,
    NumericalAssertionVerification,
    NumericComparator,
    NumericDimension,
    Source,
    TemporalAssertionVerification,
    TemporalEvidenceObservation,
    TemporalInstant,
    TemporalRelation,
    VerificationIssueFinding,
    VerificationIssueSeverity,
    VerificationPacketV2,
    VerificationReadinessImpact,
)

_UNITS = {
    "celsius": ("celsius", NumericDimension.TEMPERATURE),
    "days": ("day", NumericDimension.DURATION),
    "hours": ("hour", NumericDimension.DURATION),
    "kelvin": ("kelvin", NumericDimension.TEMPERATURE),
    "kilometres": ("kilometre", NumericDimension.DISTANCE),
    "metres": ("metre", NumericDimension.DISTANCE),
    "percent": ("percent", NumericDimension.PERCENTAGE),
    "pressure": ("kilopascal", NumericDimension.PRESSURE),
    "years": ("year_julian", NumericDimension.DURATION),
}


def bridge_legacy_verification(
    *,
    claim: AtomicClaim,
    legacy: ContextVerification,
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
) -> VerificationPacketV2:
    """Record missing typed inputs explicitly; never upgrade string checks to proof."""
    evidence_ids = tuple(dict.fromkeys(item.evidence_id for item in evidence))
    construction, comparative_assertion, comparative_finding = (
        construct_comparative_assertion(claim=claim, evidence=evidence)
    )
    temporal_construction, temporal_assertion, temporal_finding = (
        construct_temporal_comparison(claim=claim, evidence=evidence)
    )
    packet_findings = (
        *legacy.numerical.findings,
        *legacy.temporal.findings,
        *((comparative_finding,) if comparative_finding else ()),
        *((temporal_finding,) if temporal_finding else ()),
    )
    numerical = ()
    if comparative_assertion is not None:
        numerical = (comparative_assertion,)
    elif construction is None and legacy.numerical.required and legacy.numerical.claim_values:
        expected = _numeric_value(
            legacy.numerical.claim_values[0],
            legacy.numerical.claim_units[0] if legacy.numerical.claim_units else None,
        )
        if expected is not None:
            numerical = (
                NumericalAssertionVerification(
                    assertion_id=uuid5(NAMESPACE_URL, f"{claim.claim_id}/numerical/legacy"),
                    claim_id=claim.claim_id,
                    claim_text_span=claim.text,
                    comparator=NumericComparator.EQUAL,
                    expected_values=(expected,),
                    evidence_ids=evidence_ids,
                    state=AssertionVerificationState.INSUFFICIENT,
                    issues=(
                        "Legacy context provides strings, not typed evidence-bound operands.",
                    ),
                    limitations=("Stage 6 numerical verification was not guessed.",),
                    findings=(
                        *legacy.numerical.findings,
                        VerificationIssueFinding(
                            code="typed_numerical_operands_missing",
                            severity=VerificationIssueSeverity.BLOCKING,
                            message=(
                                "Legacy context provides strings, not typed "
                                "evidence-bound operands."
                            ),
                            recommended_action=(
                                "Extract typed operands with units and bind each operand to an "
                                "approved evidence passage."
                            ),
                            readiness_impact=VerificationReadinessImpact.HUMAN_REVIEW,
                            evidence_ids=evidence_ids,
                        ),
                    ),
                ),
            )
    temporal = (temporal_assertion,) if temporal_assertion is not None else ()
    if temporal_assertion is None and temporal_construction is None and legacy.temporal.required:
        publication_by_source = {
            source.source_id: source.publication_date
            for source in sources
            if source.publication_date is not None
        }
        observations = tuple(
            TemporalEvidenceObservation(
                evidence_id=item.evidence_id,
                publication_date=TemporalInstant(
                    value=publication_by_source[item.source_id],
                    precision=DatePrecision.DAY,
                ),
            )
            for item in evidence
            if item.source_id in publication_by_source
        )
        temporal = (
            TemporalAssertionVerification(
                assertion_id=uuid5(NAMESPACE_URL, f"{claim.claim_id}/temporal/legacy"),
                claim_id=claim.claim_id,
                claim_text_span=claim.text,
                relation=TemporalRelation.ACTIVE,
                reference_date=(
                    TemporalInstant(value=claim.reference_date, precision=DatePrecision.DAY)
                    if claim.reference_date
                    else None
                ),
                requires_reference_date=True,
                observations=observations,
                state=AssertionVerificationState.INSUFFICIENT,
                issues=(
                    "Legacy source dates do not establish typed effective dates or status facts.",
                ),
                limitations=("Publication dates were not treated as effective dates.",),
                findings=(
                    *legacy.temporal.findings,
                    VerificationIssueFinding(
                        code="effective_temporal_facts_missing",
                        severity=VerificationIssueSeverity.BLOCKING,
                        message=(
                            "Publication dates do not establish effective dates or status facts."
                        ),
                        recommended_action=(
                            "Retrieve approved evidence with an effective interval or explicitly "
                            "dated status observation."
                        ),
                        readiness_impact=VerificationReadinessImpact.HUMAN_REVIEW,
                        evidence_ids=tuple(item.evidence_id for item in observations),
                    ),
                ),
            ),
        )
    return VerificationPacketV2(
        claim_id=claim.claim_id,
        approved_evidence_ids=evidence_ids,
        numerical_assertions=numerical,
        temporal_assertions=temporal,
        comparative_constructions=((construction,) if construction else ()),
        temporal_constructions=(
            (temporal_construction,) if temporal_construction else ()
        ),
        limitations=(
            "Compatibility bridge is fail-closed until typed operands and temporal facts "
            "are extracted.",
        ),
        findings=packet_findings,
    )


def _numeric_value(value: str, unit_key: str | None) -> NormalizedNumericValue | None:
    try:
        parsed = Decimal(value.replace(",", ".").rstrip("%"))
    except InvalidOperation:
        return None
    unit, dimension = _UNITS.get(
        unit_key or "",
        (None, NumericDimension.DIMENSIONLESS),
    )
    return NormalizedNumericValue(value=parsed, unit=unit, dimension=dimension)
