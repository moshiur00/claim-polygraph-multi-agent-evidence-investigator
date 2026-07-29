# Phase 9 Stage 9.11 — Recovery and failure injection

## Outcome

The unified authoritative workflow now passes deterministic failure injection
for transient providers, cancellation, restart, concurrent admission,
checkpoint corruption, review acknowledgement loss and SSE reconnection.

## Recovery guarantees

- A transient search or unavailable-model failure is retried once by the
  durable job. The graph continues the unfinished node from its LangGraph
  checkpoint instead of returning an incomplete snapshot.
- Completed operation references and paid-operation receipts are retained
  across restart and are not repeated.
- Cancellation is inspected after each authoritative durable operation.
  Persisted work remains available, while the job becomes terminally cancelled
  at the first safe boundary.
- Concurrent submissions remain bounded by global and provider limits.
  Repeated idempotency keys resolve to one job and one graph thread.
- Authoritative state checkpoints include a SHA-256 integrity value. Payload
  tampering, invalid state and non-contiguous history fail closed.
- If the graph commits a review decision but the API process dies before
  acknowledging job completion, replaying the same immutable decision
  reconstructs the completed graph and safely closes the original job.
- SSE reconnect accepts `Last-Event-ID` and emits only later authoritative
  checkpoints plus the current state snapshot.

## Compatibility

Checkpoint tables created before Stage 9.11 are migrated by adding a nullable
integrity column. Existing un-hashed records remain readable; all newly written
checkpoints are hashed. Direct rollback and existing read endpoints are
unchanged.

## Validation scope

The gate runs entirely with deterministic providers. It performs no external
model calls, live searches, network fetches or PDF downloads.
