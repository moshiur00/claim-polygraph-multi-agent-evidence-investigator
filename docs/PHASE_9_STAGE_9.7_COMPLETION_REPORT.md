# Phase 9 Stage 9.7 completion report

Date: 29 July 2026

Status: Complete

## Outcome

Verification and adversarial argument construction now execute as bounded
LangGraph fan-out/fan-in workflows inside the authoritative investigation
lifecycle. `InvestigationService` remains responsible for validation,
persistence and final reconciliation. The direct sequential operations remain
available when these Stage 9.7 workflows are not configured.

## Verification workflow

```text
one approved evidence packet
  ├─ numerical context check
  ├─ temporal context check
  ├─ provenance and independence check
  └─ evidence coverage check
          ↓
  typed deterministic fan-in
          ↓
  InvestigationService validation and persistence
```

All four branches receive the same claim, plan, sources and ordered approved
evidence IDs. The workflow rejects a reordered or substituted packet. Fan-in
produces the existing `ContextVerification`, `VerificationPacketV2` and
`InvestigationProvenance` artifacts plus a typed `EvidenceCoverageCheck`.

The release fixture observed four simultaneously active branches. Its outputs
were exactly equal to recomputing the prior sequential deterministic functions.

## Argument workflow

```text
authoritative argument ledger + approved packet
  ├─ defender position
  └─ challenger position
          ↓
  deterministic reconciliation
          ↓
  unchanged authoritative argument ledger
```

The promoted Phase 8 argument workflow creates two typed assignments and runs
the roles concurrently. Their only permissions are reading approved evidence
and building a position. Search and fetch calls are structurally prohibited;
the Stage 9.7 fixture also uses zero model calls. Results are stored by
assignment and replayed after restart without executing the roles again.

`InvestigationService` accepts reconciliation only when both roles completed
and the reconciled ledger is exactly equivalent to the authoritative ledger.
Any role failure or difference routes to human review.

## Compatibility and rollback

- Existing verification, provenance and argument-ledger artifact schemas remain
  unchanged.
- Existing report consumers receive the same authoritative ledger.
- The outer graph retains one checkpoint per authoritative operation.
- Completed argument results resume from durable storage.
- Omitting the Stage 9.7 workflows preserves the prior direct behavior.

## Verification

The focused gate covers sequential equivalence, four-way verification
concurrency, approved-packet isolation, two-role coverage, tool isolation,
deterministic reconciliation, durable replay and direct fallback.

## Cost

No OpenAI, SerpAPI, live network, document download or PDF operation was used.

## Exit decision

Stage 9.7 passes. Verification and defender/challenger reasoning are genuinely
coordinated subgraphs within the authoritative LangGraph lifecycle, without
weakening domain authority, evidence isolation or rollback.
