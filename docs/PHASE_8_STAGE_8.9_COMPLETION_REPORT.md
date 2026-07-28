# Phase 8 Stage 8.9 completion report

Date: 28 July 2026

Status: Complete — calibrator not promoted

## Outcome

The project now has a versioned, leakage-safe empirical confidence-calibration
framework, but it correctly refuses to expose confidence. The current
repository contains 20 reviewed internal claims, no frozen Stage 8.9 feature
vectors for those claims and no repository-local compatible public calibration
slice. Consequently there are zero eligible feature-complete cases.

The recorded outcome is `insufficient_data`, `selected_calibrator=null` and
`confidence_available=false`. Verdict confidence therefore remains `null`.
This is the successful outcome of the safety gate, not an incomplete fitting
run.

## Frozen feature contract

The calibration input permits only observable pre-outcome features:

- evidence quality;
- independent evidence-family count;
- contradiction balance;
- full-report citation support rate;
- unresolved verification rate;
- retrieval coverage; and
- model disagreement.

Judgment readiness is intentionally absent. Readiness remains a deterministic
description of packet completeness and continues to expose
`confidence_score=null`.

The reference verdict label and correctness target are stored separately from
features and are used only for fitting/evaluation metrics.

## Leakage-safe split

Every calibration case declares a claim-group ID and either a `fit` or
`evaluation` split. A dataset is invalid if the same group appears in both
splits. Method selection and all reported metrics use only the held-out
evaluation cases.

Frozen minimum support:

- 200 feature-complete cases total;
- 140 fitting cases;
- 60 held-out evaluation cases;
- at least 3 represented domains; and
- at least 20 examples for every represented reference label.

These thresholds prevent the 20-case development benchmark from being
relabelled as a probability-calibration dataset.

## Interpretable method comparison

When the support gate passes, the evaluator compares:

1. fitting-set base rate;
2. a frozen linear evidence-feature score; and
3. Platt logistic calibration over that frozen score.

Selection is deterministic. The evaluator reports:

- held-out Brier score;
- expected calibration error;
- ten reliability bins;
- coverage at the frozen 0.70 abstention threshold; and
- accuracy among accepted predictions.

A calibrator is promoted only when it improves held-out Brier score over the
base-rate baseline by at least 0.005, has expected calibration error no greater
than 0.10 and does not worsen accepted-prediction safety. Otherwise the result
is `not_promoted` and confidence remains unavailable.

## Current inventory result

- Reviewed internal candidates: 20
- Cases with complete frozen Stage 8.9 features: 0
- Excluded incomplete-feature cases: 20
- Repository-local compatible public cases: 0
- Fit cases: 0
- Held-out cases: 0
- Selected method: none
- Confidence available: no

The eligible-case file is intentionally empty rather than populated with
invented retrospective features.

## Verification

- A 20-case fixture was rejected as insufficient.
- Claim-group leakage across fit/evaluation splits was rejected.
- A 210-case separable fixture produced deterministic held-out metrics and a
  promoted interpretable calibrator.
- A 210-case uninformative fixture was evaluated but not promoted.
- Reliability bins, Brier score, ECE and abstention metrics were recomputed.
- Repeated fitting produced identical results.
- Promoted development investigations retained `verdict.confidence=null`.
- Judgment readiness retained `confidence_score=null`.
- Complete project suite: 424 passing tests.
- Python lint passed.

No model call, live search, network fetch or PDF operation was used.

## What is required before confidence can be enabled

Create frozen feature-complete records for a sufficiently large reviewed
corpus, add compatible public cases only after license and label-taxonomy
review, predeclare group-level splits, and rerun the same evaluator. Confidence
must remain observational even after promotion; it cannot bypass abstention,
human review, citation blocking or readiness safeguards.

