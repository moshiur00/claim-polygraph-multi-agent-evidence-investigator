# Phase 10 Stage 10.7 — Report and Dashboard Transparency

## Outcome

The provisional report remains available before human review, and the dashboard
now exposes the complete persisted social-evidence trace instead of reducing a
social source to a title, passage, stance, and relevance number.

## Journalist-facing trace

Every retained social item displays:

1. discovery platform, post type, capture method, and timestamp;
2. account identity, account type, authenticity status, evidence, and scope;
3. original-source relationship and resolution status;
4. assigned evidentiary use, allowed uses, and corroboration requirement;
5. bounded verdict effect and any blocking policy finding.

The expanded record also shows attribution, origin status, eyewitness and
deleted-content flags, evidence-family membership, shared-origin grouping,
source-quality dimensions, ignored engagement or badge signals, eligibility
reasons, social-risk findings, and accessible source links.

## Publication transparency

The dashboard's publication-ready state now requires all of:

- citation assurance ready;
- judgment readiness not blocked;
- no Stage 10.6 social-policy publication block;
- authoritative publication decision allowing publication;
- no local passage-hygiene warning.

Human approval or wording revision cannot visually or operationally erase a
persisted critical social-evidence block.

## Report transparency

Markdown reports include a social-evidence trace with account, authenticity,
authority scope, post/capture type, original-source status, eligibility,
assigned and allowed uses, corroboration, independence permission, family, and
eligibility reasons.

The report and dashboard both state:

- authenticity establishes attribution, not truth;
- relevance measures topical match, not correctness;
- engagement and platform badges are not authority signals;
- cross-platform repetition from one origin is one family.

## Compatibility

- Old reports remain valid because all social fields are additive.
- Investigations without retained social evidence receive a deliberate empty
  state rather than fabricated social analysis.
- The same JSON report endpoint serves completed and pre-review provisional
  reports.
- No provider or model call was added.

## Exit criterion

A journalist can trace every retained social item from discovery to its exact
permitted influence on judgment and publication.
