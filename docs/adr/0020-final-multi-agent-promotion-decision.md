# ADR 0020: Final multi-agent research promotion decision

Date: 28 July 2026

Status: Accepted

## Context

Stages 8.0–8.13 implemented and mechanically validated the unified LangGraph
multi-agent journey. The five-case pilot and authorized ten-case comparison
passed every frozen mechanical gate. ADR 0019 holds authority promotion
because the changed candidate passages are deterministic synthetic fixtures.

The required review packet is:
`benchmarks/review_packets/phase8_stage8_14_targeted_review.md`.

## Decision

Promote multi-agent research as the default observational research subgraph.
Candidate evidence remains non-authoritative and `InvestigationService`
continues to own approved evidence, verification and verdicts.

All five targeted cases were judged improved. This approves the demonstrated
research structure and role separation. It does not convert synthetic fixture
passages into externally verified factual evidence.

## Required record

- Reviewer identity: Md Moshiur Rahman
- Review date: 28 July 2026
- Reviewer decision: `promote_observational_default`
- Reviewer rationale: All five targeted cases were judged improved; preserve
  the authority and synthetic-fixture limitations.
- Distinct approver identity: Md Rashedul Islam
- Approval date: 28 July 2026
- Approval decision: `approve`

## Invariants under every decision

- `InvestigationService` remains authoritative unless a later separately
  reviewed ADR changes that boundary.
- The direct orchestrator remains rollback.
- No candidate or out-of-packet evidence may enter a verdict silently.
- Confidence remains unavailable until the empirical calibration gate passes.
- SQLite remains limited to the measured single-host target.
