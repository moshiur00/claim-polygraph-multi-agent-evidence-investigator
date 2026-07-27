# Phase 4 execution plan

Date: 27 July 2026

Status: **completed 27 July 2026 — multi-agent promotion gate not met**

Theme: cost-controlled, evidence-driven multi-agent research

## 1. Purpose and naming

This is delivery **Phase 4** and corresponds to “Multi-agent research” in the
long-term architecture roadmap (originally numbered Phase 5 there). The prior
delivery phase already completed complex-claim analysis, typed workflow state,
checkpointing, and resume behavior.

Phase 4 will determine whether bounded specialist research materially improves
the completed Phase 3 single-coordinator baseline. It will not assume that more
agents are better.

## 2. Governing efficiency rules

1. **Reuse before rebuilding.** Retain the Phase 3 retrieval, safe fetching,
   passage extraction, evidence classification, citation audit, persistence,
   model routing, and evaluation infrastructure.
2. **Roles are policies, not runtimes.** An agent is initially a typed role
   executed by the existing Python process. Do not add LangGraph, Redis,
   PostgreSQL, containers, or separate services in this phase.
3. **Minimum viable team first.** Start with coordinator, primary-source,
   general, and challenger roles. Academic and fact-check roles are conditional.
4. **Route before calling.** Deterministic code decides which roles are needed.
   The LLM does not receive permission to create arbitrary agents.
5. **Search once where possible.** Cache by normalized provider, query,
   parameters, and retrieval date. Share retrieved candidates across roles.
6. **Fetch once.** Canonical URLs share fetched content and extracted passages.
7. **Judge once.** Reuse the Phase 3 verdict and citation stages after producing
   one consolidated evidence packet.
8. **Stop on sufficiency or low yield.** No open-ended research loop is allowed.
9. **Fail closed.** Missing, invalid, or uncited evidence cannot be converted
   into a factual assertion.
10. **Evaluate on a small development slice before the declared benchmark.**
    Paid runs are delayed until deterministic and mock tests pass.

## 3. Frozen Phase 3 baseline

The comparison baseline is:

- Dataset: `initial_claims`, version 5.
- Declared cases: CPNG-011 through CPNG-020.
- Reviewed material components: 21.
- Verdict accuracy: 90% in both declared runs.
- Material-component coverage: 100%.
- Full parent citation support: 100%.
- Exact repeated-label stability: 100%.
- Reviewed-passage retrieval recall: 80.85%.
- Mean model cost per component:
  - Run A: $0.008199.
  - Run B: $0.008780.
- Completion: 100%.

The Phase 3 artifacts remain immutable. Phase 4 writes new artifacts and never
overwrites the baseline.

## 4. Phase-level resource envelope

The phase is divided into gated stages. Later stages do not begin until the
previous gate passes.

### Development budget

- Use deterministic fixtures and mock providers for most development.
- Use local models only for optional smoke tests.
- Use OpenAI only for deliberately declared model experiments.
- Reuse the frozen Phase 3 retrieval snapshot for initial experiments.
- Do not issue live search merely to test orchestration.
- Do not download PDFs without explicit rights approval.

### Declared evaluation budget

- First paid comparison: three difficult claims selected before seeing Phase 4
  results.
- Second comparison: all ten CPNG-011–020 claims only if the three-claim gate
  passes.
- Maximum two declared multi-agent runs on the ten-claim benchmark.
- No third full run without a documented failure that invalidated, rather than
  merely disappointed, a prior run.
- Per-investigation hard limits must cover model calls, queries, fetched pages,
  elapsed time, and estimated cost.

### Default experimental limits

These are initial configuration defaults and must remain configurable:

- Maximum research rounds: 2.
- Maximum simultaneously active research roles: 3.
- Maximum role activations per component: 4.
- Maximum queries per role per component per round: 2.
- Maximum accepted candidates per query: 10.
- Maximum fetched pages per component: 12.
- Maximum bounded query revisions per missing requirement: 1.
- Stop after one completed round with no material evidence gain.
- Abort before a provider call that would exceed the configured cost ceiling.

The exact dollar ceiling will be set from a dry-run estimate before paid
evaluation; it must not be guessed in production code.

## 5. Typed architecture

### 5.1 Roles

#### Coordinator

Responsibilities:

- Receive the parent claim, material components, protected context, and budget.
- Generate or accept a deterministic research requirement plan.
- Select eligible specialist roles.
- Dispatch compatible work concurrently within the configured limit.
- Consolidate results without changing source passages.
- Ask the sufficiency controller whether another bounded round is warranted.

