# Phase 9 Stage 9.1 completion report

Date: 29 July 2026

Status: Complete

## Outcome

The frozen Stage 9.0 responsibilities now map to 18 closed authoritative
operations. Each operation has a distinct typed input and result, declared
artifact dependencies and outputs, persistence writes, idempotency scope,
cancellation boundary, retry class, failure semantics, telemetry attributes,
and paid-provider permission.

## Contract boundary

The operations are orchestration-neutral. The direct workflow and the future
authoritative LangGraph call the same contracts; neither owns domain rules.
Large evidence and report objects are represented by typed persisted artifact
references, keeping future checkpoints bounded and reconstructable.

The lifecycle is:

```text
create -> normalize -> plan -> prepare requirements
-> execute research -> consolidate -> provenance + verification
-> ledger -> defender + challenger -> reconcile
-> draft -> judgment policy -> citation assurance
-> readiness -> review routing -> finalize
```

## Safety rules

- All 18 operations have exactly one registered input, result and policy contract.
- The registry rejects missing or duplicate operations.
- Every paid-capable operation is receipt-guarded; Stage 9.5 will implement receipts.
- Input artifacts must belong to the same investigation and be unique.
- Request/result operation, ID, investigation and version must match.
- Canonical idempotency keys are invariant to JSON object key ordering.
- Strict models reject undeclared fields.
- Finalization is not cancellable after its durable commit begins.
- Citation failures block publication; partial research is retained and routed.

## Compatibility

The legacy adapter exposes current `InvestigationReport` artifacts through the
new reference model without rerunning the investigation. It preserves existing
claim, plan, source, evidence, verdict, audit, provenance, verification,
argument, policy, readiness and citation-assurance identities.

## Verification and cost

The manifest fingerprints all 36 input/result schemas and hashes the Stage 9.1
implementation, tests, documentation and Stage 9.0 baseline. No model, search,
network or PDF operation was invoked.

## Exit decision

Stage 9.1 is complete when the registry, schema manifest, compatibility adapter,
focused tests and lint pass. Stage 9.2 can now refactor the direct
`InvestigationService` into sequential composition over these contracts.
