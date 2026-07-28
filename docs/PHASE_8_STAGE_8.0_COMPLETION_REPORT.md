# Phase 8 Stage 8.0 completion report

Date: 28 July 2026

Status: Complete

## Outcome

The promoted LangGraph baseline, direct rollback, reviewed 20-case benchmark,
resource ceilings and Phase 8 quality gates are frozen. Stage 8.0 used no
model, search, network or PDF calls.

## Review-routing controls

The new balanced routing set contains five mandatory-review cases and five
safe automatic cases.

| Metric | Result | Gate |
|---|---:|---:|
| Mandatory-review recall | 100% | 100% |
| Automatic-route specificity | 100% | at least 80% |
| Review precision | 100% | reported |
| Overall route accuracy | 100% | at least 90% |
| Citation-assurance accuracy | 100% | at least 95% |
| False positives | 0 | reported |
| False negatives | 0 | 0 |

These deterministic fixtures establish that specificity can be measured. They
do not yet establish real-world routing calibration.

## Locked promotion controls

- Five-case pilot before any larger paid comparison.
- Zero verdict regressions.
- At least two improved pilot cases.
- No duplicate paid operations.
- Mean cost no more than 2x baseline.
- Median latency no more than 2x baseline.
- Maximum two research rounds and four concurrent roles.
- At least 95% citation support and 100% material-sentence audit coverage.

## Documentation and source control

- README now reflects Phases 1–7, the reviewed 20-case benchmark, LangGraph
  promotion, experimental multi-agent status and Phase 8 gaps.
- Benchmark documentation now reflects dataset version 5 and all 20 reviewed
  cases.
- ADR 0015 selects a root monorepo for the dashboard.
- The former nested dashboard repository's complete three-commit history is
  stored in a verified Git bundle.
- Only `dashboard/.git` was removed. Dashboard source and the formerly
  untracked accessibility test remain.
- Dashboard build/test scripts now set their environment portably and lint
  excludes generated work output.

## Artifact integrity

The Stage 8.0 manifest freezes 15 artifacts spanning the authoritative
benchmark, routing controls, Phase 7 baseline, promotion/topology ADRs,
dashboard history and configuration, documentation and this completion report.

## Frozen limitations

- Authoritative reviewed-label agreement remains 90%.
- CPNG-006 and CPNG-019 remain disclosed disagreements.
- The balanced routing controls are synthetic deterministic cases.
- Multi-agent research remains unpromoted.
- SQLite concurrency, durable jobs, full-report citation assurance,
  confidence calibration and production telemetry remain later Phase 8 work.
