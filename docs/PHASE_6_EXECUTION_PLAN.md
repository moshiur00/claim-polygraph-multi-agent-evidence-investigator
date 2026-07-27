# Phase 6 execution plan

Date: 28 July 2026

Status: **Complete 28 July 2026; Stages 6.0–6.8 and 6.10 completed; Stage 6.9 skipped by gate**

Theme: verification, argument structure, and calibrated judgment

## 1. Delivery-roadmap alignment

This delivery phase implements the capability called **Phase 7 — Verification,
argument, and judgment** in the long-term project roadmap. Delivery Phase 5
already completed the roadmap's source-intelligence and provenance capability.

Phase 3 remains the default investigation workflow. Phase 4's multi-agent
workflow remains implemented but unpromoted. Phase 6 improves the correctness
and auditability of the default workflow before any production infrastructure
or frontend work begins.

## 2. Why this phase is necessary

The current system has useful but deliberately shallow verification:

- numerical checks compare number and unit strings but do not normalize units,
  calculate rankings, distinguish percentages from percentage points, validate
  ranges, or reproduce arithmetic;
- temporal checks use reference and publication dates but do not represent
  effective dates, observation periods, status transitions, or historical
  snapshots;
- the evidence judge receives a packet and deterministic safeguards, but there
  is no typed claim-to-evidence argument ledger showing which material
  propositions are supported, contradicted, qualified, or unresolved;
- contradiction research exists, but a challenger conclusion is not recorded
  separately from the final judgment;
- model confidence is intentionally nullable because it has not been
  calibrated; and
- provenance uncertainty is visible but deliberately does not yet determine
  verdict confidence.

These are judgment-quality gaps. Adding PostgreSQL, Redis, pgvector, LangGraph,
or a frontend would not correct them.

## 3. Phase objective

For each material claim component, produce a versioned and inspectable
verification-and-argument packet that:

1. represents the numerical and temporal assertions actually made;
2. records which approved evidence passages verify, contradict, qualify, or
   fail to resolve each assertion;
3. preserves source-dependency and context uncertainty;
4. constrains the permitted verdict labels and mandatory review conditions;
5. never invents a fact, calculation input, date, source, or citation; and
6. improves or preserves reviewed verdict quality without unacceptable cost or
   latency.

## 4. Explicit non-goals

Phase 6 will not:

- promote the Phase 4 multi-agent workflow;
- add general autonomous browsing or model-selected tools;
- add PostgreSQL, Redis, pgvector, LangGraph, distributed workers, or a
  frontend;
- download or retain a PDF when access or reuse is not allowed;
- retain full copyrighted documents when an evidence passage is sufficient;
- introduce a universal source trust score;
- convert independence bounds into a truth probability;
- claim that model confidence is statistically calibrated;
- modify reviewed benchmark labels to improve measured results;
- place reviewed URLs, expected labels, or gold passages in production prompts
  or retrieval queries; or
- run a paid model experiment before its deterministic gate is satisfied and
  the user explicitly authorizes it.

## 5. Inputs and reusable assets

The phase will reuse:

- the 20 reviewed CPNG benchmark claims and their approved verdicts;
- the approved review packets and frozen retrieval artifacts;
- Phase 3 single-coordinator outputs;
- Phase 4 pilot outputs only as diagnostic comparisons;
- Phase 5 provenance fixtures, source-quality dimensions, and uncertainty
  bounds;
- existing exact evidence passages and citation audits; and
- deterministic and local mock providers for development.

No fresh live retrieval is required to start the phase.

## 6. Locked evaluation rules

Before implementation changes, Stage 6.0 will write a content-addressed
manifest containing the fixture versions, baseline outputs, metric definitions,
and release gates. Gold labels and metric formulas become immutable after that
manifest is approved.

The following gates are proposed:

| Gate | Required result |
|---|---:|
| Reviewed verdict regressions | 0 |
| Numerical/temporal required-check trigger recall | 100% on reviewed cases |
| False `passed` result on intentionally incomplete checks | 0 |
| Deterministic numerical operation accuracy | at least 95% |
| Deterministic temporal-relation accuracy | at least 95% |
| Argument references outside approved evidence packet | 0 |
| Unsupported material propositions marked resolved | 0 |
| Verdict-label constraint violations after enforcement | 0 |
| Required-review escalation recall | 100% |
| Full citation support | at least 95% |
| Added deterministic median latency | at most 20% |
| Added deterministic model cost | $0 |
| Optional model cost, if separately authorized | at most $0.005 per case |

