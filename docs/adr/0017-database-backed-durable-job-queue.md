# ADR 0017: Use a database-backed durable queue and defer distributed queuing

Date: 28 July 2026

Status: Accepted by measured Stage 8.11 gate

## Context

The investigation workflow previously ran synchronously. Its internal
semaphores and provider retries did not provide durable admission,
cross-process leases, crash recovery, cooperative cancellation or bounded
backpressure.

Stage 8.11 introduced a provider-neutral job contract and a SQLite adapter.
The contract supports queued, running, interrupted, cancelling, cancelled,
completed, failed, retryable and dead-letter states. It also defines:

- unique idempotency keys;
- expiring worker leases and lease renewal;
- bounded attempts and typed failure classification;
- safe-node cancellation;
- global and per-provider active-job limits;
- bounded queue admission;
- restart-persistent audit events; and
- operation receipts that prevent a paid provider operation from being
  repeated after retry or worker failure.

The frozen local target is a queue of 32 jobs, eight concurrent submitters,
four active jobs globally and two active jobs per provider.

## Decision

Use the database-backed job contract. Retain its SQLite implementation for the
bounded single-host MVP. A distributed queue such as Redis is not required at
this target.

PostgreSQL is the preferred next persistence adapter when the application
moves from a local portfolio MVP to a deployed multi-user or multi-host
service. It is not required merely to complete the current phase.

Implement the PostgreSQL adapter before production promotion when any of
these becomes a committed requirement:

- workers run on more than one host;
- queue claims need database-native row locking such as `SKIP LOCKED`;
- sustained admission or claim load exceeds the Stage 8.10/8.11 SQLite gate;
- high availability, replication, point-in-time recovery or online migration
  is required;
- operational tooling needs shared inspection across deployments; or
- review, checkpoint and job writes must share one production transactional
  database.

Adopt Redis or another dedicated broker only if measured requirements include
very high queue throughput, broker-native delayed delivery, distributed
rate-limit coordination or operational separation from the relational
database. PostgreSQL alone is sufficient for the anticipated next scale.

## Consequences

- Authoritative investigation logic remains independent of queue technology.
- The local application gains durable jobs without another running service.
- A future PostgreSQL adapter can implement the same transitions and tests.
- Cancellation is cooperative at explicit safe node boundaries; it does not
  destroy already persisted evidence or audit records.
- Dead-letter jobs require operator inspection and are never retried without
  an explicit new action.
- Queue depth is finite, so overload becomes a visible admission error rather
  than an unbounded agent loop.