The coordinator may not browse, fetch, invent evidence, or produce a final
verdict.

#### Primary-source researcher

Searches for controlling, official, original, or first-party evidence. It
returns candidates and evidence records, not conclusions outside those records.

#### General evidence researcher

Searches broadly for high-quality independent corroboration, qualification, and
context.

#### Challenger researcher

Searches specifically for contradiction, exceptions, ambiguity, outdated
context, counterexamples, and alternative interpretations.

#### Academic researcher

Activated only for scientific, medical, technical, empirical, or causal claims
where scholarly evidence is a material requirement.

#### Fact-check researcher

Activated only when prior professional fact-check coverage is likely to add
source leads, claim history, or documented counterevidence. A fact-check page
does not automatically count as primary or independent evidence.

#### Evidence-sufficiency controller

Uses deterministic features first and one typed model decision only when the
rules cannot resolve a bounded choice. It can return:

- `sufficient`
- `continue_missing_primary`
- `continue_missing_independent`
- `continue_missing_challenge`
- `continue_missing_component`
- `continue_context_mismatch`
- `stop_budget_exhausted`
- `stop_diminishing_return`
- `stop_unresolvable`
- `human_review_required`

It cannot write a verdict or create evidence.

### 5.2 Required contracts

Add typed models for:

- `ResearchRole`
- `ResearchRequirement`
- `ResearchAssignment`
- `ResearchBudget`
- `ResearchQuery`
- `ResearchResult`
- `ResearchRound`
- `EvidenceGain`
- `SufficiencyAssessment`
- `MultiAgentResearchTrace`

Every artifact must carry:

- Investigation, parent claim, and component IDs.
- Role and round identifiers.
- Provider and model provenance.
- Queries and normalized query hashes.
- Candidate and evidence IDs.
- Canonical URLs and content hashes.
- Exact passage offsets.
- Evidence stance.
- Source type and authority indicators.
- Evidence-family or dependency information available at that stage.
- Cost, latency, token, query, fetch, and cache-use telemetry.
- Failure and unresolved reasons.

### 5.3 Permission boundaries

- Search roles can request searches through the common provider interface.
- Fetching always uses the existing safe fetcher.
- Retrieved page content is data, never instructions.
- Researchers may cite only evidence IDs created from retrieved and extracted
  material.
- The coordinator may merge evidence IDs but not edit evidence passages.
- The existing verdict stage sees only the approved consolidated packet.
- Model-proposed URLs are not evidence and must pass normal retrieval.

## 6. Execution stages

## Stage 4.0 — Baseline lock and experiment manifest

Status: **completed 27 July 2026**

### Work

- Add a Phase 4 experiment manifest referencing the exact Phase 3 dataset and
  artifacts.
- Record baseline metrics, provider modes, model settings, and artifact hashes.
- Define the three-claim development comparison set before experiments.
- Define primary Phase 4 success metrics and acceptable regressions.
- Add a command that verifies all referenced baseline files and hashes.

### Tests

- Reject a missing or changed baseline artifact.
- Reject dataset-version mismatch.
- Reject a comparison with different case IDs or scoring rules.

### Gate

The comparison manifest is machine-verifiable and the baseline cannot be
silently replaced.

Completion evidence:

- Manifest: `artifacts/evaluations/phase4-experiment-manifest-v1.json`
- Offline verifier:
  `claim-polygraph --no-hosted-model verify-phase4-manifest`
- Eight Phase 3 inputs are locked by SHA-256.
- Pilot cases were predeclared as CPNG-014, CPNG-016, and CPNG-020.
- Repository manifest verification: valid, eight artifacts checked.
- No network, search-provider, or model call was made.

### Expected paid usage

None.

## Stage 4.1 — Role contracts and deterministic router

Status: **completed 27 July 2026**

### Work

- Implement the typed contracts.
- Implement deterministic role selection:
  - Primary, general, and challenger are the default minimum team.
  - Academic is conditional on domain and evidence requirements.
  - Fact-check is conditional on claim characteristics.
- Represent each role as a policy over the existing provider interfaces.
- Add schema-versioned serialization.

### Tests

- Contract round trips.
- Invalid IDs, missing provenance, and unsupported roles fail validation.
- Simple claims do not activate irrelevant specialists.
- Scientific or causal cases activate academic research when required.
- Routing never exceeds the role budget.