The numerical and temporal operation fixtures will be project-authored and
contain no benchmark verdict labels. Examples will cover equality, ranges,
ratios, percentages, percentage points, unit conversions, ranks, effective
dates, observation periods, and status transitions.

## 7. Cost-control protocol

Work proceeds from cheapest to most expensive:

1. static inspection and typed schema tests;
2. project-authored deterministic fixtures;
3. frozen benchmark replay;
4. targeted human review only for disagreements or new gold fields;
5. local model experiment only if it answers a measured unresolved question;
6. at most one bounded hosted-model pilot, only after explicit authorization.

Rules:

- No model calls in Stages 6.0 through 6.8 by default.
- No live search or page fetch unless frozen evidence cannot evaluate a
  predeclared gate.
- No broad 20-case paid rerun before a three-case pilot passes.
- Cache every eligible operation by versioned input hash.
- Reuse stored evidence, provenance, and model outputs.
- Stop a variant immediately when it cannot meet a release gate.
- Never tune against one case and report the same case as an unbiased test.

## 8. Stage plan

### Stage 6.0 — Baseline audit and locked manifest

Status: **completed 28 July 2026**

**Purpose**

Measure the current behavior before changing it.

**Work**

- Inventory current numerical, temporal, verdict, citation, provenance, and
  review artifacts.
- Replay all 20 reviewed cases from stored artifacts.
- Record current verdict accuracy, taxonomy errors, review escalations,
  citation support, latency, model calls, and cost.
- Classify failures without fixing them:
  - missing verification trigger;
  - parsing or normalization error;
  - missing evidence input;
  - arithmetic or temporal reasoning gap;
  - taxonomy error;
  - unsupported judge statement;
  - provenance or independence uncertainty;
  - citation-audit failure.
- Create `phase6-experiment-manifest-v1.json`.
- Verify the manifest with an offline CLI command.

**Deliverables**

- Baseline audit JSON and Markdown.
- Locked manifest and hash verifier.
- Short list of measured, generic failure classes.

**Exit gate**

All declared inputs exist, hashes match, all metrics are computable, and no
production change has been made.

**Recorded result**

- Manifest: `phase6-verification-judgment-v1`.
- Content-addressed artifacts checked: 7.
- Reviewed benchmark cases: 20/20 with distinct annotator and approver.
- Completed baseline cases: 20/20.
- Correct baseline verdicts: 18/20 (90%).
- Full citation audits: 20/20 (100%).
- Existing mismatches retained: CPNG-006 and CPNG-019.
- Assertion-level numerical and temporal metrics: unavailable in the baseline
  and explicitly recorded as Phase 6 gaps.
- Network, search, page fetch, PDF download, and model calls: 0.

The manifest verifier reports `valid: true`. Stage 6.0 changed no production
judgment behavior.

### Stage 6.1 — Verification contracts and safe-value model

Status: **completed 28 July 2026**

**Purpose**

Define the data model before implementing reasoning.

**Work**

- Add typed numerical assertion records:
  - original text span;
  - normalized value;
  - unit and scale;
  - comparator;
  - range endpoints;
  - precision or tolerance;
  - time period;
  - evidence IDs;
  - verification state and limitations.
- Add typed temporal assertion records:
  - claim reference date;
  - observation, publication, effective, and end dates;
  - interval inclusivity;
  - event or status transition;
  - evidence IDs;
  - verification state and limitations.
- Use `Decimal` or exact rational representations where appropriate; do not use
  binary floating point for equality decisions.
- Define explicit states: `verified`, `contradicted`, `qualified`,
  `insufficient`, `not_applicable`, and `error`.
- Reject unknown units, incompatible dimensions, missing operands, and
  unsupported calculations instead of guessing.
- Version all artifacts and keep current `ContextVerification` loadable.

**Deliverables**

- Pydantic domain contracts.
- JSON examples.
- Contract, serialization, validation, and backward-compatibility tests.

**Exit gate**

Schemas reject invalid references and ambiguous calculations while old reports
still load.

**Recorded result**

