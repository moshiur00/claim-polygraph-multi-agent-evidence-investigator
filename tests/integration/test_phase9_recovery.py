"""Stage 9.11 deterministic recovery and failure-injection gate."""

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from time import sleep

import pytest
from fastapi.testclient import TestClient

from claim_polygraph_ng.api import ApiDependencies, create_app
from claim_polygraph_ng.application.investigation_service import InvestigationService
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.domain import ReviewDecision, ReviewDecisionKind
from claim_polygraph_ng.domain.jobs import (
    JobAdmissionPolicy,
    JobSpec,
    JobStatus,
)
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.persistence.authoritative_graph import (
    AuthoritativeCheckpointCorruptionError,
    SQLiteAuthoritativeGraphCheckpointRepository,
)
from claim_polygraph_ng.persistence.jobs import SQLiteJobQueue
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
    SearchProviderError,
)


class _FailOnceResearchService(InvestigationService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.failures_remaining = 1

    async def execute_research(self, *args, **kwargs):
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise SearchProviderError("injected transient provider failure")
        return await super().execute_research(*args, **kwargs)


class _ReviewRoutedService(InvestigationService):
    @staticmethod
    def route_review(verdict, readiness, assurance):
        return True


def _workflow(tmp_path, *, service_type=InvestigationService):
    investigations = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    reviews = SQLiteReviewLedger(tmp_path / "reviews.db")
    service = service_type(
        repository=investigations,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    workflow = AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "langgraph.db",
        state_checkpoint_path=tmp_path / "state.db",
        review_ledger=reviews,
    )
    return workflow, service, investigations, reviews


def test_transient_provider_failure_resumes_unfinished_node_without_replay(tmp_path):
    workflow, service, _, _ = _workflow(
        tmp_path, service_type=_FailOnceResearchService
    )
    thread_id = "provider-recovery-thread"

    with pytest.raises(SearchProviderError, match="injected"):
        asyncio.run(workflow.start("The fixture claim is true.", thread_id=thread_id))
    before = workflow.latest_state(thread_id)
    assert before is not None
    completed_before = before.completed_operations

    recovered = asyncio.run(
        workflow.start("The fixture claim is true.", thread_id=thread_id)
    )

    assert service.failures_remaining == 0
    assert recovered.state.checkpoint_sequence > before.checkpoint_sequence
    assert recovered.state.completed_operations[: len(completed_before)] == completed_before
    assert len(set(recovered.state.completed_operations)) == len(
        recovered.state.completed_operations
    )


def test_durable_api_retries_transient_provider_failure_once(tmp_path):
    workflow, service, investigations, reviews = _workflow(
        tmp_path, service_type=_FailOnceResearchService
    )
    queue = SQLiteJobQueue(tmp_path / "jobs.db", JobAdmissionPolicy())
    app = create_app(
        ApiDependencies(
            investigations=investigations,
            reviews=reviews,
            graph_checkpoint_path=tmp_path / "legacy.db",
            investigate=service.investigate,
            job_queue=queue,
            authoritative_workflow=workflow,
        )
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/authoritative-jobs",
            json={"claim": "The fixture claim is true.", "idempotency_key": "retry-once"},
        ).json()
        job_id = created["job"]["job_id"]
        current = created
        for _ in range(250):
            current = client.get(f"/api/authoritative-jobs/{job_id}").json()
            if current["job"]["status"] in {
                "interrupted",
                "completed",
                "failed",
                "dead_letter",
            }:
                break
            sleep(0.02)

    assert current["job"]["status"] in {"interrupted", "completed"}
    assert current["job"]["attempts"] == 2
    assert [event["action"] for event in current["events"]].count(
        "retry_scheduled"
    ) == 1


def test_process_restart_reconstructs_review_and_resumes_same_thread(tmp_path):
    first, _, investigations, reviews = _workflow(
        tmp_path, service_type=_ReviewRoutedService
    )
    pending = asyncio.run(
        first.start("The fixture claim is true.", thread_id="restart-review-thread")
    )
    assert pending.interrupt is not None
    operations_before = pending.state.completed_operations
    receipts_before = pending.state.paid_receipts

    restarted = AuthoritativeFixtureLangGraphWorkflow(
        service=_ReviewRoutedService(
            repository=investigations,
            model_provider=DeterministicModelProvider(),
            search_provider=DeterministicSearchProvider(),
        ),
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "langgraph.db",
        state_checkpoint_path=tmp_path / "state.db",
        review_ledger=reviews,
    )
    reconstructed = asyncio.run(
        restarted.start(
            "The fixture claim is true.", thread_id=pending.state.thread_id
        )
    )
    assert reconstructed.interrupt is not None
    assert reconstructed.state == pending.state

    completed = asyncio.run(
        restarted.resume(
            pending.state.thread_id,
            ReviewDecision(
                kind=ReviewDecisionKind.APPROVE,
                reviewer_identity="Recovery Reviewer",
                rationale="The restarted thread retains the reviewed evidence packet.",
            ),
            approver_identity="Distinct Recovery Approver",
        )
    )
    assert completed.state.phase.value == "complete"
    assert completed.state.completed_operations[: len(operations_before)] == operations_before
    assert completed.state.paid_receipts == receipts_before


def test_review_recovery_closes_job_after_graph_completed_before_api_ack(tmp_path):
    workflow, _, investigations, reviews = _workflow(
        tmp_path, service_type=_ReviewRoutedService
    )
    queue = SQLiteJobQueue(tmp_path / "jobs.db", JobAdmissionPolicy())
    queue.initialize()
    job = queue.enqueue(
        JobSpec(
            idempotency_key="review-ack-gap",
            kind="authoritative_langgraph_investigation",
            payload={
                "claim": "The fixture claim is true.",
                "thread_id": "review-ack-thread",
            },
        )
    ).job
    queue.claim("worker")
    pending = asyncio.run(
        workflow.start("The fixture claim is true.", thread_id="review-ack-thread")
    )
    queue.interrupt(job.job_id, "worker", reason=pending.interrupt.route_reason)
    decision = ReviewDecision(
        kind=ReviewDecisionKind.APPROVE,
        reviewer_identity="Recovery Reviewer",
        rationale="The decision must survive an acknowledgement crash window.",
    )
    completed = asyncio.run(
        workflow.resume(
            pending.state.thread_id,
            decision,
            approver_identity="Recovery Approver",
        )
    )
    assert completed.state.phase.value == "complete"
    assert queue.load(job.job_id).status is JobStatus.INTERRUPTED

    restarted = AuthoritativeFixtureLangGraphWorkflow(
        service=_ReviewRoutedService(
            repository=investigations,
            model_provider=DeterministicModelProvider(),
            search_provider=DeterministicSearchProvider(),
        ),
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "langgraph.db",
        state_checkpoint_path=tmp_path / "state.db",
        review_ledger=reviews,
    )
    replay = asyncio.run(
        restarted.resume(
            pending.state.thread_id,
            decision,
            approver_identity="Recovery Approver",
        )
    )
    closed = queue.complete_interrupted(
        job.job_id,
        actor="Recovery Reviewer",
        result_reference=pending.state.thread_id,
    )
    assert replay.state == completed.state
    assert closed.status is JobStatus.COMPLETED


def test_cancellation_stops_at_authoritative_checkpoint_boundary(tmp_path):
    workflow, _, _, _ = _workflow(tmp_path)
    queue = SQLiteJobQueue(tmp_path / "jobs.db", JobAdmissionPolicy())
    queue.initialize()
    job = queue.enqueue(
        JobSpec(
            idempotency_key="cancel-recovery",
            kind="authoritative_langgraph_investigation",
            payload={"claim": "The fixture claim is true.", "thread_id": "cancel-thread"},
            maximum_attempts=2,
        )
    ).job
    queue.claim("recovery-worker")
    boundaries = 0

    def cancel_on_second_boundary() -> None:
        nonlocal boundaries
        boundaries += 1
        if boundaries == 2:
            queue.request_cancellation(job.job_id, actor="Recovery Operator")
        current = queue.safe_boundary(job.job_id, "recovery-worker")
        if current.status is JobStatus.CANCELLED:
            raise RuntimeError("cancelled at injected checkpoint")

    with pytest.raises(RuntimeError, match="cancelled"):
        asyncio.run(
            workflow.start(
                "The fixture claim is true.",
                thread_id="cancel-thread",
                safe_boundary=cancel_on_second_boundary,
            )
        )
    assert queue.load(job.job_id).status is JobStatus.CANCELLED
    state = workflow.latest_state("cancel-thread")
    assert state is not None and state.checkpoint_sequence >= 2


def test_checkpoint_payload_tampering_fails_closed(tmp_path):
    workflow, _, _, _ = _workflow(tmp_path)
    result = asyncio.run(
        workflow.start("The fixture claim is true.", thread_id="corruption-thread")
    )
    database = tmp_path / "state.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE authoritative_graph_checkpoints
            SET payload = payload || ' '
            WHERE thread_id = ? AND sequence = ?
            """,
            (result.state.thread_id, result.state.checkpoint_sequence),
        )
        connection.commit()

    repository = SQLiteAuthoritativeGraphCheckpointRepository(database)
    with pytest.raises(AuthoritativeCheckpointCorruptionError, match="SHA-256"):
        repository.latest(result.state.thread_id)


def test_concurrent_submission_is_bounded_and_idempotent(tmp_path):
    queue = SQLiteJobQueue(
        tmp_path / "jobs.db",
        JobAdmissionPolicy(maximum_queue_depth=20, maximum_active_jobs=2),
    )
    queue.initialize()

    def admit(index: int):
        return queue.enqueue(
            JobSpec(
                idempotency_key=f"concurrent-{index % 4}",
                kind="authoritative_langgraph_investigation",
                payload={
                    "claim": f"Claim {index % 4}",
                    "thread_id": f"thread-{index % 4}",
                },
            )
        ).job

    with ThreadPoolExecutor(max_workers=8) as executor:
        jobs = tuple(executor.map(admit, range(16)))

    assert len({job.job_id for job in jobs}) == 4
    with ThreadPoolExecutor(max_workers=4) as executor:
        claimed = tuple(executor.map(lambda index: queue.claim(f"worker-{index}"), range(4)))
    assert len([job for job in claimed if job is not None]) == 2
