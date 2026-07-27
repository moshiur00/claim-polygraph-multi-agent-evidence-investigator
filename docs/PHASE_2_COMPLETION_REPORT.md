# Phase 2 completion report

Status: **closed and complete**

Closed: 27 July 2026

Benchmark: `initial_claims`, version 4, CPNG-001 through CPNG-010

## Outcome

Phase 2 is complete. Every blocking exit gate in the approved execution plan
passed. The project now has a ten-claim, citation-grounded, independently
approved benchmark; a measured SerpAPI retrieval path; bounded page and
passage evaluation; and two declared ten-claim end-to-end runs.

These results are a development benchmark, not an estimate of general
fact-checking accuracy.

## Exit-gate results

| Gate | Required | Result | Status |
|---|---:|---:|:---:|
| Human-reviewed benchmark | 10/10 with distinct approval | 10/10 | Pass |
| Live query completion | at least 90% | 30/30 (100%) | Pass |
| Cases with a live candidate | at least 90% | 10/10 (100%) | Pass |
| Combined reviewed-passage recall | at least 75% | 19/23 (82.61%) | Pass |
| First-five retrieval regression | at least 75% | 9/12 (75.00%) | Pass |
| End-to-end completion, run 1 | at least 90% | 10/10 (100%) | Pass |
| End-to-end completion, run 2 | at least 90% | 10/10 (100%) | Pass |
| Verdict accuracy, run 1 | at least 80% | 9/10 (90%) | Pass |
| Verdict accuracy, run 2 | at least 80% | 8/10 (80%) | Pass |
| Full citation support, run 1 | at least 90% | 10/10 (100%) | Pass |
| Full citation support, run 2 | at least 90% | 10/10 (100%) | Pass |
| Exact repeated-label stability | at least 90% | 9/10 (90%) | Pass |
| Mean model cost, run 1 | at most $0.02/case | $0.010849785 | Pass |
| Mean model cost, run 2 | at most $0.02/case | $0.010615245 | Pass |
| Rights compliance | zero violations | zero | Pass |
| Tests, lint, formatting, coverage | all pass; at least 85% | 139 passed; 85.75% | Pass |

The review-status command was run explicitly for CPNG-001 through CPNG-010
and reported `Reviewed: 10/10`. Md Moshiur Rahman was the annotator and
Md Rashedul Islam was the distinct approver; approval was recorded on
27 July 2026.

## Retrieval evaluation

The live SerpAPI Google snapshot used three generic, claim-derived query paths
per case and returned ten candidates for every case. It completed all 30
search calls without accepting a silently empty query.

The candidate stage had low strict reviewed-URL recall (13.04%) and reviewed
host recall (17.39%). This shows that URL matching alone understates useful
retrieval, but it also identifies source targeting as an area for improvement.
Of 50 selected pages, 38 were fetched and extracted (76%). Lexical passage
matching found 17 of 23 reviewed evidence points. Bounded semantic evaluation
accepted two additional passages as equivalent, producing 19/23 combined
recall (82.61%).

For CPNG-001 through CPNG-005, lexical matching found 8/12 evidence points and
semantic evaluation recovered one equivalent point, giving 9/12 (75%). This
equals, and therefore does not regress below, the Phase 1 baseline.

## Declared end-to-end results

| Case | Gold | Run 1 | Run 2 | Exact stability |
|---|---|---|---|:---:|
| CPNG-001 | misleading | misleading | misleading | Yes |
| CPNG-002 | misleading | misleading | misleading | Yes |
| CPNG-003 | misleading | misleading | misleading | Yes |
| CPNG-004 | outdated | outdated | outdated | Yes |
| CPNG-005 | contradicted | contradicted | contradicted | Yes |
| CPNG-006 | supported | unsupported | unsupported | Yes |
| CPNG-007 | supported | supported | supported | Yes |
| CPNG-008 | supported | supported | supported | Yes |
| CPNG-009 | supported | supported | mostly_supported | No |
| CPNG-010 | misleading | misleading | misleading | Yes |

Run 1 made 79 metered model calls and cost an estimated $0.10849785. Run 2
made 77 calls and cost an estimated $0.10615245. Price calculations are
development estimates, not billing records.

The main remaining quality defects are visible rather than hidden:

- CPNG-006 was consistently wrong because live retrieval did not surface
  sufficiently direct, year-specific nominal-GDP evidence.
- CPNG-009 varied by one adjacent label because the evidence supported the
  population-level relationship but the model differed on the degree of
  qualification.
- Ten cases are too few to claim general real-world performance.

## Reliability changes completed

- Increased the default bounded model-call budget from 8 to 12, which covers
  the designed worst-case workflow while retaining a hard limit.
- Normalized a bare model-produced year to a valid end-of-year reference date.
- Added generic research-path query shaping without using benchmark-only URL
  or evidence hints.
- Deduplicated result URLs across research paths so repeated pages no longer
  consume retrieval and evidence slots.
- Updated integration coverage to assert the deduplicated behavior.

Earlier failed or weaker runs remain in `artifacts/evaluations` as diagnostic
records; they were not silently replaced or selected case by case.

## Rights and retention

No PDF host was approved for the ten-claim retrieval evaluation. Two PDF
candidates reached the page evaluator, and both were rejected before download
with `PdfPermissionRequiredError`. The declared end-to-end artifacts contain
no PDF URL. Only bounded evidence passages and provenance metadata were
retained; no full-page persistence was enabled.

## Infrastructure decision

Keep SQLite and the in-process workflow for the next phase. Phase 2 did not
show a repeated interruption or review-resume failure that justifies adding
LangGraph, PostgreSQL, Redis, or pgvector now. The observed defects are
retrieval coverage and verdict calibration problems; additional
infrastructure would not directly solve them.

SerpAPI Google remains the primary live-search provider. SearXNG remains an
experimental self-hosted comparison, not a silent fallback.

## Evidence artifacts

- `phase2-ten-serpapi-snapshot-v1.json`
- `phase2-ten-serpapi-quality-v1.json`
- `phase2-ten-serpapi-pages-v1.json`
- `phase2-ten-serpapi-semantic-v1.json`
- `phase2-ten-live-e2e-v4-independent-declared-1.json`
- `phase2-ten-live-e2e-v5-independent-declared-2.json`

All files are under `artifacts/evaluations/`.

## Recommended Phase 3 focus

Phase 3 should improve evidence diversity and verdict calibration before
introducing the full target infrastructure. Start by adding regression cases
CPNG-011 through CPNG-020, diagnosing CPNG-006 retrieval, defining
adjacent-label policy for cases such as CPNG-009, and rerunning the same staged
retrieval and declared end-to-end gates on the expanded reviewed set.