Stage 6.1 added the standalone, versioned `VerificationPacketV2` contract
without changing or replacing the legacy `ContextVerification` artifact.

The contracts include:

- exact decimal values with explicit unit, dimension, scale, and tolerance;
- numerical comparators, allowlisted operation declarations, expressions, and
  rounding-rule fields;
- explicit date precision, open or bounded intervals, publication dates,
  effective intervals, status observations, and retrospective-source flags;
- assertion states for `verified`, `contradicted`, `qualified`,
  `insufficient`, `not_applicable`, and `error`; and
- packet-level approved-evidence and claim-reference integrity.

Validation fails closed for out-of-packet citations, duplicate references,
cross-claim assertions, malformed ranges, unsupported resolved dimensions,
calculated assertions without expressions, reversed intervals, unresolved
required reference dates, and resolved assertions without evidence.

A machine-validated JSON example is stored at
`docs/examples/phase6_verification_packet_v2.json`. The existing
`ContextVerification` JSON shape remains valid and no production workflow uses
the new packet yet.

Verification completed with 283 passing tests, 86.51% coverage, and clean Ruff
checks. No network, retrieval, PDF, or model operation was used.

### Stage 6.2 — Deterministic numerical verifier

Status: **completed 28 July 2026**

**Purpose**

Verify common factual numerical relationships without a model.

**Initial supported operations**

- normalized equality with declared tolerance;
- greater-than and less-than comparisons;
- inclusive and exclusive ranges;
- sums, differences, ratios, and percentage changes;
- percentages versus percentage points;
- common unit conversions from an explicit allowlist;
- rank and ordinal checks from a complete supplied comparison set; and
- scale qualifiers such as thousands, millions, and billions.

**Safety behavior**

- Every operand must cite approved evidence.
- Every calculation stores its expression, normalized inputs, result, rounding
  rule, and evidence IDs.
- Locale-sensitive separators must be resolved explicitly.
- Currency conversion, inflation adjustment, statistical inference, and
  domain-specific formulas remain insufficient unless a dedicated rule and
  evidence input exist.
- No external calculator or API is called implicitly.

**Deliverables**

- Versioned numerical verifier.
- Project-authored positive, negative, boundary, and malformed fixtures.
- Human-readable calculation trace.

**Exit gate**

At least 95% operation accuracy, zero invented operands, zero false `verified`
on incomplete inputs, and no benchmark verdict regression.

**Recorded result**

The versioned `numerical-verifier-v1` engine now supports:

- direct equality and ordered comparisons;
- inclusive and exclusive ranges;
- sums, differences, and dimension-compatible ratios;
- percentage and percentage-point change;
- complete-set ascending or descending rank;
- exact decimal tolerance and explicit half-even rounding;
- allowlisted distance, duration, mass, pressure, percentage, and temperature
  conversions; and
- explicit scale factors.

Every operand carries an evidence ID. The output stores the evidence IDs,
operation expression, normalized result, optional rounding rule, verifier
version, and limitations. Missing operands and incomplete rankings produce
`insufficient`; incompatible dimensions, zero denominators or baselines,
unknown units, and currency conversion without a supplied external rate
produce `error`.

The project-authored `phase6_numerical_operations_v1` fixture contains 20
positive, negative, boundary, conversion, and fail-closed cases. The locked
evaluation result is:

- operation accuracy: 20/20 (100%), above the 95% gate;
- incomplete inputs falsely resolved: 0;
- evidence references outside the supplied packet: 0;
- model, network, and PDF calls: 0.

The component remains isolated and does not yet change production verdicts, so
the existing 20-claim baseline cannot regress at this stage. Full verification
completed with 289 passing tests, 86.31% coverage, and clean Ruff checks.

### Stage 6.3 — Deterministic temporal verifier

Status: **completed 28 July 2026**

**Purpose**

Evaluate time-sensitive claims at the correct reference date.

**Supported relations**

- before, after, on, and during;
- started, ended, remained active, and changed status;
- publication date versus event/effective date;
- point-in-time versus period claims;
- historical snapshot validity;
- source postdating and retrospective evidence; and
- stale evidence at a declared reference date.

**Safety behavior**

- Publication date is not automatically treated as event date.
- Later retrospective sources may describe earlier states but are marked as
  retrospective.
