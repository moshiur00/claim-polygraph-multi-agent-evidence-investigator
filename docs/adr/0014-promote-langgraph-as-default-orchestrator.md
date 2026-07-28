# ADR 0014: Promote LangGraph as the default orchestrator

Date: 28 July 2026

Status: Accepted

Approved by: Md Moshiur Rahman  
Approval date: 28 July 2026

## Context

Phase 7 added an optional typed LangGraph wrapper around the existing
authoritative investigation service. It introduced SQLite checkpoints, real
human interruption and resume, citation assurance and review routing,
append-only review and approval records, a typed FastAPI surface, a connected
evidence console, and deterministic recovery demonstrations.

The frozen CPNG-001 through CPNG-020 comparison found 100% verdict
equivalence, 100% reviewed-packet and approved-evidence preservation, 100%
required-review recall, preservation of all 20 authoritative citation-audit
outcomes, zero repeated operations, and about 0.10% deterministic median
latency overhead. The eight Stage 7.7 recovery journeys also passed.

This does not repair the authoritative baseline's existing CPNG-006 and
CPNG-019 reviewed-label mismatches. Both paths retain 90% reviewed-label
accuracy. All 20 frozen cases require review, so routing specificity was not
measured. The historical aggregate stores citation-audit outcomes rather than
complete sentence text, so Stage 7.8 verified preservation rather than
recomputed entailment.

## Decision

Promote LangGraph as the default orchestration layer for the typed
investigation journey, while retaining `InvestigationService` as the
authoritative research and verdict implementation.

The promotion must preserve these boundaries:

- LangGraph coordinates stages, checkpoints, interrupts, and resume.
- The existing investigation service remains authoritative for retrieved
  evidence, verification artifacts, and verdicts.
- The deterministic judgment policy remains observational as decided by ADR
  0013.
- Review decisions and revisions remain append-only and independently
  auditable.
- The legacy direct workflow remains an explicit rollback path.
- Provider calls remain subject to existing budgets and idempotency controls.

## Human approval

Md Moshiur Rahman approved this decision on 28 July 2026. This records the
user's explicit architecture decision; it is not an AI-simulated approval.

## Consequences

- The connected dashboard and API use the durable graph journey by default.
- Interrupted investigations survive restart without repeated paid work.
- Operators gain a visible state path and immutable review history.
- Rollback remains possible by selecting the direct authoritative workflow.
- Routing specificity and fresh sentence-level citation calibration remain
  follow-up evaluation work rather than hidden claims of Phase 7.