### Gate

All routing behavior is testable without model or search calls.

Completion evidence:

- Schema-versioned role contracts and immutable research artifacts are defined
  in `src/claim_polygraph_ng/domain/research.py`.
- Role permissions are closed and exact; research assignments reject control
  roles and permission escalation.
- The deterministic router is defined in
  `src/claim_polygraph_ng/analysis/research_routing.py`.
- Primary-source, general-evidence, and challenger roles form the minimum team.
- Academic and fact-check roles require typed claim or requirement signals.
- Activation budgets defer specialists deterministically.
- Contract and routing tests pass without network, search, or model calls.

### Expected paid usage

None.

## Stage 4.2 — Shared execution, concurrency, and caching

Status: **completed 27 July 2026**

### Work

- Add an in-process async research executor with bounded concurrency.
- Reuse query results through normalized query keys.
- Reuse fetched pages through canonical URL/content hashes.
- Preserve deterministic output order regardless of completion order.
- Checkpoint assignment, result, and round completion using SQLite.
- Resume without repeating successful search, fetch, or model work.
- Make partial role failures visible without discarding successful work.

### Tests

- Concurrent roles cannot exceed the configured semaphore.
- Duplicate queries call the provider once.
- Canonically identical URLs fetch once.
- Interrupted rounds resume without repeated billable operations.
- Output ordering and consolidation are stable.
- Provider failure preserves typed partial results.

### Gate

Mock integration tests demonstrate concurrency, deduplication, and exact resume.

Completion evidence:

- `SharedResearchOperations` coalesces identical in-flight searches and fetches.
- Successful search and fetch operations are cached durably in SQLite.
- Search keys include provider, normalized query, research path, and result
  limit; fetch keys include provider and canonical URL.
- `ResearchExecutor` enforces an in-process concurrency semaphore.
- Results retain input assignment order regardless of task completion order.
- Every terminal assignment result is checkpointed and reused on resume.
- A role failure is stored visibly without discarding successful sibling work.
- Integration tests prove one provider call for simultaneous duplicate work and
  zero repeated worker, search, or fetch calls after resume.
- Full repository verification passes with no network, search, or model calls.

### Expected paid usage

None.

## Stage 4.3 — Evidence consolidation and independence-aware deduplication

Status: **completed 27 July 2026**

### Work

- Consolidate exact duplicate evidence by content hash and passage identity.
- Canonicalize URLs using existing rules.
- Detect near-duplicate passages with a deterministic threshold.
- Group known shared-origin evidence when metadata or attribution demonstrates
  dependency.
- Retain distinct stances and genuinely independent passages.
- Record why items were merged or grouped.
- Prevent evidence count inflation across roles.

This stage performs conservative, explainable grouping. Deep provenance graphs
and probabilistic source-family inference remain a later phase.

### Tests

- Same page found by three roles counts once.
- Syndicated or explicitly attributed copies do not count as independent.
- Similar but substantively different passages remain separate.
- Conflicting evidence is never merged away.
- Consolidation is invariant to role completion order.

### Gate

A fixed fixture suite shows no false source-count gain from adding researchers.

Completion evidence:

- Canonically equivalent source URLs resolve to one deterministic
  representative with an explicit merge decision.
- Exact normalized evidence duplicates with the same claim, stance, passage,
  and context resolve to one representative.
- Evidence with conflicting stances is never merged, even when passage text is
  identical.
- Near-duplicate passages, shared publishers, shared hosts, and explicit
  cross-citations affect evidence-family independence without deleting
  auditable passages.
- Every merge records representative ID, merged IDs, and deterministic reason.
- Consolidated sources, evidence, decisions, and families are invariant to role
  completion and input order.
- Fixture tests cover canonical duplicates, syndicated reporting, conflict
  preservation, orphaned references, and order invariance.
- Full repository verification passes without network, search, or model calls.

### Expected paid usage

None.

## Stage 4.4 — Sufficiency and diminishing-return control

Status: **completed 27 July 2026**

### Work

- Compute requirements per material component:
  - relevant evidence or explicit unresolved status;
  - challenge attempt;
  - primary source found or absence documented;
  - independent corroboration when realistically available;
  - temporal, numerical, definition, geography, and population compatibility.
- Compare each round with the prior consolidated packet.
- Count only material gains, such as:
  - a newly covered component;
  - a newly satisfied evidence requirement;
  - a genuinely independent evidence family;
  - a new contradiction or material qualification;
  - resolution of temporal, numerical, or definitional mismatch.