- Missing timezone or day precision widens the interval rather than inventing
  precision.
- “Current,” “still,” and similar terms require an anchored reference date.
- Conflicting dated evidence produces `qualified` or `insufficient`, not a
  silently selected winner.

**Deliverables**

- Versioned temporal verifier.
- Transition and interval fixtures.
- Inspectable timeline entries in JSON and Markdown.

**Exit gate**

At least 95% temporal-relation accuracy, zero false `verified` on incomplete
timelines, and correct reference-date handling on every reviewed time-sensitive
case.

**Recorded result**

The versioned `temporal-verifier-v1` engine now supports:

- `before`, `after`, `on`, and `during` relations;
- explicit start and end verification;
- active, inactive, and changed-status facts;
- point-in-time and bounded or open effective intervals;
- day, month, and year precision represented as bounds;
- publication dates kept separate from effective dates; and
- later retrospective evidence when it is explicitly marked.

Coarse dates that overlap but do not prove the asserted instant produce
`qualified`. Conflicting status facts also produce `qualified`. Missing
reference dates, missing facts, publication-only event claims, and effective
intervals that do not cover the asserted reference date remain `insufficient`.
A postdated source used for an earlier state is qualified unless explicitly
marked retrospective.

The project-authored `phase6_temporal_relations_v1` fixture contains 20
positive, negative, precision-boundary, conflict, retrospective, and
fail-closed cases. The locked evaluation result is:

- temporal-relation accuracy: 20/20 (100%), above the 95% gate;
- incomplete timelines falsely resolved: 0;
- evidence references outside the supplied packet: 0;
- model, network, and PDF calls: 0.

The temporal component remains isolated and does not yet change production
verdicts. Full repository verification completed with 294 passing tests,
86.32% coverage, and clean Ruff checks.

### Stage 6.4 — Claim-to-evidence argument ledger

Status: **completed 28 July 2026**

**Purpose**

Make judgment inputs explicit and auditable.

**Work**

- Represent each material proposition separately from the final verdict.
- Link supporting, contradictory, qualifying, and contextual evidence IDs.
- Attach numerical and temporal verification results.
- Attach Phase 5 family bounds and unresolved dependency counts.
- Record missing counterevidence and unresolved material questions.
- Add a deterministic challenger pass that identifies:
  - absolute wording defeated by exceptions;
  - causal wording supported only by association;
  - population evidence applied to individuals;
  - category or definition shifts;
  - incomplete rankings or denominators;
  - outdated status; and
  - dependent sources presented as separate confirmation.
- Do not create new facts or evidence during the challenger pass.

**Deliverables**

- `ArgumentLedger` and `ChallengeFinding` contracts.
- Deterministic builder and renderer.
- Referential-integrity and mutation tests.

**Exit gate**

Every ledger statement is traceable to the claim, a verifier output, or an
approved evidence ID; no material unresolved proposition is marked resolved.

**Recorded result**

The versioned `argument-ledger-v1` artifact now records material propositions,
their supporting, contradictory, qualifying, and contextual evidence IDs,
attached numerical and temporal assertion IDs, deterministic resolution, and
explicit unresolved reasons. Packet validation requires exactly one argument
per proposition and rejects cross-claim propositions, missing propositions,
and evidence references outside the approved packet.

The bounded challenger emits stable, inspectable findings for absolute
wording, causal overreach, population-to-individual generalization, missing
counterevidence, unresolved numerical checks, temporal contradictions or
insufficiency, and confirmed independence below the required source-family
count. Findings reorganize only supplied claim text and typed artifacts; they
cannot browse, add facts, create evidence, or determine a verdict label.

Referential-integrity, deterministic-rerun, mutation, stance-resolution, and
challenger tests pass. Full verification completed with 298 passing tests,
86.36% coverage, and clean Ruff checks. No model, network, retrieval, or PDF
operation was used. The ledger remains isolated from production judgment until
Stage 6.7.

### Stage 6.5 — Constrained judgment policy

Status: **completed 28 July 2026**

**Purpose**

Separate model interpretation from deterministic release constraints.

**Work**

- Define a versioned verdict-constraint matrix for `supported`,
  `contradicted`, `mixed`, `misleading`, `outdated`, `unsupported`, and
  `unverifiable`.
