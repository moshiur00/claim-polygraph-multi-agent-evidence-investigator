"""Contract tests for assertion-level Phase 6 verification artifacts."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    AssertionConstructionState,
    AssertionVerificationState,
    ComparativeAssertionConstruction,
    ContextValueObservation,
    ContextValueOrigin,
    ContextVerification,
    DatePrecision,
    NormalizedNumericValue,
    NumericalAssertionVerification,
    NumericalContextCheck,
    NumericComparator,
    NumericDimension,
    NumericOperation,
    TemporalAssertionVerification,
    TemporalContextCheck,
    TemporalEvidenceObservation,
    TemporalInstant,
    TemporalInterval,
    TemporalRelation,
    VerificationIssueFinding,
    VerificationIssueSeverity,
    VerificationPacketV2,
    VerificationReadinessImpact,
    VerificationStatus,
)


def test_verification_packet_round_trips_exact_decimals_and_dates() -> None:
    claim_id, numerical_evidence, temporal_evidence = uuid4(), uuid4(), uuid4()
    packet = VerificationPacketV2(
        claim_id=claim_id,
        approved_evidence_ids=(numerical_evidence, temporal_evidence),
        numerical_assertions=(
            NumericalAssertionVerification(
                claim_id=claim_id,
                claim_text_span="increased by 10 percent",
                comparator=NumericComparator.EQUAL,
                operation=NumericOperation.PERCENTAGE_CHANGE,
                expected_values=(
                    NormalizedNumericValue(
                        value=Decimal("10.0"),
                        unit="percent",
                        dimension=NumericDimension.PERCENTAGE,
                    ),
                ),
                evidence_ids=(numerical_evidence,),
                state=AssertionVerificationState.VERIFIED,
                normalized_result=NormalizedNumericValue(
                    value=Decimal("10.0"),
                    unit="percent",
                    dimension=NumericDimension.PERCENTAGE,
                ),
                expression="(110 - 100) / 100 * 100",
            ),
        ),
        temporal_assertions=(
            TemporalAssertionVerification(
                claim_id=claim_id,
                claim_text_span="remained active during 2025",
                relation=TemporalRelation.ACTIVE,
                reference_date=TemporalInstant(
                    value=date(2025, 12, 31),
                    precision=DatePrecision.DAY,
                ),
                claimed_interval=TemporalInterval(
                    start=TemporalInstant(
                        value=date(2025, 1, 1),
                        precision=DatePrecision.YEAR,
                    ),
                    end=TemporalInstant(
                        value=date(2025, 12, 31),
                        precision=DatePrecision.YEAR,
                    ),
                ),
                observations=(
                    TemporalEvidenceObservation(
                        evidence_id=temporal_evidence,
                        publication_date=TemporalInstant(
                            value=date(2026, 1, 10),
                            precision=DatePrecision.DAY,
                        ),
                        observed_status="The designation remained active throughout 2025.",
                        retrospective=True,
                    ),
                ),
                state=AssertionVerificationState.VERIFIED,
            ),
        ),
    )

    restored = VerificationPacketV2.model_validate_json(packet.model_dump_json())

    assert restored == packet
    assert restored.numerical_assertions[0].expected_values[0].value == Decimal("10.0")


def test_packet_rejects_evidence_outside_approved_set() -> None:
    claim_id = uuid4()
    assertion = NumericalAssertionVerification(
        claim_id=claim_id,
        claim_text_span="exactly 42",
        comparator=NumericComparator.EQUAL,
        expected_values=(NormalizedNumericValue(value=Decimal("42")),),
        evidence_ids=(uuid4(),),
        state=AssertionVerificationState.VERIFIED,
        normalized_result=NormalizedNumericValue(value=Decimal("42")),
    )

    with pytest.raises(ValidationError, match="approved evidence"):
        VerificationPacketV2(
            claim_id=claim_id,
            approved_evidence_ids=(),
            numerical_assertions=(assertion,),
        )


def test_packet_rejects_cross_claim_and_duplicate_approved_references() -> None:
    evidence_id = uuid4()
    assertion = NumericalAssertionVerification(
        claim_id=uuid4(),
        claim_text_span="equals 42",
        comparator=NumericComparator.EQUAL,
        expected_values=(NormalizedNumericValue(value=Decimal("42")),),
        state=AssertionVerificationState.INSUFFICIENT,
        issues=("No evidence value was normalized.",),
    )

    with pytest.raises(ValidationError, match="packet claim"):
        VerificationPacketV2(
            claim_id=uuid4(),
            approved_evidence_ids=(evidence_id,),
            numerical_assertions=(assertion,),
        )

    with pytest.raises(ValidationError, match="must be unique"):
        VerificationPacketV2(
            claim_id=uuid4(),
            approved_evidence_ids=(evidence_id, evidence_id),
        )


def test_range_requires_two_values_and_resolved_state_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="requires 2 expected"):
        NumericalAssertionVerification(
            claim_id=uuid4(),
            claim_text_span="between 1 and 2",
            comparator=NumericComparator.BETWEEN_INCLUSIVE,
            expected_values=(NormalizedNumericValue(value=Decimal("1")),),
            state=AssertionVerificationState.INSUFFICIENT,
            issues=("The upper endpoint is unavailable.",),
        )

    with pytest.raises(ValidationError, match="require approved evidence"):
        NumericalAssertionVerification(
            claim_id=uuid4(),
            claim_text_span="equals 1",
            comparator=NumericComparator.EQUAL,
            expected_values=(NormalizedNumericValue(value=Decimal("1")),),
            state=AssertionVerificationState.VERIFIED,
            normalized_result=NormalizedNumericValue(value=Decimal("1")),
        )


def test_calculated_assertion_requires_expression_and_errors_require_issues() -> None:
    with pytest.raises(ValidationError, match="require an expression"):
        NumericalAssertionVerification(
            claim_id=uuid4(),
            claim_text_span="increased by 10 percent",
            comparator=NumericComparator.EQUAL,
            operation=NumericOperation.PERCENTAGE_CHANGE,
            expected_values=(
                NormalizedNumericValue(
                    value=Decimal("10"),
                    unit="percent",
                    dimension=NumericDimension.PERCENTAGE,
                ),
            ),
            state=AssertionVerificationState.INSUFFICIENT,
            issues=("Operands are unavailable.",),
        )

    with pytest.raises(ValidationError, match="require an issue"):
        TemporalAssertionVerification(
            claim_id=uuid4(),
            claim_text_span="was active",
            relation=TemporalRelation.ACTIVE,
            state=AssertionVerificationState.ERROR,
        )


def test_unknown_dimension_and_missing_reference_date_fail_closed() -> None:
    with pytest.raises(ValidationError, match="unknown numerical dimensions"):
        NumericalAssertionVerification(
            claim_id=uuid4(),
            claim_text_span="is 3 mystery units",
            comparator=NumericComparator.EQUAL,
            expected_values=(
                NormalizedNumericValue(
                    value=Decimal("3"),
                    unit="mystery",
                    dimension=NumericDimension.UNKNOWN,
                ),
            ),
            evidence_ids=(uuid4(),),
            state=AssertionVerificationState.VERIFIED,
            normalized_result=NormalizedNumericValue(
                value=Decimal("3"),
                unit="mystery",
                dimension=NumericDimension.UNKNOWN,
            ),
        )

    with pytest.raises(ValidationError, match="missing required reference date"):
        TemporalAssertionVerification(
            claim_id=uuid4(),
            claim_text_span="is currently active",
            relation=TemporalRelation.ACTIVE,
            requires_reference_date=True,
            observations=(
                TemporalEvidenceObservation(
                    evidence_id=uuid4(),
                    observed_status="Active.",
                ),
            ),
            state=AssertionVerificationState.VERIFIED,
        )


def test_invalid_intervals_and_empty_temporal_observations_are_rejected() -> None:
    with pytest.raises(ValidationError, match="start cannot follow"):
        TemporalInterval(
            start=TemporalInstant(value=date(2026, 1, 2), precision=DatePrecision.DAY),
            end=TemporalInstant(value=date(2026, 1, 1), precision=DatePrecision.DAY),
        )

    with pytest.raises(ValidationError, match="must contain"):
        TemporalEvidenceObservation(evidence_id=uuid4())


def test_legacy_context_verification_payload_remains_unchanged() -> None:
    claim_id = uuid4()
    old_payload = {
        "claim_id": str(claim_id),
        "numerical": {
            "required": True,
            "status": "qualified",
            "claim_values": ["100"],
            "evidence_values": ["99.974"],
            "claim_units": ["celsius"],
            "evidence_units": ["celsius"],
            "exactness_terms": [],
            "issues": ["Scale convention differs."],
        },
        "temporal": {
            "required": False,
            "status": "not_required",
            "reference_date": None,
            "source_publication_dates": [],
            "issues": [],
        },
        "limitations": ["Legacy bounded check."],
    }

    restored = ContextVerification.model_validate(old_payload)

    assert restored.claim_id == claim_id
    assert restored.numerical == NumericalContextCheck(
        required=True,
        status=VerificationStatus.QUALIFIED,
        claim_values=("100",),
        evidence_values=("99.974",),
        claim_units=("celsius",),
        evidence_units=("celsius",),
        issues=("Scale convention differs.",),
    )
    assert restored.temporal == TemporalContextCheck(
        required=False,
        status=VerificationStatus.NOT_REQUIRED,
    )


def test_typed_findings_and_value_provenance_round_trip_without_breaking_v2() -> None:
    claim_id, source_id, evidence_id = uuid4(), uuid4(), uuid4()
    finding = VerificationIssueFinding(
        code="typed_operand_missing",
        severity=VerificationIssueSeverity.BLOCKING,
        message="The value is not bound to an approved typed operand.",
        recommended_action="Bind the value and unit to the exact evidence passage.",
        readiness_impact=VerificationReadinessImpact.HUMAN_REVIEW,
        evidence_ids=(evidence_id,),
    )
    context = ContextVerification(
        claim_id=claim_id,
        numerical=NumericalContextCheck(
            required=True,
            status=VerificationStatus.INSUFFICIENT,
            evidence_observations=(
                ContextValueObservation(
                    raw_text="41.8",
                    normalized_text="41.8",
                    origin=ContextValueOrigin.EVIDENCE,
                    evidence_id=evidence_id,
                    source_id=source_id,
                    start_char=10,
                    end_char=14,
                    unit_hint="percent",
                ),
            ),
            findings=(finding,),
        ),
        temporal=TemporalContextCheck(
            required=False,
            status=VerificationStatus.NOT_REQUIRED,
        ),
    )
    packet = VerificationPacketV2(
        claim_id=claim_id,
        approved_evidence_ids=(evidence_id,),
        findings=(finding,),
    )

    assert ContextVerification.model_validate_json(context.model_dump_json()) == context
    assert VerificationPacketV2.model_validate_json(packet.model_dump_json()) == packet


def test_legacy_absolute_wording_finding_migrates_to_scope_review() -> None:
    claim_id = uuid4()
    payload = {
        "claim_id": str(claim_id),
        "numerical": {
            "required": False,
            "status": "qualified",
            "exactness_terms": ["all"],
            "issues": ["Absolute wording requires explicit verification: all."],
            "findings": [
                {
                    "code": "absolute_wording_requires_verification",
                    "severity": "caution",
                    "message": "Absolute wording requires explicit verification: all.",
                    "recommended_action": "Review or narrow the universal wording.",
                    "readiness_impact": "readiness_signal",
                    "evidence_ids": [],
                }
            ],
        },
        "temporal": {"required": False, "status": "not_required"},
    }

    restored = ContextVerification.model_validate(payload)

    assert restored.numerical.status is VerificationStatus.NOT_REQUIRED
    assert restored.numerical.findings == ()
    assert restored.numerical.issues == ()
    assert restored.scope_findings[0].code == "absolute_wording_requires_verification"


def test_packet_rejects_finding_evidence_outside_approved_set() -> None:
    with pytest.raises(ValidationError, match="approved evidence"):
        VerificationPacketV2(
            claim_id=uuid4(),
            approved_evidence_ids=(),
            findings=(
                VerificationIssueFinding(
                    code="outside_packet",
                    severity=VerificationIssueSeverity.CAUTION,
                    message="The finding points to an unavailable record.",
                    recommended_action="Use evidence from the approved packet.",
                    evidence_ids=(uuid4(),),
                ),
            ),
        )


def test_comparative_construction_round_trips_and_is_evidence_bounded() -> None:
    claim_id, evidence_id, assertion_id = uuid4(), uuid4(), uuid4()
    construction = ComparativeAssertionConstruction(
        claim_id=claim_id,
        claim_text_span="A is hotter than B.",
        left_subject="A",
        right_subject="B",
        compared_property="temperature",
        comparator=NumericComparator.GREATER_THAN,
        dimension=NumericDimension.TEMPERATURE,
        state=AssertionConstructionState.CONSTRUCTED,
        assertion_id=assertion_id,
        evidence_ids=(evidence_id,),
        explanation="Both operands were bound in one approved passage.",
    )
    packet = VerificationPacketV2(
        claim_id=claim_id,
        approved_evidence_ids=(evidence_id,),
        comparative_constructions=(construction,),
    )

    restored = VerificationPacketV2.model_validate_json(packet.model_dump_json())
    assert restored.comparative_constructions == (construction,)

    with pytest.raises(ValidationError, match="approved evidence"):
        VerificationPacketV2(
            claim_id=claim_id,
            approved_evidence_ids=(),
            comparative_constructions=(construction,),
        )
