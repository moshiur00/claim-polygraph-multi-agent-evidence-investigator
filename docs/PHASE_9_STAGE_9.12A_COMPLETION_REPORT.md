# Phase 9 Stage 9.12a — Stance-semantic remediation

## Decision

The Stage 9.12a remediation is **complete**. The unified authoritative graph
now preserves the direct workflow's verdict on all 20 frozen benchmark claims,
while retaining the challenger's material evidence-coverage gains.

Stage 9.12b subsequently integrated typed review routing and raised the frozen
benchmark's review-routing recall from 60% to 100%. The complete comparison is
now eligible for the Stage 9.13 audit.

## Root cause and contract

The former deterministic research worker encoded challenger passages as
`qualifies`, while deterministic judgment treated `qualifies` as support.
That crossed two independent concepts:

- research role: who looked for the evidence;
- evidence stance: what the passage says about the claim.

`analysis.stance` is now the shared, role-independent boundary. It preserves
four distinct relationships:

| Evidence packet | Deterministic fixture verdict |
|---|---|
| Support only | `supported` |
| Contradiction without support | `contradicted` |
| Qualification without support | `mixed` |
| Support plus contradiction or qualification | `mixed` |
| Context only or no usable evidence | `unverifiable` |

A challenger may therefore produce contradiction, qualification, or neutral
context. Its role never determines its stance.

## Frozen 20-claim replay

| Metric | Unified | Without challenger |
|---|---:|---:|
| Verdict equivalence to direct | **100%** | 95% |
| Mean evidence coverage | **100%** | 88.3% |
| Mean family coverage | **92.5%** | 84.2% |
| Challenge/qualification case coverage | **100%** | 95% |
| Duplicate paid operations | **0** | 0 |

The challenger made a material evidence or family contribution in seven
claims. The remediation therefore did not obtain equivalence by suppressing
counter-evidence.

The reviewed-label accuracy remains 40% for both direct and unified fixture
paths. That result reflects the deliberately simple deterministic verdict
provider, not a calibrated production-quality judgment model. Stage 9.12a
only proves parity and preservation of research coverage.

## Regression protection

Tests now cover:

- support plus contradiction;
- support plus material qualification;
- context-only evidence;
- challenger contradiction, qualification, and context stances;
- 20-case direct/unified equivalence;
- challenger evidence, family, and challenge-coverage gains.

The replay used recorded local evidence only: no external model, live search,
network fetch, PDF download, or paid provider operation was performed.
