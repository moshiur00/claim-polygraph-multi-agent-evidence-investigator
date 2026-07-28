# Phase 8 Stage 8.4 completion report

Date: 28 July 2026

Status: Complete

## Outcome

Claim Polygraph NG now has provider-neutral academic and fact-check search
contracts plus three dedicated adapters:

- PubMed through NCBI E-utilities;
- Semantic Scholar Academic Graph; and
- Google Fact Check Claim Search.

The adapters are ready for Stage 8.5 routing but are not silently enabled in
the product path.

## Distinct specialist metadata

Academic records retain provider record ID, DOI, journal, publication date,
authors, publication types, and correction/retraction signals. Fact-check
records retain the reviewed claim, claimant, claim date, reviewing publisher,
textual rating, review date, language and review URL.

Both types normalize into the existing `SearchResult` candidate contract with
the correct source type. Candidate snippets and abstracts remain discovery
metadata, not evidence. `inline_content` is deliberately absent, requiring the
existing safe fetch, extraction and evidence-classification pipeline before
anything can support a verdict.

Rights status defaults to `unknown`, with
`evidence_passages_only` retention. No PDF or full publication content is
downloaded or embedded.

## Permissions and budgets

- Academic adapters declare the exact academic-role permission set.
- Google Fact Check declares the exact fact-check-role permission set.
- Each operation has explicit request/result ceilings.
- A process-local asynchronous gate limits request-start frequency.
- PubMed defaults to three request starts per second and performs at most the
  two calls required for ESearch plus ESummary.
- Semantic Scholar and Google Fact Check default to one request start per
  second and one API call per page.
- Existing global research budgets, concurrency limits and durable caches
  remain above these provider-local controls.
- HTTP 429, authentication, malformed payload and network failures become
  controlled provider errors; the existing research executor records such
  failures as typed role results rather than discarding other role work.

The NCBI defaults follow its published E-utilities guidance:
https://www.ncbi.nlm.nih.gov/books/NBK25497/

Google request and pagination fields follow its official `claims.search`
reference:
https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search

Semantic Scholar fields follow its official Academic Graph API schema:
https://api.semanticscholar.org/api-docs/

## Recorded-fixture verification

Versioned JSON fixtures cover:

- PubMed ESearch pagination, ESummary metadata and empty results;
- Semantic Scholar identifiers, journal metadata, pagination and missing
  abstract handling;
- Google ClaimReview rating metadata, opaque page tokens and empty results;
- provider rate-limit failure; and
- specialist-role path enforcement.

The fixtures contain synthetic records and invoke no external service.

## Verification

- Complete project suite: 405 passing tests
- Python lint clean
- Dashboard lint clean
- Dashboard production build successful
- Zero live search calls
- Zero model calls
- Zero PDF downloads

## Deliberate limits

API credentials are configuration-only and remain Git-ignored. No live smoke
call was needed because fixture and contract gates passed. Stage 8.5 must wire
these adapters into concurrent role fan-out, shared caching and durable
assignment/result checkpoints before the project claims genuine specialist
agent execution.
