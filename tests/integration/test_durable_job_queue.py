"""Stage 8.11 durable jobs, recovery, cancellation and backpressure."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from claim_polygraph_ng.domain.jobs import (
    JobAdmissionPolicy,
    JobAuditAction,
    JobFailureClass,
    JobSpec,
    JobStatus,
)
from claim_polygraph_ng.persistence.jobs import (
    JobBackpressureError,
    JobLeaseError,
    JobStateError,
    SQLiteJobQueue,
)


def _queue(tmp_path, **policy) -> SQLiteJobQueue:
    queue = SQLiteJobQueue(
        tmp_path / "jobs.sqlite3",
        JobAdmissionPolicy(**policy),
    )
    queue.initialize()
    return queue


def _spec(index: int = 1, *, provider: str = "search", attempts: int = 3) -> JobSpec:
    return JobSpec(
        idempotency_key=f"investigation-{index}",
        kind="investigation",
        payload={"claim": f"Claim {index}"},
        provider=provider,
        maximum_attempts=attempts,
    )


def test_enqueue_is_idempotent_and_queue_admission_is_bounded(tmp_path) -> None:
    queue = _queue(tmp_path, maximum_queue_depth=2)
    first = queue.enqueue(_spec(1))
    replay = queue.enqueue(_spec(1))
    queue.enqueue(_spec(2))

    assert first.created
    assert not replay.created
    assert replay.job.job_id == first.job.job_id
    with pytest.raises(JobBackpressureError, match="capacity"):
        queue.enqueue(_spec(3))


def test_global_and_provider_claim_limits_apply_under_contention(tmp_path) -> None:
    queue = _queue(
        tmp_path,
        maximum_active_jobs=3,
        default_provider_limit=2,
        provider_limits={"academic": 1},
    )
    queue.enqueue(_spec(1, provider="academic"))
    queue.enqueue(_spec(2, provider="academic"))
    queue.enqueue(_spec(3, provider="search"))
    queue.enqueue(_spec(4, provider="search"))

    with ThreadPoolExecutor(max_workers=4) as executor:
        claimed = list(executor.map(lambda index: queue.claim(f"worker-{index}"), range(4)))
    active = [job for job in claimed if job is not None]

    assert len(active) == 3
    assert sum(job.spec.provider == "academic" for job in active) == 1
    assert sum(job.spec.provider == "search" for job in active) == 2
    assert queue.snapshot().running == 3


def test_running_cancellation_stops_only_at_safe_boundary(tmp_path) -> None:
    queue = _queue(tmp_path)
    job = queue.enqueue(_spec()).job
    running = queue.claim("worker-1")
    assert running is not None

    cancelling = queue.request_cancellation(job.job_id, actor="operator")
    assert cancelling.status is JobStatus.CANCELLING
    with pytest.raises(JobStateError, match="safe boundary"):
        queue.complete(job.job_id, "worker-1", result_reference="report.md")

    cancelled = queue.safe_boundary(job.job_id, "worker-1")
    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.lease_owner is None
    assert [event.action for event in queue.audit_events(job.job_id)][-2:] == [
        JobAuditAction.CANCELLATION_REQUESTED,
        JobAuditAction.CANCELLED,
    ]


def test_queued_and_interrupted_cancellation_is_immediate(tmp_path) -> None:
    queue = _queue(tmp_path)
    queued = queue.enqueue(_spec(1)).job
    assert queue.request_cancellation(queued.job_id, actor="operator").status is JobStatus.CANCELLED

    interrupted = queue.enqueue(_spec(2)).job
    queue.claim("worker")
    queue.interrupt(interrupted.job_id, "worker", reason="human review")
    assert queue.request_cancellation(
        interrupted.job_id, actor="reviewer"
    ).status is JobStatus.CANCELLED


def test_interrupt_resume_and_restart_preserve_state(tmp_path) -> None:
    database = tmp_path / "jobs.sqlite3"
    policy = JobAdmissionPolicy()
    first = SQLiteJobQueue(database, policy)
    first.initialize()
    job = first.enqueue(_spec()).job
    first.claim("worker")
    interrupted = first.interrupt(job.job_id, "worker", reason="human review")

    restarted = SQLiteJobQueue(database, policy)
    restarted.initialize()
    assert restarted.load(job.job_id) == interrupted
    restarted.resume(job.job_id, actor="reviewer")
    reclaimed = restarted.claim("new-worker")
    assert reclaimed is not None
    assert reclaimed.job_id == job.job_id
    assert reclaimed.attempts == 2


def test_transient_retry_exhaustion_moves_to_dead_letter(tmp_path) -> None:
    queue = _queue(tmp_path)
    job = queue.enqueue(_spec(attempts=2)).job
    queue.claim("first")
    retryable = queue.fail(
        job.job_id,
        "first",
        classification=JobFailureClass.TRANSIENT,
        error="provider timeout",
    )
    assert retryable.status is JobStatus.RETRYABLE
    queue.claim("second")
    dead = queue.fail(
        job.job_id,
        "second",
        classification=JobFailureClass.TRANSIENT,
        error="provider timeout again",
    )
    assert dead.status is JobStatus.DEAD_LETTER
    assert queue.claim("third") is None


def test_permanent_failure_does_not_retry(tmp_path) -> None:
    queue = _queue(tmp_path)
    job = queue.enqueue(_spec()).job
    queue.claim("worker")
    failed = queue.fail(
        job.job_id,
        "worker",
        classification=JobFailureClass.INVALID_INPUT,
        error="invalid claim",
    )
    assert failed.status is JobStatus.FAILED


def test_expired_lease_recovers_without_repeating_paid_operation(tmp_path) -> None:
    queue = _queue(tmp_path)
    job = queue.enqueue(_spec()).job
    claimed = queue.claim("crashed-worker", lease_seconds=1)
    assert claimed is not None
    assert queue.begin_operation(job.job_id, "search:query-1")
    queue.complete_operation(
        job.job_id, "search:query-1", result_reference="evidence/search-1.json"
    )

    recovery_time = datetime.now(UTC) + timedelta(seconds=2)
    recovered = queue.recover_expired_leases(now=recovery_time)
    assert recovered[0].status is JobStatus.RETRYABLE
    assert not queue.begin_operation(job.job_id, "search:query-1")
    reclaimed = queue.claim("replacement-worker", now=recovery_time)
    assert reclaimed is not None
    assert reclaimed.attempts == 2


def test_expired_final_attempt_is_dead_lettered(tmp_path) -> None:
    queue = _queue(tmp_path)
    queue.enqueue(_spec(attempts=1))
    queue.claim("crashed", lease_seconds=1)
    recovered = queue.recover_expired_leases(
        now=datetime.now(UTC) + timedelta(seconds=2)
    )
    assert recovered[0].status is JobStatus.DEAD_LETTER


def test_wrong_worker_cannot_mutate_lease(tmp_path) -> None:
    queue = _queue(tmp_path)
    job = queue.enqueue(_spec()).job
    queue.claim("owner")
    with pytest.raises(JobLeaseError):
        queue.renew_lease(job.job_id, "intruder")
