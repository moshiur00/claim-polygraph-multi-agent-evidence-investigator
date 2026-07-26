# Claim Polygraph NG

Claim Polygraph NG is an evidence-first claim investigation system. It will
decompose complex claims when useful, retrieve supporting and contradictory
evidence, assess source quality and independence, verify numerical and temporal
context, and produce citation-audited verdicts.

The project begins with a lightweight vertical slice and grows toward a durable
multi-agent architecture only after the core evidence workflow is measurable.

## Current milestone

The repository now contains the first executable, mock-driven investigation
lifecycle:

- claims and investigation plans;
- sources, evidence, and source assessments;
- verdicts and sentence-level citation audits;
- execution budgets and operating-mode policies.
- asynchronous model and search provider protocols;
- deterministic providers for reproducible development;
- SQLite persistence for investigations, artifacts, and trace events;
- an end-to-end claim-to-audited-verdict application service.
- a local CLI with JSON, Markdown, and trace exports.

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

The current CLI uses deterministic synthetic providers. It is intended to
validate the workflow and report format before real search is connected.

```powershell
claim-polygraph investigate "The claim to investigate"
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
deterministic until a real model provider is added.

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
