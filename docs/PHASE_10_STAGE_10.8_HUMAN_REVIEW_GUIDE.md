# Stage 10.8 Human Calibration Guide

Review the 12 cases in
`artifacts/reviews/phase10-stage10.8-human-calibration-packet-v1.json`.

For each case, confirm or revise:

1. eligibility: `eligible`, `conditional`, or `ineligible`;
2. whether human review is mandatory;
3. whether publication would be unsafe without the recorded block;
4. whether the listed policy findings correctly explain the outcome.

Use one decision:

- `approve` — the frozen labels and machine behavior are acceptable;
- `revise` — record revised fields and explain the policy change;
- `reject` — the case or expected behavior is unsuitable.

Every case requires review notes. After the annotator completes the cases, a
different person records either `approve` or `approve_with_revisions` in the
packet-level approval.

Pay particular attention to:

- `SOCADV-001`: whether an authenticated, corroborated first-party statement
  should still route review because it appears on the decisive side;
- `SOCADV-006`: whether an ineligible screenshot retained only as a lead should
  block publication when the non-social primary record independently supports
  the claim;
- `SOCADV-010`: whether a resolved social link used only as context can safely
  avoid review;
- `SOCADV-012`: whether resolved context-only repetition should remain a review
  trigger after family deduplication.

Do not approve because engagement, virality, or a platform verification badge
looks persuasive. Those signals are deliberately excluded.
