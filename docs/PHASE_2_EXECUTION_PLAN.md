# Phase 2 execution plan

Status: **closed and complete**

Start date: 27 July 2026

Close date: 27 July 2026

Theme: benchmark expansion and live-retrieval hardening

The final gate results, case-level outcomes, rights check, limitations, and
infrastructure decision are recorded in
[`PHASE_2_COMPLETION_REPORT.md`](PHASE_2_COMPLETION_REPORT.md).

## Purpose

Phase 1 proved that the lightweight evidence-to-verdict vertical slice works
on five reviewed claims. Phase 2 must test whether that result survives a
broader set of claim types and replace the frozen search-candidate dependency
with a measurable, dependable live retrieval path.

This execution phase crosses several items in the original architecture
roadmap. It does not mean that every target-architecture component is now
needed. The project will continue to add infrastructure only when evaluation
shows a concrete need.

## Starting state

- CPNG-001 through CPNG-005 are human-reviewed and independently approved.
- Two consecutive final Phase 1 runs completed all five cases with identical
  verdict labels and fully supported concise verdict sentences.
- Combined reviewed-passage recall is 75% using a frozen candidate ranking and
  live public-page fetching.
- CPNG-006 through CPNG-010 are drafts. They currently have no evidence packet,
  proposed verdict, expected verdict, reviewer, or approval metadata.
- The local SearXNG service responds, but its tested engines do not yet provide
  acceptable reviewed-source recall.
- SerpAPI is selected as the primary Phase 2 live-search provider; SearXNG
  remains an experimental self-hosted comparison.

## Progress checkpoint — 27 July 2026

The first provider milestone is complete:

- Added a secret-safe SerpAPI provider supporting Google and optional
  DuckDuckGo results.
- Added CLI configuration, normalized failures, verified operating-system TLS,
  and one bounded transient retry.
- Captured a five-claim, three-query Google snapshot with 15/15 successful
  search calls.
- The top-five page run fetched and extracted 76% of attempted candidates,
  reached 66.67% lexical passage recall, and succeeded on 80% of cases.
- Bounded semantic evaluation recovered two equivalent evidence points and
  raised combined passage recall to 83.33%, above the 75% gate.
- A live SerpAPI-to-page-to-verdict smoke run completed 5/5 cases, matched all
  five reviewed verdicts, produced full citation support for all five concise
  verdict sentences, and estimated $0.009443 model cost per completed case.
- No PDF host was approved or downloaded.

SerpAPI Google is therefore promoted as the primary provider for preparing
CPNG-006. The next milestone is the CPNG-006 provisional evidence packet and
genuine two-person review.

## Objectives

1. Expand the scored benchmark from five to ten genuinely human-reviewed
   claims.
2. Make SerpAPI live retrieval observable and dependable enough to evaluate
   without silently falling back to frozen candidates, while retaining SearXNG
   as a non-blocking comparison.
3. Preserve evidence rights, provenance, source-independence, temporal,
   numerical, and citation-audit safeguards.
4. Measure quality, stability, latency, and cost on the expanded benchmark.
5. Decide from evidence whether durable workflow orchestration is justified
   for the following phase.

## Workstreams

### 1. Benchmark expansion

Prepare CPNG-006 through CPNG-010 one case at a time:

1. Record the exact claim interpretation, ambiguity resolution, reference
   date, geography, units, and definitions.
2. Build a bounded evidence packet containing an authoritative or primary
   source, independent corroboration, and contradictory or qualifying evidence
   where available.
3. Verify every retained passage against its surrounding page context.
4. Record rights status and retain only bounded passages. Do not download a PDF
   unless its exact host has been explicitly approved after a rights check.
5. Use an LLM only to prepare a provisional annotation and critique. Do not
   represent AI output as human review.
6. Have Md Moshiur Rahman complete the annotation and a distinct approver
   complete the second review.
7. Increment the benchmark dataset version when the five new reviewed cases
   are accepted.

Deliverables:

- A CPNG-006–010 review packet.
- Five completed evidence packets in the benchmark dataset.
- Reviewer and distinct-approver identities and dates.
- `review-status` reporting 10/10 across CPNG-001–010.

### 2. Live search integration and comparison

1. Use SerpAPI Google as the primary live engine and DuckDuckGo only as an
   optional comparison.
2. Keep credentials in the Git-ignored environment file and never place them
   in commands, traces, provider IDs, or artifacts.
3. Distinguish connection, HTTP, authentication, quota, empty-result,
   rate-limit, and malformed-response failures.
