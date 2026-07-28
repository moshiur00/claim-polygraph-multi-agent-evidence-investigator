"""Backend-neutral worker boundary for durable investigation jobs."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from claim_polygraph_ng.domain.jobs import DurableJob, JobFailureClass, JobStatus
from claim_polygraph_ng.domain.telemetry import MetricName, SpanKind
from claim_polygraph_ng.persistence.jobs import SQLiteJobQueue
from claim_polygraph_ng.telemetry import TelemetryCollector, parse_traceparent


class RetryableJobExecutionError(RuntimeError):
    """Execution failed transiently and may consume another bounded attempt."""


class PermanentJobExecutionError(RuntimeError):
    """Execution failed deterministically and must not retry."""


class JobCancelledAtBoundary(RuntimeError):
    """Execution observed cancellation at a declared safe node boundary."""


@dataclass(frozen=True)
class JobExecutionContext:
    """Operations available to authoritative workflow adapters."""

    queue: SQLiteJobQueue
    job_id: UUID
    worker_id: str

    def safe_boundary(self) -> None:
        job = self.queue.safe_boundary(self.job_id, self.worker_id)
        if job.status is JobStatus.CANCELLED:
            raise JobCancelledAtBoundary("job cancelled at safe node boundary")

    def reserve_paid_operation(self, operation_key: str) -> bool:
        return self.queue.begin_operation(self.job_id, operation_key)

    def complete_paid_operation(self, operation_key: str, result_reference: str) -> None:
        self.queue.complete_operation(
            self.job_id, operation_key, result_reference=result_reference
        )


JobExecutor = Callable[[DurableJob, JobExecutionContext], str]


class DurableJobWorker:
    """Claim one job and translate execution outcomes into durable transitions."""

    def __init__(
        self,
        queue: SQLiteJobQueue,
        worker_id: str,
        telemetry: TelemetryCollector | None = None,
    ) -> None:
        self._queue = queue
        self._worker_id = worker_id
        self._telemetry = telemetry

    def run_once(self, executor: JobExecutor) -> DurableJob | None:
        job = self._queue.claim(self._worker_id)
        if job is None:
            return None
        if self._telemetry is not None:
            parent = parse_traceparent(job.spec.traceparent)
            with self._telemetry.span(
                "job.execute",
                SpanKind.JOB,
                parent=parent,
                attributes={
                    "job.kind": job.spec.kind,
                    "job.provider": job.spec.provider,
                    "job.attempt": job.attempts,
                },
            ):
                queue_snapshot = self._queue.snapshot()
                self._telemetry.metric(
                    MetricName.JOB_QUEUE_DEPTH,
                    queue_snapshot.queued + queue_snapshot.retryable,
                    "jobs",
                )
                self._telemetry.metric(
                    MetricName.JOB_WAIT_MS,
                    (datetime.now(UTC) - job.created_at).total_seconds() * 1_000,
                    "ms",
                )
                return self._execute_claimed(job, executor)
        return self._execute_claimed(job, executor)

    def _execute_claimed(self, job: DurableJob, executor: JobExecutor) -> DurableJob:
        context = JobExecutionContext(self._queue, job.job_id, self._worker_id)
        try:
            result_reference = executor(job, context)
            context.safe_boundary()
            return self._queue.complete(
                job.job_id,
                self._worker_id,
                result_reference=result_reference,
            )
        except JobCancelledAtBoundary:
            return self._queue.load(job.job_id)
        except RetryableJobExecutionError as error:
            if self._telemetry is not None:
                self._telemetry.metric(
                    MetricName.JOB_FAILURE,
                    1,
                    "failure",
                    attributes={"failure.class": "transient"},
                )
            return self._queue.fail(
                job.job_id,
                self._worker_id,
                classification=JobFailureClass.TRANSIENT,
                error=str(error),
            )
        except PermanentJobExecutionError as error:
            if self._telemetry is not None:
                self._telemetry.metric(
                    MetricName.JOB_FAILURE,
                    1,
                    "failure",
                    attributes={"failure.class": "permanent"},
                )
            return self._queue.fail(
                job.job_id,
                self._worker_id,
                classification=JobFailureClass.PERMANENT,
                error=str(error),
            )