- Do not count duplicate URLs, paraphrased copies, or extra low-quality passages
  as gain.
- Stop on sufficiency, budget exhaustion, unresolvable status, or no gain.

### Tests

- Duplicate evidence triggers diminishing-return stopping.
- A missing material component routes only the needed role.
- Missing challenge evidence routes challenger once, not the whole team.
- Budget exhaustion stops before the next provider call.
- Unresolved status remains visible in the final packet.

### Gate

No fixture can enter an unbounded loop, and every termination has a typed
reason.

Completion evidence:

- Requirement satisfaction is computed deterministically from consolidated
  sources, evidence stances, evidence families, attempted roles, and resolved
  context records.
- Decision precedence is fixed: sufficient, human review, unresolvable, budget
  exhausted, diminishing return, then targeted continuation.
- Hard limits cover rounds, role activations, searches, fetched pages, model
  calls, and configured paid cost.
- Material gain counts only newly covered components, satisfied requirements,
  independent families, challenge evidence, or resolved context.
- Duplicate-only progress produces zero gain and stops another research round.
- Continuation activates only roles relevant to missing requirements.
- Tests cover sufficiency, primary-source gaps, independence gaps, challenge
  gaps, budget exhaustion, no-gain stopping, unresolved outcomes, human review,
  and duplicate-insensitive gain calculation.
- Full repository verification passes without network, search, or model calls.

### Expected paid usage

None.

## Stage 4.5 — Minimum multi-agent end-to-end workflow

Status: **completed 27 July 2026**

### Work

- Connect coordinator, primary, general, challenger, consolidation, sufficiency,
  and the existing Phase 3 verdict/citation stages.
- Preserve Phase 3 context, component, aggregation, and checkpoint invariants.
- Add CLI flags for multi-agent mode and budgets.
- Keep Phase 3 mode available as the control.
- Produce a readable trace showing role activations, shared work, evidence gain,
  stopping reason, cost, and latency.

### Tests

- End-to-end mock investigations for supported, contradicted, mixed,
  misleading, and unresolved outcomes.
- No researcher can introduce an evidence ID absent from storage.
- Verdict and report citations resolve to the consolidated evidence packet.
- Restart at every new checkpoint.
- Phase 3 CLI behavior remains backward compatible.

### Gate

The full workflow passes unit, contract, integration, security, formatting, and
coverage checks without live providers.

Completion evidence:

- The coordinator connects deterministic routing, bounded concurrent
  execution, durable operation caching, evidence storage, consolidation,
  independence analysis, sufficiency assessment, verdict construction, and
  citation audit.
- Durable coordinator checkpoints exist at planned, researched, consolidated,
  assessed, and complete stages.
- Completed workflows reload without repeating worker or provider calls.
- Worker results must reference stored source and evidence records before
  consolidation; missing records fail closed.
- Judgment receives only the consolidated packet and cites only stored evidence
  IDs.
- Empty evidence produces `unverifiable`, a visible failed citation audit, and
  required human review.
- A readable multi-agent trace reports roles, calls, evidence yield,
  consolidation, sufficiency, verdict, and citation support.
- Phase 3 remains unchanged and continues to pass its regression tests.
- Multi-agent mode remains programmatic until the controlled pilot validates
  it; it is intentionally not exposed as the default CLI workflow yet.
- Full repository verification passes without network, search, or model calls.

### Expected paid usage

None.

## Stage 4.6 — Three-claim controlled pilot

Status: **completed 27 July 2026; promotion gate not met**

### Work

- Select three difficult CPNG-011–020 claims from the locked manifest, covering
  different failure modes.
- Reuse the frozen Phase 3 retrieval snapshot first.
- Run the Phase 3 control and Phase 4 workflow with identical evidence access
  and model policy.
- If testing new live searches, freeze one shared candidate snapshot before
  judging either system.
- Inspect the research trace for duplicate work, invented evidence,
  unnecessary specialist activation, and premature/late stopping.

### Metrics

- Material evidence-requirement coverage.
- Primary-source coverage.
- Independent evidence-family count.
- Contradiction/qualification discovery.
- Verdict correctness.
- Citation correctness.
- Unsupported-assertion rate.
- Completion and failure rate.
- Model/search/fetch calls, cost, latency, and cache reuse.

### Pilot gate

Proceed to the ten-claim evaluation only if:

