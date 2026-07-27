"""Precision-aware temporal verification over evidence-bound dated facts."""

from calendar import monthrange
from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from claim_polygraph_ng.domain import (
    AssertionVerificationState,
    DatePrecision,
    TemporalAssertionVerification,
    TemporalEvidenceObservation,
    TemporalInstant,
    TemporalInterval,
    TemporalRelation,
)
from claim_polygraph_ng.domain.base import DomainModel

TEMPORAL_VERIFIER_VERSION = "temporal-verifier-v1"


class TemporalFactStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CHANGED = "changed"
    UNKNOWN = "unknown"


class TemporalEvidenceFact(DomainModel):
    evidence_id: UUID
    publication_date: TemporalInstant | None = None
    effective_interval: TemporalInterval | None = None
    status: TemporalFactStatus = TemporalFactStatus.UNKNOWN
    observed_status: str | None = Field(default=None, min_length=1, max_length=1_000)
    retrospective: bool = False


class TemporalVerificationRequest(DomainModel):
    claim_id: UUID
    claim_text_span: str = Field(min_length=1, max_length=2_000)
    relation: TemporalRelation
    reference_date: TemporalInstant | None = None
    claimed_interval: TemporalInterval | None = None
    requires_reference_date: bool = False
    facts: tuple[TemporalEvidenceFact, ...]


def verify_temporal_assertion(
    request: TemporalVerificationRequest,
) -> TemporalAssertionVerification:
    """Verify one temporal relation and preserve ambiguity from coarse dates."""
    observations = tuple(
        TemporalEvidenceObservation(
            evidence_id=fact.evidence_id,
            publication_date=fact.publication_date,
            effective_interval=fact.effective_interval,
            observed_status=fact.observed_status or fact.status.value,
            retrospective=fact.retrospective,
        )
        for fact in request.facts
    )
    if request.requires_reference_date and request.reference_date is None:
        return _result(request, observations, AssertionVerificationState.INSUFFICIENT,
                       "A required reference date is missing.")
    if not request.facts:
        return _result(request, observations, AssertionVerificationState.INSUFFICIENT,
                       "No evidence-bound temporal facts were supplied.")
    target = _target_bounds(request)
    if target is None:
        return _result(request, observations, AssertionVerificationState.INSUFFICIENT,
                       "The asserted temporal boundary or interval is missing.")

    outcomes: list[AssertionVerificationState] = []
    for fact in request.facts:
        outcome = _evaluate_fact(request.relation, fact, target)
        if outcome is not AssertionVerificationState.INSUFFICIENT:
            if _unmarked_postdated_fact(fact, target):
                outcome = AssertionVerificationState.QUALIFIED
            outcomes.append(outcome)
    if not outcomes:
        return _result(request, observations, AssertionVerificationState.INSUFFICIENT,
                       "Evidence facts contain no applicable effective date or status.")
    distinct = set(outcomes)
    state = (
        outcomes[0]
        if len(distinct) == 1
        else AssertionVerificationState.QUALIFIED
    )
    issue = (
        "Temporal evidence is conflicting or precision-limited."
        if state is AssertionVerificationState.QUALIFIED
        else None
    )
    return _result(request, observations, state, issue)


def _evaluate_fact(
    relation: TemporalRelation,
    fact: TemporalEvidenceFact,
    target: tuple[date, date],
) -> AssertionVerificationState:
    if relation in {TemporalRelation.ACTIVE, TemporalRelation.CHANGED_STATUS}:
        return _evaluate_status(relation, fact, target)
    if fact.effective_interval is None:
        return AssertionVerificationState.INSUFFICIENT
    subject = _interval_bounds(fact.effective_interval)
    if relation is TemporalRelation.BEFORE:
        if subject[1] < target[0]:
            return AssertionVerificationState.VERIFIED
        if subject[0] >= target[1]:
            return AssertionVerificationState.CONTRADICTED
    elif relation is TemporalRelation.AFTER:
        if subject[0] > target[1]:
            return AssertionVerificationState.VERIFIED
        if subject[1] <= target[0]:
            return AssertionVerificationState.CONTRADICTED
    elif relation is TemporalRelation.ON:
        if subject[0] <= target[0] and subject[1] >= target[1]:
            return AssertionVerificationState.VERIFIED
        if subject[1] < target[0] or subject[0] > target[1]:
            return AssertionVerificationState.CONTRADICTED
    elif relation is TemporalRelation.DURING:
        if subject[0] >= target[0] and subject[1] <= target[1]:
            return AssertionVerificationState.VERIFIED
        if subject[1] < target[0] or subject[0] > target[1]:
            return AssertionVerificationState.CONTRADICTED
    elif relation is TemporalRelation.STARTED:
        return _compare_instant_bounds(_start_bounds(fact.effective_interval), target)
    elif relation is TemporalRelation.ENDED:
        return _compare_instant_bounds(_end_bounds(fact.effective_interval), target)
    return AssertionVerificationState.QUALIFIED


