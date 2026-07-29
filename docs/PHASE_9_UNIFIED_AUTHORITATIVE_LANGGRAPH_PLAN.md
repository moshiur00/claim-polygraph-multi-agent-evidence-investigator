# Phase 9 — Unified authoritative LangGraph workflow

## Objective

Replace the graph-around-a-completed-investigation arrangement with one
checkpointed LangGraph lifecycle. `InvestigationService` remains authoritative
for domain rules and persistence through typed operations. The sequential
direct composition remains a tested rollback until promotion.

## Non-negotiable controls

- Only retrieved, validated and persisted evidence may affect a verdict.
- Readiness is not probability; calibrated confidence remains separately gated.
- Every paid operation requires an idempotent receipt before live graph wiring.
- Completed operations are not repeated after retry, restart or reconnect.
- Existing report and API consumers remain compatible.
- Publication remains blocked for unsupported critical material assertions.

## Stages and gates

1. **9.0 Baseline freeze.** Freeze the reviewed 20-case set, workflow
   responsibilities, compatibility contracts and hashes. Zero paid calls.
2. **9.1 Operation contracts.** Define typed inputs, outputs, persistence,
   idempotency, cancellation, retry, telemetry and paid-call policy.
3. **9.2 Service decomposition.** Recompose the direct workflow from the new
   operations and prove deterministic baseline equivalence.
4. **9.3 Durable graph state.** Version checkpoint references, budgets,
   receipts, assignments, review links and reconstruction rules.
5. **9.4 Graph skeleton.** Run all authoritative fixture operations as
   checkpointed nodes with conditional routing.
6. **9.5 Paid-operation ledger.** Prove duplicate submission, retry and crash
   scenarios cannot duplicate completed provider work.
7. **9.6 Multi-agent research.** Persist typed assignments/results, run the
   minimum compatible roles concurrently, deduplicate and stop on sufficiency
   or hard budgets.
8. **9.7 Verification and arguments.** Fan out deterministic numerical,
   temporal, provenance and coverage checks; reconcile defender/challenger
   outputs from the same approved packet.
9. **9.8 Judgment and publication.** Checkpoint label policy, sentence-level
   citations, readiness and publication blocking.
10. **9.9 Human review.** Interrupt and resume the same graph for approval,
    revision, more evidence or rejection without replaying completed work.
11. **9.10 API/dashboard.** Expose one truthful job, SSE and visual workflow
    while retaining old reads and direct rollback.
12. **9.11 Recovery.** Pass provider, cancellation, restart, concurrency,
    checkpoint and SSE reconnect failure injection.
13. **9.12 Evaluation.** Compare direct, wrapper, unified and role-ablated
    workflows on the frozen benchmark, cost, latency and quality.
14. **9.13 Human/security audit.** Calibrate representative cases and close
    security, accessibility, citation and trust gaps.
15. **9.14 Promotion.** Record promote, observational, or do-not-promote ADR;
    reconcile documentation, hashes, monitoring and rollback thresholds.

## Cost sequence

Stages 9.0–9.5 use fixtures only. Live providers start only after paid-call
idempotency passes, initially on three representative claims. The full
20-claim comparison runs only at Stage 9.12 and stops early on a mandatory
gate failure.

## Completion

Phase 9 closes only when one durable graph controls the lifecycle, genuine
bounded research roles operate within it, all material nodes and paid calls
are recoverable, review resumes the same graph, users see one truthful
workflow, benchmark gates pass, and the direct rollback remains tested.
