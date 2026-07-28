# Phase 8 Stage 8.2 completion report

Date: 28 July 2026

Status: Complete

## Outcome

Claim Polygraph NG now accepts three typed input forms: a manual factual claim,
pasted article text, and a public article URL. Article inputs produce ranked
claim candidates for explicit user selection. Extraction is a separate,
zero-cost analysis boundary: it does not judge truth, start an investigation,
or invoke a model.

## Contracts and provenance

- A discriminated input union prevents ambiguous request interpretation.
- Every candidate records exact source-relative character offsets, surrounding
  context, deterministic check-worthiness signals, and rank.
- Every extraction records a SHA-256 content hash and input length.
- URL packets also record requested URL, canonical final URL, retrieval time,
  unknown rights status, and evidence-passages-only retention.
- Contract validation rejects inconsistent offsets, incomplete URL provenance,
  and any packet claiming that extraction automatically started research.

## Product paths

- `POST /api/claim-inputs/extract` exposes the typed extraction contract.
- `claim-polygraph extract-claims` supports pasted text and `--url`.
- The dashboard lets the user select manual claim, article text, or public URL,
  displays candidates, and starts the promoted investigation path only after
  the user chooses a candidate.

All selected candidates enter the existing investigation endpoint and therefore
retain the Stage 8.1 orchestrator boundary.

## Network, rights, and cost controls

Public URLs use the existing safe HTTP fetcher. It validates the initial target
and redirects, blocks private and loopback destinations, bounds response size
and time, and limits accepted content types. PDF retrieval remains denied
unless a host has been explicitly approved. Retrieved pages are reduced to
readable text; scripts are not treated as claim content.

Rights status defaults to `unknown`, and durable retention is declared as
`evidence_passages_only`. No PDF, external search, hosted model, or paid
provider call was used to complete this stage.

## Verification

- Exact-offset, context-preservation and duplicate-claim tests
- Mocked public-URL canonical-provenance and script-removal test
- API extraction-without-investigation test
- API-level loopback/SSRF rejection test
- CLI extraction-without-database-creation test
- Python lint, dashboard lint and production dashboard build
- Complete project regression suite

## Deliberate limit

Stage 8.2 uses deterministic sentence and check-worthiness heuristics. The
planned optional model smoke test was not needed to satisfy the exit criteria
and was skipped to preserve budget. Model-assisted extraction can be evaluated
later behind the same contracts, but it must not bypass user selection or
silently initiate paid research.