- No provenance, citation, rights, resume, or budget-control regression occurs.
- At least one quality metric improves on at least two of the three cases.
- No verdict-correctness regression is introduced.
- Mean cost is no more than 2.0 times the matched Phase 3 control.
- Median latency is no more than 2.5 times the control.

If the pilot fails, revise one identified mechanism and repeat only the affected
cases once. If it still fails, retain Phase 3 as the production workflow and
close Phase 4 as a negative experimental result.

### Expected paid usage

One three-claim run per system; at most one bounded affected-case rerun.

### Completed zero-cost preflight

- The locked cases and matched Phase 3 controls validate successfully.
- Control cost for CPNG-014, CPNG-016, and CPNG-020 is **$0.05665305**.
- The predeclared 2x Phase 4 ceiling is **$0.11330610**.
- Control median latency is **36.178653 seconds**.
- The predeclared 2.5x median-latency ceiling is **90.446632 seconds**.
- Six reviewed material components imply 22 initial role activations under the
  current deterministic routing policy.
- The absolute preflight envelope is 44 searches and 72 fetched pages; these
  are safety ceilings, not targets.
- Structural dry run: 3/3 completed, 11 fixture searches, zero fetches, zero
  model calls, zero cost, and 3/3 grounded citation packets.
- No PDF was fetched.
- `paid_calls_authorized` remains `false`.

Artifacts:

- `artifacts/evaluations/phase4-pilot-preflight.json`
- `artifacts/evaluations/phase4-pilot-dry-run.json`

Preflight limitation:

- A causal claim activates the academic specialist in addition to the minimum
  three-role team. With the current four-activation component limit, this
  consumes the full activation budget in round one and disallows a targeted
  second round. This is safe and bounded but must be accepted or deliberately
  revised before the paid pilot; the budget will not be raised implicitly.

## Stage 4.7 — Conditional specialist roles

Status: **completed 27 July 2026; specialists remain conditional**

This stage runs only if pilot traces show a specific evidence gap that the
minimum team cannot address.

### Academic researcher

- Add source-specific query policy and scholarly metadata capture.
- Do not treat abstracts as full-paper evidence beyond their actual content.
- Respect access and copyright restrictions.

### Fact-check researcher

- Use professional fact checks as leads and secondary analysis.
- Trace their citations to originals when available.
- Avoid counting the fact-check and its cited original as independent support
  when the former merely repeats the latter.

### Gate

Each specialist must improve a predefined metric on the cases that triggered
it. Otherwise remove or disable the role by default.

### Expected paid usage

Affected pilot cases only.

## Stage 4.8 — Declared ten-claim comparison

Status: **skipped by the failed three-claim promotion gate**

### Work

- Evaluate CPNG-011–020 with the frozen dataset and scoring rules.
- Run one declared Phase 4 evaluation.
- Run a second only for stability, using the same declared configuration.
- Produce per-case deltas and aggregate metrics against both Phase 3 runs.
- Separate retrieval gain from verdict-model gain.
- Report failures and negative findings without patching expected labels or
  reviewed URLs into production prompts or queries.

### Primary success condition

Phase 4 must show a material improvement in at least one:

- Evidence-requirement coverage.
- Primary-source coverage.
- Independent-source coverage.
- Contradiction/qualification recall.
- Verdict accuracy or macro-F1.

### Required non-regressions

- Completion at least 90%.
- Material-component coverage at least 90%.
- Full citation support at least 95%.
- Unsupported-assertion rate no worse than Phase 3.
- Exact repeated-label stability at least 90%.
- No rights, security, provenance, resume, or budget-control gate failure.

### Efficiency condition

- Report absolute and relative cost and latency.
- Default promotion target: quality gain with mean cost no more than 2.0 times
  and median latency no more than 2.5 times Phase 3.
- A larger increase requires a clearly documented, high-value quality gain and
  explicit user approval; it is not automatically promoted.

### Promotion rule

Promote Phase 4 as the default research workflow only when the success,
non-regression, and efficiency conditions all pass. Otherwise:

- Keep Phase 3 as default.
- Preserve Phase 4 as an optional experimental mode.
- Publish the negative or mixed result.
- Do not add production infrastructure to compensate for a quality failure.

## Stage 4.9 — Closure and documentation

Status: **completed 27 July 2026**

### Deliverables

