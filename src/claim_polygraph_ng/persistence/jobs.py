"""SQLite durable-job queue with leases, cancellation and backpressure."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from claim_polygraph_ng.domain.jobs import (
    TERMINAL_JOB_STATUSES,
    DurableJob,
    JobAdmissionPolicy,
    JobAdmissionResult,
    JobAuditAction,
    JobAuditEvent,
    JobFailureClass,
    JobOperationReceipt,
    JobQueueSnapshot,
    JobSpec,
    JobStatus,
)
from claim_polygraph_ng.persistence.sqlite_runtime import connect_sqlite, enable_wal


class JobQueueError(RuntimeError):
    """Base durable-job error."""


class JobBackpressureError(JobQueueError):
    """Admission was rejected because the bounded queue is full."""


class JobLeaseError(JobQueueError):
    """A worker attempted to mutate a job without its current lease."""


class JobStateError(JobQueueError):
    """The requested job transition is invalid."""


class SQLiteJobQueue:
    """Single-host durable queue behind a provider-neutral contract."""

    def __init__(self, database_path: str | Path, policy: JobAdmissionPolicy) -> None:
        self._path = str(database_path)
        self._policy = policy

    @contextmanager
    def _connect(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = connect_sqlite(self._path)
        connection.row_factory = sqlite3.Row
        try:
            if immediate:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            enable_wal(connection)
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS durable_jobs (
                    job_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    provider TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS durable_jobs_claim
                    ON durable_jobs(status, available_at, priority, created_at);
                CREATE INDEX IF NOT EXISTS durable_jobs_provider_status
                    ON durable_jobs(provider, status);
                CREATE TABLE IF NOT EXISTS job_audit_events (
                    job_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY(job_id, sequence),
                    FOREIGN KEY(job_id) REFERENCES durable_jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS job_operation_receipts (
                    job_id TEXT NOT NULL,
                    operation_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY(job_id, operation_key),
                    FOREIGN KEY(job_id) REFERENCES durable_jobs(job_id)
                );
                """
            )

    def enqueue(self, spec: JobSpec, *, actor: str = "api") -> JobAdmissionResult:
        with self._connect(immediate=True) as connection:
            existing = connection.execute(
                "SELECT payload FROM durable_jobs WHERE idempotency_key = ?",
                (spec.idempotency_key,),
            ).fetchone()
            if existing:
                return JobAdmissionResult(
                    job=DurableJob.model_validate_json(existing["payload"]), created=False
                )
            depth = connection.execute(
                "SELECT COUNT(*) FROM durable_jobs WHERE status IN (?, ?)",
                (JobStatus.QUEUED.value, JobStatus.RETRYABLE.value),
            ).fetchone()[0]
            if depth >= self._policy.maximum_queue_depth:
                raise JobBackpressureError(
                    f"queue capacity {self._policy.maximum_queue_depth} reached"
                )
            job = DurableJob(spec=spec)
            self._save(connection, job)
            self._audit(connection, job.job_id, JobAuditAction.ENQUEUED, actor, "accepted")
        return JobAdmissionResult(job=job, created=True)

    def claim(
        self,
        worker_id: str,
        *,
        lease_seconds: int = 30,
        now: datetime | None = None,
    ) -> DurableJob | None:
        if lease_seconds < 1:
            raise ValueError("lease seconds must be positive")
        instant = now or datetime.now(UTC)
        with self._connect(immediate=True) as connection:
            active = connection.execute(
                "SELECT COUNT(*) FROM durable_jobs WHERE status IN (?, ?)",
                (JobStatus.RUNNING.value, JobStatus.CANCELLING.value),
            ).fetchone()[0]
            if active >= self._policy.maximum_active_jobs:
                return None
            candidates = connection.execute(
                """
                SELECT payload FROM durable_jobs
                WHERE status IN (?, ?) AND available_at <= ?
                ORDER BY priority ASC, created_at ASC
                """,
                (
                    JobStatus.QUEUED.value,
                    JobStatus.RETRYABLE.value,
                    instant.isoformat(),
                ),
            ).fetchall()
            selected: DurableJob | None = None
            for row in candidates:
                candidate = DurableJob.model_validate_json(row["payload"])
                provider_active = connection.execute(
                    "SELECT COUNT(*) FROM durable_jobs "
                    "WHERE provider = ? AND status IN (?, ?)",
                    (
                        candidate.spec.provider,
                        JobStatus.RUNNING.value,
                        JobStatus.CANCELLING.value,
                    ),
                ).fetchone()[0]
                if provider_active < self._policy.provider_limit(candidate.spec.provider):
                    selected = candidate
                    break
            if selected is None:
                return None
            claimed = selected.model_copy(
                update={
                    "status": JobStatus.RUNNING,
                    "attempts": selected.attempts + 1,
                    "lease_owner": worker_id,
                    "lease_expires_at": instant + timedelta(seconds=lease_seconds),
                    "updated_at": instant,
                }
            )
            self._save(connection, claimed)
            self._audit(
                connection,
                claimed.job_id,
                JobAuditAction.CLAIMED,
                worker_id,
                f"attempt {claimed.attempts}",
            )
            return claimed

    def renew_lease(
        self, job_id: UUID, worker_id: str, *, lease_seconds: int = 30
    ) -> DurableJob:
        with self._connect(immediate=True) as connection:
            job = self._owned(connection, job_id, worker_id)
            now = datetime.now(UTC)
            renewed = job.model_copy(
                update={
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "updated_at": now,
                }
            )
            self._save(connection, renewed)
            self._audit(
                connection, job_id, JobAuditAction.LEASE_RENEWED, worker_id, "lease renewed"
            )
            return renewed

    def request_cancellation(self, job_id: UUID, *, actor: str) -> DurableJob:
        with self._connect(immediate=True) as connection:
            job = self._load(connection, job_id)
            if job.status in TERMINAL_JOB_STATUSES:
                return job
            now = datetime.now(UTC)
            if job.status in {JobStatus.QUEUED, JobStatus.RETRYABLE, JobStatus.INTERRUPTED}:
                updated = job.model_copy(
                    update={
                        "status": JobStatus.CANCELLED,
                        "cancellation_requested_at": now,
                        "updated_at": now,
                    }
                )
                action = JobAuditAction.CANCELLED
            elif job.status is JobStatus.RUNNING:
                updated = job.model_copy(
                    update={
                        "status": JobStatus.CANCELLING,
                        "cancellation_requested_at": now,
                        "updated_at": now,
                    }
                )
                action = JobAuditAction.CANCELLATION_REQUESTED
            else:
                return job
            self._save(connection, updated)
            self._audit(connection, job_id, action, actor, "cancellation requested")
            return updated

    def safe_boundary(self, job_id: UUID, worker_id: str) -> DurableJob:
        """A worker calls this between nodes; completed artifacts remain untouched."""
        with self._connect(immediate=True) as connection:
            job = self._owned(connection, job_id, worker_id)
            if job.status is not JobStatus.CANCELLING:
                return job
            now = datetime.now(UTC)
            cancelled = job.model_copy(
                update={
                    "status": JobStatus.CANCELLED,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "updated_at": now,
                }
            )
            self._save(connection, cancelled)
            self._audit(
                connection,
                job_id,
                JobAuditAction.CANCELLED,
                worker_id,
                "cancelled at safe node boundary",
            )
            return cancelled

    def interrupt(self, job_id: UUID, worker_id: str, *, reason: str) -> DurableJob:
        return self._finish_active(
            job_id,
            worker_id,
            JobStatus.INTERRUPTED,
            JobAuditAction.INTERRUPTED,
            reason=reason,
        )

    def resume(self, job_id: UUID, *, actor: str) -> DurableJob:
        with self._connect(immediate=True) as connection:
            job = self._load(connection, job_id)
            if job.status is not JobStatus.INTERRUPTED:
                raise JobStateError("only interrupted jobs may resume")
            now = datetime.now(UTC)
            resumed = job.model_copy(
                update={"status": JobStatus.QUEUED, "available_at": now, "updated_at": now}
            )
            self._save(connection, resumed)
            self._audit(connection, job_id, JobAuditAction.RESUMED, actor, "review resolved")
            return resumed

    def complete(
        self, job_id: UUID, worker_id: str, *, result_reference: str
    ) -> DurableJob:
        return self._finish_active(
            job_id,
            worker_id,
            JobStatus.COMPLETED,
            JobAuditAction.COMPLETED,
            result_reference=result_reference,
            reason="completed",
        )

    def complete_interrupted(
        self, job_id: UUID, *, actor: str, result_reference: str
    ) -> DurableJob:
        """Complete the same durable job after its graph interruption is resolved.

        The graph decision is persisted before this transition. Repeating the API
        request is therefore safe: a completed job is returned unchanged.
        """
        with self._connect(immediate=True) as connection:
            job = self._load(connection, job_id)
            if job.status is JobStatus.COMPLETED:
                return job
            if job.status is not JobStatus.INTERRUPTED:
                raise JobStateError("only interrupted jobs may complete after review")
            now = datetime.now(UTC)
            completed = job.model_copy(
                update={
                    "status": JobStatus.COMPLETED,
                    "result_reference": result_reference,
                    "updated_at": now,
                }
            )
            self._save(connection, completed)
            self._audit(
                connection,
                job_id,
                JobAuditAction.COMPLETED,
                actor,
                "authoritative graph completed after review",
            )
            return completed

    def fail(
        self,
        job_id: UUID,
        worker_id: str,
        *,
        classification: JobFailureClass,
        error: str,
        retry_delay_seconds: int = 0,
    ) -> DurableJob:
        with self._connect(immediate=True) as connection:
            job = self._owned(connection, job_id, worker_id)
            retry = (
                classification is JobFailureClass.TRANSIENT
                and job.attempts < job.spec.maximum_attempts
            )
            if retry:
                status = JobStatus.RETRYABLE
                action = JobAuditAction.RETRY_SCHEDULED
            elif classification is JobFailureClass.TRANSIENT:
                status = JobStatus.DEAD_LETTER
                action = JobAuditAction.DEAD_LETTERED
            else:
                status = JobStatus.FAILED
                action = JobAuditAction.FAILED
            now = datetime.now(UTC)
            failed = job.model_copy(
                update={
                    "status": status,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "available_at": now + timedelta(seconds=retry_delay_seconds),
                    "last_error": error,
                    "updated_at": now,
                }
            )
            self._save(connection, failed)
            self._audit(connection, job_id, action, worker_id, error)
            return failed

    def recover_expired_leases(self, *, now: datetime | None = None) -> tuple[DurableJob, ...]:
        instant = now or datetime.now(UTC)
        recovered: list[DurableJob] = []
        with self._connect(immediate=True) as connection:
            rows = connection.execute(
                "SELECT payload FROM durable_jobs WHERE status IN (?, ?)",
                (JobStatus.RUNNING.value, JobStatus.CANCELLING.value),
            ).fetchall()
            for row in rows:
                job = DurableJob.model_validate_json(row["payload"])
                if job.lease_expires_at is None or job.lease_expires_at > instant:
                    continue
                if job.status is JobStatus.CANCELLING:
                    status = JobStatus.CANCELLED
                elif job.attempts < job.spec.maximum_attempts:
                    status = JobStatus.RETRYABLE
                else:
                    status = JobStatus.DEAD_LETTER
                updated = job.model_copy(
                    update={
                        "status": status,
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "available_at": instant,
                        "last_error": "worker lease expired",
                        "updated_at": instant,
                    }
                )
                self._save(connection, updated)
                self._audit(
                    connection,
                    job.job_id,
                    JobAuditAction.LEASE_RECOVERED,
                    "recovery",
                    f"expired lease became {status.value}",
                )
                recovered.append(updated)
        return tuple(recovered)

    def begin_operation(self, job_id: UUID, operation_key: str) -> bool:
        """Reserve a paid operation once across retries and worker crashes."""
        with self._connect(immediate=True) as connection:
            self._load(connection, job_id)
            receipt = JobOperationReceipt(job_id=job_id, operation_key=operation_key)
            try:
                connection.execute(
                    "INSERT INTO job_operation_receipts VALUES (?, ?, ?)",
                    (str(job_id), operation_key, receipt.model_dump_json()),
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def complete_operation(
        self, job_id: UUID, operation_key: str, *, result_reference: str
    ) -> JobOperationReceipt:
        with self._connect(immediate=True) as connection:
            row = connection.execute(
                "SELECT payload FROM job_operation_receipts "
                "WHERE job_id = ? AND operation_key = ?",
                (str(job_id), operation_key),
            ).fetchone()
            if row is None:
                raise JobStateError("operation was not reserved")
            saved = JobOperationReceipt.model_validate_json(row["payload"])
            if saved.completed:
                return saved
            completed = saved.model_copy(
                update={
                    "completed": True,
                    "result_reference": result_reference,
                    "completed_at": datetime.now(UTC),
                }
            )
            connection.execute(
                "UPDATE job_operation_receipts SET payload = ? "
                "WHERE job_id = ? AND operation_key = ?",
                (completed.model_dump_json(), str(job_id), operation_key),
            )
            return completed

    def load(self, job_id: UUID) -> DurableJob:
        with self._connect() as connection:
            return self._load(connection, job_id)

    def audit_events(self, job_id: UUID) -> tuple[JobAuditEvent, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM job_audit_events WHERE job_id = ? ORDER BY sequence",
                (str(job_id),),
            ).fetchall()
        return tuple(JobAuditEvent.model_validate_json(row["payload"]) for row in rows)

    def snapshot(self) -> JobQueueSnapshot:
        with self._connect() as connection:
            counts = dict(
                connection.execute(
                    "SELECT status, COUNT(*) FROM durable_jobs GROUP BY status"
                ).fetchall()
            )
        def count(status: JobStatus) -> int:
            return int(counts.get(status.value, 0))

        return JobQueueSnapshot(
            queued=count(JobStatus.QUEUED),
            running=count(JobStatus.RUNNING),
            interrupted=count(JobStatus.INTERRUPTED),
            cancelling=count(JobStatus.CANCELLING),
            retryable=count(JobStatus.RETRYABLE),
            terminal=(
                count(JobStatus.CANCELLED)
                + count(JobStatus.COMPLETED)
                + count(JobStatus.FAILED)
            ),
            dead_letter=count(JobStatus.DEAD_LETTER),
        )

    def _finish_active(
        self,
        job_id: UUID,
        worker_id: str,
        status: JobStatus,
        action: JobAuditAction,
        *,
        reason: str,
        result_reference: str | None = None,
    ) -> DurableJob:
        with self._connect(immediate=True) as connection:
            job = self._owned(connection, job_id, worker_id)
            if job.status is JobStatus.CANCELLING and status is not JobStatus.CANCELLED:
                raise JobStateError("cancelling job must stop at a safe boundary")
            now = datetime.now(UTC)
            updated = job.model_copy(
                update={
                    "status": status,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "result_reference": result_reference,
                    "updated_at": now,
                }
            )
            self._save(connection, updated)
            self._audit(connection, job_id, action, worker_id, reason)
            return updated

    @staticmethod
    def _load(connection: sqlite3.Connection, job_id: UUID) -> DurableJob:
        row = connection.execute(
            "SELECT payload FROM durable_jobs WHERE job_id = ?", (str(job_id),)
        ).fetchone()
        if row is None:
            raise JobQueueError(f"job not found: {job_id}")
        return DurableJob.model_validate_json(row["payload"])

    def _owned(
        self, connection: sqlite3.Connection, job_id: UUID, worker_id: str
    ) -> DurableJob:
        job = self._load(connection, job_id)
        if (
            job.status not in {JobStatus.RUNNING, JobStatus.CANCELLING}
            or job.lease_owner != worker_id
        ):
            raise JobLeaseError("worker does not own the active lease")
        return job

    @staticmethod
    def _save(connection: sqlite3.Connection, job: DurableJob) -> None:
        connection.execute(
            """
            INSERT INTO durable_jobs
                (job_id, idempotency_key, provider, priority, status,
                 available_at, created_at, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                provider=excluded.provider, priority=excluded.priority,
                status=excluded.status, available_at=excluded.available_at,
                payload=excluded.payload
            """,
            (
                str(job.job_id),
                job.spec.idempotency_key,
                job.spec.provider,
                job.spec.priority,
                job.status.value,
                job.available_at.isoformat(),
                job.created_at.isoformat(),
                job.model_dump_json(),
            ),
        )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        job_id: UUID,
        action: JobAuditAction,
        actor: str,
        detail: str,
    ) -> None:
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM job_audit_events WHERE job_id = ?",
            (str(job_id),),
        ).fetchone()[0]
        event = JobAuditEvent(
            job_id=job_id,
            sequence=sequence,
            action=action,
            actor=actor,
            detail=detail,
        )
        connection.execute(
            "INSERT INTO job_audit_events VALUES (?, ?, ?)",
            (str(job_id), sequence, event.model_dump_json()),
        )
