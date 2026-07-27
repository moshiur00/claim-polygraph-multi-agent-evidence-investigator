# Claim Polygraph NG

Claim Polygraph NG is an evidence-first claim investigation system. It will
decompose complex claims when useful, retrieve supporting and contradictory
evidence, assess source quality and independence, verify numerical and temporal
context, and produce citation-audited verdicts.

The project begins with a lightweight vertical slice and grows toward a durable
multi-agent architecture only after the core evidence workflow is measurable.

## Current milestone

The repository now contains the executable atomic workflow plus the Phase 3
complex-claim coordinator:

- claims and investigation plans;
- sources, evidence, and source assessments;
- verdicts and sentence-level citation audits;
- execution budgets and operating-mode policies.
- asynchronous model and search provider protocols;
- deterministic providers for reproducible development;
- SQLite persistence for investigations, artifacts, and trace events;
- an end-to-end claim-to-audited-verdict application service.
- a local CLI with JSON, Markdown, and trace exports.
- bounded document chunks with exact source-relative offsets;
- deterministic BM25-style claim-passage ranking and top passage selection.
- selective, typed claim decomposition with protected parent context;
- one durable child investigation per material component;
- component-coverage accounting and constrained parent aggregation;
- resumable SQLite checkpoints that reuse completed work;
- complex-run evaluation metrics for decomposition, context, coverage,
  citations, verdicts, and cost.

The mock providers deliberately return synthetic evidence. They validate
orchestration, policy, persistence, and audit contracts; they do not perform
real fact-checking.

See the complete
[project specification](docs/PROJECT_SPECIFICATION_AND_PLAN.md).

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
```

## Local CLI

The CLI uses deterministic synthetic providers by default. It is intended to
validate the workflow and report format before real providers are enabled.
If `.env` defines an OpenAI model, add `--no-hosted-model` to explicitly force
the local deterministic or selected Ollama provider.

```powershell
claim-polygraph investigate "The claim to investigate"
claim-polygraph investigate --complex "A compound claim with two assertions"
claim-polygraph resume-complex ROOT_INVESTIGATION_ID
claim-polygraph list
claim-polygraph show INVESTIGATION_ID
```

To opt into real retrieval through a trusted SearXNG instance whose JSON output
is enabled:

```powershell
claim-polygraph --searxng-url http://localhost:8080 investigate "The claim"
```

Alternatively, set `SEARXNG_BASE_URL`. Search-result pages are validated
against the public-network policy and fetched with redirect, content-type,
timeout, and response-size limits. The structured analysis and verdict remain
deterministic unless an Ollama model is explicitly enabled.

For Phase 2, SerpAPI is the primary live-search path and SearXNG remains an
optional self-hosted comparison. Put the key only in the Git-ignored `.env`
file:

```dotenv
SERPAPI_API_KEY=your-real-key
SERPAPI_ENGINE=google
SERPAPI_LANGUAGE=en
SERPAPI_COUNTRY=us
SERPAPI_TIMEOUT_SECONDS=15
```

Then run:

```powershell
claim-polygraph --serpapi-engine google investigate "The claim"
```

`duckduckgo` is also accepted as an optional comparison engine. SerpAPI and
SearXNG cannot be enabled in the same command. The API key is deliberately not
accepted as a command-line argument and is never included in provider IDs.

To opt into local schema-constrained reasoning with an already installed
Ollama model:

```powershell
claim-polygraph --ollama-model YOUR_MODEL investigate "The claim"
```

Use both real retrieval and local reasoning with:

```powershell
claim-polygraph `
  --searxng-url http://localhost:8080 `
  --ollama-model YOUR_MODEL `
  investigate "The claim"
```

`OLLAMA_MODEL` and `OLLAMA_BASE_URL` provide equivalent environment
configuration. Ollama must already be running, and the named model must already
be installed. Model output is validated against Pydantic schemas and protected
evidence provenance fields, but it remains provisional until evaluated on
reviewed benchmark cases. Use `--ollama-timeout SECONDS` or
`OLLAMA_TIMEOUT_SECONDS` when local hardware needs a longer per-task deadline.

### Faster hosted reasoning with OpenAI

OpenAI is available as an explicit paid acceleration path. The deterministic
provider remains the default, and the application never silently falls back
between providers.

