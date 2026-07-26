# ADR 0003: Record rights, evidence families, and context checks

- Status: Accepted
- Date: 26 July 2026

## Context

Evidence retrieval must not treat technical accessibility as permission to copy
or retain a work. Verdict quality also depends on whether apparently separate
pages are independent and whether numerical or temporal wording survives
normalization and matches the cited context.

## Decision

- PDF retrieval is denied by default. Exact hosts require an explicit operator
  allowlist decision made after a rights check.
- Every source records rights status and retention scope. A non-unknown status
  requires a written basis.
- Full fetched documents and unselected chunks remain transient. Durable
  storage contains source metadata, hashes, and bounded selected passages.
- Evidence families are assigned deterministically from shared hosts,
  publishers, near-duplicate passages, and explicit cross-citations.
- Judgment receives the family analysis and required family count. An unmet
  family requirement forces human review.
- Numerical checks record claim/evidence values, units, and absolute wording.
- Temporal checks preserve the user's exact temporal language, anchor
  still/currently/today claims to the investigation date, and record missing or
  postdated source context.
- Context checks are review signals. They do not independently decide truth,
  copyright permission, legal exceptions, unit conversions, or historical
  status.

## Consequences

The workflow retains less copyrighted content, cannot silently count repeated
sources as independent confirmation, and exposes missing context before a
verdict is relied upon. Deterministic family detection cannot discover
undisclosed syndication or a shared offline authority, so the analysis records
that limitation and remains reviewable.
