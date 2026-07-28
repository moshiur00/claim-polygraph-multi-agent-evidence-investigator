# Phase 8 Stage 8.11 completion report

Date: 28 July 2026

Status: Complete — durable database queue promoted for bounded local MVP

## Delivered behavior

The new typed durable-job layer sits outside `InvestigationOrchestrator` and
does not alter `InvestigationService` authority. A thin worker accepts an
adapter callback, exposes safe cancellation boundaries and operation
receipts, and durably translates completion or typed failures.

Implemented lifecycle:

`queued → running → completed`

Additional controlled paths:

- `running → interrupted → queued` for human review;
- `queued/retryable/interrupted → cancelled` immediately;
- `running → cancelling → cancelled` at a safe node boundary;
- `running → retryable → running` for bounded transient failures;
- `running → failed` for permanent, budget or invalid-input failures; and
- expired final lease or exhausted transient attempts → `dead_letter`.

## Backpressure and recovery

- Idempotency keys deduplicate repeated submissions.
- Queue depth is bounded and overflow is rejected.
- Claims obey global and per-provider concurrency limits.
- Worker leases expire and can be recovered after a crash.
- Audit events survive process restart.
- Paid-operation receipts survive retry and prevent duplicate calls.
- Completed evidence and artifacts are not deleted by cancellation.

## Recorded gate

| Check | Result |
|---|---:|
| Queue capacity | 32 |
| Concurrent submitters | 8 |
| Concurrent jobs admitted | 24 |
| Duplicate jobs created | 0 |
| Overflow rejected | Yes |
| Global active ceiling | 4 / 4 |
| Per-provider ceiling | 2 / 2 |
| P95 admission latency | 176.149 ms |
| Cancellation | Passed |
| Retry | Passed |
| Dead letter | Passed |
| Crash/lease recovery | Passed |
| Restart persistence | Passed |
| Duplicate paid operations | 0 |

The 500 ms latency ceiling and every correctness gate passed with no external
model, search, network or PDF calls.

## PostgreSQL decision

PostgreSQL is not necessary for the current single-host MVP. It is, however,
the recommended next adapter for a deployed multi-user or multi-host version.
The domain and worker contracts deliberately contain no SQLite-specific
types, so PostgreSQL can be added without rewriting the investigation
workflow.

A distributed queue is not currently justified. PostgreSQL-backed claims and
leases should be evaluated before introducing Redis. Redis becomes justified
only for measured broker throughput, delayed-delivery or distributed
rate-limit requirements.

## Verification

- 14 focused durable queue, worker and gate tests pass.
- The release gate is reproducible with:

```powershell
.\.venv\Scripts\python.exe scripts/run_phase8_job_backend_gate.py
```

Recorded result:
`artifacts/evaluations/phase8-stage8.11-job-backend-v1.json`.
