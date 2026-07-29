# Phase 9 Stage 9.4 completion report

Date: 29 July 2026

Status: Complete

## Outcome

The initial unified authoritative LangGraph skeleton executes all 18 extracted
`InvestigationService` operations as graph nodes. LangGraph controls sequence,
conditional review routing, interruption and resume. `InvestigationService`
continues to own domain rules, provider access, artifacts, lifecycle events and
the final report.

## Topology

```text
create -> normalize -> plan -> requirements
-> research -> consolidate -> provenance -> verify
-> ledger -> defender -> challenger -> reconcile
-> draft -> judgment policy -> citation assurance
-> readiness -> review routing
   -> finalize
   -> real LangGraph review interrupt -> resume -> finalize
```

Every material operation appends one
`AuthoritativeInvestigationGraphState` checkpoint. An automatic fixture has 18
checkpoints; a review-routed fixture adds one resume checkpoint while retaining
the same 18 completed-operation identities.

## Durability and data boundaries

- LangGraph uses its asynchronous SQLite checkpointer.
- The authoritative state independently uses the append-only Stage 9.3 SQLite
  repository.
- Evidence passages, sources and reports are not copied into authoritative
  state checkpoints.
- Nodes reconstruct inputs from persisted artifact references.
- The bounded provisional verdict is retained only in LangGraph execution
  state until citation audit persists the authoritative verdict.
- Finalization persists a standalone `report` artifact for exact reconstruction.

## Review scope

The graph uses LangGraph's actual `interrupt` and `Command(resume=...)`
mechanisms. The release runner supplies a clearly identified deterministic
fixture approval. Immutable production reviewer records and complete review
routing remain Stage 9.9 work.

## Cost

The fixture executes seven deterministic model operations and three
deterministic searches. External model calls, live searches, network fetches,
PDF downloads and paid cost are all zero.

## Exit decision

Stage 9.4 passes when all 18 operations execute once, every operation is
checkpointed, both automatic and interrupted routes complete, a persisted
report reconstructs, lint and regressions pass, and the release hashes verify.
Stage 9.5 may now add durable paid-operation receipts before live providers are
connected.
