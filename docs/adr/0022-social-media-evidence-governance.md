# ADR 0022: Govern social media as a distribution medium, not an authority class

- Status: Proposed
- Date: 29 July 2026
- Phase: 10

## Context

The live workflow can discover social pages through general search and preserve them as generic sources. It does not yet represent account authenticity, post type, original-source derivation, or the narrowly permitted use of a social item. Existing independence logic may also overcount copies distributed through different platforms.

Discarding all social material would remove useful eyewitness reports, attributable statements, official announcements, and discovery leads. Treating all of it as ordinary web evidence would allow virality and cross-platform repetition to imitate authority and corroboration.

## Decision

Represent social media as a distribution medium independently from:

- author or institutional authority;
- authenticity and attribution confidence;
- the proposition the item is eligible to support;
- its original or shared evidence family;
- its role as decisive evidence, qualified evidence, context, or a lead.

The authoritative workflow will retain social items but apply deterministic eligibility and publication controls. A model cannot override those controls. Social-only decisive evidence cannot yield a publishable `supported` or `contradicted` verdict. When an item links or derives from an underlying source, the underlying source is preferred and both items share provenance.

## Consequences

Positive:

- journalists can inspect useful social material without mistaking it for verified fact;
- repost cascades cannot inflate source independence;
- first-party statements and official announcements remain usable within explicit scope;
- reports can explain exclusions and qualifications instead of silently hiding sources.

Costs:

- source contracts, fixtures, provenance analysis, readiness, reporting, and dashboard views require extension;
- authenticity and original-source resolution can add latency and occasionally require human review;
- legacy generic sources need conservative reconstruction defaults.

## Compatibility

This decision does not replace `SourceType` or rewrite historical records. New fields are additive and versioned. `InvestigationService` remains authoritative, LangGraph remains the default orchestrator, and the direct workflow remains rollback.