def _evaluate_status(
    relation: TemporalRelation,
    fact: TemporalEvidenceFact,
    target: tuple[date, date],
) -> AssertionVerificationState:
    if fact.effective_interval is None:
        return AssertionVerificationState.INSUFFICIENT
    effective = _interval_bounds(fact.effective_interval)
    if effective[1] < target[0] or effective[0] > target[1]:
        return AssertionVerificationState.INSUFFICIENT
    if relation is TemporalRelation.ACTIVE:
        if fact.status is TemporalFactStatus.ACTIVE:
            return AssertionVerificationState.VERIFIED
        if fact.status is TemporalFactStatus.INACTIVE:
            return AssertionVerificationState.CONTRADICTED
    elif relation is TemporalRelation.CHANGED_STATUS:
        if fact.status is TemporalFactStatus.CHANGED:
            return AssertionVerificationState.VERIFIED
        if fact.status in {TemporalFactStatus.ACTIVE, TemporalFactStatus.INACTIVE}:
            return AssertionVerificationState.CONTRADICTED
    return AssertionVerificationState.QUALIFIED


def _target_bounds(request: TemporalVerificationRequest) -> tuple[date, date] | None:
    if request.claimed_interval is not None:
        return _interval_bounds(request.claimed_interval)
    if request.reference_date is not None:
        return _instant_bounds(request.reference_date)
    return None


def _instant_bounds(instant: TemporalInstant) -> tuple[date, date]:
    value = instant.value
    if instant.precision is DatePrecision.DAY:
        return value, value
    if instant.precision is DatePrecision.MONTH:
        return date(value.year, value.month, 1), date(
            value.year, value.month, monthrange(value.year, value.month)[1]
        )
    return date(value.year, 1, 1), date(value.year, 12, 31)


def _interval_bounds(interval: TemporalInterval) -> tuple[date, date]:
    start = _instant_bounds(interval.start)[0] if interval.start else date.min
    end = _instant_bounds(interval.end)[1] if interval.end else date.max
    return start, end


def _start_bounds(interval: TemporalInterval) -> tuple[date, date]:
    return _instant_bounds(interval.start) if interval.start else (date.min, date.max)


def _end_bounds(interval: TemporalInterval) -> tuple[date, date]:
    return _instant_bounds(interval.end) if interval.end else (date.min, date.max)


def _compare_instant_bounds(
    observed: tuple[date, date],
    target: tuple[date, date],
) -> AssertionVerificationState:
    if observed == target:
        return AssertionVerificationState.VERIFIED
    if observed[1] < target[0] or observed[0] > target[1]:
        return AssertionVerificationState.CONTRADICTED
    return AssertionVerificationState.QUALIFIED


def _unmarked_postdated_fact(
    fact: TemporalEvidenceFact,
    target: tuple[date, date],
) -> bool:
    if fact.publication_date is None or fact.retrospective:
        return False
    publication_start = _instant_bounds(fact.publication_date)[0]
    return publication_start > target[1]


def _result(
    request: TemporalVerificationRequest,
    observations: tuple[TemporalEvidenceObservation, ...],
    state: AssertionVerificationState,
    issue: str | None,
) -> TemporalAssertionVerification:
    return TemporalAssertionVerification(
        claim_id=request.claim_id,
        claim_text_span=request.claim_text_span,
        relation=request.relation,
        reference_date=request.reference_date,
        claimed_interval=request.claimed_interval,
        requires_reference_date=request.requires_reference_date,
        observations=observations,
        state=state,
        issues=(issue,) if issue else (),
        limitations=(
            "Date precision is preserved as an interval and never silently "
            "expanded to day precision.",
            "Publication date is distinct from effective date.",
            f"Verifier version: {TEMPORAL_VERIFIER_VERSION}.",
        ),
    )
