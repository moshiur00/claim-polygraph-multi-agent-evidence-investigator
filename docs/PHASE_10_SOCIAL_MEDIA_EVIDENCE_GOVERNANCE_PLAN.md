# Phase 10 — Social Media Evidence Governance

## Objective

Make social-media material usable without allowing popularity, repetition, screenshots, or platform identity to masquerade as authority or independent corroboration.

Phase 10 preserves the Phase 9 architecture:

- the unified authoritative LangGraph remains the default orchestrator;
- `InvestigationService` operations remain the domain and persistence authority;
- the direct workflow remains the rollback path;
- reports remain available before human review, but unsafe publication remains blocked.

## Operating principles

1. Distribution medium and source authority are separate properties.
2. A social post proves that a statement was published; it does not automatically prove the statement's factual content.
3. The original underlying source is preferred over a post that links, quotes, screenshots, or reposts it.
4. Cross-platform repetition is not independent corroboration when items share an origin.
5. Social-only decisive evidence cannot produce a publishable `supported` or `contradicted` verdict.
6. Social evidence is retained with transparent limitations; it is not silently discarded.
7. Models may classify or explain evidence, but deterministic policy decides eligibility and publication safety.

## Stages

### Stage 10.0 — Baseline, policy, and migration manifest

- Freeze current ingestion, normalization, independence, quality, readiness, and reporting behavior.
- Establish the social-use policy matrix and non-negotiable safeguards.
- Record backward-compatibility and zero-cost resource rules.
- Hash the baseline inputs and make the manifest reproducible.

Exit: the manifest validates locally, has tamper-detection tests, and makes no provider calls.

### Stage 10.1 — Typed social-source contracts

- Add backward-compatible fields for distribution medium, account identity, authorship, authenticity, original-source linkage, post type, and evidence eligibility.
- Keep legacy `SourceType.OTHER` records readable.
- Add deterministic defaults of `unknown`, never optimistic inference.

Exit: old artifacts deserialize unchanged and new contracts round-trip.

### Stage 10.2 — Detection and normalization

- Detect supported social hosts and URL forms.
- Normalize canonical post/account URLs without fetching private or prohibited content.
- Separate original posts, replies, reposts, quotes, screenshots, and link shares.
- Preserve provider metadata and record classification provenance.

Exit: recorded fixtures cover supported platforms, malformed URLs, mirrors, and unknown hosts.

### Stage 10.3 — Authenticity and attribution

- Record account identity, verification evidence, post time, deletion/unavailability, and capture method.
- Require explicit attribution scope: statement, eyewitness observation, institutional announcement, or linked document.
- Treat screenshots and copied text as unverified until tied to an accessible original or reliable archive.

Exit: deterministic eligibility tests reject unauthenticated decisive use.

### Stage 10.4 — Original-source resolution

- Follow permitted links to the underlying report, dataset, ruling, paper, transcript, or announcement.
- Cite the underlying item for factual claims and retain the social post as discovery or statement evidence.
- Record derivation links so reposts and coverage of the same origin share one evidence family.

Exit: fixture investigations prefer originals and expose unresolved provenance.

### Stage 10.5 — Independence and source-quality integration

- Add shared-origin clustering across social platforms and web publications.
- Score authority according to author and claim scope, not platform.
- Prevent engagement metrics and verification badges from becoming truth scores.
- Add explicit social-risk findings to readiness and the challenger.

Exit: repeated/reposted claims do not inflate independent-family counts.

### Stage 10.6 — Argument, judgment, and publication constraints

- Restrict each social item to its approved evidentiary use.
- Require non-social corroboration for decisive factual propositions except narrowly scoped first-party facts.
- Route unresolved eyewitness, authenticity, scope, or single-origin risks to review.
- Block publication when a critical conclusion depends on ineligible social evidence.

Exit: adversarial tests cannot obtain a decisive publishable verdict from virality alone.

### Stage 10.7 — Report and dashboard transparency

- Label social evidence by account, post type, authenticity, original source, approved use, and limitations.
- Explain why an item counts as evidence, context, a lead, or is excluded.
- Show shared-origin families and prevent users from reading relevance as correctness.
- Keep the provisional report visible before human judgment.

Exit: a journalist can trace every social item from discovery to its effect on the verdict.

### Stage 10.8 — Benchmark and human calibration

- Add synthetic and reviewed cases for official announcements, eyewitness posts, manipulated screenshots, repost cascades, deleted posts, and social links to primary documents.
- Measure eligibility precision, unsafe-publication rate, origin-resolution rate, independence inflation, review-routing recall, and verdict stability.
- Calibrate policy thresholds through targeted human review.

Exit: no unsafe decisive use in the reviewed adversarial set and 100% recall for declared mandatory-review cases.

### Stage 10.9 — Recovery, security, audit, and promotion

- Test provider failure, deleted content, restart, checkpoint reconstruction, malicious HTML, prompt injection, PII minimization, and access controls.
- Reconcile documentation and dashboard language.
- Hash release artifacts and record the promotion decision in an ADR.

Exit: Phase 10 is promoted only if evidence safety improves without breaking the Phase 9 rollback and recovery guarantees.

Stage 10.9 mechanical status: passed on 30 July 2026. ADR 0023 was explicitly
approved by Md Moshiur Rahman on the same date. Phase 10 is promoted and
closed for bounded local, human-reviewed operation.

## Cost-control plan

- Stages 10.0–10.3 use local fixtures and deterministic tests.
- Live provider calls begin only after eligibility policy is enforced.
- Resolve an original source once and share it through the existing cache and paid-operation receipt system.
- Use model calls only where deterministic classification is insufficient, with hard per-investigation budgets.
- Run narrow adversarial gates before the full 20-claim replay.