- Keep the model free to propose a label and explanation from approved inputs.
- Deterministically reject or revise combinations that violate evidence,
  temporal, numerical, component-aggregation, or citation invariants.
- Preserve both the proposed and enforced labels when enforcement occurs.
- Require an explicit reason code for every forced review.
- Ensure that a constraint can downgrade certainty or require review but cannot
  invent support.

**Deliverables**

- Judgment-policy artifact.
- Constraint matrix and exhaustive table tests.
- Proposed-versus-enforced judgment trace.

**Exit gate**

Zero invalid post-enforcement label combinations, zero correct reviewed-label
regressions, and 100% review escalation for unresolved critical checks.

**Recorded result**

The versioned `judgment-policy-v1` matrix maps proposition resolution to
permitted verdict labels:

- supported → `supported`;
- contradicted → `contradicted`, `outdated`, or `misleading`;
- qualified → `mixed` or `misleading`; and
- unresolved → `unsupported` or `unverifiable`.

Mixed material proposition resolutions permit only `mixed`. Valid model
proposals are preserved. An incompatible proposal is moved to a conservative
resolution-compatible default, while `JudgmentPolicyTrace` retains the
proposed label, enforced label, allowed labels, policy version, and reason
codes. Every override requires human review. Blocking challenger findings also
require review without changing an otherwise compatible label.

The exhaustive 4-resolution × 7-label matrix passes with zero invalid
post-enforcement combinations. Cross-claim verdicts are rejected. Full
repository verification completed with 332 passing tests, 86.36% coverage,
and clean Ruff checks. No model, network, retrieval, or PDF operation was
used. The policy remains isolated until Stage 6.7, so reviewed production
verdicts have not changed.

### Stage 6.6 — Deterministic readiness features

Status: **completed 28 July 2026**

**Purpose**

Expose confidence-relevant conditions without pretending to know a calibrated
truth probability.

**Features**

- material proposition coverage;
- supporting and contradictory evidence coverage;
- confirmed and possible independent-family counts;
- unresolved dependency width;
- numerical and temporal verification completeness;
- source-quality unknown count;
- citation-audit status;
- challenger findings; and
- unresolved-question count.

The result is a `JudgmentReadiness` state such as `ready`, `qualified`, or
`human_review_required`, plus reason codes. It is not a probability.

`Verdict.confidence` remains `null` unless a later calibration experiment shows
that a numerical score is reliable on held-out reviewed data.

**Deliverables**

- Versioned readiness feature artifact.
- Monotonicity tests: removing evidence or adding unresolved critical issues
  cannot improve readiness.
- Report section explaining every feature.

**Exit gate**

All readiness changes are explainable, monotonicity tests pass, and no feature
directly encodes the expected verdict label.

**Recorded result**

The versioned `judgment-readiness-v1` artifact reports material proposition
coverage, supporting and counterevidence counts, provenance bounds and
unresolved dependency count, verification completeness, source-quality unknown
count, citation-audit completeness, challenger counts, and unresolved-question
count.

It produces only `ready`, `qualified`, or `human_review_required`, with explicit
reason codes. It does not accept an expected verdict label and its
`confidence_score` field is structurally fixed to `null`.

Monotonicity tests confirm that removing proposition resolution, losing a full
citation audit, adding unresolved questions, adding nonblocking uncertainty,
or adding a blocking challenge cannot improve readiness. Material unresolved
propositions, critical verification gaps, incomplete citation audit, and
blocking findings require human review.

Full repository verification completed with 336 passing tests, 86.40%
coverage, and clean Ruff checks. No model, network, retrieval, or PDF operation
was used. Readiness remains isolated until Stage 6.7.

### Stage 6.7 — Default-workflow integration

Status: **completed 28 July 2026**

**Purpose**

Integrate the new artifacts without destabilizing the proven workflow.

**Order**

1. research and retain evidence;
2. consolidate and build provenance;
3. perform numerical and temporal verification;
4. build the argument ledger and challenger findings;
5. request the provisional judgment;
6. enforce deterministic judgment constraints;
7. compute readiness;
8. audit citations; and
9. persist and render the report.

**Compatibility and recovery**

- New artifacts are optional when loading older investigations.
- Existing verdict inputs remain available during a versioned transition.
- A checkpoint or retry reuses completed deterministic artifacts by input hash.
- A failure records an explicit limitation and follows a declared fail-closed
  or human-review path.
