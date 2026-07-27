# Phase 3 readiness report

Date: 27 July 2026

Status: **superseded by the completed Phase 3 release**

Human benchmark approval and the dependent declared accuracy/stability runs
have now completed. The authoritative release record is
`docs/PHASE_3_COMPLETION_REPORT.md`.

## Implemented

- Typed selective decomposition with one immutable root and one to eight
  independently identified material components.
- Application-protected retention of the complete submitted parent claim,
  reference date, geography, and model-supplied qualifiers.
- Component-specific research queries carrying bounded parent context.
- One linked child investigation per component.
- Explicit completed, unresolved, and failed component outcomes.
- Deterministic parent-label aggregation that cannot conceal a failed material
  component.
- Compositional parent citation audit inherited only when all child audits are
  full and no component failed.
- Durable SQLite checkpoints after decomposition, every component, aggregation,
  citation audit, and completion.
- Resume by root investigation ID without repeating completed provider work.
- Component-scoped benchmark-evidence pools, preventing an early component
  from consuming a later component's evidence.
- `investigate --complex`, `resume-complex`, complex-aware `show`, and
  `evaluate --complex`.
- `--no-hosted-model` for an explicit zero-cost local smoke path even when
  `.env` configures OpenAI.
- Complex evaluation metrics for component recall, parent linkage, protected
  context, material coverage, parent citation support, verdict accuracy, and
  estimated cost per completed component.
- Component-aware retrieval evaluation using one non-oracle query per expected
  material component, with completion, candidate, and reviewed-evidence
  recovery metrics.
- Strict comparison of two declared runs for completion, exact verdict-label,
  and exact normalized component-set stability.
- Typed human provenance with separate annotator and approver identities and
  dates; a reviewed case rejects self-approval.
- `audit-phase3`, which validates artifact identity and reports every numerical
  release gate as passed, failed, or pending without silently omitting missing
  declared runs.
- CPNG-011 through CPNG-020 expanded into ten genuine complex claims with 21
  expected material components and evidence mappings for every component.
- Transparent v2 AI annotator/critic records using `gpt-4o-mini`; they remain
  explicitly non-human and non-gold.

## Verified results

### Automated verification

- Tests: **178 passed**
- Coverage: **85.31%** (required: at least 85%)
- Ruff lint: **passed**
- Ruff formatting: **passed**
- Resume checks: decomposition, partial components, aggregation, citation
  audit, and completed reload are covered; completed provider calls are reused.

### Model-backed complex smoke

Artifact:
`artifacts/evaluations/phase3-complex-openai-smoke-v4.json`

Case: CPNG-011, evidence-oracle mode, `gpt-4o-mini`

| Metric | Result |
|---|---:|
| Completion | 100% |
| Expected-component recall | 100% |
| Parent linkage validity | 100% |
| Protected-context validity | 100% |
| Material-component coverage | 100% |
| Full parent citation support | 100% |
| Estimated cost per completed component | $0.001010 |

Verdict accuracy is correctly unavailable because CPNG-011 has not received
human gold approval.

### Retry and model-routing diagnostic

Artifact:
`artifacts/evaluations/phase3-retry-diagnostic-v2.json`

Cases: CPNG-017 through CPNG-020, evidence-oracle mode,
`gpt-5.4-mini` primary and `gpt-4o-mini` fast model

| Metric | Result |
|---|---:|
| Completion | 100% (4/4) |
| Expected-component recall | 100% |
| Parent linkage validity | 100% |
| Protected-context validity | 100% |
| Material-component coverage | 100% |
| Full parent citation support | 75% |
| Estimated cost per completed component | $0.008802 |

CPNG-020's second component exhausted its bounded retry after a transient
OpenAI HTTP 520. The coordinator correctly retained it as a failed component,
constrained the parent to `mixed`, and refused to award full parent citation
support. This diagnostic therefore verifies fail-closed behavior; it is not a
declared release run.

### Live retrieval and bounded-page evaluation

Artifacts:

- `artifacts/evaluations/phase3-live-retrieval.json`
- `artifacts/evaluations/phase3-live-retrieval-snapshot.json`
- `artifacts/evaluations/phase3-live-pages-top10.json`

Provider: local SearXNG; strategy: guarded fusion; top 10; component queries
enabled.

| Metric | Result | Gate |
|---|---:|---:|
| Live query completion | 100% (81/81) | at least 90% |
| Cases searched | 100% (20/20) | at least 90% |
| Component query completion | 100% (21/21) | at least 90% |
| Components with a candidate | 100% (21/21) | at least 90% |
| Components recovering reviewed evidence | 61.90% | diagnostic |
| Reviewed-passage lexical recall | 80.85% (38/47) | at least 80% combined |
| Case passage success | 90% | diagnostic |
| First-ten lexical recall | 86.96% (20/23) | regression gate |
| Phase 2 first-ten combined recall | 82.61% (19/23) | baseline |
| First-ten change | +4.35 points | no worse than -3 points |

The combined-recall gate passes from lexical matches alone. A preliminary
top-five fetch plus semantic evaluation reached 74.47%; expanding only the
already ranked candidates to top ten raised lexical recall to 80.85% without
new search queries or oracle hints.

The current machine-readable audit is
`artifacts/evaluations/phase3-gate-audit-pending.json`: **7 passed, 0 failed,
15 pending**. Pending gates are the CPNG-011–020 human review plus the two
declared runs and their derived stability comparison.

### Rights audit

- No source PDF was downloaded for CPNG-011 through CPNG-020.
- The live ranking contained eight PDF candidate URLs; all eight were rejected
  by the exact-host allowlist, so zero PDF candidates and zero PDF content were
  fetched.
- All research targets in the new packet are HTML pages.
- The only test-time PDF is a generated 429-byte blank fixture under the
  ignored `.pytest-tmp/` directory.
- A pre-existing ignored private handbook PDF dated 26 July 2026 remains under
  `docs/private/`; Phase 3 did not download or modify it.
- Durable benchmark storage contains bounded excerpts and metadata, not full
  pages.

## Closed release gates

### 1. Genuine human benchmark approval — completed

CPNG-011 through CPNG-020 were annotated by Md Moshiur Rahman and distinctly
approved by Md Rashedul Islam on 27 July 2026. CPNG-014 was approved as
`mixed`; the benchmark was promoted to version 5.

Review documents:

- `benchmarks/review_packets/cpng_011_020.md`
- `benchmarks/review_packets/cpng_011_020_ai_review.md`

### 2. Human-dependent declared runs — completed

Both declared evaluations pass: 100% completion, 90% accuracy, 100% parent
citation support, 100% exact repeated-label stability, and average per-component
costs below $0.009.

## Release decision

Phase 3 is complete. The machine audit reports 22 passed, 0 failed, and 0
pending gates.
