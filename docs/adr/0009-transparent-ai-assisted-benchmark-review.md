# ADR 0009: Transparent AI-assisted benchmark review

- Status: Accepted
- Date: 2026-07-26

## Context

Preparing benchmark annotations manually is slow, but presenting model output
as human review would contaminate the ground truth used to evaluate that same
class of system. An AI pass can still reduce preparation time by identifying
ambiguities, evidence gaps, numerical checks, and disagreements for later
human adjudication.

## Decision

Provide an optional two-pass AI review:

- a blinded annotator sees the claim and supplied evidence but not the draft
  verdict or rationale;
- a critic reviews the packet and annotator output, identifies overstatement
  and missing checks, and may recommend a different verdict.

Store the result with `ai_reviewed` status and explicit provenance: models,
prompt version, timestamp, supplied-packet-only verification scope, structured
outputs, disagreements, token usage, and estimated cost.

AI-reviewed cases must retain empty `expected_verdict`, `reviewed_by`, and
`reviewed_at` fields. They are excluded from human-grounded accuracy. The
workflow refuses to replace an already human-reviewed case.

## Consequences

The project gains a fast, inexpensive review-preparation step without falsely
claiming human provenance. Reviewers can focus on recorded evidence gaps and
label disagreements.

The output remains susceptible to model error, shared model biases, and defects
in the supplied excerpts. A human must open the sources, resolve disagreements,
approve the final verdict, and record genuine reviewer metadata before a case
can become scoring ground truth.
