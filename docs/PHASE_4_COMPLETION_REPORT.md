# Phase 4 completion report

Date: 27 July 2026

## Outcome

Phase 4 is complete. The bounded multi-agent workflow is **not promoted**, and
the proven Phase 3 single-coordinator workflow remains the default.

## Controlled pilot

| Measure | Result | Gate |
|---|---:|---|
| Completed cases | 3/3 | Pass |
| Correct verdicts after deterministic recomputation | 3/3 | Pass |
| Cases improved over Phase 3 | 1/3 | **Fail: required 2** |
| Regressions | 0 | Pass |
| Full citation support | 100% | Pass |
| Estimated paid cost | $0.03882495 | Pass: ceiling $0.11330610 |
| Median latency | 22.293 s | Pass: ceiling 90.447 s |
| Live page or PDF fetches | 0 | Pass |

CPNG-014 initially failed because the generic parent aggregation rule treated
the combination `misleading + contradicted` as `misleading`. The component
results themselves were correct. The rule was corrected to produce `mixed`,
then the saved component outputs were recomputed without retrieval or model
calls. Both the original and corrected artifacts are retained for provenance.

## Remaining-stage decisions

- Stage 4.7: complete. The academic role was conditionally activated for
  CPNG-016 and CPNG-020, but those cases were already correct in Phase 3. No
  specialist is promoted by default.
- Stage 4.8: closed as skipped by the declared pilot gate. Running the
  ten-claim comparison would violate the cost-control protocol.
- Repeat stability: also skipped by gate because no promoted ten-claim run
  exists.
- Stage 4.9: complete. The final machine-readable audit and architecture
  decision record the negative promotion result.

## Artifact trail

- `phase4-experiment-manifest-v1.json`: locked experiment definition.
- `phase4-pilot-preflight.json`: matched controls and resource ceilings.
- `phase4-pilot-dry-run.json`: zero-cost structural validation.
- `phase4-paid-pilot.json`: original provider outputs.
- `phase4-paid-pilot-final.json`: deterministic parent-label recomputation.
- `phase4-final-gate-audit.json`: authoritative closure decision.

The implementation used schema-constrained OpenAI outputs followed by local
typed validation. Retrieved benchmark passages remained the only evidence;
models could not invent or bypass evidence records.
