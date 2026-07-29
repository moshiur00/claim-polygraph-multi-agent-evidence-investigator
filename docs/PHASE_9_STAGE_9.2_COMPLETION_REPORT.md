# Phase 9 Stage 9.2 completion report

Date: 29 July 2026

Status: Complete

## Outcome

`InvestigationService.investigate()` is now a sequential composition of the 18
Stage 9.1 authoritative operations. Provider, persistence, budget, retry,
failure, artifact and reporting behavior remains owned by
`InvestigationService`; LangGraph has not been introduced into this layer.

The operation methods are independently callable and preserve the existing
domain models. The direct orchestrator therefore remains a usable rollback
while Stage 9.3 and later graph work proceeds.

## Behavior-preserving decisions

- Research execution still uses the proven retrieval implementation.
- Consolidation exposes and validates the existing research packet without
  changing evidence identity.
- Defender and challenger operations expose the current deterministic ledger
  views without inventing a new debate result.
- Reconciliation requires those legacy views to agree.
- Judgment-policy output remains observational (`applied=false`) exactly as in
  the prior workflow.
- Review routing remains side-effect free in the direct service; the promoted
  wrapper continues to own current review-request creation.
- Terminal success and failure event semantics are unchanged.

Independent defender/challenger execution is deliberately deferred to Stage
9.7. Adding it during a structural refactor would invalidate equivalence.

## Verification

The zero-cost frozen-set run completed all 20 claims with identical structural
signatures:

- Three sources and three evidence items per deterministic fixture.
- Seven deterministic model operations and three deterministic searches.
- One of every required singleton artifact.
- Identical event-type ordering and terminal usage fields.
- No live provider, network or PDF operation.

Existing lifecycle, reporting, retry, failure, prepared-component and citation
revision tests remain the compatibility authority.

## Exit decision

Stage 9.2 passes when the 20-case fixture evaluation, operation-order tests,
existing direct-workflow regressions, lint and artifact verification pass.
Stage 9.3 may now define graph state against independently callable operations.
