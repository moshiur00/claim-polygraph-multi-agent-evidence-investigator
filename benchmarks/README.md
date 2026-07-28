# Evaluation benchmarks

`initial_claims_v1.json` is the first twenty-claim regression set required by
the project charter. It covers numerical, scientific or medical, political or
policy, corporate, historical, causal, comparative, ambiguous, outdated, and
derivative-reporting claims.

The claims are investigation inputs, not endorsed statements. A draft case may
contain a researched `proposed_verdict`, rationale, and short candidate
evidence excerpts. These remain proposals and do not count as ground truth.
Only `expected_verdict` values on human-reviewed cases contribute to accuracy.
The intermediate `ai_reviewed` status is explicitly non-scoring.

Dataset version 5 contains approved human-reviewed labels for `CPNG-001`
through `CPNG-020`. Md Moshiur Rahman completed the annotation pass and
Md Rashedul Islam distinctly approved the evidence and verdicts. The dataset
records the applicable review dates and preserves the earlier AI-assisted
records as transparent preparation provenance rather than human ground truth.

## Annotation workflow

For each case:

1. Resolve the ambiguity notes and preserve a clear reference date,
   geography, definition, comparison basis, and measurement unit.
2. Check every candidate excerpt against the linked page and its surrounding
   context.
3. Add primary or authoritative evidence plus genuinely independent
   corroborating or contradictory evidence.
4. Confirm or revise the proposed verdict and rationale.
5. Have a second person review the evidence and conclusion.
6. Copy the approved result to `expected_verdict`; record `annotated_by`,
   `annotated_at`, `approved_by`, and `approved_at`; mirror the approver in the
   compatibility fields `reviewed_by` and `reviewed_at`; and only then change
   `annotation_status` to `reviewed`.

Changing an existing reviewed claim, expected verdict, or evidence packet
requires a dataset version increment. New experimental annotations should not
silently overwrite a reviewed version.

## First five-claim review batch

Run:

```powershell
claim-polygraph review-status
```

The default output covers `CPNG-001` through `CPNG-005`. Their
[human-review packet](review_packets/cpng_001_005.md) is complete, and the
command should report `Reviewed: 5/5`.

After editing the dataset, rerun `claim-polygraph review-status` and the test
suite. Only reviewed cases with an expected verdict, candidate evidence,
reviewer identity, and review date pass schema validation and contribute to
verdict accuracy.

## Optional AI-assisted preparation

An AI annotator and a separate AI critic can prepare the next draft packet:

```powershell
claim-polygraph ai-review `
  --cases CPNG-006 CPNG-007 CPNG-008 CPNG-009 CPNG-010
```

The annotator is not shown the draft verdict or rationale. The critic receives
the evidence packet and annotator output, challenges unsupported conclusions,
and can recommend a different provisional verdict. The dataset records both
passes, disagreements, model identifiers, prompt version, token usage, and
estimated cost under `ai_review`.

AI review does not verify linked pages beyond the excerpts already supplied.
It therefore sets `source_verification_scope` to `provided_packet_only`,
requires later human review, and cannot populate human reviewer metadata or
`expected_verdict`.

The AI review command refuses to overwrite a human-reviewed case.

To promote a case after genuine human review:

1. Open and verify each linked source and complete the review packet.
2. Resolve the AI passes and any recorded disagreement; do not accept the
   provisional verdict automatically.
3. Add or correct evidence, `proposed_verdict`, and `proposed_rationale`.
4. Set `expected_verdict`, the typed annotator and distinct-approver fields,
   plus the compatibility `reviewed_by` and `reviewed_at` fields.
5. Change `annotation_status` from `ai_reviewed` to `reviewed`.
6. Increment the dataset version if the approved benchmark is being released.
7. Run `claim-polygraph review-status` and `python -m pytest`.

## Metrics boundary

Draft and AI-reviewed cases contribute to workflow metrics such as completion,
latency, source/evidence counts, and structural citation status. They do not
contribute to verdict accuracy. Structural citation status is also not
semantic entailment; that requires a real citation-support evaluator.

Evaluation may also report `ai_provisional_agreement_rate` for AI-reviewed
cases. This is a development diagnostic for detecting changes and
disagreements. It is not accuracy, does not validate either model, and must not
be presented as benchmark performance.

OpenAI evaluation summaries include metered token totals and estimated model
costs based on the pricing version recorded in each model-usage trace event.
These estimates exclude search infrastructure and are not invoices.

Use `claim-polygraph evaluate --benchmark-evidence --limit 5` to test the
reasoning pipeline with the reviewed evidence packets supplied as retrieval
results. Treat this as an evidence-oracle baseline, not an end-to-end retrieval
score. Normal deterministic or SearXNG modes remain separate so retrieval
quality can be measured independently.

`claim-polygraph --searxng-url URL evaluate-retrieval --limit 5 --top-k 10`
runs the first search-candidate baseline. It uses only each claim as the query
and measures reviewed URL/host recall and ranking. Search-snippet lexical recall
is reported only as a proxy; it must not be described as semantic evidence or
passage recall.

Use `--query-strategy claim_only` as the control and `--query-strategy balanced`
as the bounded multi-query treatment. The balanced strategy uses only generic
templates derived from the claim, never reviewed URLs, publishers, excerpts,
or annotation labels.

`guarded_fusion` is the ranking-preserving treatment: for top-10 evaluation it
keeps seven claim-only candidates and permits no more than three expansion
candidates. This makes its recall and MRR tradeoff directly comparable with the
claim-only control.

For reproducible comparisons, capture a `guarded_fusion` run with
`--snapshot-output`, then evaluate both strategies with `--snapshot-input`.
Snapshots contain normalized search responses before fusion and are bound to
the benchmark dataset identity, version, and original top-K budget.

`quality_rerank` operates entirely on a snapshot. Its authority and risk
features are deterministic engineering heuristics, not verified publisher
labels or evidence judgments. Compare reviewed-source recall, MRR, mean quality
score, low-quality-candidate rate, and unique-host rate before promotion.

`evaluate-pages` consumes a retrieval evaluation and fetches only its bounded
top-N candidates. Its reviewed-passage score is a lexical proxy over the top-K
ranked passages, not semantic entailment. Report HTTP, extraction, duplication,
and passage-selection failures as separate stages.

`evaluate-semantic-passages` is a bounded diagnostic for lexically unmatched
references. It compares only the highest-coverage passage above a configured
lower gate. Its `equivalent` result is model-generated and must remain
distinguished from human-reviewed ground truth.
