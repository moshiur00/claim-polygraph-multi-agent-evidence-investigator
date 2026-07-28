# ADR 0016: Retain SQLite WAL for the bounded local MVP

Date: 28 July 2026

Status: Accepted by measured gate

## Context

The investigation, research, review-ledger and LangGraph checkpoint paths use
SQLite. Earlier reviews correctly treated multi-process write behavior,
review-sequence contention and restart integrity as unproven. Stage 8.10
therefore defines and measures a bounded portfolio-MVP workload before adding
PostgreSQL.

The declared target is one host with four API worker processes, eight
simultaneous investigations, four competing reviewers and eight simultaneous
LangGraph runs. The write load is 200 transactions. The gate requires:

- WAL mode and a 10-second busy timeout on every application connection;
- no lock or busy errors and no lost writes;
- P95 local write latency no greater than 500 ms;
- exactly one winner for a shared expected review sequence, with every stale
  writer rejected cleanly;
- a valid append-only review hash chain; and
- identical reconstruction of every checkpoint after closing and reopening
  its process-level connection.

## Decision

Retain SQLite in WAL mode for the bounded, single-host MVP. PostgreSQL is not
necessary at the measured target.

The 28 July 2026 recorded run used four real writer processes and recorded
200 of 200 writes, zero lock errors, 5.802 ms
P95 write latency, one accepted review write and three clean concurrency
conflicts, a valid audit chain, and eight of eight checkpoint states preserved
across restart.

This is not a general production-scale endorsement. Migrate through the
existing repository boundaries and rerun the same gate when any of these
conditions applies:

- multiple application hosts need to write the same store;
- the target exceeds four API worker processes or eight simultaneous active
  investigations;
- lock/busy errors occur under the declared workload;
- sustained P95 write latency exceeds 500 ms;
- operational requirements demand database-native replication, failover,
  row-level access controls or online schema migration; or
- the durable-job design in Stage 8.11 requires cross-host leasing.

pgvector remains separate from this decision and requires a measured
corpus-scale similarity need.

## Consequences

- Local development remains lightweight and requires no new service.
- All SQLite repositories share WAL, foreign-key and busy-timeout policy.
- Review mutations acquire an immediate write transaction before checking
  their expected sequence, preventing a stale-writer race.
- PostgreSQL remains an anticipated adapter, not current infrastructure.
- The concurrency artifact and test are reproducible and make future
  migration evidence-based.
