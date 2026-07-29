# Phase 10 Stage 10.2 — Social URL Detection and Normalization

Date: 29 July 2026  
Status: Implemented

## Outcome

General search candidates now receive a deterministic, fetch-free distribution classification. Recognized social URLs carry a canonical public locator and typed platform, URL kind, account handle, and post identifier. Ordinary web URLs remain web candidates, and look-alike domains are not classified as social.

## Supported URL families

- X and legacy Twitter
- Facebook
- Instagram
- Threads
- LinkedIn
- YouTube
- TikTok
- Bluesky
- Reddit
- `mastodon.social`

Federated Mastodon instances are not guessed from path shape alone. Additional instances require an explicit trusted host registry or later provider metadata.

## Canonicalization rules

- Require HTTP or HTTPS and reject embedded credentials.
- Match exact known hosts, including explicitly supported mobile and legacy aliases.
- Normalize aliases to a stable HTTPS host and remove fragments/tracking parameters.
- Preserve identifiers without resolving redirects.
- Classify recognized platform paths that are not known post/account forms as `unknown`.
- Never infer account authenticity, authority, privacy state, or factual correctness from a URL.

## Provider metadata

`SearchResult` now carries optional `ProviderResultMetadata`:

- provider ID;
- provider rank and result ID;
- a bounded allowlist of original JSON attributes.

Credential-like fields, excessive field counts, and oversized payloads are rejected. SerpAPI and SearXNG preserve relevant result metadata without changing its JSON values.

## Network and rights boundary

This stage classifies URLs found in search-provider responses only. It does not:

- open the social URL;
- download a post, image, video, attachment, or profile;
- bypass login, robots, privacy, paywall, or access controls;
- archive deleted content;
- infer reuse permission.

The recorded fixture contains only synthetic URLs and metadata; it includes no copyrighted post content.

## Compatibility

Legacy `SearchResult` JSON reconstructs with:

- `distribution_medium = unknown`
- `social_url = null`
- `provider_metadata = null`

Existing `Source` records are unchanged. Candidate-to-source authentication and attribution begin in Stage 10.3.

## Gate

The reproducible gate covers 15 cases across ten platforms, hostile look-alike domains, and unknown paths. It requires exact fixture agreement, zero social-page fetches, zero search/model calls, and valid hashes for the fixture, normalizer, contracts, and adapters.

