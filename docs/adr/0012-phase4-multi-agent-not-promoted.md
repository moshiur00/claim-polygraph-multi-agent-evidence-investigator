# ADR 0012: Keep Phase 3 as the default workflow

Date: 27 July 2026

Status: accepted

## Decision

Phase 4 is complete, but its bounded multi-agent workflow is not promoted. The
Phase 3 single-coordinator workflow remains the default. Phase 4 remains
available only as experimental infrastructure.

## Evidence

The corrected three-claim pilot achieved 3/3 expected verdicts, full citation
support, no regressions, a median latency of 22.293 seconds, and an estimated
cost of $0.03882495. It improved one case over Phase 3, below the predeclared
minimum of two.

The initial parent result for CPNG-014 exposed a generic deterministic
aggregation defect: a misleading component plus a contradicted component was
labelled misleading instead of mixed. The rule was corrected and the stored
component outputs were recomputed without another provider call.

## Consequences

- The ten-claim paid comparison and repeat-stability run are skipped by gate.
- Academic specialization remains conditional and experimental; the pilot did
  not show case-level benefit attributable to that role.
- Future work should improve evidence-family breadth and role contribution
  measurement before reconsidering promotion.
