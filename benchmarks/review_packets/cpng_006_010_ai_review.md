# AI review summary: CPNG-006 through CPNG-010

Run date: 27 July 2026

This file summarizes the machine review recorded in
`benchmarks/initial_claims_v1.json`. It is not source verification, a human
annotation, or benchmark ground truth.

## Provenance

- Annotator model: `gpt-5.4-mini`
- Critic model: `gpt-4o-mini`
- Prompt version: `ai-benchmark-review-v1`
- Verification scope: supplied evidence packet only
- Estimated total cost: `$0.017946`
- Human review still required: yes

## Results

| Case | Annotator | Critic | Recorded provisional | Evidence sufficient according to critic |
|---|---|---|---|---|
| CPNG-006 | `supported` | `mixed` | `mixed` | no |
| CPNG-007 | `mostly_supported` | `mixed` | `mixed` | no |
| CPNG-008 | `supported` | `supported` | `supported` | yes |
| CPNG-009 | `supported` | `supported` | `supported` | no |
| CPNG-010 | `misleading` | `misleading` | `misleading` | yes |

## Review signals

- **CPNG-006:** re-run the official, revision-sensitive data and compare it
  with an independent statistical source before approval.
- **CPNG-007:** make the meaning of “founded” explicit and check the competing
  1994 incorporation versus 1995 commercial-launch interpretation.
- **CPNG-008:** read both paragraphs of Article 99 to preserve the distinction
  between entry into force and application.
- **CPNG-009:** inspect the NCI reference chain and keep population causation
  separate from individual certainty or sole-cause wording.
- **CPNG-010:** check post-2013 context and keep prevention, duration,
  severity, dose, timing, and subgroup findings separate.

The full structured rationales, gaps, disagreements, token use, and per-call
costs remain embedded with each benchmark case for auditability.
