# ADR 0010: Use SerpAPI as the Phase 2 primary live-search provider

- Status: Accepted
- Date: 2026-07-27

## Context

The Phase 1 SearXNG integration proved the provider and retrieval contracts, but
the tested upstream engines were suspended, challenged, or returned inadequate
candidates. Continued engine troubleshooting would make search infrastructure,
rather than evidence quality, the critical path for Phase 2.

The project needs a dependable structured search response for a bounded
ten-claim evaluation while preserving SearXNG as a self-hosted target and
frozen snapshots as reproducible controls.

## Decision

Add an opt-in SerpAPI search provider behind the existing `SearchProvider`
protocol:

- Google is the Phase 2 primary engine.
- DuckDuckGo is an optional comparison engine through the same provider.
- The API key is read only from `SERPAPI_API_KEY`; there is no CLI key option.
- SerpAPI and SearXNG are mutually exclusive for one command.
- One retry is permitted only for transient network, timeout, rate-limit, and
  server failures.
- Normalized results contain only the existing candidate fields.
- The provider never fetches result pages; the existing rights-aware safe
  fetcher remains responsible for page access.
- Search snapshots remain mandatory for reproducible ranking comparisons.

SearXNG remains supported but is not a blocking Phase 2 dependency.

## Consequences

Phase 2 can measure live search without first operating a reliable metasearch
fleet. This adds a hosted dependency, sends queries to a third party, consumes
search credits, and requires secret management. It does not change page rights:
a returned URL is not permission to download or retain its contents.

Provider identity, search-call counts, snapshot timestamps, query parameters,
and normalized failures must remain visible in evaluation artifacts. Private or
sensitive claims require a separate data-handling review before hosted search.
