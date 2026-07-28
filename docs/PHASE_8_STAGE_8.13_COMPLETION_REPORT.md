# Phase 8 Stage 8.13 completion report

Date: 28 July 2026

Status: Complete — mechanical gates passed; authority promotion held

## Controlled experiment

The experiment compared the direct authoritative coordinator, LangGraph with
the same authority, LangGraph multi-agent research, a minus-challenger
ablation and a minus-provenance-family ablation.

The five claims were frozen before execution. Passing the pilot authorized a
larger comparison over reviewed benchmark claims CPNG-001 through CPNG-010.
No paid provider, model, live search, network or PDF operation was used.

## Five-case result

| Gate | Result |
|---|---:|
| Authoritative regressions | 0 / 5 |
| Cases with added candidate evidence | 5 / 5 |
| Cases with independent-family gain | 5 / 5 |
| Cases with challenger-only gain | 5 / 5 |
| Approved packet preserved | 5 / 5 |
| Sentence citation support | 100% |
| Material-sentence audit coverage | 100% |
| Invented/out-of-packet evidence | 0 |
| Duplicate paid operations | 0 |
| Deterministic termination | 100% |
| Mean paid cost ratio | 1.0x |
| Median local latency ratio | 1.809x |
| Negative-control review specificity | 100% |

Mandatory-review recall is not estimated because the five pilot cases did not
require review. The eight recovery journeys separately exercised approval,
revision, more-evidence routing and rejection.

## Ten-case comparison

The authorized comparison recorded zero authoritative regressions, candidate
gain in all ten cases, 100% citation and audit coverage, zero invented
evidence, zero duplicate paid operations and deterministic termination.

## Recovery coverage

All approval, revision, more-evidence, rejection, provider-failure, restart
and idempotent-resume journeys passed. The durable-job crash and lease gate
passed, as did specialist academic escalation and telemetry continuity.

A new composite journey proved:

```text
traced durable job
  → FastAPI request
  → authoritative investigation
  → LangGraph multi-agent research
  → research agents and provider operations
  → durable graph checkpoint
  → process-level close/reopen reconstruction
  → idempotent paid-operation receipt
```

## Decision

Every frozen mechanical gate passed, but the system did not self-promote
multi-agent candidate evidence. Candidate-count and family-count gains are
evidence-adequacy signals, not human judgments of relevance or factual
quality.

LangGraph remains the default orchestrator. `InvestigationService` remains
authoritative. Multi-agent research remains observational pending Stage 8.14
targeted human review.

Recorded result:
`artifacts/evaluations/phase8-stage8.13-controlled-promotion-v1.json`.
