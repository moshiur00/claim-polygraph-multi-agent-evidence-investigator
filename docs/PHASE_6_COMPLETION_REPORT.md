# Phase 6 completion report

Date: 28 July 2026

## Outcome

Phase 6 is complete. Numerical and temporal verification, the typed argument
ledger, challenger findings, judgment-policy traces, and readiness features
are integrated as optional, backward-compatible artifacts.

The deterministic judgment policy is **not promoted**. The existing
evidence-grounded verdict remains authoritative, and policy candidates are
observational with `applied: false`.

## Frozen evaluation

| Measure | Result | Gate |
|---|---:|---|
| Frozen cases | 20/20 | Pass |
| Baseline verdict accuracy | 90% | Reference |
| Full policy accuracy | 65% | Fail |
| Improved cases | 0 | Fail |
| Regressed cases | 5 | Fail: maximum 0 |
| Citation support | 100% | Pass |
| Numerical fixture accuracy | 100% | Pass |
| Temporal fixture accuracy | 100% | Pass |
| Added model, network, or PDF calls | 0 | Pass |

The failed policy gate is a controlled negative result, not an incomplete
phase. The unsafe variant was not promoted, and the fallback behavior is
covered by regression tests.

## Targeted review

The targeted packet contains only the six policy-changed cases:
CPNG-006, CPNG-007, CPNG-008, CPNG-009, CPNG-011, and CPNG-014. It also points
to the new numerical and temporal gold fixtures and records every unresolved
policy-versus-reviewed-label disagreement.

No benchmark truth changed. Therefore, no new annotator or approver identity is
asserted and no additional human approval is required for closure. The
existing reviewed labels remain authoritative.

## Quality and security verification

- Full suite: **339 passed**.
- Coverage: **86.42%**, above the configured 85% threshold.
- Ruff: clean.
- Python dependency consistency (`pip check`): clean.
- Safe-fetcher security tests: passed.
- Phase 6 release manifest: hash-valid.
- Final closure audit: hash-valid.

No third-party vulnerability scanner was installed or claimed. The closure
uses the repository's available offline dependency-consistency and SSRF-safe
fetcher checks.

## Frozen artifact trail

- `phase6-experiment-manifest-v1.json`
- `phase6-stage6.0-baseline-v1.json`
- `phase6-stage6.2-numerical-v1.json`
- `phase6-stage6.3-temporal-v1.json`
- `phase6-stage6.8-frozen-ablation-v1.json`
- `phase6-stage6.10-targeted-review-v1.json`
- `phase6-final-release-audit.json`
- `phase6_numerical_operations_v1.json`
- `phase6_temporal_relations_v1.json`
- ADR 0013

The final release audit stores SHA-256 hashes for all frozen inputs and closure
documents except itself and can be verified offline.

## Closure decision

Every gate is explicitly recorded as passed, failed, or skipped by gate. The
policy-promotion gate is failed and the optional model experiment is skipped;
neither is described as passed. Safe fallback, artifact integrity,
verification quality, citation support, compatibility, and repository quality
allow the phase itself to close.
