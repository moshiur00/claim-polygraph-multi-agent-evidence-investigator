# Phase 7 completion report

Date: 28 July 2026

Status: Complete; LangGraph promoted as the default orchestrator

## Outcome

The visible LangGraph investigation and accountable-review implementation is
complete. The authoritative investigation service is preserved behind a typed,
durable orchestration layer with checkpoint recovery, human interruption,
append-only review history, API access, Server-Sent Events, and a connected
evidence console.

Md Moshiur Rahman approved ADR 0014 on 28 July 2026. LangGraph is now the
default orchestration layer while `InvestigationService` remains authoritative
and the direct workflow remains an explicit rollback.

## Frozen quality result

| Measure | Result | Gate |
|---|---:|---|
| Frozen cases | 20/20 | Pass |
| Verdict equivalence | 100% | Pass |
| Reviewed-packet and evidence preservation | 100% | Pass |
| Required-review recall | 100% | Pass |
| Preserved authoritative citation audits | 100% | Pass |
| Duplicate paid or deterministic operations | 0 | Pass |
| Deterministic median latency overhead | about 0.10% | Pass: maximum 20% |
| Stage 7.7 recovery journeys | 8/8 | Pass |
| Baseline and wrapper reviewed-label accuracy | 90% | Disclosed limitation |

The 90% result reflects the existing CPNG-006 and CPNG-019 baseline
disagreements. LangGraph introduced no new verdict regression and did not
silently alter benchmark truth.

## Targeted calibration

The Stage 7.9 selector found:

- zero new routing disagreements;
- zero new citation-audit errors;
- zero changed authoritative outputs; and
- two already documented baseline-versus-reviewed-label disagreements.

No CPNG case needs reannotation for Phase 7 and no Phase 7 human action remains.

## Security and accessibility

- Full Python suite: **380 passed**.
- Branch-aware coverage: **86.68%**, above the configured 85% threshold.
- Ruff and Python dependency consistency checks: passed.
- Dashboard production build, rendered checks, and ESLint: passed.
- API provider exceptions are sanitized and do not expose secret-bearing
  messages or tracebacks.
- CORS permits declared dashboard origins and does not use a wildcard.
- Reviewer identity mismatches, stale decisions, and conflicting resumes are
  rejected by tested boundaries.
- SSRF-safe fetching and provider secret-handling tests pass.
- Python dependency consistency passes.
- The dashboard build and ESLint checks pass.
- Server-rendered accessibility checks confirm document language, main and
  navigation landmarks, heading, explicit form labels, named buttons, and no
  forced negative tab order.

No third-party vulnerability scanner, full WCAG conformance audit, or
assistive-technology browser session was performed or claimed.

## Closure state

All engineering, recovery, quality, security, accessibility-structure,
artifact-integrity, and human-promotion gates are complete. Phase 7 is closed.
The API composition uses LangGraph by default. Set
`CLAIM_POLYGRAPH_ORCHESTRATOR=direct` to select the direct authoritative
workflow as the rollback path.
