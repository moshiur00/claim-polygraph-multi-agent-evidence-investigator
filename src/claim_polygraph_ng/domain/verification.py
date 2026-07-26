"""Deterministic temporal and numerical context-check artifacts."""

from datetime import date
from enum import StrEnum
from uuid import UUID

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
