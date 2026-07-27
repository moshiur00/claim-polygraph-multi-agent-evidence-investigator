# AI review summary: CPNG-011 through CPNG-020

Run date: 27 July 2026

This file summarizes the structured machine review embedded in
`benchmarks/initial_claims_v1.json`. It is not source verification, human
annotation, distinct approval, or benchmark ground truth.

## Provenance

- Annotator model: `gpt-4o-mini`
- Critic model: `gpt-4o-mini`
- Prompt version: `ai-benchmark-review-v2`
- Verification scope: supplied evidence packet only
- Estimated saved-call cost: `$0.006055`
- Human review still required: yes

The timed-out initial ten-case attempt and the superseded v1 records are not
included in the saved-record figure. Provider-side usage for the aborted
attempt is unavailable in local telemetry. Version 2 explicitly classifies the
submitted claim rather than the persuasiveness of the evidence packet and
requires component-wise aggregation.

## Results

| Case | Curated proposal | Annotator | Critic/recorded provisional | Critic says sufficient |
|---|---|---|---|---|
| CPNG-011 | `mixed` | `contradicted` | `contradicted` | yes |
| CPNG-012 | `contradicted` | `contradicted` | `contradicted` | yes |
| CPNG-013 | `contradicted` | `contradicted` | `contradicted` | yes |
| CPNG-014 | `contradicted` | `mixed` | `misleading` | yes |
| CPNG-015 | `contradicted` | `contradicted` | `mixed` | no |
| CPNG-016 | `contradicted` | `contradicted` | `mixed` | no |
| CPNG-017 | `mixed` | `contradicted` | `mixed` | no |
| CPNG-018 | `mixed` | `mixed` | `mixed` | yes |
| CPNG-019 | `contradicted` | `contradicted` | `contradicted` | yes |
| CPNG-020 | `misleading` | `misleading` | `mixed` | no |

## Required human attention

- **CPNG-011:** decide whether one near-true electricity component plus two
  false total-energy/fossil-fuel components should aggregate to `mixed` or
  `contradicted`.
- **CPNG-012:** the critic’s `mixed` label conflicts with evidence that both the
  absolute statement and the safety inference are false.
- **CPNG-014:** record the length convention and uncertainty explicitly; verify
  a current independent discharge comparison.
- **CPNG-015:** independently verify the historical height estimate and
  contemporary comparison population.
- **CPNG-016:** v2 corrected the earlier direction inversion, but the critic
  still selected `mixed` because it wanted more direct no-5G outbreak data.
  Manually check both components before selecting `contradicted`.
- **CPNG-017:** harmonize deliveries versus sales and the corporate-group scope
  before selecting `mixed`.
- **CPNG-018:** verify the complete monthly series, even though one exact
  counterexample is logically sufficient to refute the universal clause.
- **CPNG-019:** retain the dose, habituation, population, and duration limits.
- **CPNG-020:** identify the attributed study and do not generalize selected
  occupations or outcome measures to all employees.

Full rationales, gaps, disagreements, token counts, and per-call costs remain
embedded in each case for auditability.
