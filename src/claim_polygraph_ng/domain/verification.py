"""Deterministic temporal and numerical verification contracts."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class VerificationStatus(StrEnum):
    """Outcome of a bounded context check."""

    NOT_REQUIRED = "not_required"
    PASSED = "passed"
    QUALIFIED = "qualified"
    INSUFFICIENT = "insufficient"


class NumericalContextCheck(DomainModel):
    required: bool
    status: VerificationStatus
    claim_values: tuple[str, ...] = ()
    evidence_values: tuple[str, ...] = ()
    claim_units: tuple[str, ...] = ()
    evidence_units: tuple[str, ...] = ()
    exactness_terms: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


class TemporalContextCheck(DomainModel):
    required: bool
    status: VerificationStatus
    reference_date: date | None = None
    source_publication_dates: tuple[date, ...] = ()
    issues: tuple[str, ...] = ()


class ContextVerification(DomainModel):
    """Combined context checks passed to judgment and reporting."""

    claim_id: UUID
    numerical: NumericalContextCheck
    temporal: TemporalContextCheck
    limitations: tuple[str, ...] = ()


class AssertionVerificationState(StrEnum):
    """Outcome of one assertion-level verification."""

    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    QUALIFIED = "qualified"
    INSUFFICIENT = "insufficient"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


class NumericComparator(StrEnum):
    """Explicit numerical relationship asserted by a claim."""

    EQUAL = "equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    BETWEEN_INCLUSIVE = "between_inclusive"
    BETWEEN_EXCLUSIVE = "between_exclusive"


class NumericOperation(StrEnum):
    """Allowlisted operation requested of the later numerical verifier."""

    DIRECT = "direct"
    SUM = "sum"
    DIFFERENCE = "difference"
    RATIO = "ratio"
    PERCENTAGE_CHANGE = "percentage_change"
    PERCENTAGE_POINT_CHANGE = "percentage_point_change"
    RANK = "rank"


class NumericDimension(StrEnum):
    """Small dimension vocabulary; unsupported dimensions remain explicit."""

    DIMENSIONLESS = "dimensionless"
    COUNT = "count"
    CURRENCY = "currency"
    DISTANCE = "distance"
    DURATION = "duration"
    MASS = "mass"
    PERCENTAGE = "percentage"
    PRESSURE = "pressure"
    TEMPERATURE = "temperature"
    UNKNOWN = "unknown"


class NormalizedNumericValue(DomainModel):
    """An exact decimal value with explicit scale, unit, and uncertainty."""

    value: Decimal
    unit: str | None = Field(default=None, min_length=1, max_length=100)
    dimension: NumericDimension = NumericDimension.DIMENSIONLESS
    scale: Decimal = Field(default=Decimal("1"), gt=0)
    tolerance: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_unit_and_dimension(self) -> "NormalizedNumericValue":
        if self.unit is None and self.dimension not in {
            NumericDimension.DIMENSIONLESS,
            NumericDimension.COUNT,
            NumericDimension.UNKNOWN,
        }:
            raise ValueError("dimensioned values require an explicit unit")
        if self.unit is not None and self.dimension is NumericDimension.DIMENSIONLESS:
            raise ValueError("a unit requires a non-dimensionless dimension")
        return self


class NumericalAssertionVerification(DomainModel):
    """One numerical claim assertion and its evidence-grounded result."""

    assertion_id: UUID = Field(default_factory=uuid4)
    claim_id: UUID
    claim_text_span: str = Field(min_length=1, max_length=2_000)
    comparator: NumericComparator
    operation: NumericOperation = NumericOperation.DIRECT
    expected_values: tuple[NormalizedNumericValue, ...] = Field(min_length=1, max_length=2)
    evidence_ids: tuple[UUID, ...] = ()
    state: AssertionVerificationState
    normalized_result: NormalizedNumericValue | None = None
    expression: str | None = Field(default=None, max_length=2_000)
    rounding_rule: str | None = Field(default=None, max_length=1_000)
    issues: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_numerical_resolution(self) -> "NumericalAssertionVerification":
        range_comparators = {
            NumericComparator.BETWEEN_INCLUSIVE,
            NumericComparator.BETWEEN_EXCLUSIVE,
        }
        expected_count = 2 if self.comparator in range_comparators else 1
        if len(self.expected_values) != expected_count:
            raise ValueError(f"{self.comparator.value} requires {expected_count} expected value(s)")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("numerical evidence IDs must be unique")
        resolved = {
            AssertionVerificationState.VERIFIED,
            AssertionVerificationState.CONTRADICTED,
            AssertionVerificationState.QUALIFIED,
        }
        if self.state in resolved and not self.evidence_ids:
            raise ValueError("resolved numerical assertions require approved evidence")
        if self.state in resolved and self.normalized_result is None:
            raise ValueError("resolved numerical assertions require a normalized result")
        if self.operation is not NumericOperation.DIRECT and not self.expression:
            raise ValueError("calculated numerical assertions require an expression")
        if self.state in {
            AssertionVerificationState.INSUFFICIENT,
            AssertionVerificationState.ERROR,
        } and not self.issues:
            raise ValueError("insufficient or error states require an issue")
        if any(
            item.dimension is NumericDimension.UNKNOWN for item in self.expected_values
        ) and self.state in resolved:
            raise ValueError("unknown numerical dimensions cannot be marked resolved")
        return self


class DatePrecision(StrEnum):
    """Precision actually supplied by a source or claim."""

    YEAR = "year"
    MONTH = "month"
    DAY = "day"


class TemporalInstant(DomainModel):
    """One date with explicit precision rather than invented day accuracy."""

    value: date
    precision: DatePrecision


class TemporalInterval(DomainModel):
    """A bounded or open date interval."""

    start: TemporalInstant | None = None
    end: TemporalInstant | None = None
    start_inclusive: bool = True
    end_inclusive: bool = True

    @model_validator(mode="after")
    def validate_interval(self) -> "TemporalInterval":
        if self.start is None and self.end is None:
            raise ValueError("a temporal interval requires a start or end")
        if self.start and self.end and self.start.value > self.end.value:
            raise ValueError("temporal interval start cannot follow its end")
        return self


class TemporalRelation(StrEnum):
    """Time relationship asserted by a claim."""

    BEFORE = "before"
    AFTER = "after"
    ON = "on"
    DURING = "during"
    STARTED = "started"
    ENDED = "ended"
    ACTIVE = "active"
    CHANGED_STATUS = "changed_status"


class TemporalEvidenceObservation(DomainModel):
    """Dated observation from one approved evidence passage."""

    evidence_id: UUID
    publication_date: TemporalInstant | None = None
    effective_interval: TemporalInterval | None = None
    observed_status: str | None = Field(default=None, min_length=1, max_length=1_000)
    retrospective: bool = False

    @model_validator(mode="after")
    def require_temporal_observation(self) -> "TemporalEvidenceObservation":
        if (
            self.publication_date is None
            and self.effective_interval is None
            and self.observed_status is None
        ):
            raise ValueError("temporal evidence must contain a date, interval, or status")
        return self


class TemporalAssertionVerification(DomainModel):
    """One time-sensitive assertion and its evidence-grounded result."""

    assertion_id: UUID = Field(default_factory=uuid4)
    claim_id: UUID
    claim_text_span: str = Field(min_length=1, max_length=2_000)
    relation: TemporalRelation
    reference_date: TemporalInstant | None = None
    claimed_interval: TemporalInterval | None = None
    requires_reference_date: bool = False
    observations: tuple[TemporalEvidenceObservation, ...] = ()
    state: AssertionVerificationState
    issues: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_temporal_resolution(self) -> "TemporalAssertionVerification":
        if (
            self.requires_reference_date
            and self.reference_date is None
            and self.state
            not in {
                AssertionVerificationState.INSUFFICIENT,
                AssertionVerificationState.ERROR,
            }
        ):
            raise ValueError("a missing required reference date cannot be resolved")
        evidence_ids = [item.evidence_id for item in self.observations]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("temporal evidence observations must be unique by evidence ID")
        resolved = {
            AssertionVerificationState.VERIFIED,
            AssertionVerificationState.CONTRADICTED,
            AssertionVerificationState.QUALIFIED,
        }
        if self.state in resolved and not self.observations:
            raise ValueError("resolved temporal assertions require approved evidence")
        if self.state in {
            AssertionVerificationState.INSUFFICIENT,
            AssertionVerificationState.ERROR,
        } and not self.issues:
            raise ValueError("insufficient or error states require an issue")
        return self


class VerificationPacketV2(DomainModel):
    """Assertion-level packet introduced alongside the legacy context check."""

    claim_id: UUID
    verification_version: str = Field(
        default="verification-packet-v2",
        pattern=r"^verification-packet-v2$",
    )
    approved_evidence_ids: tuple[UUID, ...] = ()
    numerical_assertions: tuple[NumericalAssertionVerification, ...] = ()
    temporal_assertions: tuple[TemporalAssertionVerification, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_packet_references(self) -> "VerificationPacketV2":
        if len(set(self.approved_evidence_ids)) != len(self.approved_evidence_ids):
            raise ValueError("approved evidence IDs must be unique")
        assertions = (*self.numerical_assertions, *self.temporal_assertions)
        if len({item.assertion_id for item in assertions}) != len(assertions):
            raise ValueError("assertion IDs must be unique within a verification packet")
        if any(item.claim_id != self.claim_id for item in assertions):
            raise ValueError("all assertions must reference the packet claim")
        referenced = {
            evidence_id
            for item in self.numerical_assertions
            for evidence_id in item.evidence_ids
        }
        referenced.update(
            observation.evidence_id
            for item in self.temporal_assertions
            for observation in item.observations
        )
        if not referenced.issubset(self.approved_evidence_ids):
            raise ValueError("assertions may reference only approved evidence IDs")
        return self
