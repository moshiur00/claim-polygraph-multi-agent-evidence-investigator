# Phase 10 Stage 10.1 — Typed Social-Source Contracts

Date: 29 July 2026  
Status: Implemented

## Outcome

The domain layer now separates a source's distribution medium from its authority and adds typed, conservative social-evidence metadata. The change is additive: historical `Source` and `Evidence` JSON remains valid.

## Contracts

- `DistributionMedium` records how material was distributed.
- `SocialAccountIdentity` records platform identity, owner type, authenticity evidence, and a narrowly declared institutional authority scope.
- `SocialSourceContext` records post type, platform item ID, time, eyewitness status, availability, and original-source linkage.
- `SocialOriginalSourceLink` records derivation for underlying documents, reposts, quotations, screenshots, and links.
- `EvidentiaryUse` distinguishes decisive evidence, qualified observation, attributed statement, context, discovery lead, exclusion, and the legacy-safe `unspecified` state.
- `SocialEvidenceEligibility` records the deterministic decision, permitted uses, corroboration, independence, review, and reason codes.

## Deterministic policy

`evaluate_social_evidence_eligibility()` does not call a model or provider.

- Unknown or unauthenticated accounts are limited to leads and context.
- Reposts, quotes, and screenshots remain leads even when their origin is known.
- Link shares direct the workflow to the underlying source.
- Eyewitness material remains qualified, requires corroboration, and routes to review.
- An authenticated government or institutional account can prove a first-party statement only when its authority scope is recorded.
- Institutional eligibility never grants general decisive use.
- Academic announcements require the underlying paper or data for research claims.
- A caller cannot forge a more permissive result: `Source` recomputes and validates the eligibility contract.

## Backward compatibility

Legacy records without new fields reconstruct as:

- `distribution_medium = unknown`
- `social_context = null`
- `social_eligibility = null`
- `evidentiary_use = unspecified`

These defaults do not infer that a generic `SourceType.OTHER` item is social, authentic, authoritative, independent, or decisive.

## Deferred to later stages

Stage 10.1 defines contracts only. Provider detection and normalization begin in Stage 10.2. Original-source fetching, independence-family integration, judgment constraints, reporting, and publication enforcement remain later staged work.

## Reproducible audit

`scripts/run_phase10_contract_audit.py` validates six schema hashes, reconstructs representative legacy `Source` and `Evidence` payloads, and records zero provider/model calls in `artifacts/evaluations/phase10-stage10.1-social-contract-audit-v1.json`.
