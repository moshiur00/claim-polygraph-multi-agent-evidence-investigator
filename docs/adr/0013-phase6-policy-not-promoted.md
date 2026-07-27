# ADR 0013: Keep the Phase 6 judgment policy observational

Date: 28 July 2026

Status: Accepted

## Context

Phase 6 added deterministic numerical and temporal verification, a typed
claim-to-evidence argument ledger, judgment constraints, and readiness
features. Stage 6.8 replayed the frozen, human-reviewed 20-claim benchmark.

The existing workflow achieved 90% verdict accuracy. Applying the deterministic
judgment policy reduced accuracy to 65%, changed six verdicts, improved none,
and regressed five. The main failure was coarse evidence-stance aggregation
that could not preserve qualified and mixed meaning.

## Decision

The existing evidence-grounded verdict remains authoritative. The integrated
judgment-policy trace remains available for diagnostics, but records
`applied: false` and cannot replace the verdict.

Numerical verification, temporal verification, the argument ledger, challenger
findings, and readiness remain available as typed, auditable artifacts. They
do not independently rewrite the verdict.

Stage 6.9 is skipped because the observed failure is a broad deterministic
representation problem, not a narrow ambiguity suitable for the bounded model
experiment.

## Consequences

- Phase 6 can close without concealing a failed promotion gate.
- Existing verdict quality and backward compatibility are preserved.
- Reports retain useful verification and diagnostic information.
- A future policy version requires a new locked evaluation and must demonstrate
  zero regressions before promotion.
- No model, retrieval, network, or PDF work is required for this decision.
