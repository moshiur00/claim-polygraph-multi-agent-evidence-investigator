# Phase 9 Stage 9.3 completion report

Date: 29 July 2026

Status: Complete

## Outcome

The unified authoritative workflow now has a versioned durable state contract:
`AuthoritativeInvestigationGraphState` schema version 1 and graph version
`authoritative-investigation-graph-v1`.

The state stores references rather than evidence passages or full reports. It
covers investigation and component identity, phase, completed operations,
artifacts, research requirements, assignments and results, evidence families,
approved evidence, defender/challenger results, argument and verdict artifacts,
citation assurance, readiness, review records, budgets and consumption, paid
operation receipts, unresolved questions, failures and the final report.

## Checkpoint policy

The SQLite repository stores append-only `(thread_id, sequence)` checkpoints in
WAL mode. A new checkpoint is compared with the latest durable state before it
is committed. Duplicate sequences and non-monotonic updates are rejected.

Twelve enforced invariants include:

- Immutable graph identity and version.
- Exactly incremental checkpoint sequence.
- No disappearance of completed operations, artifacts or approved evidence.
- Append-only receipts, reviews and failures.
- Non-decreasing cost, token, call, page, duration and round consumption.
- Immutable final report identity.
- No transition from terminal state.
- Successful reconstruction of every artifact reference.

Human requests for more evidence may route from review back to research.
Completed work and consumption still remain monotonic during that loop.

## Migration and reconstruction

Existing `DurableMultiAgentGraphState` payloads migrate deterministically to the
new v1 envelope. Stored source and evidence IDs become artifact references;
research assignments, results, evidence families, budget, consumption and
unresolved questions are retained. Unsupported future versions fail closed.

Reconstruction performs schema migration, cross-reference validation and an
authoritative artifact-existence check. Missing artifacts block resume rather
than allowing a node to operate on incomplete state.

## Scope boundary

This stage defines and persists state but does not replace the current
LangGraph topology. Stage 9.4 will make nodes consume and emit this state.
Paid-operation receipt status is represented, while its atomic provider ledger
is intentionally deferred to Stage 9.5.

## Cost

No model, search, network or PDF calls were made.

## Exit decision

Stage 9.3 passes when schema hashing, migration, append-only persistence,
monotonic transitions, artifact reconstruction, restart loading, tests and
release hashes verify. The authoritative fixture graph can now be built.
