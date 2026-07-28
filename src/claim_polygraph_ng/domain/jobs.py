"""Provider-neutral durable background-job contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, JsonValue, model_validator

from claim_polygraph_ng.domain.base import DomainModel


def job_utc_now() -> datetime:
    return datetime.now(UTC)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYABLE = "retryable"
    DEAD_LETTER = "dead_letter"


class JobFailureClass(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    BUDGET = "budget"
    INVALID_INPUT = "invalid_input"


class JobAuditAction(StrEnum):
    ENQUEUED = "enqueued"
    CLAIMED = "claimed"
    LEASE_RENEWED = "lease_renewed"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    RESUMED = "resumed"
    COMPLETED = "completed"
    RETRY_SCHEDULED = "retry_scheduled"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    LEASE_RECOVERED = "lease_recovered"


class JobSpec(DomainModel):
    idempotency_key: str = Field(min_length=3, max_length=300)
    kind: str = Field(min_length=3, max_length=100)
    payload: dict[str, JsonValue]
    provider: str = Field(default="internal", min_length=2, max_length=100)
    priority: int = Field(default=100, ge=0, le=1_000)
    maximum_attempts: int = Field(default=3, ge=1, le=20)
    traceparent: str | None = Field(
        default=None,
        pattern=r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$",
    )


class DurableJob(DomainModel):
    job_id: UUID = Field(default_factory=uuid4)
    spec: JobSpec
    status: JobStatus = JobStatus.QUEUED
    attempts: int = Field(default=0, ge=0)
    lease_owner: str | None = Field(default=None, min_length=2, max_length=200)
    lease_expires_at: datetime | None = None
    available_at: datetime = Field(default_factory=job_utc_now)
    cancellation_requested_at: datetime | None = None
    last_error: str | None = Field(default=None, max_length=2_000)
    result_reference: str | None = Field(default=None, max_length=1_000)
    created_at: datetime = Field(default_factory=job_utc_now)
    updated_at: datetime = Field(default_factory=job_utc_now)

    @model_validator(mode="after")
    def validate_lease(self) -> "DurableJob":
        leased = self.lease_owner is not None or self.lease_expires_at is not None
        if leased != (
            self.lease_owner is not None and self.lease_expires_at is not None
        ):
            raise ValueError("lease owner and expiry must be set together")
        if self.status in {JobStatus.RUNNING, JobStatus.CANCELLING} and not leased:
            raise ValueError("active jobs require a lease")
        if self.status not in {JobStatus.RUNNING, JobStatus.CANCELLING} and leased:
            raise ValueError("inactive jobs may not retain a lease")
        if self.attempts > self.spec.maximum_attempts:
            raise ValueError("attempts may not exceed maximum attempts")
        return self


class JobAdmissionPolicy(DomainModel):
    maximum_queue_depth: int = Field(default=100, ge=1, le=100_000)
    maximum_active_jobs: int = Field(default=4, ge=1, le=10_000)
    default_provider_limit: int = Field(default=2, ge=1, le=10_000)
    provider_limits: dict[str, int] = Field(default_factory=dict)

    def provider_limit(self, provider: str) -> int:
        return self.provider_limits.get(provider, self.default_provider_limit)


class JobAdmissionResult(DomainModel):
    job: DurableJob
    created: bool


class JobAuditEvent(DomainModel):
    event_id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    sequence: int = Field(ge=1)
    action: JobAuditAction
    actor: str = Field(min_length=2, max_length=200)
    detail: str = Field(min_length=2, max_length=2_000)
    occurred_at: datetime = Field(default_factory=job_utc_now)


class JobOperationReceipt(DomainModel):
    job_id: UUID
    operation_key: str = Field(min_length=3, max_length=300)
    completed: bool = False
    result_reference: str | None = Field(default=None, max_length=1_000)
    created_at: datetime = Field(default_factory=job_utc_now)
    completed_at: datetime | None = None


class JobQueueSnapshot(DomainModel):
    queued: int = Field(ge=0)
    running: int = Field(ge=0)
    interrupted: int = Field(ge=0)
    cancelling: int = Field(ge=0)
    retryable: int = Field(ge=0)
    terminal: int = Field(ge=0)
    dead_letter: int = Field(ge=0)


TERMINAL_JOB_STATUSES = frozenset(
    {JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DEAD_LETTER}
)
