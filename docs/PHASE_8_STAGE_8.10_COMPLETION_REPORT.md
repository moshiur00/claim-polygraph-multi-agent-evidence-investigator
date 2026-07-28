# Phase 8 Stage 8.10 completion report

Date: 28 July 2026

Status: Complete — SQLite retained for bounded local MVP

## Scope and target

This stage tested persistence only and made no model, search, network or PDF
calls. The frozen target represents a single-host portfolio MVP:

| Dimension | Target |
|---|---:|
| API worker processes | 4 |
| Simultaneous investigations | 8 |
| Writes per investigation | 25 |
| Competing review writers | 4 |
| Simultaneous LangGraph runs | 8 |
| Maximum P95 write latency | 500 ms |

## Implementation

A shared SQLite runtime policy now enables foreign keys, a 10-second busy
timeout, WAL journal mode and normal synchronous durability. Investigation,
research and review repositories and the LangGraph checkpointer use that
policy.

Review-ledger mutations now begin an immediate transaction before checking the
expected audit sequence. This serializes competing writers and turns stale
writes into typed `ReviewConcurrencyError` outcomes instead of admitting two
winners.

The reproducible gate concurrently exercises writes, review sequence
contention and independent LangGraph connections. It closes the graph
connections, opens new ones and compares typed reconstructed snapshots.

## Recorded result

| Check | Result |
|---|---:|
| Journal mode | WAL |
| Successful writes | 200 / 200 |
| Lock/busy errors | 0 |
| P95 write latency | 5.802 ms |
| Review sequence winners | 1 |
| Clean stale conflicts | 3 / 3 |
| Review hash chain | Valid |
| Checkpoint runs | 8 / 8 |
| Restart-identical snapshots | 8 / 8 |
| Checkpoint integrity errors | 0 |

All frozen checks passed. ADR 0016 therefore retains SQLite for this bounded
single-host MVP. It requires PostgreSQL reconsideration for multi-host writes,
larger concurrency, observed lock errors, sustained P95 latency above 500 ms,
stronger operational database requirements or cross-host job leasing.

## Limits

The write test uses four real worker processes. Review and LangGraph races use
independent connections across concurrent threads to test their application
objects. This is not a long-duration soak test, filesystem-failure test or
multi-host test. WAL does not turn SQLite into a distributed database. Stage
8.11 must independently decide whether durable jobs require a distributed
queue and PostgreSQL-backed leases.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/run_phase8_sqlite_concurrency_gate.py
.\.venv\Scripts\python.exe -m pytest tests/integration/test_sqlite_concurrency_gate.py -q
```

Recorded artifact:
`artifacts/evaluations/phase8-stage8.10-sqlite-concurrency-v1.json`.
