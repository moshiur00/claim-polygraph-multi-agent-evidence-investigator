# Phase 8 Stage 8.12 completion report

Date: 28 July 2026

Status: Complete — local reference telemetry promoted

## Outcome

The application now has a privacy-safe operational observability layer with
W3C trace propagation, OpenTelemetry-compatible identifiers, persistent local
spans, metric aggregation and deterministic alert evaluation.

This layer complements rather than replaces:

- authoritative investigation trace events;
- LangGraph checkpoints;
- research-role metrics;
- durable job audit events; and
- immutable review and approval history.

## Trace continuity

One trace can continue through:

```text
API request
  └─ durable job
      └─ LangGraph stage
          └─ research agent
              └─ search/model provider
  └─ review operation
```

FastAPI accepts a valid incoming `traceparent` and returns the continued
context. A durable job stores the context as a string and the worker creates a
child span. Agent and provider instrumentation inherit the active context
across asynchronous execution.

## Metrics

The frozen registry includes:

- API and provider P95 latency;
- job queue depth, wait and failure;
- provider failures;
- model tokens and estimated cost;
- evidence yield;
- citation failures;
- review backlog;
- LangGraph node latency;
- budget exhaustion; and
- checkpoint failure.

The API exposes:

- `GET /api/operations/telemetry` for aggregate metrics and active alerts;
- `GET /api/operations/traces/{trace_id}` for privacy-safe span inspection.

## Privacy

Telemetry does not retain raw claims, article text, prompts, snippets, URLs,
tokens, secrets, email/name fields or reviewer identities. Values attached to
sensitive keys are replaced by a short SHA-256 pseudonym. Tests confirm the
raw fixture values are absent after persistence and restart.

## Frozen gate

| Check | Result |
|---|---:|
| Boundary span kinds | 6 / 6 |
| Parent chain | Valid |
| Restart-preserved spans | 6 / 6 |
| Sensitive fixture values present | 0 |
| Metric families observed | 5 |
| Expected alerts | 3 / 3 |
| External/model/search/PDF calls | 0 |

The gate triggered the expected queue-depth, repeated-provider-failure and
citation-failure alerts. API and worker integration tests separately prove
real W3C propagation.

## Production boundary

The local SQLite collector is appropriate for development and the bounded
single-host MVP. A production deployment should add an OTLP exporter and
collector with retention, access control and sampling. That change does not
require altering domain audits or the trace contracts.

Recorded evaluation:
`artifacts/evaluations/phase8-stage8.12-telemetry-v1.json`.
