# Phase 9 Stage 9.0 completion report

Date: 29 July 2026

Status: Complete

## Outcome

The pre-refactor workflow is frozen as a reproducible migration baseline.
The manifest records all 20 reviewed claims, their approved expected labels,
available evidence and historical AI-review usage measurements, the current
`InvestigationService` responsibility boundary, compatibility-sensitive
schemas, and hashes of the benchmark, review packets, Phase 8 closure assets,
workflow source, API, report renderer, dashboard and Phase 9 planning records.

## Important measurement limitation

The benchmark contains reviewed labels and candidate evidence, but it does
not contain a complete per-case persisted production investigation for every
case. Therefore citation-support rate is explicitly `null` where it was not
measured, and search calls are recorded as zero for the offline review
artifact rather than inferred. Historical model usage, tokens, cost and
latency come only from recorded AI-review usage. Stage 9.0 does not fabricate
missing operational measurements.

## Frozen migration boundary

- LangGraph is the default orchestrator.
- `InvestigationService` remains the authoritative domain service.
- The direct orchestrator remains the rollback path.
- Eleven current responsibilities are mapped to their artifacts and writes.
- Six API/report/persistence compatibility contracts are recorded.
- Schema fingerprints protect investigation report, status and evidence shape.

## Cost and safety

This stage made zero model, search, network or PDF calls. It used only checked
repository artifacts and did not download copyrighted material.

## Exit decision

Stage 9.0 passes when the generated manifest verifies all hashes and schema
fingerprints and its tests pass. Stage 9.1 may now define operation contracts
against this frozen boundary.