Copy `.env.example` to `.env`, place your real API key in `.env`, and keep that
file private:

```dotenv
OPENAI_API_KEY=your-real-key
OPENAI_MODEL=gpt-5.4-mini
OPENAI_FAST_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=60
```

Then run:

```powershell
claim-polygraph --openai-model gpt-5.4-mini investigate "The claim"
```

Use real retrieval and hosted reasoning together with:

```powershell
claim-polygraph `
  --searxng-url http://localhost:8080 `
  --openai-model gpt-5.4-mini `
  --openai-fast-model gpt-4o-mini `
  investigate "The claim"
```

The key is read only from `OPENAI_API_KEY` in the process environment or the
Git-ignored `.env` file; there is deliberately no API-key command-line option.
OpenAI calls use the Responses API, request strict schema-constrained JSON, do
not store responses through the API request, and are validated against the same
protected provenance rules as Ollama. Selecting an OpenAI model sends claim and
evidence text to a hosted paid service. API-side project budgets and usage
alerts should be configured separately because the CLI does not yet calculate
or enforce a monetary cap.

The current cost-first route uses `gpt-4o-mini` for claim normalization,
evidence classification, and review critique. `gpt-5.4-mini` handles
investigation planning, final verdict judgment, semantic passage evaluation,
and citation auditing. `--openai-model` remains a single-model override when
`--openai-fast-model` is omitted. Model quality must be compared against the
benchmark before changing the production route.

An inaccessible result is recorded with its extraction status and skipped.
The workflow tries the next candidate within its page budget instead of
failing the complete investigation. HTTPS verification uses the operating
system trust store and is never disabled.

Each completed investigation creates:

```text
artifacts/INVESTIGATION_ID/
├── report.json
├── report.md
└── trace.json
```

The end-to-end behavior is demonstrated in
`tests/integration/test_investigation_lifecycle.py`.

## Evaluation baseline

The repository includes a versioned twenty-claim benchmark covering the claim
categories required by the project specification. CPNG-001 through CPNG-010
have two-person human-reviewed labels. CPNG-011 through CPNG-020 contain 21
mapped material components and transparent AI-review records, but remain
non-gold until genuine annotation and distinct approval. Run a
deterministic workflow baseline with:

```powershell
claim-polygraph evaluate
```

For a quick smoke test:

```powershell
claim-polygraph evaluate --limit 2
```

Run the Phase 3 complex-only structural evaluation with:

```powershell
claim-polygraph --no-hosted-model evaluate --complex `
  --benchmark-evidence --limit 1 `
  --output artifacts/evaluations/phase3-complex-smoke.json
```

Remove `--no-hosted-model` (or provide explicit OpenAI/Ollama options) for a
model-backed run. The complex summary reports expected-component token-overlap
recall, parent-link validity, protected-context validity, material coverage,
parent citation support, verdict accuracy when human gold exists, and estimated
cost per completed component. The overlap metric is a deterministic diagnostic,
not a substitute for human semantic review.

To measure reasoning and verdict classification against the reviewed evidence
packets without search quality affecting the result, run:

```powershell
claim-polygraph evaluate --benchmark-evidence --limit 5 `
  --output artifacts/evaluations/benchmark-evidence-openai.json
```

Add `--openai-model MODEL` (or configure `OPENAI_MODEL`) for a hosted-model
run. This is an evidence-oracle baseline: it passes each reviewed excerpt
through the normal extraction, evidence classification, synthesis, and
citation-audit stages, but it does not measure web search or retrieval.

Measure live search-candidate quality separately with a claim-only query for
each of the five reviewed cases. Phase 2 uses SerpAPI Google:

```powershell
claim-polygraph --serpapi-engine google evaluate-retrieval `
  --limit 5 --top-k 10 `
  --query-strategy claim_only `
  --snapshot-output artifacts/evaluations/serpapi-five-claim-snapshot.json `
  --output artifacts/evaluations/serpapi-retrieval.json
```

The equivalent SearXNG comparison remains available:

```powershell
claim-polygraph --searxng-url http://localhost:8080 evaluate-retrieval `
  --limit 5 --top-k 10 `
  --query-strategy claim_only `
  --output artifacts/evaluations/searxng-retrieval.json
