# Phase 10 Stage 10.5 — Independence, Source Quality, and Readiness

Date: 29 July 2026  
Status: Implemented

## Outcome

Social and web publications that share an explicitly recorded origin now count as one family even before the original link receives a stored source ID. Social-source authority is assessed from authenticated ownership and assertion-specific scope, while platform badges and engagement metrics are explicitly excluded. Typed social-risk findings now affect readiness and human-review routing.

## Shared-origin clustering

Both independence paths compare canonicalized recorded origin URLs:

- posts on different platforms that link to the same underlying record;
- a social post and the web record it links to;
- resolved source-ID links from Stage 10.4.

Confirmed shared origins use `shared_origin_url` or `resolved_original_source` and count once. Merely similar wording without an explicit origin remains governed by existing duplicate and uncertainty rules.

## Social authority

A favorable authority finding for social material requires:

1. a resolved institutional identity;
2. retained authentication evidence;
3. an institutional account type;
4. an authority scope applicable to the assertion.

A platform badge, follower count, like count, repost count, view count, or other engagement measure cannot satisfy any of these requirements. These fields are recorded as ignored signals for transparency.

Source quality remains eight explainable dimensions with no aggregate trust or truth score.

## Readiness risks

The provenance packet records typed findings for:

- unresolved identity or origin;
- unauthenticated accounts;
- missing institutional scope;
- shared-origin repetition;
- screenshots or copied text;
- unavailable originals without verified archives;
- use of ineligible social evidence;
- unauthorized decisive use;
- social-only evidence packets;
- ignored engagement and badge signals.

Blocking findings force `human_review_required`. Caution findings produce `qualified` readiness unless a stronger failure already applies. Informational ignored-signal findings do not reduce readiness by themselves. Readiness remains packet safety, not claim probability.

## Compatibility

New provenance findings, ignored-signal fields, and readiness counters are additive with empty/zero defaults. Historical packets remain readable. Non-social quality rules retain their previous behavior.

## Gate

The zero-cost gate proves that badge-only authority remains unknown, engagement changes do not alter authority, authenticated scoped authority remains favorable, and three cross-platform/web records sharing one origin produce exactly one family. Adversarial unit tests prove blocking review routing for ineligible decisive social evidence.

