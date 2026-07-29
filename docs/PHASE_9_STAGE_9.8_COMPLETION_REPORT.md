# Phase 9 Stage 9.8 completion report

Date: 29 July 2026

Status: Complete

## Outcome

Judgment, sentence-level citation assurance, readiness and publication control
now form one explicit authoritative chain. Internal completion is distinct from
permission to publish: a blocked investigation remains available for audit and
human review, but the public renderer fails closed.

## Authoritative chain

```text
approved argument ledger
  -> proposed verdict
  -> deterministic safeguards and judgment-policy trace
  -> policy-enforced verdict
  -> sentence audit and at most two wording revisions
  -> full material-assertion assurance
  -> deterministic readiness
  -> persisted publication decision
  -> publish, review, or block
```

The proposed verdict, policy-enforced verdict and citation-revised verdict are
separate artifact types. The graph state points to each boundary instead of
using one ambiguous verdict reference.

## Citation assurance and revision

Every material assertion in the structured verdict/evidence report inventory
is audited against the approved evidence packet. Failed wording may be narrowed
for at most two revision attempts and must be re-audited. Revisions cannot add
or remove assertions, cite out-of-packet evidence, or change the verdict label.

Publication is blocked when any critical material assertion remains unsupported
or when final full support is below 95 percent.

## Readiness and publication

Readiness remains an explainable deterministic workflow signal, not a truth
probability. The new `AuthoritativePublicationDecision` records:

- Proposed and enforced labels.
- Whether formal judgment-policy changes were applied.
- Citation revision count and final support rate.
- Unsupported critical assertion count.
- Readiness state.
- Ready, review-required or blocked status.
- Explicit reason codes and blocking reasons.

The formal Phase 6 judgment-policy candidate remains observational
(`applied=false`) to preserve reviewed verdict behavior; existing deterministic
safeguards remain enforced. Promotion of label-changing policy behavior still
requires benchmark calibration rather than being silently introduced here.

## Fail-closed rendering

`render_publishable_markdown` now checks the authoritative publication decision
before rendering. Older stored reports without the additive decision field
retain the existing full-report-assurance gate for backward compatibility.

The direct sequential workflow emits and enforces the same publication
decision, so rollback cannot bypass the gate.

## Verification

The Stage 9.8 gate proves:

- Distinct proposed, policy-enforced and final verdict references.
- Judgment policy, assurance and readiness checkpoints.
- The two-attempt citation-revision bound.
- Successful ready publication.
- Blocking of an unsupported critical assertion.
- Fail-closed public rendering.
- The same gate on the direct rollback workflow.

## Cost

No OpenAI, SerpAPI, live network, document download or PDF operation was used.

## Exit decision

Stage 9.8 passes. The authoritative graph now produces an explicit,
auditable and fail-closed publication disposition without changing reviewed
verdict behavior or removing direct rollback.
