# Phase 10 Stage 10.4 — Original-Source Resolution

Date: 29 July 2026  
Status: Implemented

## Outcome

The system can now resolve an explicitly recorded social link to a permitted public report, dataset, ruling, paper, transcript, or official announcement through the existing safe retrieval and durable cache path. Resolution creates a separate underlying `Source`, updates the social derivation link, and forces both records into one evidence family.

## Authorization boundary

A resolution request must:

- reference an existing persisted social source;
- match the exact pre-recorded underlying URL after safe canonicalization;
- use an `underlying_record` or `links_to` relationship;
- carry explicit authorization, author, time, and purpose;
- state that public access is expected;
- identify the expected record kind and source type;
- explicitly authorize a URL that visibly targets a PDF.

The resolver rejects mismatched URLs, social-to-social targets, already-resolved links, non-social source records, non-public expectations, unsupported relationships, and unauthorized requests before retrieval.

Models cannot invent or silently follow a link. A link must already exist in typed source provenance.

## Safe retrieval and persistence

Allowed targets use `SharedResearchOperations`, which provides the durable fetch cache and the existing SSRF, redirect, response-size, content-type, and PDF-host controls. The resolver stores:

- the updated social source;
- the new underlying source;
- a durable resolution result;
- URL, content type, byte count, content hash, status, and failure reason.

Full fetched content remains in the bounded research cache; the resolution audit does not copy it into release artifacts.

Resolution requests are idempotent by `request_id`. A completed durable result reconstructs its persisted social and underlying sources without refetching. A result that references missing sources raises an integrity error rather than silently repeating the operation.

## Copyright and PDF handling

No PDF is fetched merely because a social item links to it. Visible `.pdf` targets require request-level authorization, and the existing safe fetcher independently requires an approved PDF host before downloading content. Unsupported or unapproved PDFs fail closed.

## Independence invariant

Both independence implementations now consume resolved source IDs:

- the authoritative `analyze_source_independence` path;
- the provenance-bound `infer_evidence_families` path.

When a social item and its underlying record both contain retained evidence, they are grouped with reason `resolved_original_source` and count as one family. Cross-platform posts resolving to the same underlying record therefore cannot manufacture independent corroboration.

## Compatibility

The research database adds an idempotent `original_source_resolutions` table. Existing databases create it through the normal initialization path. Existing sources without resolved links retain their previous behavior.

## Gate

The zero-network release gate checks exact-match permission, mismatched target, social target, and already-resolved cases; proves the one-family invariant; and hashes the fixtures, contracts, resolver, persistence, and both independence paths.
