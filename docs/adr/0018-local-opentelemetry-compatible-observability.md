# ADR 0018: Use privacy-safe OpenTelemetry-compatible observability

Date: 28 July 2026

Status: Accepted

## Context

Claim Polygraph NG already persisted evidentiary trace events, append-only
review records, LangGraph checkpoints, role-level research metrics and job
audit events. Those artifacts answer what the system decided and preserve
research accountability, but they did not provide one operational trace
across API requests, durable jobs, graph execution, agents, providers and
review actions.

Operational telemetry has a different trust purpose from evidence audit
history. It must diagnose latency, failure and congestion without becoming a
second source of truth or retaining raw claims and personal data.

## Decision

Adopt W3C `traceparent` propagation and OpenTelemetry-compatible trace/span
identifiers and parent relationships. Keep immutable domain audits
authoritative. Use the local SQLite collector as a deterministic development
and portfolio reference exporter.

The reference instrumentation covers these span kinds:

- API request;
- durable job;
- LangGraph stage;
- research agent;
- external provider; and
- human-review operation.

Persist low-cardinality operational attributes only. Keys associated with
claim text, prompts, documents, URLs, secrets, tokens and reviewer identity
are SHA-256 pseudonyms; their raw values are never stored in telemetry.

Aggregate API and provider latency, queue depth and wait, job/provider
failures, token and cost use, evidence yield, citation failure, review
backlog, LangGraph node latency, budget exhaustion and checkpoint failure.
Evaluate deterministic warning or critical rules over aggregates.

## Production exporter decision

Do not add a hosted telemetry vendor in this stage. The contracts are
compatible with an OpenTelemetry SDK/exporter adapter, but installing a
collector is a deployment decision.

Before a production release:

- replace or supplement the SQLite exporter with OTLP export;
- configure retention and access control;
- sample successful high-volume traces while retaining errors;
- keep claim content and reviewer identities excluded;
- make alerts actionable through the chosen operations channel; and
- verify trace continuity through the selected PostgreSQL job adapter if it
  is promoted.

## Consequences

- Operators can distinguish provider delay, job congestion, graph failure and
  review backlog without reading raw investigation evidence.
- API responses expose a continuation `traceparent`.
- Durable job payloads may carry only the W3C trace context, not telemetry
  implementation objects.
- The local API exposes privacy-safe snapshots and trace lookup.
- Operational telemetry can be deleted according to retention policy without
  damaging evidentiary or review audit history.
