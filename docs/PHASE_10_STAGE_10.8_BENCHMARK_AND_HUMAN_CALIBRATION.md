# Phase 10 Stage 10.8 — Benchmark Replay and Human Calibration

## Machine benchmark outcome

The frozen benchmark contains 12 cases across six required categories:

- official announcements;
- eyewitness posts;
- manipulated screenshots;
- repost cascades;
- deleted posts;
- social links to primary documents.

All cases run through the actual deterministic eligibility, provenance,
independence, argument-ledger, and social publication-policy implementations.
No expected metric is copied into an actual result.

| Metric | Result | Gate |
|---|---:|---:|
| Exact eligibility | 12/12 | pass |
| Eligibility precision | 100% | pass |
| Unsafe-publication rate | 0/6 (0%) | pass |
| Origin-resolution accuracy | 3/3 (100%) | pass |
| Required origin-resolution rate | 2/2 (100%) | pass |
| Independence inflation | 0 cases | pass |
| Mandatory-review recall | 9/9 (100%) | pass |
| Review-routing precision | 90% | calibration observation |
| Verdict stability under duplicate distribution | 4/4 (100%) | pass |

## Calibration observation

`SOCADV-012` contains three context-only social link-shares and one resolved
primary document. All four records correctly form one family, the primary
document supplies the factual support, and publication is not blocked.

The system nevertheless routes human review because shared-origin repetition
is a caution-level provenance risk. This is conservative over-routing, not an
unsafe publication. The human calibration approved retaining this safeguard.
`SOCADV-012` remains labelled non-mandatory so review-routing precision
continues to expose the deliberate additional review instead of hiding it.

## Human-calibration integrity

The generated review packet is complete:

- Annotator: Md Moshiur Rahman
- Distinct approver: Md Rashedul Islam
- Review date: 30 July 2026
- Case decisions: all twelve approved
- Packet decision: approved
- `SOCADV-012`: conservative review routing retained

Review packet:
`artifacts/reviews/phase10-stage10.8-human-calibration-packet-v1.json`.

## Cost and scope

- Model calls: 0
- Search calls: 0
- Network calls: 0
- The cases are synthetic adversarial policy fixtures; they evaluate control
  behavior, not empirical truth accuracy on a social platform.

## Exit status

The machine exit gates pass, targeted human calibration is approved, and the
Stage 10.8 exit gate is ready.
