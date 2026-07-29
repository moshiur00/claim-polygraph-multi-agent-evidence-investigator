# Phase 10 Stage 10.3 — Authenticity and Attribution

Date: 29 July 2026  
Status: Implemented

## Outcome

Recognized social search candidates now persist as transparent attribution records without being fetched or promoted to factual evidence. Account identity, authenticity evidence, attribution scope, capture method, origin availability, archive provenance, provider discovery metadata, and eligibility are retained separately.

## Authenticity records

An authenticated or disputed account requires a recorded basis or typed evidence:

- an official website link;
- a platform assertion;
- a cross-referenced identifier;
- a cryptographic signature;
- a reliable archive;
- explicit human verification.

Platform verification alone is an observation, not proof that every statement is correct. Institutional authority also requires a narrow `authority_scope`.

## Attribution scope

Social material can be limited to:

- publication existence;
- an attributed statement;
- a qualified eyewitness observation;
- an institutional announcement;
- discovery of a linked underlying source.

Search snippets are always retained as discovery/context only. Their text is not treated as authenticated post content.

## Capture and unavailable content

The contracts distinguish direct public pages, provider APIs, reliable archives, screenshots, copied text, and search snippets.

- Screenshots and copied text are lead-only until tied to an accessible original or reliable archive.
- Deleted or unavailable originals without a verified archive are lead-only and require review.
- A verified archive remains conditional and requires attribution review.
- Archive reliability requires an explicit verification basis.

## Runtime integration

Both the authoritative `InvestigationService` research path and multi-agent workers:

1. recognize a classified social candidate;
2. persist it as a `PARTIAL` source with conservative social context;
3. retain provider discovery metadata;
4. do not call the generic content fetcher;
5. do not create evidence from the provider snippet;
6. continue searching for independently usable material.

The shared research fetch operation also rejects recognized social URLs as defense in depth.

## Compatibility

All new fields are additive. Legacy source records retain unknown/null defaults. Existing non-social candidates continue through the normal safe fetch path.

## Gate

Six recorded cases cover unresolved search candidates, screenshots, copied text, unavailable originals, verified archives, and scoped official accounts. The gate requires exact decisions, zero decisive permissions, zero external calls, and valid artifact hashes.