```

This reports exact reviewed-URL recall@K, reviewed-host recall@K, MRR,
case success, reviewed-primary-host recall, and a lexical title/snippet proxy.
The query does not include gold-source metadata. The lexical proxy is not
semantic entailment or page-level passage recall.

For the bounded query-strategy ablation, repeat the run with
`--query-strategy balanced`. It issues the claim-only query plus generic
authoritative-source and counterevidence queries, deduplicates candidates with
reciprocal-rank fusion, and retains the same final top-K candidate budget.

`--query-strategy guarded_fusion` uses the same expansion queries but protects
the first seven claim-only results in a top-10 run. It reserves at most three
tail positions for weighted expansion candidates, including one candidate from
each expansion path when available.

Capture all three query paths once, using either live provider:

```powershell
claim-polygraph --searxng-url http://localhost:8080 evaluate-retrieval `
  --query-strategy guarded_fusion --component-queries --limit 20 --top-k 10 `
  --snapshot-output artifacts/evaluations/phase3-searxng-snapshot.json `
  --output artifacts/evaluations/guarded-live.json
```

`--component-queries` adds one query for every declared material component
without using reviewed source metadata. The summary reports component-query
completion, components with any candidate, and components recovering reviewed
evidence. Atomic cases add no component queries.

Then replay any strategy without SearXNG or network access:

```powershell
claim-polygraph evaluate-retrieval --query-strategy claim_only `
  --snapshot-input artifacts/evaluations/searxng-five-claim-snapshot.json `
  --output artifacts/evaluations/claim-only-replay.json
```

Replay rejects missing queries, larger result budgets, and benchmark
identity/version mismatches.

After two declared complex end-to-end runs, calculate the exact stability gate:

```powershell
claim-polygraph compare-complex-runs `
  --first artifacts/evaluations/phase3-complex-run-1.json `
  --second artifacts/evaluations/phase3-complex-run-2.json `
  --output artifacts/evaluations/phase3-complex-stability.json
```

The comparison rejects different datasets or case sets and reports completion,
exact verdict-label, and exact normalized component-set stability. Stability is
repeatability, not factual accuracy.

Use `--query-strategy quality_rerank` with a captured three-query snapshot to
apply deterministic source-quality ranking. The score combines lexical claim
relevance, government/academic authority signals, primary-source likelihood,
query-fusion support, social/forum risk, and a repeated-host diversity penalty.
Every selected candidate records its score and component features.

Evaluate whether the quality-ranked pages are accessible and contain useful
ranked passages:

```powershell
claim-polygraph evaluate-pages `
  --retrieval artifacts/evaluations/quality-rerank-v2.json `
  --top-n 3 --passage-top-k 3 `
  --output artifacts/evaluations/page-fetch-quality-v1.json
```

This stage reports fetch and extraction success, duplicate-content rate,
reviewed-passage token-coverage recall, and per-case passage success. Fetch
failures remain separate from search and ranking failures.

HTML, XHTML, plain text, and PDFs are supported. PDF responses have a separate
20 MB download ceiling; encrypted files, files over 500 pages, and extraction
output over 500,000 characters are rejected. Image-only PDFs produce no
readable text because OCR is intentionally outside this stage. PDF retrieval
is disabled by default: an operator must explicitly approve each source host
after checking its license, permission, public-domain status, or applicable
legal exception. Finding a public URL is not treated as permission.

Every stored source records a rights status and retention scope. `unknown` is
the default. Non-unknown rights claims require a written basis and may include
a reference URL. Full fetched documents and unselected chunks are not persisted;
only metadata, hashes, and bounded passages selected as evidence are retained.

After completing that check, approve an exact host for one command:

```powershell
claim-polygraph --allow-pdf-host example.gov evaluate-pages `
  --retrieval artifacts/evaluations/quality-rerank-v2.json
```

Run a bounded semantic comparison only for lexically unmatched passages above
the lower coverage gate:

```powershell
claim-polygraph evaluate-semantic-passages `
  --pages artifacts/evaluations/page-fetch-quality-v3.json `
  --lower-lexical-threshold 0.2 `
  --output artifacts/evaluations/semantic-passages-v1.json
