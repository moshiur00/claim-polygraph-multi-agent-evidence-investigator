"""Strict boundary for optional model-assisted assertion construction.

The model may propose typed operands only. Deterministic code validates every
span and later performs verification; a proposal can never supply a verdict.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import Field, model_validator

from claim_polygraph_ng.analysis.candidate_extraction import (
    VerificationCandidateExtraction,
    VerificationCandidateKind,
)
from claim_polygraph_ng.domain import (
    ConstructionEligibilityPacket,
    ConstructionEligibilityRoute,
    DatePrecision,
    Evidence,
    NormalizedNumericValue,
    NumericComparator,
    NumericDimension,
    NumericOperation,
    TemporalInstant,
    TemporalInterval,
    TemporalRelation,
)
from claim_polygraph_ng.domain.base import DomainModel

ASSISTED_CONSTRUCTION_PROMPT_VERSION = "verification-construction-v4.9d-v8"
ASSISTED_CANONICALIZATION_VERSION = "assisted-canonicalization-v4.9a"
ASSISTED_TEMPORAL_WIRE_VERSION = "assisted-temporal-facts-v4.9d"


class AssistedConstructionKind(StrEnum):
    NUMERICAL = "numerical"
    NUMERICAL_SCALAR = "numerical_scalar"
    TEMPORAL_STATUS = "temporal_status"


class AssistedConstructionEligibility(StrEnum):
    NUMERICAL = "numerical"
    NUMERICAL_SCALAR = "numerical_scalar"
    NUMERICAL_RANGE = "numerical_range"
    NUMERICAL_CONVERSION = "numerical_conversion"
    TEMPORAL = "temporal"
    MISSING_REFERENCE_DATE = "missing_reference_date"
    EXCLUDED_QUALITATIVE = "excluded_qualitative"


def classify_assisted_eligibility(claim_text: str) -> AssistedConstructionEligibility:
    """Fail-closed routing before any assisted provider reservation."""
    values = _explicit_measure_tokens(claim_text)
    decimal_values = _explicit_decimal_values(claim_text)
    normalized = f" {_normalized_text(claim_text)} "
    if len(decimal_values) >= 2 and any(
        term in normalized for term in (" equals ", " equal to ", " conversion rate ", " contains ")
    ):
        return AssistedConstructionEligibility.NUMERICAL_CONVERSION
    if len(values) >= 2 and any(
        term in normalized for term in (" between ", " from ", " through ")
    ):
        return AssistedConstructionEligibility.NUMERICAL_RANGE
    if len(values) >= 2 and any(
        term in normalized for term in (" than ", " compared with ", " versus ")
    ):
        return AssistedConstructionEligibility.NUMERICAL
    dates = _explicit_dates(claim_text)
    temporal_terms = (
        " began ",
        " started ",
        " ended ",
        " applying ",
        " entered into force ",
        " took effect ",
        " active ",
        " inactive ",
        " founded ",
        " established ",
        " created ",
        " enacted ",
        " adopted ",
        " launched ",
        " reached ",
        " runs from ",
        " as of ",
        " on ",
    )
    if dates and any(term in normalized for term in temporal_terms):
        return AssistedConstructionEligibility.TEMPORAL
    if values or re.search(r"\b(?:twice|double|half)\b", normalized):
        return AssistedConstructionEligibility.NUMERICAL_SCALAR
    if any(word in normalized for word in ("still", "currently")) and not dates:
        return AssistedConstructionEligibility.MISSING_REFERENCE_DATE
    return AssistedConstructionEligibility.EXCLUDED_QUALITATIVE


def resolve_assisted_eligibility(
    *,
    claim_text: str,
    extraction: VerificationCandidateExtraction,
    routing: ConstructionEligibilityPacket,
) -> AssistedConstructionEligibility:
    """Resolve the single authoritative assisted route from V4 typed artifacts."""
    assisted_ids = {
        candidate_id
        for decision in routing.decisions
        if decision.route is ConstructionEligibilityRoute.ASSISTED
        for candidate_id in decision.candidate_ids
    }
    if not assisted_ids:
        return AssistedConstructionEligibility.EXCLUDED_QUALITATIVE
    candidates = tuple(
        item
        for item in extraction.candidates
        if item.material and item.candidate_id in assisted_ids
    )
    values = tuple(item for item in candidates if item.kind is VerificationCandidateKind.VALUE)
    kinds = {item.kind for item in candidates}
    normalized = f" {_normalized_text(claim_text)} "
    if values:
        if len(values) >= 2 and any(
            term in normalized
            for term in (" equals ", " equal to ", " conversion rate ", " contains ")
        ):
            return AssistedConstructionEligibility.NUMERICAL_CONVERSION
        if len(values) >= 2 and any(
            term in normalized for term in (" between ", " from ", " through ")
        ):
            return AssistedConstructionEligibility.NUMERICAL_RANGE
        if len(values) >= 2:
            return AssistedConstructionEligibility.NUMERICAL
        return AssistedConstructionEligibility.NUMERICAL_SCALAR
    if kinds.intersection(
        {
            VerificationCandidateKind.DATE,
            VerificationCandidateKind.STATUS,
        }
    ):
        return AssistedConstructionEligibility.TEMPORAL
    if VerificationCandidateKind.RANK in kinds:
        return AssistedConstructionEligibility.NUMERICAL_SCALAR
    return AssistedConstructionEligibility.EXCLUDED_QUALITATIVE


class AssistedEvidenceBinding(DomainModel):
    evidence_id: UUID
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    quoted_text: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def validate_offsets(self) -> AssistedEvidenceBinding:
        if self.end_char <= self.start_char:
            raise ValueError("evidence binding end must follow its start")
        return self


class AssistedTemporalEvidenceBinding(AssistedEvidenceBinding):
    effective_interval: TemporalInterval | None = None
    observed_status: str | None = Field(default=None, min_length=1, max_length=1_000)
    retrospective: bool = False

    @model_validator(mode="after")
    def require_temporal_fact(self) -> AssistedTemporalEvidenceBinding:
        if self.effective_interval is None and self.observed_status is None:
            raise ValueError("temporal binding requires an effective date or status")
        return self


class AssistedConstructionRequest(DomainModel):
    claim_id: UUID
    claim_text: str = Field(min_length=3, max_length=10_000)
    failed_construction_id: UUID
    approved_evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    construction_kind: AssistedConstructionKind = AssistedConstructionKind.NUMERICAL


class AssistedNumericalProviderProposal(DomainModel):
    """Provider schema containing numerical fields only."""

    failed_construction_id: UUID
    claim_text_span: str = Field(min_length=1, max_length=2_000)
    left_subject: str = Field(min_length=1, max_length=500)
    right_subject: str = Field(min_length=1, max_length=500)
    comparator: NumericComparator
    dimension: NumericDimension
    left_value: NormalizedNumericValue
    right_value: NormalizedNumericValue
    evidence_bindings: tuple[AssistedEvidenceBinding, ...] = Field(min_length=1)

    def to_proposal(self) -> AssistedConstructionProposal:
        return AssistedConstructionProposal(
            kind=AssistedConstructionKind.NUMERICAL,
            **self.model_dump(),
        )


class AssistedScalarForm(StrEnum):
    SINGLE_VALUE = "single_value"
    RANGE = "range"
    CONVERSION = "conversion"


class AssistedScalarProviderProposal(DomainModel):
    """Provider schema for one value, a bounded range, or an exact conversion."""

    failed_construction_id: UUID
    claim_text_span: str = Field(min_length=1, max_length=2_000)
    form: AssistedScalarForm
    subject: str = Field(min_length=1, max_length=500)
    comparator: NumericComparator
    operation: NumericOperation = NumericOperation.DIRECT
    dimension: NumericDimension
    values: tuple[NormalizedNumericValue, ...] = Field(min_length=1, max_length=2)
    evidence_bindings: tuple[AssistedEvidenceBinding, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_form(self) -> AssistedScalarProviderProposal:
        expected = (
            2
            if self.form
            in {
                AssistedScalarForm.RANGE,
                AssistedScalarForm.CONVERSION,
            }
            else 1
        )
        if len(self.values) != expected:
            raise ValueError(f"{self.form.value} requires {expected} value(s)")
        if self.form is AssistedScalarForm.RANGE and self.comparator not in {
            NumericComparator.BETWEEN_INCLUSIVE,
            NumericComparator.BETWEEN_EXCLUSIVE,
        }:
            raise ValueError("range construction requires a between comparator")
        if (
            self.form is AssistedScalarForm.CONVERSION
            and self.comparator is not NumericComparator.EQUAL
        ):
            raise ValueError("conversion construction requires equality")
        if any(value.dimension is not self.dimension for value in self.values):
            raise ValueError("scalar values must use the declared dimension")
        return self

    def to_proposal(self) -> AssistedConstructionProposal:
        return AssistedConstructionProposal(
            kind=AssistedConstructionKind.NUMERICAL_SCALAR,
            failed_construction_id=self.failed_construction_id,
            claim_text_span=self.claim_text_span,
            scalar_form=self.form,
            scalar_subject=self.subject,
            comparator=self.comparator,
            numeric_operation=self.operation,
            dimension=self.dimension,
            expected_values=self.values,
            evidence_bindings=self.evidence_bindings,
        )


class AssistedTemporalInstantWire(DomainModel):
    """Provider-facing date text converted deterministically after generation."""

    value: str = Field(min_length=4, max_length=40)
    precision: DatePrecision

    def to_domain(self) -> TemporalInstant:
        return TemporalInstant(
            value=_parse_explicit_date_text(self.value, self.precision),
            precision=self.precision,
        )


class AssistedTemporalIntervalWire(DomainModel):
    start: AssistedTemporalInstantWire | None = None
    end: AssistedTemporalInstantWire | None = None
    start_inclusive: bool = True
    end_inclusive: bool = True

    def to_domain(self) -> TemporalInterval:
        return TemporalInterval(
            start=self.start.to_domain() if self.start else None,
            end=self.end.to_domain() if self.end else None,
            start_inclusive=self.start_inclusive,
            end_inclusive=self.end_inclusive,
        )


class AssistedTemporalProviderBinding(AssistedEvidenceBinding):
    effective_interval: AssistedTemporalIntervalWire | None = None
    observed_status: str | None = Field(default=None, min_length=1, max_length=1_000)
    retrospective: bool = False

    def to_domain(
        self,
        *,
        fallback_interval: AssistedTemporalIntervalWire | None = None,
        fallback_status: str | None = None,
    ) -> AssistedTemporalEvidenceBinding:
        interval = self.effective_interval or fallback_interval
        status = self.observed_status or fallback_status
        return AssistedTemporalEvidenceBinding(
            evidence_id=self.evidence_id,
            start_char=self.start_char,
            end_char=self.end_char,
            quoted_text=self.quoted_text,
            effective_interval=interval.to_domain() if interval else None,
            observed_status=status,
            retrospective=self.retrospective,
        )


class AssistedTemporalProviderProposal(DomainModel):
    """Provider schema containing temporal/status fields only."""

    failed_construction_id: UUID
    claim_text_span: str = Field(min_length=1, max_length=2_000)
    temporal_relation: TemporalRelation
    reference_date: AssistedTemporalInstantWire | None = None
    claimed_interval: AssistedTemporalIntervalWire | None = None
    requires_reference_date: bool
    claimed_status: str | None = Field(default=None, min_length=1, max_length=1_000)
    temporal_bindings: tuple[AssistedTemporalProviderBinding, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_reconstructible_temporal_facts(
        self,
    ) -> AssistedTemporalProviderProposal:
        fallback_exists = any(
            item is not None
            for item in (
                self.reference_date,
                self.claimed_interval,
                self.claimed_status,
            )
        )
        reconstructed_claim = _unique_explicit_temporal_instant_wire(self.claim_text_span)
        if not fallback_exists and reconstructed_claim is None:
            raise ValueError(
                "temporal provider proposal requires a typed or uniquely reconstructible claim fact"
            )
        for binding in self.temporal_bindings:
            binding_fact = (
                binding.effective_interval is not None or binding.observed_status is not None
            )
            if (
                not binding_fact
                and not fallback_exists
                and _unique_explicit_temporal_instant_wire(binding.quoted_text) is None
            ):
                raise ValueError(
                    "temporal provider binding requires a typed or uniquely "
                    "reconstructible evidence fact"
                )
        return self

    def to_proposal(self) -> AssistedConstructionProposal:
        reference_date = self.reference_date
        claimed_status = self.claimed_status
        if claimed_status is None and self.temporal_relation in {
            TemporalRelation.ACTIVE,
            TemporalRelation.CHANGED_STATUS,
        }:
            claimed_status = _unique_claimed_status_phrase(self.claim_text_span)
        if reference_date is None and self.claimed_interval is None:
            reference_date = _unique_explicit_temporal_instant_wire(self.claim_text_span)
        fallback_interval = self.claimed_interval
        if fallback_interval is None and reference_date is not None:
            fallback_interval = AssistedTemporalIntervalWire(
                start=reference_date,
                end=reference_date,
            )
        return AssistedConstructionProposal(
            kind=AssistedConstructionKind.TEMPORAL_STATUS,
            failed_construction_id=self.failed_construction_id,
            claim_text_span=self.claim_text_span,
            temporal_relation=self.temporal_relation,
            reference_date=(reference_date.to_domain() if reference_date else None),
            claimed_interval=(self.claimed_interval.to_domain() if self.claimed_interval else None),
            requires_reference_date=self.requires_reference_date,
            claimed_status=claimed_status,
            temporal_bindings=tuple(
                item.to_domain(
                    fallback_interval=fallback_interval,
                    fallback_status=claimed_status,
                )
                for item in self.temporal_bindings
            ),
        )


class AssistedTemporalFactProviderBinding(AssistedEvidenceBinding):
    """Exact provider-selected evidence facts; no provider-built domain dates."""

    explicit_date_texts: tuple[str, ...] = Field(default=(), max_length=2)
    explicit_status_text: str | None = Field(default=None, min_length=1, max_length=500)
    retrospective: bool = False

    @model_validator(mode="after")
    def require_exact_fact_text(self) -> AssistedTemporalFactProviderBinding:
        facts = (*self.explicit_date_texts, self.explicit_status_text)
        if not any(facts):
            raise ValueError("temporal evidence binding requires an explicit fact")
        if any(item and item not in self.quoted_text for item in facts):
            raise ValueError("temporal evidence fact must be exact text inside quoted_text")
        return self


class AssistedTemporalFactProviderProposal(DomainModel):
    """Simplified temporal wire; deterministic code constructs all domain objects."""

    failed_construction_id: UUID
    claim_text_span: str = Field(min_length=1, max_length=2_000)
    temporal_relation: TemporalRelation
    explicit_claim_date_texts: tuple[str, ...] = Field(default=(), max_length=2)
    explicit_claim_status_text: str | None = Field(default=None, min_length=1, max_length=500)
    requires_reference_date: bool = False
    temporal_bindings: tuple[AssistedTemporalFactProviderBinding, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_exact_claim_facts(self) -> AssistedTemporalFactProviderProposal:
        facts = (*self.explicit_claim_date_texts, self.explicit_claim_status_text)
        if not any(facts):
            raise ValueError("temporal proposal requires an explicit claim fact")
        if any(item and item not in self.claim_text_span for item in facts):
            raise ValueError("temporal claim fact must be exact text inside claim_text_span")
        return self

    def to_proposal(self) -> AssistedConstructionProposal:
        claim_instants = tuple(
            _temporal_wire_from_exact_fact(item).to_domain()
            for item in self.explicit_claim_date_texts
        )
        reference_date = claim_instants[0] if len(claim_instants) == 1 else None
        claimed_interval = (
            TemporalInterval(start=claim_instants[0], end=claim_instants[1])
            if len(claim_instants) == 2
            else None
        )
        bindings = []
        for item in self.temporal_bindings:
            evidence_instants = tuple(
                _temporal_wire_from_exact_fact(value).to_domain()
                for value in item.explicit_date_texts
            )
            interval = None
            if len(evidence_instants) == 1:
                interval = TemporalInterval(start=evidence_instants[0], end=evidence_instants[0])
            elif len(evidence_instants) == 2:
                interval = TemporalInterval(start=evidence_instants[0], end=evidence_instants[1])
            bindings.append(
                AssistedTemporalEvidenceBinding(
                    evidence_id=item.evidence_id,
                    start_char=item.start_char,
                    end_char=item.end_char,
                    quoted_text=item.quoted_text,
                    effective_interval=interval,
                    observed_status=item.explicit_status_text,
                    retrospective=item.retrospective,
                )
            )
        return AssistedConstructionProposal(
            kind=AssistedConstructionKind.TEMPORAL_STATUS,
            failed_construction_id=self.failed_construction_id,
            claim_text_span=self.claim_text_span,
            temporal_relation=self.temporal_relation,
            reference_date=reference_date,
            claimed_interval=claimed_interval,
            requires_reference_date=self.requires_reference_date,
            claimed_status=self.explicit_claim_status_text,
            temporal_bindings=tuple(bindings),
        )


class AssistedConstructionProposal(DomainModel):
    """Untrusted proposal without any verification state or verdict field."""

    kind: AssistedConstructionKind = AssistedConstructionKind.NUMERICAL
    failed_construction_id: UUID
    claim_text_span: str = Field(min_length=1, max_length=2_000)
    left_subject: str | None = Field(default=None, min_length=1, max_length=500)
    right_subject: str | None = Field(default=None, min_length=1, max_length=500)
    comparator: NumericComparator | None = None
    dimension: NumericDimension | None = None
    left_value: NormalizedNumericValue | None = None
    right_value: NormalizedNumericValue | None = None
    scalar_form: AssistedScalarForm | None = None
    scalar_subject: str | None = Field(default=None, min_length=1, max_length=500)
    numeric_operation: NumericOperation | None = None
    expected_values: tuple[NormalizedNumericValue, ...] = ()
    evidence_bindings: tuple[AssistedEvidenceBinding, ...] = ()
    temporal_relation: TemporalRelation | None = None
    reference_date: TemporalInstant | None = None
    claimed_interval: TemporalInterval | None = None
    requires_reference_date: bool = False
    claimed_status: str | None = Field(default=None, min_length=1, max_length=1_000)
    temporal_bindings: tuple[AssistedTemporalEvidenceBinding, ...] = ()

    @model_validator(mode="after")
    def require_known_compatible_dimension(self) -> AssistedConstructionProposal:
        numerical = (
            self.left_subject,
            self.right_subject,
            self.comparator,
            self.dimension,
            self.left_value,
            self.right_value,
        )
        temporal = (
            self.temporal_relation,
            self.reference_date,
            self.claimed_interval,
            self.claimed_status,
        )
        if self.kind is AssistedConstructionKind.NUMERICAL:
            if any(item is None for item in numerical) or not self.evidence_bindings:
                raise ValueError("numerical construction requires all numerical fields")
            if any(item is not None for item in temporal) or self.temporal_bindings:
                raise ValueError("numerical construction cannot contain temporal fields")
            assert self.dimension is not None
            assert self.left_value is not None
            assert self.right_value is not None
            if self.dimension is NumericDimension.UNKNOWN:
                raise ValueError("assisted construction requires a known dimension")
            if {
                self.left_value.dimension,
                self.right_value.dimension,
            } != {self.dimension}:
                raise ValueError("assisted values must use the declared dimension")
            if (
                self.scalar_form is not None
                or self.scalar_subject is not None
                or self.numeric_operation is not None
                or self.expected_values
            ):
                raise ValueError("comparison cannot contain scalar fields")
        elif self.kind is AssistedConstructionKind.NUMERICAL_SCALAR:
            if (
                self.scalar_form is None
                or self.scalar_subject is None
                or self.numeric_operation is None
                or self.comparator is None
                or self.dimension is None
                or not self.expected_values
                or not self.evidence_bindings
            ):
                raise ValueError("scalar construction requires all scalar fields")
            if (
                any(
                    item is not None
                    for item in (
                        self.left_subject,
                        self.right_subject,
                        self.left_value,
                        self.right_value,
                    )
                )
                or self.temporal_bindings
            ):
                raise ValueError("scalar construction contains incompatible fields")
        else:
            if self.temporal_relation is None or not self.temporal_bindings:
                raise ValueError("temporal construction requires a relation and bindings")
            if (
                any(item is not None for item in numerical)
                or self.evidence_bindings
                or self.scalar_form is not None
                or self.scalar_subject is not None
                or self.numeric_operation is not None
                or self.expected_values
            ):
                raise ValueError("temporal construction cannot contain numerical fields")
            if (
                self.temporal_relation in {TemporalRelation.ACTIVE, TemporalRelation.CHANGED_STATUS}
                and self.claimed_status is None
            ):
                raise ValueError("status construction requires an exact claimed status")
            if self.requires_reference_date and self.reference_date is None:
                raise ValueError("required temporal reference date is missing")
        return self


class AssistedConstructionProvider(Protocol):
    """Optional provider; implementations must be receipt- and budget-wrapped."""

    def propose(
        self,
        request: AssistedConstructionRequest,
    ) -> AssistedConstructionProposal: ...


def validate_assisted_proposal(
    *,
    request: AssistedConstructionRequest,
    proposal: AssistedConstructionProposal,
    evidence: tuple[Evidence, ...],
) -> AssistedConstructionProposal:
    """Reject proposals that are not exactly claim- and evidence-span-bound."""
    if proposal.failed_construction_id != request.failed_construction_id:
        raise ValueError("proposal references a different failed construction")
    if proposal.kind is not request.construction_kind:
        raise ValueError("proposal kind differs from the preflight-authorized kind")
    if proposal.claim_text_span not in request.claim_text:
        raise ValueError("proposal claim span is not present in the claim")
    approved = set(request.approved_evidence_ids)
    records = {item.evidence_id: item for item in evidence}
    available_approved = approved.intersection(records)
    if available_approved != approved:
        raise ValueError("one or more approved evidence records are unavailable")
    bindings = (
        proposal.evidence_bindings
        if proposal.kind
        in {
            AssistedConstructionKind.NUMERICAL,
            AssistedConstructionKind.NUMERICAL_SCALAR,
        }
        else proposal.temporal_bindings
    )
    binding_ids = [item.evidence_id for item in bindings]
    if len(binding_ids) != len(set(binding_ids)):
        raise ValueError("proposal evidence bindings must be unique")
    for binding in bindings:
        if binding.evidence_id not in approved:
            raise ValueError("proposal references evidence outside the approved packet")
        record = records.get(binding.evidence_id)
        if record is None:
            raise ValueError("proposal evidence record is unavailable")
        if binding.end_char > len(record.passage):
            raise ValueError("proposal evidence span exceeds the retained passage")
        if record.passage[binding.start_char : binding.end_char] != binding.quoted_text:
            raise ValueError("proposal quote does not match the retained evidence span")
    if proposal.kind is AssistedConstructionKind.NUMERICAL:
        _validate_numerical_grounding(proposal)
    elif proposal.kind is AssistedConstructionKind.NUMERICAL_SCALAR:
        _validate_scalar_grounding(proposal)
    else:
        _validate_temporal_grounding(proposal)
    return proposal


def canonicalize_assisted_proposal(
    *,
    proposal: AssistedConstructionProposal,
    evidence: tuple[Evidence, ...],
) -> AssistedConstructionProposal:
    """Reconstruct trusted spans and bounded scalar subjects deterministically."""
    records = {item.evidence_id: item for item in evidence}

    def binding_update(binding):
        record = records.get(binding.evidence_id)
        if record is None:
            return binding
        span = _unique_exact_span(record.passage, binding.quoted_text)
        if span is None:
            span = _unique_fact_sentence_span(record.passage, proposal)
        if span is None:
            return binding
        start, end = span
        if isinstance(binding, AssistedTemporalEvidenceBinding):
            sentence = record.passage[start:end]
            observed_status = binding.observed_status
            if observed_status and _normalized_text(observed_status) not in _normalized_text(
                sentence
            ):
                reconstructed = _unique_explicit_status_phrase(sentence)
                if reconstructed is not None:
                    binding = binding.model_copy(update={"observed_status": reconstructed})
            expanded = _safe_temporal_binding_span(
                passage=record.passage,
                start=start,
                end=end,
                observed_status=binding.observed_status,
            )
            if expanded is None:
                return binding
            start, end = expanded
        quote = record.passage[start:end]
        return binding.model_copy(
            update={
                "start_char": start,
                "end_char": end,
                "quoted_text": quote,
            }
        )

    updates: dict[str, object] = {}
    if proposal.evidence_bindings:
        updates["evidence_bindings"] = tuple(
            binding_update(item) for item in proposal.evidence_bindings
        )
    if proposal.temporal_bindings:
        updates["temporal_bindings"] = tuple(
            binding_update(item) for item in proposal.temporal_bindings
        )
    if (
        proposal.kind is AssistedConstructionKind.NUMERICAL_SCALAR
        and proposal.scalar_subject
        and _normalized_text(proposal.scalar_subject)
        not in _normalized_text(proposal.claim_text_span)
    ):
        updates["scalar_subject"] = _bounded_scalar_subject(proposal.claim_text_span)
    return proposal.model_copy(update=updates)


def _unique_exact_span(
    passage: str,
    quote: str,
) -> tuple[int, int] | None:
    starts = [match.start() for match in re.finditer(re.escape(quote), passage)]
    if len(starts) != 1:
        return None
    return starts[0], starts[0] + len(quote)


def _unique_fact_sentence_span(
    passage: str,
    proposal: AssistedConstructionProposal,
) -> tuple[int, int] | None:
    """Recover one exact sentence only when all proposed facts occur in it."""
    required_values = {
        item.value
        for item in (
            *proposal.expected_values,
            *tuple(
                item for item in (proposal.left_value, proposal.right_value) if item is not None
            ),
        )
        if not (proposal.scalar_form is AssistedScalarForm.CONVERSION and item.value == Decimal(1))
    }
    required_dates = {
        item.value
        for item in _temporal_instants(proposal.reference_date, proposal.claimed_interval)
    }
    required_status = _normalized_text(proposal.claimed_status or "")
    matches: list[tuple[int, int]] = []
    for sentence in re.finditer(r"[^.!?\n]+(?:[.!?]|$)", passage):
        text = sentence.group(0).strip()
        start = sentence.start() + len(sentence.group(0)) - len(sentence.group(0).lstrip())
        end = start + len(text)
        if not text or len(text) > 2_000:
            continue
        if start == 0 and end == len(passage):
            continue
        if required_values and not required_values.issubset(_explicit_decimal_values(text)):
            continue
        if required_dates and not required_dates.issubset(_explicit_dates(text)):
            continue
        if required_status and required_status not in _normalized_text(text):
            continue
        if required_values or required_dates or required_status:
            matches.append((start, end))
    if len(matches) == 1:
        return matches[0]
    if required_dates and required_status:
        date_only = []
        for sentence in re.finditer(r"[^.!?\n]+(?:[.!?]|$)", passage):
            text = sentence.group(0).strip()
            start = sentence.start() + len(sentence.group(0)) - len(sentence.group(0).lstrip())
            end = start + len(text)
            if (
                text
                and len(text) <= 2_000
                and required_dates.issubset(_explicit_dates(text))
                and _unique_explicit_status_phrase(text) is not None
            ):
                date_only.append((start, end))
        if len(date_only) == 1:
            return date_only[0]
    return None


def _unique_explicit_status_phrase(text: str) -> str | None:
    """Extract one bounded, explicit status/event phrase without semantic inference."""
    patterns = (
        r"\b(?:once again\s+)?became\s+(?:an?|the)\s+[^,.;!?]{1,120}",
        r"\b(?:began|started|ended|ceased|resumed)\s+[^,.;!?]{1,120}",
        r"\b(?:is|was|remains?|remained)\s+(?:active|inactive|effective|independent)\b",
    )
    matches = [
        match.group(0).strip()
        for pattern in patterns
        for match in re.finditer(pattern, text, re.IGNORECASE)
    ]
    unique = tuple(dict.fromkeys(matches))
    return unique[0] if len(unique) == 1 else None


def _safe_temporal_binding_span(
    *,
    passage: str,
    start: int,
    end: int,
    observed_status: str | None,
) -> tuple[int, int] | None:
    if not observed_status:
        return start, end
    quote = passage[start:end]
    if _normalized_text(observed_status) in _normalized_text(quote):
        return start, end
    pattern = re.compile(
        rf"(?<!\w){re.escape(observed_status)}(?!\w)",
        re.IGNORECASE,
    )
    matches = tuple(pattern.finditer(passage))
    if len(matches) != 1:
        return None
    expanded_start = min(start, matches[0].start())
    expanded_end = max(end, matches[0].end())
    bridge = passage[expanded_start:expanded_end]
    if len(bridge) > 500 or re.search(r"[.!?\n]", bridge):
        return None
    return expanded_start, expanded_end


def _validate_numerical_grounding(proposal: AssistedConstructionProposal) -> None:
    assert proposal.left_subject is not None
    assert proposal.right_subject is not None
    assert proposal.left_value is not None
    assert proposal.right_value is not None
    normalized_span = _normalized_text(proposal.claim_text_span)
    if _normalized_text(proposal.left_subject) not in normalized_span:
        raise ValueError("left subject is not present in the proposed claim span")
    if _normalized_text(proposal.right_subject) not in normalized_span:
        raise ValueError("right subject is not present in the proposed claim span")
    claim_values = _explicit_decimal_values(proposal.claim_text_span)
    if proposal.left_value.value not in claim_values:
        raise ValueError("left value is not explicit in the proposed claim span")
    if proposal.right_value.value not in claim_values:
        raise ValueError("right value is not explicit in the proposed claim span")
    evidence_values = _explicit_decimal_values(
        " ".join(item.quoted_text for item in proposal.evidence_bindings)
    )
    if proposal.left_value.value not in evidence_values:
        raise ValueError("left value is not explicit in the bound evidence")
    if proposal.right_value.value not in evidence_values:
        raise ValueError("right value is not explicit in the bound evidence")


def _validate_temporal_grounding(proposal: AssistedConstructionProposal) -> None:
    claim_dates = _explicit_dates(proposal.claim_text_span)
    for instant in _temporal_instants(proposal.reference_date, proposal.claimed_interval):
        if instant.value not in claim_dates:
            raise ValueError("temporal claim date is not explicit in the claim span")
    if proposal.claimed_status and _normalized_text(
        proposal.claimed_status
    ) not in _normalized_text(proposal.claim_text_span):
        raise ValueError("claimed status is not explicit in the claim span")
    for binding in proposal.temporal_bindings:
        evidence_dates = _explicit_dates(binding.quoted_text)
        for instant in _temporal_instants(None, binding.effective_interval):
            if instant.value not in evidence_dates:
                raise ValueError("effective date is not explicit in bound evidence")
        if binding.observed_status and _normalized_text(
            binding.observed_status
        ) not in _normalized_text(binding.quoted_text):
            raise ValueError("observed status is not explicit in bound evidence")


def _validate_scalar_grounding(proposal: AssistedConstructionProposal) -> None:
    assert proposal.scalar_subject is not None
    if _normalized_text(proposal.scalar_subject) not in _normalized_text(proposal.claim_text_span):
        raise ValueError("scalar subject is not present in the claim span")
    claim_values = _explicit_decimal_values(proposal.claim_text_span)
    evidence_values = _explicit_decimal_values(
        " ".join(item.quoted_text for item in proposal.evidence_bindings)
    )
    for value in proposal.expected_values:
        if value.value not in claim_values:
            raise ValueError("scalar value is not explicit in the claim span")
        implicit_conversion_unit = (
            proposal.scalar_form is AssistedScalarForm.CONVERSION
            and value.value == Decimal(1)
            and value.unit is not None
            and any(
                _normalized_text(value.unit) in _normalized_text(binding.quoted_text)
                for binding in proposal.evidence_bindings
            )
        )
        if value.value not in evidence_values and not implicit_conversion_unit:
            raise ValueError("scalar value is not explicit in bound evidence")


def _unique_claimed_status_phrase(claim_span: str) -> str | None:
    patterns = (
        r"\bbegan applying\b",
        r"\bentered into force\b",
        r"\btook effect\b",
        r"\b(?:is|was|remains?|became) (?:active|inactive|effective)\b",
        r"\bno longer active\b",
    )
    matches = [
        match.group(0)
        for pattern in patterns
        for match in re.finditer(pattern, claim_span, re.IGNORECASE)
    ]
    return matches[0] if len(matches) == 1 else None


def _temporal_wire_from_exact_fact(value: str) -> AssistedTemporalInstantWire:
    wire = _unique_explicit_temporal_instant_wire(value)
    if wire is None:
        raise ValueError("explicit temporal fact is not one unambiguous date")
    return wire


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _bounded_scalar_subject(claim_span: str) -> str:
    boundary = re.search(
        r"\b(?:is|are|was|were|has|have|contains?|equals?|converts?|"
        r"grew|rose|fell|holds?|lasts?|needs?|means?)\b|"
        r"(?<![\w.])[-+]?\d",
        claim_span,
        re.IGNORECASE,
    )
    subject = claim_span[: boundary.start()].strip(" ,.;:-") if boundary else ""
    return subject or claim_span.strip()


def _explicit_decimal_values(value: str) -> set[Decimal]:
    results: set[Decimal] = set()
    for coefficient, exponent in re.findall(
        r"(?<![\w.])([-+]?\d+(?:\.\d+)?)\s*(?:x|\u00d7)\s*10\s*"
        r"(?:\^|\*\*)?\s*\{?([-+\u2212]?\d+)\}?",
        value,
        re.IGNORECASE,
    ):
        try:
            results.add(
                Decimal(coefficient) * (Decimal(10) ** int(exponent.replace("\u2212", "-")))
            )
        except (InvalidOperation, ValueError):
            continue
    for token in re.findall(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?(?![\w.])", value):
        try:
            results.add(Decimal(token.replace(",", "")))
        except InvalidOperation:
            continue
    number_words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "twice": 2,
        "double": 2,
        "half": Decimal("0.5"),
    }
    for word, number in number_words.items():
        if re.search(rf"\b{word}\b", value, re.IGNORECASE):
            results.add(Decimal(number))
    return results


def _explicit_measure_tokens(value: str) -> tuple[str, ...]:
    number = (
        r"(?:[$€£]\s*)?(?:[-+]?\d[\d,]*(?:\.\d+)?|"
        r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"twice|double|half)\b)"
    )
    unit = (
        r"%|percent(?:age)?(?:\s+points?)?|°?\s*(?:c|f|k)\b|"
        r"degrees?\s+(?:celsius|fahrenheit)|(?:[a-z]+\s+)?years?|"
        r"(?:[a-z]+\s+)?days?|hours?|minutes?|seconds?|"
        r"kilometres?|kilometers?|km|metres?|meters?|miles?|feet|foot|"
        r"kilograms?|kg|grams?|pounds?|lbs?|kilopascals?|kpa|"
        r"hectopascals?|hpa|pascals?|pa|atmospheres?|atm|psi|mph|km/h|m/s|"
        r"usd|eur|gbp|dollars?|euros?|litres?|liters?|millilitres?|"
        r"milliliters?|ml|hertz|hz|kilohertz|khz|megahertz|mhz|"
        r"gigahertz|ghz|btu|joules?|kilojoules?|kj|megajoules?|mj|"
        r"gigajoules?|gj|kwh|deutsche\s+marks?|marks?|kuna|"
        r"people|persons?|residents?|stations?|countries|territories|cases?|"
        r"births?|gallons?|barrels?|million|billion|items?|chromosomes?|"
        r"banks?|states?|museums?|members?|anniversary|anniversaries"
    )
    pattern = re.compile(
        rf"{number}(?:\s*-\s*|\s+)(?:[a-z]+\s+){{0,2}}(?:{unit})\b",
        re.IGNORECASE,
    )
    return tuple(match.group(0).strip() for match in pattern.finditer(value))


def _temporal_instants(
    reference: TemporalInstant | None,
    interval: TemporalInterval | None,
) -> tuple[TemporalInstant, ...]:
    return tuple(
        item
        for item in (
            reference,
            interval.start if interval else None,
            interval.end if interval else None,
        )
        if item is not None
    )


def _explicit_dates(value: str) -> set[date]:
    results: set[date] = set()
    months = {
        name.casefold(): index
        for index, name in enumerate(
            (
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            )
        )
        if name
    }
    for match in re.finditer(
        r"(?<!\d)(\d{1,2})\s+([A-Za-z]+)\s+((?:1[0-9]{3}|2[0-9]{3}))(?!\d)",
        value,
    ):
        month = months.get(match.group(2).casefold())
        if month:
            results.add(date(int(match.group(3)), month, int(match.group(1))))
    for match in re.finditer(
        r"([A-Za-z]+)\s+(\d{1,2}),\s*((?:1[0-9]{3}|2[0-9]{3}))",
        value,
    ):
        month = months.get(match.group(1).casefold())
        if month:
            results.add(date(int(match.group(3)), month, int(match.group(2))))
    for match in re.finditer(
        r"(?<!\d)((?:1[0-9]{3}|2[0-9]{3}))-(\d{2})-(\d{2})(?!\d)",
        value,
    ):
        results.add(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
    for match in re.finditer(r"(?<!\d)((?:1[0-9]{3}|2[0-9]{3}))(?!\d)", value):
        results.add(date(int(match.group(1)), 1, 1))
    return results


def _parse_explicit_date_text(value: str, precision: DatePrecision) -> date:
    normalized = value.strip()
    if precision is DatePrecision.DAY:
        year = r"(?:1[0-9]{3}|2[0-9]{3})"
        month_names = (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        )
        iso = re.fullmatch(rf"({year})-(\d{{2}})-(\d{{2}})", normalized)
        if iso:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        written = re.fullmatch(
            rf"(\d{{1,2}})\s+([A-Za-z]+)\s+({year})",
            normalized,
        )
        if written:
            month_name = written.group(2).casefold()
            if month_name in month_names:
                return date(
                    int(written.group(3)),
                    month_names.index(month_name) + 1,
                    int(written.group(1)),
                )
        month_first = re.fullmatch(
            rf"([A-Za-z]+)\s+(\d{{1,2}}),?\s+({year})",
            normalized,
        )
        if month_first:
            month_name = month_first.group(1).casefold()
            if month_name in month_names:
                return date(
                    int(month_first.group(3)),
                    month_names.index(month_name) + 1,
                    int(month_first.group(2)),
                )
    if precision is DatePrecision.MONTH:
        match = re.fullmatch(r"((?:1[0-9]{3}|2[0-9]{3}))-(\d{2})", normalized)
        if match:
            return date(int(match.group(1)), int(match.group(2)), 1)
        named = re.fullmatch(
            r"([A-Za-z]+)\s+((?:1[0-9]{3}|2[0-9]{3}))",
            normalized,
        )
        if named:
            month_names = (
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            )
            month_name = named.group(1).casefold()
            if month_name in month_names:
                return date(
                    int(named.group(2)),
                    month_names.index(month_name) + 1,
                    1,
                )
    if precision is DatePrecision.YEAR:
        match = re.fullmatch(r"(?:1[0-9]{3}|2[0-9]{3})", normalized)
        if match:
            return date(int(normalized), 1, 1)
    raise ValueError("provider date text does not match its declared precision")


def _unique_explicit_temporal_instant_wire(
    value: str,
) -> AssistedTemporalInstantWire | None:
    year = r"(?:1[0-9]{3}|2[0-9]{3})"
    month = (
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)"
    )
    patterns = (
        (
            DatePrecision.DAY,
            re.compile(rf"(?<!\d){year}-\d{{2}}-\d{{2}}(?!\d)"),
        ),
        (
            DatePrecision.DAY,
            re.compile(
                rf"(?<!\d)\d{{1,2}}\s+{month}\s+{year}(?!\d)",
                re.IGNORECASE,
            ),
        ),
        (
            DatePrecision.DAY,
            re.compile(
                rf"\b{month}\s+\d{{1,2}},?\s+{year}(?!\d)",
                re.IGNORECASE,
            ),
        ),
        (
            DatePrecision.MONTH,
            re.compile(rf"\b{month}\s+{year}(?!\d)", re.IGNORECASE),
        ),
        (
            DatePrecision.MONTH,
            re.compile(rf"(?<!\d){year}-\d{{2}}(?!-\d|\d)"),
        ),
        (
            DatePrecision.YEAR,
            re.compile(rf"(?<![\d-]){year}(?![\d-])"),
        ),
    )
    candidates: list[tuple[int, int, AssistedTemporalInstantWire]] = []
    occupied: list[tuple[int, int]] = []
    for precision, pattern in patterns:
        for match in pattern.finditer(value):
            span = (match.start(), match.end())
            if any(start <= span[0] and span[1] <= end for start, end in occupied):
                continue
            occupied.append(span)
            try:
                instant = AssistedTemporalInstantWire(
                    value=match.group(0),
                    precision=precision,
                )
                instant.to_domain()
            except (ValueError, OverflowError):
                continue
            candidates.append((*span, instant))
    if len(candidates) != 1:
        return None
    return candidates[0][2]


class DisabledAssistedConstructionProvider:
    """Zero-cost default until an explicit provider and budget are configured."""

    def propose(
        self,
        request: AssistedConstructionRequest,
    ) -> AssistedConstructionProposal:
        del request
        raise RuntimeError("model-assisted verification construction is disabled")
