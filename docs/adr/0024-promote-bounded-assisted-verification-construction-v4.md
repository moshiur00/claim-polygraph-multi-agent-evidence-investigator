# ADR 0024: Promote bounded assisted verification construction V4

- Status: Accepted
- Date: 1 August 2026
- Phase: Verification Construction V4

## Context

Deterministic numerical and temporal verification can fail to construct a safe
typed assertion from naturally worded claims even when the required operands
are explicit. V4 introduced typed candidate extraction, compound assertion
contracts, deterministic eligibility routing, a constrained assisted proposal,
exact-span validation, temporal fact reconstruction, cost observability, and
receipt-protected execution.

The configuration passed its replacement calibration and its newly collected,
independently annotated held-out evaluation. The held-out run executed exactly
once: 15 of 18 constructible cases were recovered, precision was 100%, recall
was 83.33%, human-review routing recall was 100%, and no unsafe construction,
publication regression, or duplicate paid operation occurred.

## Proposed decision

Promote V4 bounded assisted construction as a fallback after deterministic
construction fails, subject to the frozen eligibility, validation, budget,
receipt, review-routing, and publication constraints.

Deterministic code remains authoritative. The model proposes exact spans and
explicit facts but cannot determine verification state, verdict, readiness,
review outcome, or publication status.

## Scope

Included:

- explicit numerical and temporal assertions covered by the typed contracts;
- one bounded structured proposal per eligible operation identity;
- receipt-protected OpenAI execution with caching and cost accounting;
- fail-closed routing for invalid, incomplete, ambiguous, or unsupported
  proposals;
- local bounded deployment with the existing human-review gate.

Excluded:

- qualitative claims outside numerical or temporal verification;
- autonomous truth judgments or publication;
- reuse of any exposed calibration or held-out case for tuning;
- claims of population-level accuracy or calibrated factual confidence;
- removal of deterministic or human-review safeguards.

## Consequences

Positive:

- naturally worded explicit assertions receive materially better construction
  coverage than the deterministic-only baseline;
- exact-span and deterministic domain validation preserve precision;
- unresolved cases remain visible and route to review;
- receipt reconstruction prevents duplicate charging after restart or resume;
- measured cost is substantially below the frozen budget.

Costs and limitations:

- a provider call adds latency and non-zero cost for eligible failures;
- three of 18 constructible held-out cases still failed safely;
- the held-out set is small and temporally concentrated;
- future improvements require new development, calibration, and held-out data.

## Evidence

- `artifacts/evaluations/verification-construction-v4-stage11-held-out-evaluation-freeze-v1.json`
- `artifacts/evaluations/verification-construction-v4-stage11-held-out-evaluation-v1.json`
- `artifacts/evaluations/verification-construction-v4-stage12-final-audit-v1.json`
- `docs/private/verification-construction-v4-stage12-closure.md`

## Approval

Approved by Md Moshiur Rahman on 1 August 2026 through an explicit project-owner
decision. V4 bounded assisted verification construction is promoted within the
scope and safeguards defined by this ADR.
