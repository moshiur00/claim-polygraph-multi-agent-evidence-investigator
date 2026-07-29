# Phase 10 Stage 10.0 — Baseline and Policy

Date: 29 July 2026  
Status: Complete; policy ADR awaiting approval

## Frozen current behavior

| Concern | Current behavior | Risk frozen for remediation |
|---|---|---|
| General search ingestion | SerpAPI normalizes general results as `SourceType.OTHER`. | Social distribution and source authority are indistinguishable. |
| Evidence creation | Relevant fetched passages can be persisted by the authoritative and multi-agent research paths. | A social passage can become evidence without a social-specific eligibility decision. |
| Independence | Host, publisher, duplication, and citation relationships drive family analysis. | Copies on different platforms may appear independent when their common origin is unresolved. |
| Source quality | Explainable metadata-based quality is recorded. | Account authenticity, post type, and underlying-source authority are not first-class inputs. |
| Readiness | Unknown quality and provenance risks can trigger safeguards or review. | There is no mandatory social-only decisive-evidence gate. |
| Retrieval evaluation | Some social/low-quality host penalties exist. | Evaluation-only heuristics do not protect the live workflow. |
| Reporting | Sources, evidence, citations, reasoning, and review status are visible. | Social evidentiary scope and shared origin are not explained explicitly. |

## Approved-use policy matrix

| Social material | Allowed use | Independent proof of underlying claim? | Required control |
|---|---|---:|---|
| Unknown individual post | Lead or public-reaction context | No | Resolve identity/origin; corroborate |
| Authenticated individual statement | Proof that the person made the statement | No | Limit proposition to the statement |
| Eyewitness post | Qualified observation | No by itself | Authenticate, time/place check, independent corroboration |
| Verified institutional account | First-party statement within institutional scope | Sometimes, narrowly | Verify account and scope; prefer linked official record |
| Government account | Official announcement within legal/administrative authority | Sometimes, narrowly | Distinguish announcement from controlling instrument |
| Academic/institutional post | Discovery or first-party announcement | No for research findings | Cite and inspect the underlying paper/data |
| Repost, quote, or screenshot | Lead only | No | Find original; record derivation |
| Post linking a report | Discovery and context | No separate family from report | Cite underlying report for factual proposition |

## Enforcement boundary

The future enforcement chain is:

`search result → medium/authority classification → authenticity and origin resolution → evidence-use eligibility → independence clustering → argument-use restriction → judgment constraint → citation audit → review/publication gate`

The model may propose classifications and explanations. Deterministic validators own eligibility, independence-family effects, mandatory review, and publication blocking.

## Compatibility and migration

- Existing `SourceType` values and persisted `SourceType.OTHER` records remain valid.
- New social fields will be optional and default to `unknown` or the safest non-decisive use.
- No existing evidence, report, review, checkpoint, or receipt is rewritten destructively.
- Historical artifacts remain readable through versioned reconstruction.
- The direct rollback path remains available throughout the phase.

## Stage resource record

- Model calls: 0
- Search calls: 0
- Network calls: 0
- PDF downloads: 0

The reproducible manifest is `artifacts/evaluations/phase10-stage10.0-social-evidence-baseline-v1.json`.