```

This requires an explicitly configured OpenAI or Ollama model. It evaluates at
most one passage per unmatched reviewed target, records token/cost telemetry,
and does not count partial matches as recovered evidence.

The investigation workflow also assigns evidence-family identifiers using
shared hosts, publishers, near-duplicate passages, and explicit cross-citations.
It passes the resulting independent-family count into judgment and requires
human review when the plan's minimum is not met. Numerical and temporal checks
record exactness terms, values, units, reference dates, and missing source-date
context without treating those deterministic checks as verdicts.

The completed five-claim retrieval iteration is recorded in:

- `quality-rerank-v3-counter-coverage.json`
- `page-fetch-quality-v7-top5-frozen.json`
- `semantic-passages-v4-top5-frozen.json`

The semantic stage raises combined passage recall from 66.67% to 75%. To run
the reproducible candidate ranking through live page fetching, extraction,
reasoning, and citation audit:

```powershell
claim-polygraph --openai-model gpt-5.4-mini `
  --openai-fast-model gpt-4o-mini --openai-timeout 120 evaluate `
  --dataset benchmarks/initial_claims_v1.json `
  --retrieval-candidates artifacts/evaluations/quality-rerank-v3-counter-coverage.json `
  --limit 5 --output artifacts/evaluations/phase1-live-e2e.json
```

The two final repeated results are `phase1-live-e2e-v8-enforced-audit.json` and
`phase1-live-e2e-v9-enforced-repeat.json`. Both completed 5/5 cases, matched all
five reviewed verdicts, and produced full citation support on all five concise
verdict sentences. The candidate list is frozen for reproducibility, while the
selected public pages are fetched live. This is not a live SearXNG search
measurement.

Phase 2 is closed. The ten-claim SerpAPI evaluation completed all 30 live
queries and returned candidates for 10/10 cases. Combined reviewed-passage
recall was 82.61%, with the original five cases holding their 75% Phase 1
baseline. Two declared end-to-end runs completed 10/10 cases each, reached
90% and 80% reviewed-label accuracy, delivered 100% full citation support,
and achieved 90% exact label stability. Mean estimated model cost was
$0.01085 and $0.01062 per completed case. No PDF was approved or downloaded.

The final artifacts use the `phase2-ten-` prefix under
`artifacts/evaluations/`. See
[`docs/PHASE_2_COMPLETION_REPORT.md`](docs/PHASE_2_COMPLETION_REPORT.md) for
the gate table, case-level outcomes, known weaknesses, and infrastructure
decision.

See [`docs/PHASE_1_COMPLETION_REPORT.md`](docs/PHASE_1_COMPLETION_REPORT.md) for
the closed Phase 1 exit gates, costs, rights controls, and limitations. The
closed Phase 2 scope and original measurable gates remain in
[`docs/PHASE_2_EXECUTION_PLAN.md`](docs/PHASE_2_EXECUTION_PLAN.md).

The default summary is written to
`artifacts/evaluations/deterministic-baseline.json`. All cases measure workflow
completion, latency, artifact counts, structural citation status, and verdict
distribution. Verdict accuracy is calculated only for cases with
human-reviewed expected verdicts. See
[`benchmarks/README.md`](benchmarks/README.md) for the annotation policy.

OpenAI runs additionally record the selected model, task, request latency,
input tokens, cached input tokens, output tokens, schema-validation outcome,
and a versioned list-price estimate. These values appear in trace events,
Markdown execution summaries, and evaluation JSON. Estimates are not billing
records and must be compared with the OpenAI usage dashboard.

Check readiness of the first human-review batch with:

```powershell
claim-polygraph review-status
```

An optional AI annotator-and-critic pass can prepare the next draft packet:

```powershell
claim-polygraph ai-review --cases CPNG-006 CPNG-007 CPNG-008 CPNG-009 CPNG-010
```

This command records model, prompt, token, cost, and disagreement provenance
and marks the cases `ai_reviewed`. It deliberately leaves `expected_verdict`,
typed human annotation and approval fields, `reviewed_by`, and `reviewed_at`
empty, so the output does not count as human
ground truth or verdict accuracy.

Then follow the
[CPNG-001–005 review packet](benchmarks/review_packets/cpng_001_005.md).
