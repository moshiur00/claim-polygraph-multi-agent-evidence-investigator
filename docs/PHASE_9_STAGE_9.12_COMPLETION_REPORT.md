# Phase 9 Stage 9.12 — Frozen comparison and role ablation

> Historical gate result: this report records the original Stage 9.12
> comparison. Stage 9.12a subsequently repaired the stance-semantic regression
> and replayed the same frozen benchmark. See
> `PHASE_9_STAGE_9.12A_COMPLETION_REPORT.md` for the current result.

## Decision

The unified authoritative graph is **not eligible for promotion yet**. It
completed every case, preserved citation support, improved aggregate evidence
and family coverage, routed every reviewed case to review, and produced no
duplicate paid operation. However, it changed seven of twenty direct-workflow
verdicts. The mandatory verdict-equivalence gate therefore failed.

This is a useful failure: the comparison identified a semantic integration
problem rather than an infrastructure or persistence problem.

## Controlled comparison

Every path received the same frozen CPNG-001 through CPNG-020 reviewed evidence
annotations through case-scoped local providers.

| Metric | Direct | Previous wrapper | Unified | Minus challenger |
|---|---:|---:|---:|---:|
| Completion | 100% | 100% | 100% | 100% |
| Reviewed-label accuracy | 20% | 20% | 20% | 20% |
| Verdict equivalence to direct | 100% | 100% | 65% | 65% |
| Review-routing recall | 0% | 20% | 100% | 100% |
| Mean evidence coverage | 96.7% | 96.7% | 100% | 88.3% |
| Mean family coverage | 90.8% | 90.8% | 92.5% | 84.2% |
| Challenge/qualification coverage | 100% | 100% | 35% | 0% |
| Citation support | 100% | 100% | 100% | 100% |
| Search calls | 60 | 60 | 75 | 42 |
| Model calls | 125 | 125 | 0 | 0 |
| Duplicate paid operations | 0 | 0 | 0 | 0 |
| Median local latency | 0.364 s | 0.396 s | 0.972 s | 0.978 s |
| Median latency ratio | 1.00x | 1.09x | 2.67x | 2.69x |

The fixture run made no paid calls. The historical recorded cost of the frozen
baseline is $0.0409845; it is included as context and is not treated as a
current price estimate. Provider work units show that the unified fixture used
40.5% of the direct path's search-plus-model call count, largely because its
research worker is deterministic and performs no model classification.

## Regression analysis

The unified graph changed CPNG-002, CPNG-005, CPNG-006, CPNG-013, CPNG-018,
CPNG-019 and CPNG-020 from `mixed` to `supported`.

The cause is the boundary between role research and judgment semantics.
`DeterministicResearchWorker` records challenger passages as `qualifies`, while
the deterministic verdict provider groups `qualifies` with supporting
evidence. The direct workflow classifies contradiction-path evidence as
`contradicts`. Moving genuine multi-agent research into the authoritative graph
therefore changed the meaning of the evidence packet even though the source
material was the same.

The twenty-case reviewed-label accuracy is only 20% for all variants. This does
not establish production quality: the deterministic model validates workflow
contracts and is not intended to reproduce nuanced labels such as
`misleading`, `outdated`, or qualified subgroup conclusions. Stage 9.12 uses
accuracy as a regression signal, not as confidence calibration.

## Ablation finding

Removing the challenger reduced mean evidence coverage from 100% to 88.3%,
family coverage from 92.5% to 84.2%, and challenge/qualification coverage from
35% to zero. Challenger research made a material evidence or family
contribution in seven cases. The role is therefore useful, but its typed stance
output must be reconciled consistently before judgment.

## Required remediation before Stage 9.13

1. Define one role-to-evidence stance contract shared by direct and multi-agent
   research.
2. Preserve the distinction between support, qualification and contradiction
   through consolidation and verdict drafting.
3. Add unit tests for challenger passages that contradict, merely qualify, or
   supply neutral context.
4. Replay Stage 9.12 and require 100% verdict equivalence without losing the
   challenger coverage gains.

No live search, external model, network fetch or PDF operation was used.
