# Phase 1 completion report

Evidence date: 26 July 2026  
Closed: 27 July 2026  
Decision: **closed and complete for the five-claim lightweight vertical slice**

This decision applies to the current evidence-quality milestone, not to the
entire product roadmap. PostgreSQL, Redis, pgvector, LangGraph orchestration,
production SearXNG operations, and the frontend remain target-architecture
work.

## Scope and ground truth

The scored benchmark is `initial_claims` version 3, cases CPNG-001 through
CPNG-005. Md Moshiur Rahman completed the annotation and Md Rashedul Islam
performed the distinct approval on 26 July 2026. All five cases have reviewed
evidence packets and expected verdicts.

## Exit gates

| Gate | Required | Result | Evidence |
|---|---:|---:|---|
| Reviewed benchmark | 5 approved cases | 5/5 | `benchmarks/review_packets/cpng_001_005.md` |
| Combined passage recall | at least 75% | 75% | `semantic-passages-v4-top5-frozen.json` |
| Live-page workflow completion | 100% | 100% | both final runs |
| Verdict accuracy | 100% on the five reviewed cases | 100% | both final runs |
| Fully supported citation audits | at least 90% | 100% | both final runs |
| Repeated-run label stability | identical reviewed-case labels | 5/5 identical | both final runs |
| Automated verification | lint, tests, coverage threshold | passed | 121 tests; 85.56% coverage |

Final repeated runs:

- `phase1-live-e2e-v8-enforced-audit.json`: 5/5 completed, 100% verdict
  accuracy, 100% full citation audits, 37 metered model calls, estimated model
  cost $0.051832.
- `phase1-live-e2e-v9-enforced-repeat.json`: 5/5 completed, 100% verdict
  accuracy, 100% full citation audits, 37 metered model calls, estimated model
  cost $0.056379.

Both runs produced the same labels:

| Case | Label |
|---|---|
| CPNG-001 | misleading |
| CPNG-002 | misleading |
| CPNG-003 | misleading |
| CPNG-004 | outdated |
| CPNG-005 | contradicted |

## Retrieval result

The bounded top-five page evaluation attempted 25 candidates. Its fetch success
was 88%, extraction success was 84%, lexical reviewed-passage recall was
66.67%, and case success was 80%. The bounded semantic evaluator recovered one
additional equivalent target, raising combined passage recall to exactly 75%.
The semantic evaluation's estimated model cost was $0.009628.

The final investigation runs replayed the accepted frozen candidate ranking but
fetched the selected public HTML pages live. This separates ranking
reproducibility from page-access and extraction behavior.

## Citation enforcement

The sentence auditor now receives the original claim, verdict label, and all
approved evidence items. It runs on the primary reasoning model rather than the
fast model. When an audit is partial and supplies a conservative revision, the
application may revise only the concise verdict sentence and audit it once
more. The final stored verdict and audit always refer to the same sentence.
This is a bounded correction pass; it cannot add evidence, URLs, or facts.

## Rights and copyright controls

- PDF fetching remains denied by default and requires an exact explicitly
  approved host.
- No PDF was downloaded for the final benchmark runs.
- Search visibility is not treated as copying permission.
- Unknown rights status is retained as unknown.
- Full fetched pages and unselected chunks are not persisted.
- Stored evidence is limited to bounded selected passages, provenance,
  timestamps, offsets, hashes, and retrieval metadata.

## Known limitations

The current local SearXNG instance is not yet a dependable production search
service. Its default engines were suspended or challenged, while the tested
Bing/Mojeek combination produced a complete but low-quality snapshot with zero
reviewed page recall. The accepted retrieval score therefore uses a previously
captured, rights-safe frozen Startpage candidate snapshot. Production SearXNG
engine configuration, monitoring, and fallback policy remain Phase 2 work.

Five cases are enough for a vertical-slice exit, not for statistical claims
about general fact-checking accuracy. The result must be described as 5/5 on
this reviewed benchmark, never as general 100% accuracy. Model costs are
versioned estimates, not invoices. Independence and temporal safeguards can
still require human review even when the workflow completes.

## Phase 2 entry

Phase 2 is approved to start. Its detailed scope and gates are recorded in
`docs/PHASE_2_EXECUTION_PLAN.md`. It will expand the reviewed benchmark before
optimizing infrastructure:

1. Human-review CPNG-006 through CPNG-010 using the existing two-person policy.
2. Repair and monitor live SearXNG engines, then capture a new non-empty,
   rights-safe snapshot.
3. Compare live-search retrieval with the frozen control and preserve
   per-stage failure metrics.
4. Add a CLI-level regression test for the audit repair path.
5. Re-run the expanded benchmark and set Phase 2 gates before introducing
   PostgreSQL, Redis, pgvector, or frontend complexity.
