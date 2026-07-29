"""Measured SQLite suitability gate for the single-host MVP."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from contextlib import closing
from pathlib import Path
from statistics import quantiles
from time import perf_counter
from uuid import uuid4

from pydantic import Field

from claim_polygraph_ng.application.langgraph_durable import (
    DurableFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.graph import FixtureGraphRequest
from claim_polygraph_ng.domain.models import VerdictLabel
from claim_polygraph_ng.domain.review import (
    ReviewFinding,
    ReviewFindingKind,
    ReviewRequest,
)
from claim_polygraph_ng.persistence.review import (
    ReviewConcurrencyError,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.persistence.sqlite_runtime import connect_sqlite, enable_wal


class SQLiteMvpConcurrencyTarget(DomainModel):
    """The bounded workload supported by the local MVP."""

    api_worker_processes: int = 4
    simultaneous_investigations: int = 8
    writes_per_investigation: int = 25
    competing_review_writers: int = 4
    simultaneous_graph_runs: int = 8
    maximum_p95_write_latency_ms: float = 500.0


class SQLiteConcurrencyGateResult(DomainModel):
    """Auditable measurements and the resulting persistence decision."""

    target: SQLiteMvpConcurrencyTarget
    journal_mode: str
    attempted_writes: int
    successful_writes: int
    locked_errors: int
    p95_write_latency_ms: float
    review_successes: int
    review_clean_conflicts: int
    review_chain_valid: bool
    checkpoint_runs: int
    checkpoint_restart_matches: int
    checkpoint_integrity_errors: int
    checkpoint_error_messages: tuple[str, ...] = ()
    passed: bool
    decision: str = Field(min_length=3)
    failed_checks: tuple[str, ...] = ()


def _write_investigation_process(
    database: str, investigation_index: int, writes: int
) -> tuple[list[float], int]:
    """Execute a writer in a separate process for a real file-lock test."""
    own_latencies: list[float] = []
    own_errors = 0
    investigation_id = f"gate-{investigation_index}"
    for sequence in range(writes):
        started = perf_counter()
        try:
            with closing(connect_sqlite(database)) as connection:
                connection.execute(
                    "INSERT INTO writes VALUES (?, ?, ?)",
                    (investigation_id, sequence, f"payload-{sequence}"),
                )
                connection.commit()
        except Exception as exc:  # measured and reported, never hidden
            if "locked" in str(exc).casefold() or "busy" in str(exc).casefold():
                own_errors += 1
            else:
                raise
        own_latencies.append((perf_counter() - started) * 1_000)
    return own_latencies, own_errors


def run_sqlite_concurrency_gate(
    directory: str | Path,
    *,
    target: SQLiteMvpConcurrencyTarget | None = None,
) -> SQLiteConcurrencyGateResult:
    """Run the bounded, zero-provider concurrency and recovery evaluation."""
    workload = target or SQLiteMvpConcurrencyTarget()
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)

    write_db = root / "write-contention.sqlite3"
    with closing(connect_sqlite(str(write_db))) as connection:
        enable_wal(connection)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS writes "
            "(investigation_id TEXT NOT NULL, sequence INTEGER NOT NULL, "
            "payload TEXT NOT NULL, PRIMARY KEY (investigation_id, sequence))"
        )
        connection.commit()

    latencies: list[float] = []
    locked_errors = 0

    with ProcessPoolExecutor(max_workers=workload.api_worker_processes) as executor:
        futures = [
            executor.submit(
                _write_investigation_process,
                str(write_db),
                index,
                workload.writes_per_investigation,
            )
            for index in range(workload.simultaneous_investigations)
        ]
        for future in as_completed(futures):
            observed, errors = future.result()
            latencies.extend(observed)
            locked_errors += errors

    attempted = workload.simultaneous_investigations * workload.writes_per_investigation
    with closing(connect_sqlite(str(write_db))) as connection:
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        successful = int(connection.execute("SELECT COUNT(*) FROM writes").fetchone()[0])

    review_db = root / "review-contention.sqlite3"
    ledger = SQLiteReviewLedger(review_db)
    ledger.initialize()
    request = ledger.create_request(
        ReviewRequest(
            investigation_id=uuid4(),
            graph_thread_id=str(uuid4()),
            claim_id=uuid4(),
            reason="Concurrency gate review request.",
            created_by="Stage 8.10 gate",
        )
    )

    def compete_for_review(index: int) -> str:
        contender = SQLiteReviewLedger(review_db)
        try:
            contender.add_finding(
                ReviewFinding(
                    request_id=request.request_id,
                    kind=ReviewFindingKind.OTHER,
                    summary=f"Concurrent finding number {index}.",
                    recorded_by=f"Gate reviewer {index}",
                ),
                expected_sequence=1,
            )
            return "success"
        except ReviewConcurrencyError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=workload.competing_review_writers) as executor:
        review_outcomes = list(
            executor.map(compete_for_review, range(workload.competing_review_writers))
        )
    trail = SQLiteReviewLedger(review_db).load(request.request_id)

    graph_db = root / "graph-checkpoints.sqlite3"
    # Initialize LangGraph's shared checkpoint schema before concurrent workers
    # begin. Production startup owns this migration boundary; allowing every
    # worker to race schema creation measures a deployment bug, not WAL writes.
    with DurableFixtureLangGraphWorkflow(graph_db, enabled=True):
        pass
    requests = [
        FixtureGraphRequest(
            claim_text=f"Concurrency fixture claim {index}.",
            approved_evidence_ids=(uuid4(),),
            authoritative_verdict=VerdictLabel.SUPPORTED,
        )
        for index in range(workload.simultaneous_graph_runs)
    ]

    def run_graph(request_: FixtureGraphRequest) -> tuple[str, object]:
        with DurableFixtureLangGraphWorkflow(graph_db, enabled=True) as workflow:
            snapshot = workflow.start(request_)
        return str(request_.graph_run_id), snapshot

    checkpoint_errors = 0
    checkpoint_error_messages: list[str] = []
    originals: dict[str, object] = {}
    with ThreadPoolExecutor(max_workers=workload.simultaneous_graph_runs) as executor:
        futures = [executor.submit(run_graph, request_) for request_ in requests]
        for future in as_completed(futures):
            try:
                thread_id, snapshot = future.result()
                originals[thread_id] = snapshot
            except Exception as exc:
                checkpoint_errors += 1
                checkpoint_error_messages.append(f"{type(exc).__name__}: {exc}")

    restart_matches = 0
    for thread_id, original in originals.items():
        try:
            with DurableFixtureLangGraphWorkflow(graph_db, enabled=True) as restarted:
                restart_matches += restarted.snapshot(thread_id) == original
        except Exception as exc:
            checkpoint_errors += 1
            checkpoint_error_messages.append(f"{type(exc).__name__}: {exc}")

    p95 = quantiles(latencies, n=20, method="inclusive")[18] if len(latencies) > 1 else 0
    review_successes = review_outcomes.count("success")
    review_conflicts = review_outcomes.count("conflict")
    failed: list[str] = []
    checks = {
        "WAL mode was not active": journal_mode.casefold() == "wal",
        "a write was lost": successful == attempted,
        "SQLite returned lock/busy errors": locked_errors == 0,
        "write latency exceeded the MVP ceiling": p95 <= workload.maximum_p95_write_latency_ms,
        "review sequence admitted multiple winners": review_successes == 1,
        "stale review writers were not cleanly rejected": (
            review_conflicts == workload.competing_review_writers - 1
        ),
        "review audit chain failed validation": trail.chain_valid,
        "checkpoint execution or integrity failed": checkpoint_errors == 0,
        "restart reconstruction differed": restart_matches == workload.simultaneous_graph_runs,
    }
    failed.extend(message for message, outcome in checks.items() if not outcome)
    passed = not failed
    return SQLiteConcurrencyGateResult(
        target=workload,
        journal_mode=journal_mode,
        attempted_writes=attempted,
        successful_writes=successful,
        locked_errors=locked_errors,
        p95_write_latency_ms=round(p95, 3),
        review_successes=review_successes,
        review_clean_conflicts=review_conflicts,
        review_chain_valid=trail.chain_valid,
        checkpoint_runs=len(originals),
        checkpoint_restart_matches=restart_matches,
        checkpoint_integrity_errors=checkpoint_errors,
        checkpoint_error_messages=tuple(checkpoint_error_messages),
        passed=passed,
        decision=(
            "Retain SQLite WAL for the bounded single-host MVP."
            if passed
            else "Migrate the affected persistence path to PostgreSQL before MVP promotion."
        ),
        failed_checks=tuple(failed),
    )
