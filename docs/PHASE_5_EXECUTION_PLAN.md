# Phase 5 execution plan

Date: 27 July 2026

Status: **Stages 5.0 through 5.10 completed; Phase 5 implementation closed**

Theme: source intelligence and explainable provenance

## Decision boundary

Phase 3 remains the default investigation workflow. Phase 4 remains
experimental and is not a prerequisite for this phase. Phase 5 adds source
canonicalization, duplication detection, dependency relationships, and
evidence-family reasoning without adding PostgreSQL, Redis, pgvector,
distributed runtimes, or a frontend.

## Stage 5.0 — Baseline and provenance benchmark

The repository now contains:

- A 12-case synthetic, project-authored provenance benchmark.
- Exact expected source relationships and evidence-family labels.
- Predeclared numerical release thresholds.
- Content-addressed references to the fixture and Phase 4 closure audit.
- An offline verifier that makes no network, search, PDF, or model call.

The fixture covers tracking URL variants, print views, mirrors, syndication,
summaries, common press-release origins, independent measurements, shared data
with independent analysis, explicit citations, translations, topical
similarity, and ambiguous paraphrasing.

The expected relationships, canonical-document labels, family labels, and
rationales were reviewed by Md Moshiur Rahman and distinctly approved by
Md Rashedul Islam on 27 July 2026.

## Locked release thresholds

| Metric | Threshold |
|---|---:|
| Canonical precision | 100% |
| Exact duplicate precision | 100% |
| Exact duplicate recall | 100% |
| Derivative precision | 95% |
| Derivative recall | 90% |
| Evidence-family accuracy | 90% |
| Maximum false-independent rate | 5% |
| Existing correct-verdict regressions | 0 |
| Full citation support | 95% |
| Maximum added deterministic latency ratio | 20% |
| Maximum added model cost per investigation | $0.005 |

## Next gated stage

## Stage 5.1 — Deterministic canonicalization

Status: **completed 28 July 2026**

The versioned `url-v1` canonicalizer:

- normalizes HTTP(S) scheme, host, default ports, paths, fragments, and query
  ordering;
- removes a narrow denylist of tracking and presentation parameters while
  preserving identity-bearing parameters;
- normalizes language-path variants and DOI forms;
- rejects relative, non-HTTP(S), and credential-bearing URLs; and
- records every transformation and removed parameter.

The locked 12-pair evaluation achieved 100% precision, 75% recall, and zero
false merges. The only missed expected canonical relationship is a cross-host
archive mirror. This is deliberately not merged from URL text alone and will be
resolved using explicit provenance signals in a later stage.

Paid model calls, network access, live searches, and PDF downloads remained
unused and unauthorized.

## Next gated stage

## Stage 5.2 — Explainable source-quality dimensions

Status: **completed 28 July 2026**

The deterministic `dimensions-v1` assessor represents:

- authority;
- directness;
- methodological transparency;
- editorial accountability;
- citation transparency;
- temporal relevance;
- domain relevance; and
- conflict of interest.

Each dimension carries a finding, reason, and observed signals. Sparse metadata
remains `unknown`; source type alone does not establish authority; an interested
party can remain a direct primary source while its conflict is disclosed
separately. No aggregate trust or truth score exists.

The structural evaluation assessed all 24 fixture sources with 100% dimension
completeness, 100% explained findings, 100% unknown preservation, and zero
aggregate scores. It made no network, search, model, or PDF call.

The calibration set now contains eight balanced scenarios and 64 proposed
dimension labels. The deterministic assessor agrees with all 64 labels, passing
the numerical agreement gate at 100%. Md Moshiur Rahman reviewed the labels and
Md Rashedul Islam distinctly approved them on 28 July 2026. The human-review
gate therefore passes.

## Next gated action

Stage 5.2 is closed. The reviewed calibration remains immutable unless a new
version is created with a documented correction.

## Stage 5.3 — Exact duplicate detection

Status: **completed 28 July 2026**

The `exact-text-v1` implementation:

- applies Unicode NFKC, whitespace, and case normalization;
- creates versioned SHA-256 fingerprints;
- rejects duplicate record identifiers;
- creates stable duplicate clusters with deterministic representatives;
- preserves every original member identifier for audit; and
- supplies the same normalizer to evidence consolidation so duplicates
  contribute only once.

