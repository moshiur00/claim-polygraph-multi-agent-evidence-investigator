# Phase 8 Stage 8.5 completion report

Date: 28 July 2026

Status: Complete

## Outcome

The promoted LangGraph mode now runs a genuine research map/reduce subgraph.
Typed requirements are routed to a minimum primary-source, general-evidence and
challenger team. LangGraph dispatches compatible assignments concurrently and
joins them at a deterministic fan-in boundary.

This is no longer merely a modular sequential pipeline: each role has an
independent typed assignment, permission scope, result and metric record, and
the role nodes execute concurrently under a shared coordinator and budget.

## Execution path

1. The authoritative `InvestigationService` creates the report and approved
   evidence packet.
2. The deterministic router creates the minimum useful research assignments.
3. A LangGraph `Send` operation maps each assignment to a research-role node.
4. A shared executor bounds concurrency and isolates role failures.
5. Shared search and fetch operations coalesce identical in-flight work and
   reuse SQLite cache records.
6. The fan-in node deduplicates result references.
7. Existing consolidation removes duplicate sources/evidence and infers
   evidence families.
8. Assignment, result, family, usage and unresolved-requirement references are
   projected into the durable parent LangGraph checkpoint.
9. Candidate research remains separate from the authoritative approved packet.

## Durable recovery

The SQLite research repository saves the plan before dispatch and saves every
terminal assignment result independently. A complete restart performs no role
or provider work. A simulated mid-round restart with one completed assignment
reused that result and ran only the two unfinished roles.

Role metrics and fan-in duplicate counts are stored with the workflow
checkpoint, not only returned transiently.

## Metrics

Every role records:

- success or failure;
- source and evidence counts;
- retained evidence after consolidation;
- independent evidence-family gain;
- search, fetch and model calls;
- estimated cost; and
- measured wall-clock duration.

The concurrency fixture observed three simultaneously active role workers.
Three roles requesting an identical query produced one provider call through
in-flight cache coalescing. Duplicate evidence was reduced at fan-in.

## Authority isolation

Candidate fan-out evidence is stored and auditable but is not automatically
approved. The durable state has a separate `approved_evidence_ids` collection,
which exactly matches the authoritative report. The expanded stored-evidence
set may include research candidates, but those candidates cannot affect the
verdict in this stage.

`InvestigationService` therefore remains the sole evidence/verdict authority,
and direct rollback still creates no LangGraph research state.

## Three-case frozen fixture pilot

Three deterministic claims completed through the promoted API:

- 3 investigations;
- 9 role activations;
- 9 terminal role results;
- 0 model calls in the research subgraph;
- USD 0 estimated research cost;
- candidate evidence present for all cases; and
- authoritative approved-evidence containment preserved for all cases.

No live search, hosted model, network fetch or PDF operation was used.

## Verification

- Minimum-team routing
- Concurrent role execution
- Shared in-flight and durable operation caches
- Fan-in source/evidence consolidation
- Complete and mid-round restart recovery
- Per-role result checkpointing and metrics
- Partial-role failure isolation
- Global and per-role budget validation
- Promoted API state exposure
- Three-case frozen fixture pilot
- Complete project suite: 409 passing tests
- Python lint, dashboard lint and production dashboard build

## Deliberate limits

The default development path currently uses deterministic fixture providers.
Stage 8.4 specialist adapters are available, but provider selection for
conditional academic and fact-check assignments remains configuration work.
Iterative rounds and diminishing-return stopping belong to Stage 8.6.
Multi-agent candidate evidence must remain non-authoritative until a later
benchmark promotion gate proves material quality improvement.