- Complex-claim child investigations use the same component-level packet.

**Exit gate**

Atomic and complex workflows pass integration, resume, idempotency,
serialization, no-results, and provider-failure tests.

**Recorded result**

The default atomic workflow now persists exactly one optional artifact for each
of:

- `verification_packet`;
- `argument_ledger`;
- `judgment_policy`; and
- `readiness`.

The judgment policy runs after the existing evidence and context safeguards.
Readiness runs after citation audit. JSON and Markdown reports expose all four
artifacts. Repeated report reconstruction loads the stored artifacts without
recomputation or duplication. Complex reports inherit them through their
component reports and existing checkpoint reconstruction.

Following the Stage 6.8 promotion-gate result, the integrated judgment-policy
trace is observational: it records its candidate label and `applied: false`,
while the proven workflow verdict remains authoritative. This preserves the
integration and its audit trail without promoting a regressive policy.

Backward compatibility is preserved: investigations and serialized report
payloads created before Stage 6.7 load with all four fields set to `null`.

The current retrieval path does not yet extract typed numerical operands,
effective dates, or explicit status facts. A versioned compatibility bridge
therefore records required checks as `insufficient` rather than treating
legacy string/date checks as Stage 6 proof. The legacy `ContextVerification`
artifact remains stored and visible.

Atomic, complex-component, no-results, provider-failure, serialization,
Markdown, idempotent-load, and artifact-count tests pass. Full verification
completed with 336 passing tests, 86.58% coverage, and clean Ruff checks. No
new model, network, retrieval, or PDF operation was added.

### Stage 6.8 — Frozen 20-claim evaluation and ablations

Status: **completed 28 July 2026; promotion gate failed safely**

**Purpose**

Decide whether the implementation improves judgment quality.

**Runs**

- frozen Phase 3 baseline;
- verification only;
- verification plus argument ledger;
- full deterministic Phase 6 constraints and readiness;
- Phase 4 multi-agent results only as an existing diagnostic comparison.

**Measurements**

- verdict accuracy and per-label confusion;
- taxonomy changes;
- numerical and temporal check accuracy;
- critical insufficiency escalation;
- unsupported-sentence and citation-support rates;
- provenance/independence uncertainty preservation;
- latency, model calls, tokens, and estimated cost; and
- case-level regression and improvement explanations.

No reviewed URL, gold passage, or expected verdict enters the production path.

**Exit gate**

All locked release gates pass. A failing deterministic variant is retained as
a diagnostic artifact and is not promoted.

**Recorded result**

The frozen evaluator ran all 20 reviewed CPNG cases without model, network,
retrieval, or PDF calls. Expected verdicts were used only for scoring after
inference and were never passed into the judgment policy.

- frozen baseline accuracy: **90%**;
- verification-only accuracy: **90%**;
- verification-plus-ledger accuracy: **90%**;
- full deterministic-policy accuracy: **65%**;
- improved cases: **0**;
- regressed cases: **5**;
- policy overrides: **6**;
- numerical fixture accuracy: **100%**;
- temporal fixture accuracy: **100%**; and
- citation-support rate: **100%**.

The full-policy variant changed CPNG-006, CPNG-007, CPNG-008, CPNG-009,
CPNG-011, and CPNG-014. Five changes regressed against reviewed truth. The
main failure mode is coarse stance aggregation losing qualified or mixed
meaning; it is not a narrow model-resolvable ambiguity. The policy was
therefore not promoted and was changed to observational-only operation.

The machine-readable result is
`artifacts/evaluations/phase6-stage6.8-frozen-ablation-v1.json`. A regression
test locks the measured outcome so accidental promotion cannot occur.

### Stage 6.9 — Optional bounded model experiment

Status: **skipped 28 July 2026**

**Default**

Skipped.

This stage is allowed only if Stage 6.8 identifies a narrowly defined ambiguity
that deterministic rules cannot resolve and whose resolution would affect a
release gate.

Stage 6.8 instead identified a broad deterministic representation and
aggregation limitation. A bounded model experiment would not test a narrow
ambiguity and would add cost without satisfying this stage's entry condition.

**Protocol**