The locked fixture produced four exact duplicate clusters with 100% precision,
100% recall, and zero false merges. Punctuation and numerical differences
remain distinct. No network, search, model, or PDF operation was used.

## Next development stage

Stage 5.4 adds conservative near-duplicate and syndication detection using
lexical shingles, shared quotations, publication ordering, and attribution
signals. Its results must not affect independence automatically unless
precision remains at least 95%.

## Stage 5.4 — Near-duplicate and syndication detection

Status: **completed 28 July 2026**

The versioned `lexical-provenance-v1` detector records token Jaccard and
containment, shared three-token shingles, shared numerical tokens, attribution
and controlling-reference markers, explicit independence markers, and
publication ordering.

It distinguishes exact, likely derivative, possibly related, and distinct
pairs. Topical similarity alone cannot establish derivation, and explicit
independent-analysis language prevents a derivative label.

The locked evaluation included six eligible pairs and excluded six pairs
assigned to exact-copy, translation, or unresolved-relationship handling. It
achieved 100% precision and 100% recall, exceeding the 95% and 90% gates.
Individual detector results still prohibit automatic independence changes;
controlled integration occurs only after the provenance-link and
evidence-family stages consume the passed evaluation.

No network, search, model, embedding, or PDF operation was used.

## Next development stage

Stage 5.5 extracts explicit provenance links such as citations, named
standards, attribution, and common announcements. Extracted URLs remain
untrusted data and must pass the existing safe-fetch policy before retrieval.

## Stage 5.5 — Explicit provenance-link extraction

Status: **completed 28 July 2026**

The versioned `explicit-links-v1` extractor records citations, summaries,
attribution to announcements, controlling standards, and HTTP(S) references.
Each link contains exact source-relative offsets, target text, confidence,
resolution state, and permission state.

The extractor does not open links, resolve targets, create sources, or authorize
retrieval. Non-HTTP schemes are ignored as URL references, and every extracted
HTTP(S) URL remains subject to the existing safe-fetch policy.

The locked 12-pair evaluation extracted five links across the three expected
explicit-link relationships. Precision and recall were both 100%, all offsets
matched their stored excerpts, every link remained unresolved, and retrieval
calls remained zero.

## Next development stage

Stage 5.6 combines canonical identity, exact duplicates, near-duplicate
signals, and explicit links into component-specific evidence families with
confidence and auditable grouping reasons.

## Stage 5.6 — Evidence-family inference

Status: **implementation completed 28 July 2026; false-independence gate not met**

The versioned `families-v1` inference applies fixed precedence:

1. canonical URL identity;
2. exact normalized content;
3. precision-gated near-duplicate evidence;
4. explicit provenance links;
5. explicit independent-analysis language; and
6. unresolved when signals remain insufficient.

Dependent edges form stable, component-specific families. Unknown pairs remain
separate rather than being forced together, and every family exposes its
grouping reasons. Benchmark relationships and expected verdicts are not
available to inference.

The locked evaluation correctly assigned 11 of 12 cases, giving 91.67% family
accuracy and passing the 90% accuracy gate. The deliberately ambiguous
PROV-012 paraphrase remained unresolved and separate. This produced one false
independent result among nine expected dependent pairs: 11.11%, above the 5%
ceiling.

This is the specific measured condition that authorizes Stage 5.7. The bounded
classifier may evaluate only unresolved candidate pairs; it may not reconsider
deterministically resolved pairs.

No network, search, model, or PDF operation was used in Stage 5.6.

## Next gated stage

Stage 5.7 runs a zero-cost structured mock preflight, followed—only when
explicitly authorized—by at most one hosted-model call for the single
PROV-012 unresolved pair. Promotion requires resolving the false independence
without reducing overall family precision.

## Stage 5.7 — Bounded ambiguous-relationship classifier

Status: **completed 28 July 2026; classifier not promoted**

The zero-cost preflight selected exactly one unresolved pair, validated the
strict output schema, limited execution to one call, and imposed a $0.01 hard
ceiling.

One authorized `gpt-4o-mini` call classified PROV-012 as
`likely_independent` with 0.70 confidence. The estimated cost was $0.00018930.
The result left family accuracy at 91.67% and the original false-independence
metric at 11.11%, so the release gate remained closed.

