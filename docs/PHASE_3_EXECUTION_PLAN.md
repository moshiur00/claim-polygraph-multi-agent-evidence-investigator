# Phase 3 execution plan

Status: **completed on 27 July 2026**

Start date: 27 July 2026

Theme: complex claims, retrieval robustness, and resumable typed workflow state

## Purpose

Delivery Phase 3 implements the next capability in the long-term roadmap:
selective complex-claim decomposition and durable workflow state. Phases 1 and
2 proved the evidence pipeline on ten reviewed, predominantly atomic claims.
This phase must prove that the system can preserve context across material
subclaims, cover every component, aggregate subclaim verdicts without hiding
uncertainty, and resume interrupted work without duplicate provider calls.

The phase does not introduce multi-agent execution. It establishes the typed
contracts and single-coordinator baseline against which multi-agent research
must later demonstrate an improvement.

## Scope

### 1. Selective decomposition

- Add a check-worthiness and complexity assessment.
- Preserve the submitted parent claim verbatim.
- Decompose only independently checkable material assertions.
- Preserve dates, geography, quantities, definitions, attribution, comparison
  groups, causal direction, and parent identity.
- Reject empty, duplicate, circular, or context-losing decompositions.
- Keep already-atomic claims as one material component.

### 2. Component investigation and coverage

- Build one bounded investigation plan and evidence packet per component.
- Track planned, completed, supported, unresolved, and failed components.
- Require explicit unresolved reasons when evidence is insufficient.
- Prevent workflow completion when a material component has disappeared.
- Retain provenance from every conclusion to its component and parent.

### 3. Verdict aggregation

- Add deterministic aggregation constraints around the model-produced parent
  verdict.
- Distinguish `supported`, `mostly_supported`, `mixed`, `misleading`,
  `contradicted`, `unsupported`, and `unverifiable`.
- Never allow a definitive parent verdict to conceal a material unresolved or
  failed component.
- Audit the parent explanation against the union of cited component evidence.

### 4. Durable resume

- Persist typed workflow checkpoints in SQLite.
- Make completed stages idempotent.
- Resume from the latest valid checkpoint by investigation ID.
- Do not repeat successful search, fetch, or model calls during resume.
- Detect corrupt or contract-incompatible checkpoints and fail visibly.
- Test interruption after decomposition, planning, research, judgment, and
  citation audit.

### 5. Retrieval robustness

- Generate generic research-path queries from each component and its retained
  parent context.
- Improve dated dataset and primary-source discovery without benchmark URL
  hints.
- Preserve cross-path URL and content deduplication.
- Measure candidate, page, passage, source-family, and component coverage.
- Keep PDF retrieval opt-in by exact approved host and retain bounded passages
  only.

### 6. Benchmark expansion

- Prepare CPNG-011 through CPNG-020 as a complex-claim evaluation batch.
- Ensure at least five cases require genuine multi-component decomposition.
- Use AI only for transparent provisional annotation and critique.
- Require annotation by Md Moshiur Rahman and distinct approval by
  Md Rashedul Islam before cases contribute to accuracy.
- Promote the dataset version only after both human passes.

## Blocking exit gates

| Gate | Required result |
|---|---:|
| Human-reviewed benchmark | CPNG-001 through CPNG-020 reviewed; distinct approval |
| Complex-case representation | at least 5 reviewed cases with 2+ material components |
| Decomposition validity | 100% parent linkage and context-contract validity |
| Material-component coverage | at least 90% completed or explicitly unresolved |
| Live query completion | at least 90%; no silently accepted empty query |
| Cases with a live candidate | at least 90% |
| Combined reviewed-passage recall | at least 80% overall |
| First-ten retrieval regression | not below Phase 2 combined recall by more than 3 points |
| End-to-end completion | at least 90% in each of two declared runs |
| Verdict accuracy | at least 85% in each declared run |
| Full parent citation support | at least 95% in each declared run |
| Exact repeated-label stability | at least 90% |
| Resume correctness | all declared interruption points resume without duplicate completed calls |
| Estimated model cost | at most $0.02 per completed component on average |
| Rights compliance | zero unapproved PDF downloads or full-page persistence |
| Automated verification | all tests, lint, and formatting pass; coverage at least 85% |

With twenty cases, these results remain a development benchmark and not an
estimate of general real-world accuracy.

## Stop and review conditions

Pause and review the design if:

- decomposition loses a material qualifier in any reviewed case;
- parent aggregation produces a definitive verdict while a central component
  is unresolved;
- the same resume/idempotency defect appears at three interruption points;
- retrieval improvement requires reviewed URLs or excerpts in production
  queries;
- mean model cost exceeds the gate after one bounded optimization;
- source access would require unclear or unapproved copying rights.

## Infrastructure decision

Use SQLite and explicit typed orchestration first. Introduce LangGraph only if
the checkpoint implementation cannot reliably express branching, review
interrupts, or recovery. PostgreSQL, Redis, pgvector, the multi-agent
coordinator, and the production frontend remain out of scope for this phase.

## Execution order

1. Add and test decomposition, coverage, aggregation, and checkpoint contracts.
2. Integrate them with a backwards-compatible complex investigation command.
3. Add interruption/resume and retrieval regression tests.
4. Prepare provisional CPNG-011 through CPNG-020 packets.
5. Pause for genuine annotation and distinct approval.
6. Capture the twenty-claim live retrieval snapshot.
7. Run staged retrieval evaluation and two declared end-to-end runs.
8. Fix only bounded, generic defects; preserve diagnostic runs.
9. Run the rights and automated-verification gates.
10. Publish the Phase 3 completion report and the multi-agent decision.
