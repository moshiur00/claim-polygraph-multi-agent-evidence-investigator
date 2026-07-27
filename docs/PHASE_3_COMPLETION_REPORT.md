# Phase 3 completion report

Date: 27 July 2026

Status: **completed**

Theme: complex claims, retrieval robustness, and resumable typed workflow state

## Release decision

Phase 3 is complete. The machine-readable release audit reports **22 passed,
0 failed, and 0 pending gates** and `release_ready: true`.

Authoritative audit:
`artifacts/evaluations/phase3-v5-final-gate-audit.json`

The result remains a twenty-claim development benchmark, not a general
real-world accuracy estimate.

## Delivered capability

- Selective decomposition of complex claims into independently checkable
  material components.
- Immutable parent linkage and application-protected retention of submitted
  claim text, dates, geography, quantities, attribution, comparison basis, and
  causal context.
- Explicit component outcomes, unresolved reasons, and material-coverage
  accounting.
- Conservative deterministic parent aggregation that cannot hide a failed
  material component.
- Bounded refinement when a model merges independent causal conclusions or
  coordinated `both A and B` assertions.
- Evidence-label consistency checks for logically incompatible
  `unsupported`/`unverifiable` outputs.
- Compositional parent citation auditing with up to two bounded,
  evidence-preserving sentence revisions.
- Durable SQLite checkpoints after decomposition, each component,
  aggregation, audit, and completion.
- Resume without repeating completed search, model, fetch, or component work.
- Component-aware retrieval evaluation, guarded query fusion, frozen snapshots,
  bounded HTML extraction, and passage recovery measurement.
- Typed human provenance with separate annotator and distinct approver
  identities and dates.
- Machine-checkable Phase 3 release auditing and typed sharded-run merging.

## Human-reviewed benchmark

Dataset: `initial_claims`, version 5

- CPNG-001 through CPNG-020: **20/20 reviewed**
- Complex cases CPNG-011 through CPNG-020: **10/10 reviewed**
- Material components in CPNG-011 through CPNG-020: **21**
- Annotator: **Md Moshiur Rahman**
- Distinct approver: **Md Rashedul Islam**
- Annotation and approval date: **27 July 2026**
- CPNG-014 final label: **mixed**

The AI annotation and critique records remain stored as transparent,
non-controlling provenance.

## Live retrieval results

Provider: SerpAPI Google

Artifacts:

- `artifacts/evaluations/phase3-v5-serpapi-retrieval-snapshot.json`
- `artifacts/evaluations/phase3-v5-serpapi-retrieval.json`
- `artifacts/evaluations/phase3-v5-final-pages-top10.json`

| Gate | Required | Result |
|---|---:|---:|
| Live query completion | at least 90% | 100% |
| Cases with a candidate | at least 90% | 100% |
| Component query completion | at least 90% | 100% |
| Components with a candidate | at least 90% | 100% |
| Reviewed-passage recall | at least 80% | 80.85% |
| First-ten regression | no worse than -3 points | 0.00 points |

SearXNG was attempted first and rejected because it returned incomplete empty
responses. The workflow did not silently accept those snapshots; the complete
SerpAPI artifact became the declared retrieval run.

## Declared complex evaluations

Artifacts:

- `artifacts/evaluations/phase3-v5-final-run-a.json`
- `artifacts/evaluations/phase3-v5-final-run-b.json`
- `artifacts/evaluations/phase3-v5-final-stability.json`

| Gate | Required | Run A | Run B |
|---|---:|---:|---:|
| Completion | at least 90% | 100% | 100% |
| Expected-component recall | diagnostic | 100% | 100% |
| Parent linkage | 100% | 100% | 100% |
| Protected context | 100% | 100% | 100% |
| Material coverage | at least 90% | 100% | 100% |
| Verdict accuracy | at least 85% | 90% | 90% |
| Full parent citation support | at least 95% | 100% | 100% |
| Mean model cost per component | at most $0.02 | $0.008199 | $0.008780 |

Cross-run results:

- Completion stability: **100%**
- Exact repeated-label stability: **100%**
- Exact normalized component-set stability: **70%** diagnostic

Component-set stability is deliberately stricter than the release gate and
does not credit semantic paraphrases. Both runs nevertheless recovered every
reviewed material component under the deterministic containment-aware
diagnostic.

Run B retained seven valid case results from its isolated base execution and
replaced three affected cases with a declared sequential patch run. The typed
merge validated dataset identity and provider mode, rejected cases outside the
base set, and recomputed every aggregate metric from the final ten-case result
set. This provenance is recorded in the run limitations.

## Resume and failure behavior

Automated tests cover interruption after:

- decomposition;
- partial component completion;
- aggregation;
- citation audit; and
- completed reload.

Completed work is reused rather than repeated. Invalid decompositions,
incomplete retrieval snapshots, provider failures, unresolved components, and
partial citation audits remain visible and fail closed.

## Rights and retention

- No unapproved PDF was downloaded.
- The final page evaluation fetched **zero PDF candidates** and stored **zero
  PDF content**.
- Retrieval retained URLs, metadata, short reviewed excerpts, and bounded
  passages rather than full pages.
- Production queries did not contain reviewed URLs or passages.
- Test PDF content is generated locally as a tiny fixture.

## Automated verification

- Tests: **178 passed**
- Coverage: **85.31%**; required at least 85%
- Ruff lint: **passed**
- Ruff formatting: **passed**
- Machine release audit: **22 passed, 0 failed, 0 pending**

## Diagnostics retained

Failed and superseded runs remain under `artifacts/evaluations/` rather than
being overwritten. They document:

- transient provider HTTP failures;
- incomplete SearXNG snapshots;
- evidence excerpts missing decisive numerical or satirical context;
- causal and coordinated component merging;
- verdict-taxonomy instability; and
- citation-revision behavior.

These diagnostics drove generic fixes. No reviewed URL or expected verdict was
inserted into production retrieval queries or model inputs.

## Architecture decision

The typed single-coordinator baseline is sufficient for this phase. LangGraph,
PostgreSQL, Redis, pgvector, multi-runtime agents, and a production frontend
remain target-architecture options rather than prerequisites.

The next phase may introduce multi-agent execution only through controlled
experiments against this baseline. It must demonstrate measurable improvement
in retrieval diversity, evidence independence, difficult-claim coverage, or
cost/latency tradeoffs without weakening provenance, rights controls, resume
correctness, or release-gate auditability.
