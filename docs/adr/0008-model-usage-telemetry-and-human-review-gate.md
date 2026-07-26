# ADR 0008: Model usage telemetry and human-review gate

- Status: Accepted
- Date: 2026-07-26

## Context

Task-based routing is intended to reduce cost without materially reducing
evidence or verdict quality. That claim cannot be tested without per-call usage
measurements and reviewed benchmark labels.

## Decision

Record one `model_usage_recorded` trace event after every OpenAI response,
including:

- concrete model and task;
- request duration;
- input, cached-input, and output tokens;
- estimated USD cost;
- versioned pricing identifier;
- whether the returned structured output passed application validation.

Aggregate these measurements in investigation reports and evaluation summaries.
Pricing uses a small explicit registry for supported project models. Unknown
models remain unpriced instead of silently receiving an invented estimate.
Estimates are clearly distinguished from provider billing records.

The first quality gate is a two-person human review of `CPNG-001` through
`CPNG-005`. Draft annotations may guide review but do not count as ground
truth. One annotator verifies and improves the packet; an independent approver
selects the expected verdict. A case contributes to accuracy only after all
required review metadata validates.

## Consequences

Model routing can now be compared by task, latency, token volume, and estimated
cost. Failed schema validation after a billable response is also observable.

The price registry is time-sensitive and must be updated deliberately when
OpenAI pricing changes. Human review requires coordination and cannot be
automatically completed by the system being evaluated.
