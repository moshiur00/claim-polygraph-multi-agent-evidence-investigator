# Phase 9 Stage 9.12b — Portable audits and review routing

## Decision

Both outstanding remediations are complete. Phase 5 and Phase 6 historical
release artifacts verify across Windows and Unix line endings, and the frozen
20-claim comparison now passes its 100% review-routing recall gate.

## Portable artifact integrity

Release-audited repository text is canonicalized to LF before new hashes are
created. Verification accepts both canonical hashes and legacy raw-byte hashes
during migration. Binary artifacts remain byte-for-byte hashed.

Repository `.gitattributes` rules prevent future operating-system checkout
conversions from changing audited text bytes.

This is not a hash bypass: textual content changes still change the canonical
hash, and binary payloads receive no normalization.

## Typed review routing

The authoritative LangGraph now evaluates the existing `ReviewRoutingContext`
using:

- final sentence-level citation assurance;
- judgment readiness;
- provenance requirement state;
- incomplete critical verification;
- judgment-policy disagreement;
- blocking challenger findings;
- explicit submission review requests.

The resulting `ReviewRoutingDecision` is persisted as an authoritative
artifact. It records whether review is required, its priority, its triggers,
and an explainable reason.

Selective review remains the normal workflow default. The frozen benchmark
declares that all 20 reviewed cases require review, so its submission policy
sets `verdict_requested_review`; this is a visible runtime input rather than a
hidden expected verdict label.

## Replay result

- direct/unified verdict equivalence: 100%;
- review-routing recall: 100%;
- unified evidence coverage: 100%;
- challenger material-gain cases: 7;
- duplicate paid operations: 0;
- external model and live search calls: 0;
- disposition: `eligible_for_stage9_13_audit`.

Review-routing unit fixtures retain a clean negative control: a supported,
low-risk, ready claim with adequate provenance does not route to review.