- Phase 4 completion report.
- Machine-readable gate audit.
- Frozen experiment manifest.
- Role and permission documentation.
- Cost/latency and quality comparison.
- Per-case delta table.
- Stability report.
- Limitations and failed-experiment record.
- ADR documenting whether multi-agent mode is promoted.
- Updated project roadmap.

### Final verification

- Full tests pass.
- Coverage remains at least 85%.
- Ruff lint and formatting pass.
- All benchmark and evaluation artifacts validate against typed schemas.
- No unapproved PDF was downloaded.
- All reported citations and metrics resolve to stored artifacts.

## 7. Metric definitions

To avoid optimizing vague “more evidence” claims:

| Metric | Definition |
|---|---|
| Requirement coverage | Satisfied reviewed evidence requirements divided by all material requirements |
| Primary-source coverage | Components with suitable primary evidence, or documented unavailability, divided by applicable components |
| Challenge recall | Reviewed contradictions or qualifications recovered divided by expected challenge evidence |
| Independent coverage | Components with the required number of genuinely independent evidence families |
| Unsupported assertion rate | Material report assertions lacking an entailing stored passage |
| Search duplication | Repeated normalized searches divided by requested searches |
| Fetch duplication | Repeated canonical fetches divided by requested fetches |
| Evidence yield | New material gains divided by completed role activations |
| Cost efficiency | Quality-metric gain divided by incremental cost over Phase 3 |
| Latency efficiency | Quality-metric gain divided by incremental wall-clock time |

Metric code must be shared between control and treatment runs.

## 8. Test strategy

### Unit tests

- Routing, permissions, budgets, gain calculation, stopping, deduplication, and
  deterministic ordering.

### Contract tests

- Role input/output validation, resolvable IDs, schema versioning, and provider
  provenance.

### Integration tests

- Concurrent bounded execution, caching, partial failure, checkpointing, resume,
  consolidation, sufficiency routing, and final evidence packet creation.

### Security tests

- Retrieved prompt injection cannot alter role, budget, or permissions.
- Model-proposed private URLs remain blocked by the safe fetcher.
- Secrets are absent from traces.
- Oversized or unsupported content fails safely.

### Golden tests

- Challenger must be attempted.
- Duplicates cannot inflate independence.
- Missing material evidence remains unresolved.
- No-gain rounds stop.
- Budget limits terminate before excess calls.
- Verdict citations resolve only to approved evidence.

## 9. Explicitly deferred work

The following are not required for Phase 4:

- LangGraph migration.
- PostgreSQL, Redis, pgvector, or distributed queues.
- Multiple model-serving runtimes.
- New frontend or API surface.
- Deep probabilistic provenance graphs.
- Large external benchmark expansion.
- A 100–200 claim human-review set.
- Fine-tuning.
- Autonomous publication.

They may be reconsidered only after Phase 4 identifies a measured need.

## 10. Stop-work conditions

Pause implementation and diagnose before spending on declared runs if:

- Deterministic/mock tests do not pass.
- Resume repeats paid operations.
- Researchers can cite unstored evidence.
- Evidence duplication inflates independence.
- Cost cannot be estimated before a call.
- The workflow lacks a hard termination path.
- Control and treatment use different datasets, evidence access, or scoring.
- Live retrieval artifacts are incomplete.
- Rights status is unclear for a document.

## 11. Efficient order of implementation

1. Lock baseline and metrics.
2. Add contracts and deterministic routing.
3. Add shared executor, caching, and resume.
4. Add consolidation and independence-aware deduplication.
5. Add deterministic sufficiency and stopping.
6. Connect the minimum four-role workflow.
7. Pass all offline tests.
8. Run the three-claim pilot.
9. Add academic or fact-check roles only if pilot evidence justifies them.
10. Run the declared ten-claim comparison.
11. Audit gates and close the phase.

## 12. Definition of done

Phase 4 is complete when:

- Every activated role uses typed inputs and outputs.
- Compatible research paths run concurrently within hard bounds.
- Shared searches, pages, and evidence are deduplicated.
- Evidence-sufficiency and diminishing-return decisions are auditable.
- Resume does not repeat completed paid work.
- Researchers cannot invent or bypass retrieval for evidence.
- Phase 3 and Phase 4 are compared on identical reviewed cases and metrics.
- Quality, cost, latency, stability, rights, and safety gates are published.
- A machine-readable decision either promotes multi-agent mode or retains
  Phase 3 as the default.

Completion does not require a positive result. A reliable finding that the
multi-agent workflow adds cost without material quality benefit is a valid and
useful Phase 4 outcome.
