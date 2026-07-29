"""Durable paid-operation receipts and cost-ledger contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


def paid_utc_now() -> datetime:
    return datetime.now(UTC)


class PaidOperationKind(StrEnum):
    MODEL = "model"
    SEARCH = "search"
    FETCH = "fetch"
    CITATION_REVISION = "citation_revision"
    ADDITIONAL_RESEARCH = "additional_research"


class PaidReceiptStatus(StrEnum):
    RESERVED = "reserved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_PERMANENT = "failed_permanent"
    CANCELLED = "cancelled"
    AMBIGUOUS = "ambiguous"


class PaidReceiptDecision(StrEnum):
    EXECUTE = "execute"
    RETURN_CACHED = "return_cached"
    ACTIVE = "active"
    AMBIGUOUS = "ambiguous"
    TERMINAL_FAILURE = "terminal_failure"


class PaidOperationSpec(DomainModel):
    operation_key: str = Field(min_length=16, max_length=300)
    investigation_id: UUID
    node_id: str = Field(min_length=2, max_length=200)
    kind: PaidOperationKind
    provider: str = Field(min_length=2, max_length=200)
    model_or_engine: str | None = Field(default=None, max_length=200)
    task: str = Field(min_length=2, max_length=200)
    canonical_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PaidOperationReceipt(DomainModel):
    receipt_id: UUID = Field(default_factory=uuid4)
    spec: PaidOperationSpec
    status: PaidReceiptStatus = PaidReceiptStatus.RESERVED
    attempt_number: int = Field(default=0, ge=0)
    lease_owner: str | None = Field(default=None, min_length=2, max_length=200)
    lease_expires_at: datetime | None = None
    result_reference: str | None = Field(default=None, max_length=500)
    result_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0, ge=0)
    duration_seconds: float = Field(default=0, ge=0)
    error_class: str | None = Field(default=None, max_length=200)
    safe_error: str | None = Field(default=None, max_length=1_000)
    created_at: datetime = Field(default_factory=paid_utc_now)
    updated_at: datetime = Field(default_factory=paid_utc_now)
    provider_started_at: datetime | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_receipt_state(self) -> PaidOperationReceipt:
        leased = self.lease_owner is not None or self.lease_expires_at is not None
        if leased != (
            self.lease_owner is not None and self.lease_expires_at is not None
        ):
            raise ValueError("receipt lease owner and expiry must be set together")
        if self.status in {PaidReceiptStatus.RESERVED, PaidReceiptStatus.IN_PROGRESS}:
            if not leased:
                raise ValueError("active receipt requires a lease")
        elif leased:
            raise ValueError("inactive receipt cannot retain a lease")
        if self.status is PaidReceiptStatus.IN_PROGRESS and self.provider_started_at is None:
            raise ValueError("in-progress receipt requires provider start time")
        completed_result = self.result_reference is not None or self.result_sha256 is not None
        if self.status is PaidReceiptStatus.COMPLETED:
            if (
                not completed_result
                or self.result_reference is None
                or self.result_sha256 is None
                or self.completed_at is None
            ):
                raise ValueError("completed receipt requires a durable result")
        elif completed_result or self.completed_at is not None:
            raise ValueError("only completed receipts may expose a result")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input tokens cannot exceed input tokens")
        return self


class PaidReceiptClaim(DomainModel):
    decision: PaidReceiptDecision
    receipt: PaidOperationReceipt


class PaidCostLedger(DomainModel):
    completed_operation_count: int = Field(ge=0)
    model_operation_count: int = Field(ge=0)
    search_operation_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