4. Use bounded retry, pacing, and per-provider telemetry.
5. Reject a snapshot when required queries are missing or silently empty.
6. Capture a new rights-safe SerpAPI snapshot for the ten reviewed claims.
7. Keep the Phase 1 frozen snapshot as a reproducible control and SearXNG as a
   diagnostic comparison; never silently substitute either for live SerpAPI.

Deliverables:

- Documented SerpAPI configuration and optional SearXNG comparison.
- Health-check output and normalized failure report.
- A valid ten-claim live search snapshot.
- SerpAPI-versus-frozen retrieval comparison.

### 3. Retrieval and evidence-quality evaluation

Run the evaluation stages separately so failures remain attributable:

1. Search-candidate recall and rank.
2. Page access and readable-text extraction.
3. Passage ranking and lexical reviewed-passage coverage.
4. Bounded semantic recovery for eligible unmatched passages.
5. Source-family independence and rights/retention checks.

Do not optimize only for the reviewed URLs. Query shaping must remain generic
and derived from the submitted claim, never from hidden benchmark evidence.

Deliverables:

- Ten-claim retrieval, page, and semantic evaluation artifacts.
- Per-case failure analysis.
- A comparison against the five-claim Phase 1 baseline.

### 4. Expanded end-to-end evaluation

Run the ten reviewed claims twice using the same configuration. Record:

- completion and failure types;
- verdict labels and agreement with reviewed labels;
- citation support;
- independent-family and context-review warnings;
- tokens, estimated cost, latency, search calls, and page fetches;
- whether a bounded audit revision was needed.

A failed case remains failed. Do not rerun individual cases merely to select a
better answer; repeat only the declared benchmark run.

### 5. Reliability and regression protection

Add tests for:

- CLI use of frozen and live retrieval modes;
- audit-guided revision and its one-retry limit;
- SerpAPI authentication, quota, empty-result, and transient-failure
  diagnostics;
- SearXNG empty-result and engine-failure diagnostics where it remains enabled;
- benchmark versioning and human-review requirements;
- no unapproved PDF download;
- interrupted-run persistence behavior.

Use the existing SQLite and in-process workflow during this phase. At the exit
review, decide whether observed interruption or review-resume failures justify
LangGraph and durable checkpoints.

## Phase 2 exit gates

All blocking gates must pass:

| Gate | Required result |
|---|---:|
| Human-reviewed benchmark | 10/10 cases with distinct approval |
| Live query completion | at least 90%, with no silent empty snapshot acceptance |
| Cases with at least one live candidate | at least 90% |
| Combined reviewed-passage recall | at least 75% overall |
| First-five retrieval regression | not below the 75% Phase 1 combined recall |
| End-to-end completion | at least 90% in each of two declared runs |
| Verdict accuracy | at least 80% in each run |
| Full citation support | at least 90% in each run |
| Repeated-run label stability | at least 90% |
| Estimated model cost | at most $0.02 per completed case on average |
| Rights compliance | zero unapproved PDF downloads or full-page persistence |
| Automated verification | all tests and lint pass; coverage at least 85% |

With ten cases, each case materially changes a percentage. The exit report
must therefore include case-level results and must not present these metrics as
general real-world accuracy.

## Stop and review conditions

Pause the current approach and review the design if any of these occurs:

- live SerpAPI cannot produce candidates for at least 90% of cases after one
  bounded provider/query experiment;
- passage recall remains below 75% after one documented query/ranking
  iteration;
- the same workflow interruption or audit failure repeats in three declared
  runs;
- average model cost exceeds $0.02 per completed case;
- improving a metric would require using benchmark-only source hints;
- source access would require unclear or unapproved copying rights.

## Explicitly out of scope

Unless a stop condition provides evidence that they are needed, Phase 2 will
not introduce:

- PostgreSQL, Redis, or pgvector;
- LangGraph or multiple model runtimes in one investigation;
- the multi-agent coordinator;
- a production frontend;
- unrestricted crawling, bulk document storage, or automatic PDF downloading.

## Execution order

1. Prepare the ambiguity and evidence requirements for CPNG-006.
2. Build and review CPNG-006 fully before repeating the process for CPNG-007
   through CPNG-010.
3. In parallel with human availability, validate SerpAPI on the first five
   cases and capture the live search snapshot.
4. Run staged retrieval evaluation on all ten reviewed claims.
5. Run two declared end-to-end evaluations.
6. Produce the Phase 2 exit report and the infrastructure decision for the
   next phase.

Execution is complete. The final evidence and gate decisions are recorded in
[`PHASE_2_COMPLETION_REPORT.md`](PHASE_2_COMPLETION_REPORT.md); any future work
starts under a separately approved Phase 3 plan.