- Write the hypothesis, eligible cases, prompt, schema, model, pricing version,
  maximum calls, maximum tokens, and cost ceiling before execution.
- Run a zero-cost structured mock preflight.
- Ask the user for explicit authorization.
- Run at most three representative cases first.
- Do not retry a valid unfavorable result or tune on the pilot cases.
- Expand only if at least two cases improve, none regress, citation support
  remains at least 95%, and the cost ceiling passes.

**Exit gate**

Promote only if held-out quality materially improves. Otherwise retain the
negative experiment and keep the deterministic workflow.

### Stage 6.10 — Targeted review, release audit, and closure

Status: **completed 28 July 2026**

**Purpose**

Close the phase with human accountability and a machine-verifiable record.

**Work**

- Present only changed verdicts, new verification gold fields, and unresolved
  disagreements for human review.
- Require annotator and distinct approver identities for any changed benchmark
  truth.
- Freeze final artifacts and hashes.
- Run the release audit, full tests, coverage, Ruff, and security checks.
- Write the completion report and architecture decision.
- Update the main specification status without renumbering the long-term
  roadmap.

**Exit gate**

Every gate is pass, fail, or explicitly waived with a named approver and
rationale. No pending item is described as complete.

**Recorded result**

The targeted-review packet contains only the six policy-changed cases and
explicitly records that no benchmark truth changed. The failed policy variant
remains observational, so no new human approval is asserted.

The final release audit freezes ten artifacts by SHA-256 and verifies offline.
It records seven passed gates, one failed policy-promotion gate, and one
optional experiment skipped by gate. Phase completion is valid because the
failed variant was not promoted and the safe existing verdict authority is
preserved.

Full verification completed with 339 passing tests, 86.42% coverage, clean
Ruff checks, clean dependency consistency, and 16 passing safe-fetcher
security tests. No model, retrieval, network, or PDF call was used.

Closure artifacts:

- `artifacts/evaluations/phase6-stage6.10-targeted-review-v1.json`;
- `artifacts/evaluations/phase6-final-release-audit.json`;
- `docs/adr/0013-phase6-policy-not-promoted.md`; and
- `docs/PHASE_6_COMPLETION_REPORT.md`.

## 9. Proposed implementation order

The most efficient order is:

1. Stage 6.0 baseline and manifest.
2. Stage 6.1 contracts.
3. Numerical and temporal verifiers in parallel conceptually, but implemented
   one at a time to keep review small.
4. Stage 6.4 ledger using the stable verifier outputs.
5. Stage 6.5 constraints.
6. Stage 6.6 readiness features.
7. Stage 6.7 integration.
8. Stage 6.8 frozen evaluation.
9. Stage 6.9 only if justified.
10. Stage 6.10 targeted review and closure.

Each stage should be one independently testable change set. A later stage must
not begin while an earlier exit gate is red unless the work is isolated and
cannot conceal the failure.

## 10. Stop, rollback, and scope-escalation conditions

Stop and reassess if:

- frozen baseline artifacts cannot be reconstructed;
- the verifier needs unstated domain assumptions;
- a calculation requires unavailable or unlicensed source content;
- more than two reviewed verdicts regress;
- a deterministic constraint repeatedly overrides correct model judgments;
- latency exceeds the ceiling without measurable quality improvement;
- a model experiment needs prompt tuning against its evaluation cases;
- the work requires a new paid dataset or API; or
- completing a stage would require production infrastructure.

New artifacts remain optional until Stage 6.8 passes. The rollback is therefore
to omit Phase 6 artifacts and retain the current Phase 3 plus Phase 5 default
workflow.

## 11. Definition of Phase 6 complete

Phase 6 is complete only when:

- numerical and temporal claims have typed, evidence-grounded verification
  traces;
- material propositions have an auditable argument ledger and challenger
  findings;
- final judgments obey deterministic evidence and taxonomy constraints;
- readiness communicates uncertainty without an uncalibrated probability;
- old and new investigations load and render correctly;
- the frozen 20-claim evaluation has no reviewed verdict regression;
- citation, cost, latency, and review gates pass;
- a distinct human approves any new or changed benchmark gold data; and
- the completion report and architecture decision are stored.

Passing Phase 6 will justify planning the next delivery phase: citation
publication gates and durable human-review workflow. It will not by itself
justify production infrastructure or a frontend.
