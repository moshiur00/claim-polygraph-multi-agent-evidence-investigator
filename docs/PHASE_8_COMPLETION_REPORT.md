# Phase 8 completion report

Date: 28 July 2026

Status: Complete

## Executive result

Phase 8 is complete. Every automated closure gate passed, Md Moshiur Rahman
judged all five targeted cases improved and selected
`promote_observational_default`, and distinct approver Md Rashedul Islam
approved the decision on 28 July 2026.

The repository can now state that it contains genuine multi-agent execution:
separate typed roles run concurrently, use distinct bounded permissions,
persist separate results, share controlled caches, stop under hard budgets and
reconcile through deterministic fan-in. It cannot yet state that synthetic
multi-agent candidate passages improve real-world factual accuracy.

## High-priority task disposition

| Task | Disposition |
|---|---|
| Article/URL claim extraction | Implemented and security tested |
| Academic and fact-check adapters | Implemented with separate metadata, permissions and limits |
| Unify LangGraph and multi-agent research | Implemented behind one orchestrator boundary |
| Empirical confidence | Correctly unavailable; dataset support gate failed |
| Full-report citation assurance | Implemented with publication blocking |
| SQLite concurrency | Passed bounded single-host gate; PostgreSQL conditional |
| Durable jobs/cancellation/backpressure | Implemented with leases and dead letters |
| Telemetry, alerts and traces | Implemented locally with W3C propagation |
| README and architecture docs | Reconciled |
| Nested dashboard repository | Resolved; root repository owns dashboard |

## Automated closure evidence

- 35 focused security, restart, concurrency, job and trace tests passed.
- Dashboard ESLint passed.
- Dashboard production build passed.
- Rendered HTML and accessibility tests passed.
- Stage 8.13 five-case and ten-case mechanical gates passed.
- The targeted packet contains five cases and fifteen synthetic candidate
  passages with no fabricated reviewer or approval record.
- No model, live search, network fetch or PDF download was used for closure.

## Persistence and production decisions

- SQLite WAL remains approved for the measured single-host MVP.
- PostgreSQL is preferred before multi-host or high-availability production.
- The database-backed durable queue remains sufficient locally.
- Redis is deferred until broker throughput or distributed rate limits require it.
- The local telemetry exporter should become OTLP in production.
- Confidence remains `null` until leakage-safe held-out calibration is possible.

## Final promotion decision

Multi-agent research is promoted as the default observational subgraph.
LangGraph remains the default orchestrator, `InvestigationService` remains
authoritative, candidate evidence cannot silently enter verdicts, and the
direct workflow remains rollback.

The approval concerns architectural benefit and research structure under the
synthetic fixture disclosure. A reviewed live-evidence pilot remains necessary
before claiming improved real-world factual accuracy.
