"""Durable worker translation around authoritative workflow adapters."""

from claim_polygraph_ng.application.job_worker import (
    DurableJobWorker,
    PermanentJobExecutionError,
    RetryableJobExecutionError,
)
from claim_polygraph_ng.domain.jobs import JobAdmissionPolicy, JobSpec, JobStatus
from claim_polygraph_ng.persistence.jobs import SQLiteJobQueue


def _queue(tmp_path) -> SQLiteJobQueue:
    queue = SQLiteJobQueue(tmp_path / "worker.sqlite3", JobAdmissionPolicy())
    queue.initialize()
    return queue


def _enqueue(queue: SQLiteJobQueue, index: int = 1):
    return queue.enqueue(
        JobSpec(
            idempotency_key=f"worker-{index}",
            kind="investigation",
            payload={"claim": "A bounded fixture claim."},
        )
    ).job


def test_worker_completes_adapter_and_records_paid_operation_once(tmp_path) -> None:
    queue = _queue(tmp_path)
    job = _enqueue(queue)

    def execute(_job, context):
        assert context.reserve_paid_operation("model:decompose")
        context.complete_paid_operation("model:decompose", "artifacts/decomposition.json")
        return "artifacts/report.md"

    completed = DurableJobWorker(queue, "worker-1").run_once(execute)
    assert completed is not None
    assert completed.status is JobStatus.COMPLETED
    assert completed.result_reference == "artifacts/report.md"
    assert not queue.begin_operation(job.job_id, "model:decompose")


def test_worker_honours_cooperative_cancellation(tmp_path) -> None:
    queue = _queue(tmp_path)
    job = _enqueue(queue)

    def execute(_job, context):
        queue.request_cancellation(job.job_id, actor="operator")
        context.safe_boundary()
        raise AssertionError("execution continued after cancellation")

    cancelled = DurableJobWorker(queue, "worker-1").run_once(execute)
    assert cancelled is not None
    assert cancelled.status is JobStatus.CANCELLED


def test_worker_classifies_retryable_and_permanent_failures(tmp_path) -> None:
    queue = _queue(tmp_path)
    _enqueue(queue, 1)
    retryable = DurableJobWorker(queue, "worker-1").run_once(
        lambda _job, _context: (_ for _ in ()).throw(
            RetryableJobExecutionError("timeout")
        )
    )
    assert retryable is not None
    assert retryable.status is JobStatus.RETRYABLE

    permanent_queue = SQLiteJobQueue(
        tmp_path / "permanent.sqlite3", JobAdmissionPolicy()
    )
    permanent_queue.initialize()
    _enqueue(permanent_queue, 2)
    permanent = DurableJobWorker(permanent_queue, "worker-2").run_once(
        lambda _job, _context: (_ for _ in ()).throw(
            PermanentJobExecutionError("invalid input")
        )
    )
    assert permanent is not None
    assert permanent.status is JobStatus.FAILED
