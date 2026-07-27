# ADR 0011: Typed complex-claim state before multi-agent execution

Status: Accepted

Date: 27 July 2026

## Context

The current evidence workflow has passed its ten-claim gates, but it produces
one normalized claim and one verdict per investigation. Adding independent
research agents before defining decomposition, component coverage, parent
aggregation, and resume contracts would make failures difficult to attribute.

## Decision

Implement a single-coordinator complex-claim workflow first:

- immutable submitted parent text;
- selectively decomposed, parent-linked atomic components;
- typed component results and coverage;
- constrained parent-verdict aggregation;
- SQLite-backed idempotent checkpoints.

Keep the existing atomic investigation API backwards compatible. Multi-agent
research must later use these contracts and demonstrate an improvement over
this baseline.

LangGraph is not selected yet. It will be reconsidered if explicit checkpoint
or branching code fails the Phase 3 resume gates.

## Consequences

- Decomposition and aggregation errors can be evaluated separately from agent
  coordination errors.
- Existing atomic investigations and Phase 1–2 artifacts remain valid.
- The coordinator may initially execute components sequentially.
- Some orchestration code may later be replaced by LangGraph without changing
  domain or artifact contracts.

