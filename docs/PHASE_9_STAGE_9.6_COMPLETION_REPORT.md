# Phase 9 Stage 9.6 completion report

Date: 29 July 2026

Status: Complete

## Outcome

The genuine Phase 8 multi-agent research workflow now runs inside the
authoritative LangGraph research operation. `InvestigationService` remains the
domain and persistence authority: the research subgraph returns a typed packet,
and the service validates and persists that packet before any downstream
verification, argument, judgment, citation or report operation can use it.

The legacy direct research operation remains available when no multi-agent
adapter is configured.

## Authoritative research path

```text
typed requirements + hard budget
  -> deterministic minimum-role routing
  -> concurrent primary/general/challenger fan-out
  -> optional academic/fact-check specialists
  -> shared search and fetch caches
  -> durable assignment and result checkpoints
  -> fan-in source/evidence deduplication
  -> deterministic sufficiency assessment
  -> targeted additional round, if useful and affordable
  -> stop on sufficiency, budget or diminishing returns
  -> InvestigationService packet validation and persistence
  -> authoritative verification and judgment stages
```

## Durable state

The authoritative checkpoint now records typed requirement, assignment and
result references; consolidated evidence-family references; approved evidence;
research consumption; unresolved requirements; and paid-operation receipt
references. Large source and evidence payloads remain in artifact repositories.

All budget dimensions are validated, including rounds, role activations,
searches, fetches, model calls, tokens, duration and estimated cost.

## Paid-operation safety

Paid-capable research adapters cannot be constructed without the Stage 9.5
receipt ledger. Actual provider calls must be made through the receipt-guarded
provider decorators. Receipt history is projected into the authoritative graph
state after research. The Stage 9.6 release evaluation uses deterministic
fixtures and incurs no external cost.

## Evidence and recovery guarantees

- The minimum team contains primary-source, general-evidence and challenger
  roles.
- Compatible assignments execute concurrently.
- Identical searches and fetches share durable caches.
- Fan-in removes duplicate source and evidence contributions.
- Completed assignments and workflow rounds resume from Phase 8 checkpoints.
- Insufficient evidence routes to review after controlled stopping.
- Consolidated evidence identity is preserved through the final report.
- The direct workflow remains the rollback path.

## Verification

The integration gate proves three concurrent roles, one shared search provider
call, typed assignment/result projection, bounded zero-cost consumption,
authoritative evidence persistence, final-report evidence equivalence, and
rejection of unguarded paid-capable research.

## Cost

No OpenAI, SerpAPI, live network, document download or PDF operation was used.

## Exit decision

Stage 9.6 passes. Genuine multi-agent research is now part of the authoritative
LangGraph path, while `InvestigationService` authority and direct rollback are
preserved.