No second call, prompt tuning, or result-dependent retry was performed. The
classifier is not integrated or promoted. Its result is retained as a negative
experiment.

## Next design correction

Stage 5.8 must represent unresolved dependency explicitly as an independence
interval rather than silently counting unknown pairs as independent:

- confirmed-independent lower bound;
- possible-independent upper bound; and
- unresolved dependency count.

This follows the original Phase 5 rule that unknown dependency must not be
silently counted as independence. The correction must be generic and evaluated
without changing the reviewed PROV-012 label or making another model call.

## Stage 5.8 — Uncertainty-aware independence features

Status: **completed 28 July 2026**

The versioned `independence-bounds-v1` feature set exposes:

- raw source count;
- grouped family count;
- confirmed-independent lower bound;
- possible-independent upper bound;
- unresolved dependency count;
- dependent repetition count;
- interval width; and
- a `met`, `not_met`, or `uncertain` requirement state.

Unknown dependency contributes to the possible upper bound but never to the
confirmed lower bound. No confidence or truth score is calculated.

On the locked fixture, family assignment accuracy remained 91.67%, above the
90% gate. False **confirmed** independence fell from the old binary metric's
11.11% to 0%, and zero unknown pairs were counted as confirmed independence.
PROV-012 now reports a lower bound of one family, an upper bound of two, and an
`uncertain` two-family requirement.

The Stage 5.7 model output was not used. No additional model, network, search,
or PDF operation occurred.

## Next development stage

Stage 5.9 adds provenance and independence sections to machine-readable and
Markdown reports so a reviewer can inspect family membership, dependency
reasons, uncertainty bounds, and unresolved pairs without reading internal
logs.

## Stage 5.9 — Provenance reporting and inspection

Status: **completed 28 July 2026**

The versioned `provenance-report-v1` artifact includes:

- source identifiers, titles, publishers, and canonical URLs;
- component-specific family membership;
- every dependency edge, status, confidence, and reason;
- raw, grouped, lower-bound, and upper-bound independence counts;
- unresolved dependency counts and requirement states;
- source-quality dimensions and reasons; and
- report-level limitations.

The Markdown renderer exposes the same substantive information as JSON.
PROV-012 visibly reports `[1, 2]` possible families, one unresolved dependency,
and an `uncertain` requirement state.

The locked report covers all 12 fixture components and 24 sources. It stores no
full documents or source excerpts. The failed Stage 5.7 classifier result is
not included in family inference.

No network, search, model, or PDF operation was used.

## Stage 5.10 — Default-workflow integration

Status: **completed 28 July 2026**

The default Phase 3 investigation now builds and persists one versioned
`investigation-provenance-v1` artifact after research and evidence-family
analysis. It contains conservative independence bounds, pairwise dependency
reasons, inferred families, and eight explainable quality dimensions per
retained source.

The provenance artifact is deliberately excluded from the evidence-judgment
input. It explains the stored evidence packet but cannot alter the verdict,
confidence, safeguards, or citation audit. No model call is introduced.

Both JSON and Markdown reports expose the packet. Report reconstruction treats
it as optional, so investigations stored before Stage 5.10 remain loadable.
Repeated report loads reuse the single persisted artifact and do not recompute
or append provenance. Complex-claim reconstruction inherits this behavior for
each completed component, preserving the existing checkpoint boundary.

Sources without retained evidence passages are excluded explicitly and counted
in the packet limitations. Investigations with no usable evidence receive
zero-width bounds and a `not_met` state instead of failing.

Verification completed with:

- 273 passing tests;
- 86.72% branch-aware coverage, above the 85% repository gate;
- clean Ruff checks; and
- focused compatibility, persistence, idempotent-load, no-results, JSON, and
  Markdown integration tests.

No network, search, hosted-model, or PDF operation was added for this stage.
The optional MyPy check was unavailable because MyPy is not a declared project
development dependency.

## Phase 5 closure

Phase 5 is complete. Source intelligence is now an inspectable companion to
the default workflow, while unresolved dependency remains uncertainty rather
than silently becoming independence. The failed Stage 5.7 classifier remains
unpromoted, and Phase 4 remains an optional experimental workflow.
