# Verification Construction V4 — Stage V4.12 Closure

## Decision boundary

V4.12 closes the experiment without rerunning, retuning, or otherwise exposing
the frozen V4.11 held-out evaluation. The held-out dataset is permanently
retired from model-development and future promotion testing.

The recommended promotion is deliberately narrow: promote the V4 bounded
assisted-construction fallback behind deterministic eligibility, exact-span
validation, paid-operation receipts, hard budgets, fail-closed review routing,
and publication safeguards. It is not a claim that the model verifies facts or
that the measured recall generalizes beyond the frozen dataset.

## Frozen held-out outcome

| Measure | Result | Frozen gate |
|---|---:|---:|
| Cases | 20 | 20 |
| Constructible gold cases | 18 | — |
| Correct constructions | 15 | — |
| Construction precision | 100% | at least 98% |
| Construction recall | 83.33% | at least 75% |
| Incremental recall gain | 83.33 points | at least 15 points |
| Human-review routing recall | 100% | 100% |
| Unsafe accepted constructions | 0 | 0 |
| Duplicate paid operations | 0 | 0 |
| Publication-safety regressions | 0 | 0 |
| Cost | $0.00509280 | at most $0.50 |
| Cost per recovered assertion | $0.00033952 | at most $0.05 |

The evaluation executed exactly once with the frozen V4.9d contract,
`verification-construction-v4.9d-v8` prompt, schemas, validators,
`gpt-4o-mini`, budgets, and promotion thresholds. No configuration or threshold
changed after the freeze.

## Failure adjudication

Three positive cases failed safely and remained human-review cases:

1. **V3-366 — claim-date surface form.** The claim states “February 2021.”
   The proposal was rejected because the validator could not bind that
   month-level date as an explicit claim date. This is a conservative temporal
   precision/binding failure, not contrary evidence.
2. **V3-368 — claim-span mismatch.** The proposed claim span was not an exact
   substring of the submitted claim. Exact-span enforcement correctly rejected
   it. This is a provider copying failure.
3. **V3-373 — evidence-date surface form.** The claim uses “July 1, 1953” while
   the evidence uses “1st July 1953.” The validator did not accept the evidence
   surface form as an exact effective date. This is a conservative
   normalization/binding failure.

These observations may inform a successor only through new development and
synthetic fixtures. The three held-out records cannot become tuning examples,
and the V4.11 evaluation cannot be rerun.

## Recovery and integrity interpretation

The persisted V4.11 receipt ledger reconstructs all 18 provider attempts as 18
completed, measured-cost operations. Re-reserving each completed operation
returns its cached receipt and durable result; it does not authorize another
provider call. The recorded result contains no duplicate attempts, failed paid
operations, unknown-cost operations, unsafe accepted constructions, or
publication regression.

The V4.11 freeze references are content-addressed. Stage V4.12 verifies every
frozen input, the freeze/result relationship, the approved-workbook hash, all
V4 evaluation JSON, and the final release manifest. Recovery testing is
offline; it makes no model, search, or network calls.

## Promoted runtime policy

Under the accepted ADR, the runtime policy is:

- deterministic construction remains first;
- assisted construction runs only for an explicitly eligible failed
  construction;
- at most one receipt-protected proposal is allowed per operation identity;
- deterministic code validates exact claim/evidence spans and constructs the
  domain object;
- a model cannot set verification state, verdict, readiness, review outcome,
  or publication status;
- malformed, partial, ambiguous, over-budget, cancelled, or ungrounded output
  fails closed to human review;
- held-out V4 artifacts remain evaluation evidence, never prompt examples.

## Remaining limitations

- The held-out set is small and is dominated by explicit temporal statements.
- Recall was 83.33%, so assisted construction still misses valid cases.
- The benchmark demonstrates construction behavior, not factual-verdict
  accuracy or calibrated probability.
- Human-review routing recall was measured on this bounded set and does not
  establish production prevalence or specificity.
- Promotion does not authorize autonomous publication or removal of existing
  deterministic safeguards.

## Closure condition

Engineering closure requires all frozen gates, receipt reconstruction,
artifact integrity, JSON readability, focused recovery tests, and the full
regression suite to pass. ADR 0024 was explicitly approved by Md Moshiur Rahman
on 1 August 2026. Verification Construction V4 is therefore closed and promoted
within its bounded scope.
