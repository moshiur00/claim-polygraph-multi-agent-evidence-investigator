# Verification Construction V3 — Real-World Coverage and Controlled Fallback

## Stage V3.0 status

Frozen before provider selection or model execution. This stage permits zero
model calls, zero network calls, and zero search calls.

## Objective

Determine whether a bounded assisted-construction fallback materially improves
typed assertion recall on naturally written claims while preserving the
project's fail-closed publication and human-review safeguards.

Readiness remains packet completeness, calibrated confidence remains a separate
feature, and neither is treated as claim-truth probability.

## Experimental arms

1. Deterministic construction only.
2. Deterministic construction followed by one bounded assisted proposal only
   when deterministic construction fails and the case is fallback-eligible.
3. Human-reviewed final construction.

Every accepted proposal must pass exact claim-span, approved-evidence-span,
dimension, unit, comparator, checkpoint, receipt, and deterministic-verification
validation. A model cannot set a verdict, verification state, readiness state,
or publication decision.

## Stage sequence

### V3.1 — Dataset assembly

Assemble 60 candidate cases using the frozen sampling policy. Use permitted
retained text or accessible public pages only. Do not download restricted
documents. Group by origin family before split assignment.

### V3.2 — Annotation and distinct approval

Annotate claim operands, dimension, comparator or temporal relation, exact
evidence offsets, expected construction label, and expected deterministic
verification state. A distinct approver must review every case.

### V3.3 — Deterministic baseline

Replay all cases without network or model access. Record construction recall,
precision, evidence-span validity, unsafe constructions, routing, publication
effects, latency, and supported-dimension coverage.

### V3.4 — Provider selection and paid-operation wiring

Select a low-cost structured-output model only after the dataset and baseline
are frozen. Route calls through the existing paid-operation receipt repository,
cost ledger, cache, cancellation, retry, telemetry, and checkpoint system.

### V3.5 — Development split

Use only the 20 development cases for prompt and validator debugging. Changes
must be versioned. Never tune against calibration or held-out labels.

### V3.6 — Calibration split

Run one frozen configuration over the 20 calibration cases. Decide whether the
configuration is eligible for held-out evaluation. No threshold may be changed
after seeing results.

### V3.7 — Held-out evaluation

Run the unchanged configuration once over 20 held-out cases. Persist receipts,
cost, latency, exact span validation, deterministic outcomes, review routing,
and publication decisions.

### V3.8 — Human adjudication and ablation

Compare deterministic-only, assisted fallback, and human-reviewed results.
Review every assisted proposal, every rejection, every unsafe attempt, and every
publication-impacting difference.

### V3.9 — Recovery and promotion audit

Inject provider failure, malformed schema output, cancellation, restart,
checkpoint recovery, SSE reconnection, and duplicate resume. Confirm no valid
paid receipt is charged twice.

## Frozen budgets

- V3.0: 0 model calls; 0 network calls; $0.
- Assisted calls: at most one per eligible case.
- Total paid calls: at most 25.
- Input: at most 6,000 tokens per call.
- Output: at most 800 tokens per call.
- Total experiment cost: at most $0.75.
- Cost per correctly recovered assertion: at most $0.05.
- Search calls: 0; benchmark evidence is frozen before evaluation.
- Retry after a valid paid receipt: 0.

Budget exhaustion stops assisted construction and routes the case to human
review. It never relaxes validation.

## Frozen promotion thresholds

- Exact evidence-span validity: 100%.
- Unsafe accepted constructions: 0.
- Construction precision: at least 98%.
- Recall gain on fallback-eligible cases: at least 15 percentage points.
- Overall construction recall: at least 75%.
- Human-review routing recall for unsafe or unresolved cases: 100%.
- Publication-safety regressions: 0.
- Verdict regressions attributable to construction: 0.
- Duplicate paid operations after recovery: 0.
- Cost per correctly recovered assertion: at most $0.05.
- Median latency overhead: at most 4 seconds.
- P95 latency overhead: at most 10 seconds.
- Targeted annotation and distinct approval: required.

Failure of any safety threshold blocks promotion. Quality gains cannot offset
unsafe construction, citation failure, publication regression, or duplicate
charging.

## Stage V3.0 exit criterion

The schema, sampling policy, plan, budgets, and promotion thresholds are
content-addressed in one valid manifest; all contract tests pass; provider
selection remains unset; and model/network call counts remain zero.
