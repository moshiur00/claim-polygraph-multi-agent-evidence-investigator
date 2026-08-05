"""Append-only human decisions controlling effective evidence use."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import EvidentiaryUse
from claim_polygraph_ng.domain.models import Evidence


class EvidenceDispositionKind(StrEnum):
    EXCLUDE = "exclude"
    APPROVE_USE = "approve_use"
    REQUEST_REPLACEMENT = "request_replacement"
    REQUEST_REEXTRACTION = "request_reextraction"


class EvidenceDispositionInput(DomainModel):
    evidence_id: UUID
    kind: EvidenceDispositionKind
    approved_use: EvidentiaryUse | None = None
    reason: str = Field(min_length=3, max_length=2_000)

    @model_validator(mode="after")
    def validate_approved_use(self) -> "EvidenceDispositionInput":
        if self.kind is EvidenceDispositionKind.APPROVE_USE:
            if self.approved_use in {
                None,
                EvidentiaryUse.UNSPECIFIED,
                EvidentiaryUse.EXCLUDED,
                EvidentiaryUse.DISCOVERY_LEAD,
            }:
                raise ValueError("approve-use requires a permitted evidentiary role")
        elif self.approved_use is not None:
            raise ValueError("approved_use is valid only for approve-use decisions")
        return self


class EvidenceDispositionRecord(EvidenceDispositionInput):
    disposition_id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    reviewer_identity: str = Field(min_length=3, max_length=300)
    approver_identity: str = Field(min_length=3, max_length=300)
    review_decision_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_distinct_approval(self) -> "EvidenceDispositionRecord":
        if self.reviewer_identity.strip().casefold() == self.approver_identity.strip().casefold():
            raise ValueError("evidence disposition requires a distinct approver")
        return self


def latest_evidence_dispositions(
    records: tuple[EvidenceDispositionRecord, ...],
) -> dict[UUID, EvidenceDispositionRecord]:
    """Resolve append-only records to the latest decision for each evidence item."""
    latest: dict[UUID, EvidenceDispositionRecord] = {}
    for record in sorted(records, key=lambda item: (item.created_at, str(item.disposition_id))):
        latest[record.evidence_id] = record
    return latest


def apply_evidence_dispositions(
    evidence: tuple[Evidence, ...],
    records: tuple[EvidenceDispositionRecord, ...],
) -> tuple[Evidence, ...]:
    """Return effective copies without mutating retained historical evidence."""
    latest = latest_evidence_dispositions(records)
    effective = []
    for item in evidence:
        disposition = latest.get(item.evidence_id)
        if disposition is None:
            effective.append(item)
            continue
        use = (
            disposition.approved_use
            if disposition.kind is EvidenceDispositionKind.APPROVE_USE
            else EvidentiaryUse.EXCLUDED
        )
        effective.append(item.model_copy(update={"evidentiary_use": use}))
    return tuple(effective)
