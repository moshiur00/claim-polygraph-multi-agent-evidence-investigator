# Phase 8 Stage 8.8 completion report

Date: 28 July 2026

Status: Complete

## Outcome

Every substantive sentence in the publishable investigation narrative now
enters a typed citation-assurance inventory before publication. The system
audits exact approved evidence references, permits at most two deterministic
wording-revision rounds, re-audits every revision and blocks publication when
critical support remains unresolved or full material-sentence support falls
below 95%.

Investigation completion and publication are deliberately separate. A blocked
investigation remains available as structured JSON for audit and human review,
but Markdown and exported report artifacts cannot be finalized.

## Material assertion inventory

The inventory covers:

- the critical concise verdict explanation;
- every sentence in the detailed reasoning;
- every relevant supporting, contradictory, qualifying and contextual
  evidence finding displayed in the narrative.

Each typed assertion records its claim, stable assertion ID, report section,
ordinal, sentence, materiality, criticality, asserted stance, required phrases
and cited evidence IDs. The full-report contract verifies that every declared
material sentence has exactly one final audit finding.

Administrative metadata, IDs, timestamps and execution counters are not
treated as material factual assertions.

## Approved-packet enforcement

The existing fail-closed assurance engine remains authoritative for citation
checks. It detects:

- missing citations;
- evidence outside the approved packet;
- missing evidence records;
- missing required phrases;
- stance mismatch; and
- citations whose stance contradicts the assertion.

The full-report builder rejects an approved ID without a supplied evidence
record. Revisions may select only approved evidence already supplied to the
gate. No search or evidence creation is available.

## Bounded revision and re-audit

Unsupported wording may be narrowed to an exact excerpt from approved evidence
with matching stance. Every revision records:

- the assertion ID and attempt number;
- original and revised wording;
- approved evidence IDs;
- rationale; and
- an invariant that the verdict label was not changed.

Revised assertions are sent through the same audit again. A revision is never
accepted merely because the revision procedure generated it.

## Publication gate

Publication is `ready` only when:

- every material sentence was audited;
- no critical material assertion remains unsupported; and
- at least 95% of material assertions have full support.

Otherwise publication is `blocked` with explicit reasons. Export performs this
check before creating its output directory, preventing partial report
publication. The Markdown API returns HTTP 409 for a blocked report, while JSON
continues exposing the assurance packet for diagnosis.

Publishable verdict and reasoning sentences use the final re-audited wording
and display explicit evidence references. The authoritative verdict label is
not modified.

## Persistence and integration

`InvestigationService` creates and persists a
`full_report_assurance` artifact after the existing sentence audit.
The complex investigation service applies the same gate to the parent
narrative, and complex export requires both the parent and every completed
component to be publication-ready.
`InvestigationReport`, report reconstruction, JSON APIs and generated Markdown
expose the typed gate result. Existing single-sentence audit records remain
available for backward compatibility.

## Verification

- Generic unsupported wording was deterministically narrowed and re-audited.
- The final revised fixture packet reached 100% sentence support.
- An unsupported critical assertion remained blocked after bounded attempts.
- Export stopped before creating files for a blocked report.
- Revisions preserved the verdict label.
- Missing and out-of-packet citations remained fail-closed.
- Three promoted fixture cases audited 100% of declared material sentences,
  reached at least 95% full support and had zero critical failures.
- Complete project suite: 420 passing tests.
- Python lint passed.

No hosted-model call, live search, network fetch or PDF operation was used for
the Stage 8.8 assurance gate.

## Deliberate limits

The deterministic lexical audit proves exact phrase and stance compatibility;
it is not a general semantic-entailment model. A later semantic audit may
evaluate only predeclared ambiguous cases, but it cannot bypass approved-ID
checks or the deterministic publication gate.
