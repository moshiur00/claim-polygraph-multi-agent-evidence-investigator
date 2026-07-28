"""Stage 8.11 measured durable-job backend decision gate."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import quantiles
from time import perf_counter

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.jobs import (
    JobAdmissionPolicy,
    JobFailureClass,
    JobSpec,
    JobStatus,
)
from claim_polygraph_ng.persistence.jobs import JobBackpressureError, SQLiteJobQueue


class JobBackendTarget(DomainModel):
    queue_capacity: int = Field(default=32, ge=1)
    concurrent_submitters: int = Field(default=8, ge=1)
    admitted_jobs: int = Field(default=24, ge=1)
    global_active_limit: int = Field(default=4, ge=1)
    provider_active_limit: int = Field(default=2, ge=1)
    maximum_p95_admission_latency_ms: float = Field(default=500.0, gt=0)


class JobBackendGateResult(DomainModel):
    target: JobBackendTarget
    admitted_jobs: int
    duplicate_jobs_created: int
    overflow_rejected: bool
    maximum_observed_active: int
    maximum_observed_provider_active: int
    p95_admission_latency_ms: float
    cancellation_passed: bool
    retry_passed: bool
    dead_letter_passed: bool
    crash_recovery_passed: bool
    restart_passed: bool
    duplicate_paid_operations: int
    passed: bool
    postgresql_required_for_mvp: bool
    distributed_queue_required_for_mvp: bool
    decision: str
    failed_checks: tuple[str, ...] = ()


def run_job_backend_gate(
    directory: str | Path, *, target: JobBackendTarget | None = None
) -> JobBackendGateResult:
    workload = target or JobBackendTarget()
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    database = root / "durable-jobs.sqlite3"
    policy = JobAdmissionPolicy(
        maximum_queue_depth=workload.queue_capacity,
        maximum_active_jobs=workload.global_active_limit,
        default_provider_limit=workload.provider_active_limit,
    )
    queue = SQLiteJobQueue(database, policy)
    queue.initialize()

    def submit(index: int) -> tuple[float, bool]:
        started = perf_counter()
        result = queue.enqueue(
            JobSpec(
                idempotency_key=f"gate-job-{index}",
                kind="investigation",
                payload={"claim": f"Gate claim {index}"},
                provider=f"search-{index % 2}",
            )
        )
        return (perf_counter() - started) * 1_000, result.created

    with ThreadPoolExecutor(max_workers=workload.concurrent_submitters) as executor:
        submissions = list(executor.map(submit, range(workload.admitted_jobs)))
    latencies = [latency for latency, _created in submissions]

    duplicate_created = int(
        queue.enqueue(
            JobSpec(
                idempotency_key="gate-job-0",
                kind="investigation",
                payload={"claim": "Gate claim 0"},
                provider="search-0",
            )
        ).created
    )
    overflow_rejected = False
    for index in range(workload.admitted_jobs, workload.queue_capacity):
        queue.enqueue(
            JobSpec(
                idempotency_key=f"gate-job-{index}",
                kind="investigation",
                payload={"claim": f"Gate claim {index}"},
            provider="search-a",
            )
        )
    try:
        queue.enqueue(
            JobSpec(
                idempotency_key="gate-overflow",
                kind="investigation",
                payload={"claim": "Must be rejected"},
                provider="search",
            )
        )
    except JobBackpressureError:
        overflow_rejected = True

    with ThreadPoolExecutor(max_workers=workload.concurrent_submitters) as executor:
        claims = list(executor.map(lambda index: queue.claim(f"worker-{index}"), range(8)))
    active = [job for job in claims if job is not None]
    maximum_active = len(active)
    maximum_provider = max(Counter(job.spec.provider for job in active).values())

    cancellation_job = active[0]
    queue.request_cancellation(cancellation_job.job_id, actor="gate")
    cancellation_passed = (
        queue.safe_boundary(cancellation_job.job_id, cancellation_job.lease_owner or "").status
        is JobStatus.CANCELLED
    )

    retry_job = active[1]
    retry_passed = (
        queue.fail(
            retry_job.job_id,
            retry_job.lease_owner or "",
            classification=JobFailureClass.TRANSIENT,
            error="injected timeout",
        ).status
        is JobStatus.RETRYABLE
    )

    recovery_queue = SQLiteJobQueue(root / "recovery-jobs.sqlite3", policy)
    recovery_queue.initialize()
    dead_spec = JobSpec(
        idempotency_key="dead-letter-fixture",
        kind="investigation",
        payload={"claim": "Crash fixture"},
        provider="academic",
        maximum_attempts=1,
    )
    dead_job = recovery_queue.enqueue(dead_spec).job
    claimed_dead = recovery_queue.claim("crashed-dead", lease_seconds=1)
    assert claimed_dead is not None and claimed_dead.job_id == dead_job.job_id
    future = datetime.now(UTC) + timedelta(seconds=2)
    recovered = recovery_queue.recover_expired_leases(now=future)
    dead_letter_passed = any(job.status is JobStatus.DEAD_LETTER for job in recovered)

    crash_spec = JobSpec(
        idempotency_key="recovery-fixture",
        kind="investigation",
        payload={"claim": "Recovery fixture"},
        provider="fact_check",
    )
    crash_job = recovery_queue.enqueue(crash_spec).job
    claimed_crash = recovery_queue.claim("crashed-worker", lease_seconds=1, now=future)
    if claimed_crash is None:
        crash_recovery_passed = False
        duplicate_paid_operations = 1
    else:
        first_operation = recovery_queue.begin_operation(
            claimed_crash.job_id, "provider-call-1"
        )
        recovery_queue.complete_operation(
            claimed_crash.job_id,
            "provider-call-1",
            result_reference="evidence/fixture.json",
        )
        later = future + timedelta(seconds=2)
        recovered_again = recovery_queue.recover_expired_leases(now=later)
        crash_recovery_passed = any(
            job.job_id == claimed_crash.job_id and job.status is JobStatus.RETRYABLE
            for job in recovered_again
        )
        repeated_operation = recovery_queue.begin_operation(
            claimed_crash.job_id, "provider-call-1"
        )
        duplicate_paid_operations = int(not first_operation) + int(repeated_operation)

    restarted = SQLiteJobQueue(root / "recovery-jobs.sqlite3", policy)
    restarted.initialize()
    restart_passed = restarted.load(crash_job.job_id).job_id == crash_job.job_id

    p95 = quantiles(latencies, n=20, method="inclusive")[18]
    checks = {
        "admission lost a job": all(created for _latency, created in submissions),
        "idempotency created a duplicate": duplicate_created == 0,
        "overflow was not rejected": overflow_rejected,
        "global active limit was violated": maximum_active <= workload.global_active_limit,
        "provider limit was violated": maximum_provider <= workload.provider_active_limit,
        "admission latency exceeded target": p95
        <= workload.maximum_p95_admission_latency_ms,
        "cooperative cancellation failed": cancellation_passed,
        "retry scheduling failed": retry_passed,
        "dead-letter transition failed": dead_letter_passed,
        "crash recovery failed": crash_recovery_passed,
        "restart persistence failed": restart_passed,
        "a paid operation was duplicated": duplicate_paid_operations == 0,
    }
    failed = tuple(message for message, outcome in checks.items() if not outcome)
    passed = not failed
    return JobBackendGateResult(
        target=workload,
        admitted_jobs=sum(created for _latency, created in submissions),
        duplicate_jobs_created=duplicate_created,
        overflow_rejected=overflow_rejected,
        maximum_observed_active=maximum_active,
        maximum_observed_provider_active=maximum_provider,
        p95_admission_latency_ms=round(p95, 3),
        cancellation_passed=cancellation_passed,
        retry_passed=retry_passed,
        dead_letter_passed=dead_letter_passed,
        crash_recovery_passed=crash_recovery_passed,
        restart_passed=restart_passed,
        duplicate_paid_operations=duplicate_paid_operations,
        passed=passed,
        postgresql_required_for_mvp=not passed,
        distributed_queue_required_for_mvp=False,
        decision=(
            "Retain the SQLite database-backed queue for the bounded single-host MVP; "
            "prefer PostgreSQL when multi-host leasing or production operations are required."
            if passed
            else "Do not promote the SQLite job backend; implement PostgreSQL and rerun."
        ),
        failed_checks=failed,
    )
