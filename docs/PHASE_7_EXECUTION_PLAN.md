# Phase 7 execution plan

Date: 28 July 2026

Status: **completed 28 July 2026; LangGraph promotion approved**

Theme: visible LangGraph investigation and accountable human review

## 1. Outcome

Phase 7 will deliver a locally usable web console where a user can submit a
claim, observe its LangGraph execution path, inspect evidence and verification
artifacts, resolve a human-review interruption, resume from a durable
checkpoint, and export the final citation-grounded report.

The visible interface is not a substitute for workflow correctness. The
existing evidence-grounded service remains authoritative until the LangGraph
implementation passes equivalence, recovery, and no-duplicate-work gates.

## 2. Scope

Included:

- a LangGraph state contract and bounded graph;
- SQLite-backed checkpointing;
- deterministic review routing;
- sentence-level citation assurance;
- durable pause and resume;
- FastAPI endpoints and progress events;
- a responsive investigation and review console;
- immutable review decisions and revision history;
- fixture-first evaluation and a small final live demonstration.

Deferred:

- PostgreSQL, Redis, distributed workers, and Kubernetes;
- organization authentication and role provisioning;
- collaborative simultaneous editing;
- hosted production data;
- rewriting the validated retrieval and verdict components;
- broad model experiments or a new benchmark.

## 3. Product surfaces

### Investigation dashboard

Shows claim, status, current graph node, verdict, readiness, citation support,
cost, and review state.

### Live graph

Shows completed, active, interrupted, waiting, failed, and resumed nodes. Each
transition exposes its reason, checkpoint identity, and whether work was reused.

### Evidence workspace

Shows exact passages, stance, source quality, evidence family, independence,
numerical and temporal checks, argument ledger, and challenger findings.

### Citation assurance

Maps each material report assertion to exact passages and labels it supported,
partially supported, unsupported, or contradictory.

### Human-review console

Shows the routing reason and allows approve, revise, request-more-evidence, or
reject. It records reviewer identity, rationale, timestamp, prior state, and
the next graph route. Benchmark-truth changes still require a distinct
approver.

## 4. LangGraph boundary

The initial graph wraps proven services rather than reimplementing them:

```text
START
  -> normalize
  -> research
  -> consolidate
  -> verify_context
  -> build_argument_ledger
  -> draft_verdict
  -> audit_citations
  -> assess_readiness
  -> route_review
       -> finalize -> END
       -> interrupt_for_review
            -> approve -> finalize -> END
            -> revise -> audit_citations -> assess_readiness
            -> request_evidence -> research
            -> reject -> END
```

All cycles have declared iteration, retrieval, model-call, token, time, and
cost limits. A node can consume only typed state and approved evidence IDs.

## 5. State and persistence

`InvestigationGraphState` will contain versioned identifiers and references,
not duplicated unbounded content:

- investigation and graph-run IDs;
- normalized and component claims;
- evidence packet and artifact references;
- verification, ledger, verdict, citation-audit, and readiness references;
- review request and decision references;
- current node, route reasons, counters, limitations, and errors;
- provider-operation cache keys;
- schema and workflow versions.

SQLite remains the first checkpoint store. Restart tests must prove that a
paused run reloads exactly once and does not repeat completed retrieval or model
operations.

## 6. Stages

### Stage 7.0 — Plan and static product prototype

Status: **completed 28 July 2026**

Deliverables:

- this locked execution plan;
- responsive static review console under `dashboard/`;
- visible graph, evidence packet, citation status, and review interruption;
- simulated approve-and-resume interaction;
- fixture content derived from reviewed CPNG cases.

Exit gate: the prototype builds, renders without backend services, and exposes
the complete intended review journey without claiming persistence.

### Stage 7.1 — Contracts and LangGraph skeleton

Status: **completed 28 July 2026**

Define typed graph state, node inputs/outputs, commands, route decisions,
interrupt payloads, error taxonomy, and budgets. Add LangGraph behind an
optional feature flag and implement a zero-cost fixture graph.

Exit gate: the fixture graph produces the same authoritative verdict and
artifacts as the current service, with no hidden evidence or model access.

**Recorded result**

LangGraph `1.2.9` is installed behind the isolated
`FixtureLangGraphWorkflow`, which is disabled by default and is not referenced
by `InvestigationService`. The typed boundary defines:

- graph nodes, routes, statuses, and route decisions;
- a zero-cost execution budget;
- an approved-evidence fixture request; and
- a validated result that rejects out-of-packet evidence, provider usage,
  repeated nodes, and inconsistent status/route combinations.

The compiled `StateGraph` executes normalization, fixture research,
consolidation, verification, argument-ledger, provisional-verdict,
citation-audit, readiness, and review-routing nodes. It either finalizes or
ends at a bounded review placeholder. Actual durable `interrupt` and `Command`
resume behavior remains Stage 7.2.

The reproducible CPNG-005 fixture preserved the authoritative `contradicted`
verdict, consumed exactly three approved evidence IDs, routed to human review,
completed ten unique nodes, and made zero model calls, search calls, network
calls, or paid operations. Its machine-readable output is
`artifacts/evaluations/phase7-stage7.1-fixture-graph-v1.json`.

Eight focused contract and integration tests pass, including explicit
feature-disablement, authoritative-service isolation, evidence containment,
verdict equivalence, review routing, and step-budget enforcement.

Full repository verification completed with 347 passing tests, 86.49%
coverage, clean Ruff checks, and no broken Python requirements. No model,
search, retrieval, page-fetch, or PDF operation was used.

### Stage 7.2 — Durable checkpoints and interruption

Status: **completed 28 July 2026**

Add SQLite checkpointer integration, versioned state serialization, human
interrupts, restart recovery, idempotency, and operation-cache reuse.

Exit gate: kill/restart/resume tests show zero repeated retrieval/model calls
and one immutable transition per accepted decision.

**Recorded result**

The optional durable fixture graph now uses LangGraph's official
`langgraph-checkpoint-sqlite` `3.1.0` saver with a file-backed SQLite database.
Checkpoint deserialization uses an explicit empty MessagePack module allowlist;
durable state is restricted to JSON-safe primitives.

The review node calls the real `interrupt()` primitive and exposes a typed,
JSON-safe payload containing the thread ID, claim, provisional verdict,
approved evidence IDs, route reason, and allowed decisions. Resume uses
`Command(resume=...)` with a validated `ReviewDecision`.

Supported decisions are approve, revise, request more evidence, and reject.
The accepted decision ID and reviewer identity are persisted. Replaying the
same decision returns the existing terminal snapshot without graph execution;
a different second decision is rejected.

The deterministic restart demonstration:

- interrupted and checkpointed the CPNG-005 fixture;
- closed the first SQLite connection;
- reconstructed an identical paused state through a new workflow instance;
- resumed to the preserved `contradicted` verdict;
- executed every pre-interrupt node exactly once;
- applied the review and finalize nodes exactly once;
- returned the identical result for an idempotent decision replay; and
- made zero model, search, network, retrieval, page-fetch, or PDF calls.

The machine-readable output is
`artifacts/evaluations/phase7-stage7.2-durable-resume-v1.json`.

Eight focused contract and integration tests cover real interruption, strict
checkpoint reconstruction, restart/resume, same-decision replay, conflicting
decision rejection, revision, more-evidence routing, disabled/unknown/duplicate
thread guards, and step-budget enforcement.

Full repository verification completed with 355 passing tests, 86.60%
coverage, clean Ruff checks, and no broken Python requirements.

### Stage 7.3 — Citation assurance and review routing

Status: **completed 28 July 2026**

Implement assertion extraction from structured report content, exact
assertion-to-passage links, entailment status, unsupported-assertion detection,
and deterministic high-risk/readiness/disagreement routing.

Exit gate: frozen fixtures meet 100% critical-route recall, at least 95%
citation classification accuracy, and zero unsupported assertions marked
supported.

**Recorded result**

Stage 7.3 adds a deterministic companion to the existing model-generated
`SentenceAudit`; it does not silently replace that artifact. A
`StructuredReportAssertion` declares the protected sentence, approved citation
IDs, material/critical status, expected evidence stance, and exact required
phrases. The assurance engine links exact stored passages and fails closed when
semantic support cannot be established deterministically.

Finding states are supported, partial, unsupported, contradictory, and
out-of-packet. A supported finding requires:

- at least one supplied citation;
- every citation to remain inside the approved evidence packet;
- every cited evidence record to be present;
- every required phrase to occur in an exact cited passage; and
- at least one cited passage with the declared stance.

The deterministic router consumes only typed diagnostics. It routes on
critical or material citation failure, out-of-packet citations, unresolved
critical verification, readiness requiring review, uncertain provenance,
observational-policy disagreement, blocking challenges, an existing verdict
review request, and high/critical risk. It returns ordered triggers, priority,
and a reason; it cannot change a verdict.

The optional durable graph accepts this routing decision as the authoritative
review/no-review input for the fixture. A routing decision can therefore cause
a real SQLite-backed LangGraph interruption even when the fixture's manual
review flag is false.

The locked ten-case fixture covers full support, missing citations,
out-of-packet citations, contradictory stance, partial phrase support,
high-risk routing, readiness escalation, policy disagreement, provenance
uncertainty, and a clean qualified case. Results:

- citation classification accuracy: **100%**;
- critical-review route recall: **100%**;
- overall route accuracy: **100%**;
- unsupported assertions marked supported: **0**; and
- model, search, network, retrieval, page-fetch, and PDF calls: **0**.

The frozen input and output are:

- `benchmarks/phase7_citation_routing_v1.json`; and
- `artifacts/evaluations/phase7-stage7.3-assurance-routing-v1.json`.

Full repository verification completed with 363 passing tests, 86.73%
coverage, clean Ruff checks, and no broken Python requirements.

### Stage 7.4 — Review domain and persistence

Implement `ReviewRequest`, `ReviewFinding`, `ReviewerDecision`,
`ApprovalRecord`, `VerdictRevision`, and `ReviewAuditTrail`. Enforce distinct
approval when authoritative benchmark truth changes.

Exit gate: decisions are append-only, attributable, replayable, and cannot
silently overwrite original verdicts or annotations.

Status: **completed on 28 July 2026**.

The implementation adds strict review, finding, decision, approval, revision,
and audit-event contracts plus an independent SQLite review ledger. Every
write appends its entity and a canonical SHA-256 hash-chain event in one
transaction. Database triggers reject `UPDATE` and `DELETE` operations on all
ledger tables. Expected-sequence checks reject stale writers, exact decision
replays are idempotent, and conflicting or duplicate decisions are rejected.

Authoritative verdict and benchmark revisions are new records that retain the
original verdict identifier and label. They require an approving record tied
to the proposed revision, and the approver must differ from the reviewer
case-insensitively. Reopening the database reconstructs the complete typed
history and verifies its audit chain without a model, search, retrieval,
network, page-fetch, or PDF call.

### Stage 7.5 — API and progress stream

Add FastAPI endpoints for investigations, graph state, evidence, citation
audit, review queue, decisions, resume, reports, and a Server-Sent Events
progress stream.

Exit gate: contract and integration tests cover success, stale decision,
duplicate submission, unauthorized transition placeholder, provider failure,
restart, and no-results behavior.

Status: **completed on 28 July 2026**.

FastAPI now exposes typed health, investigation collection/create/detail,
evidence, JSON/Markdown report, durable graph start/state, review
collection/history, decision, approval, verdict-revision, and persisted trace
event endpoints. The event endpoint uses Server-Sent Events with event IDs,
typed event names, replay from an `after` cursor, terminal completion, and
keep-alives while following an active investigation.

The HTTP layer receives repositories and the investigation runner through an
explicit dependency container. It therefore reuses the authoritative
investigation service and deterministic fixture graph rather than duplicating
their business logic. Stale decisions and duplicate graph starts return 409,
missing resources return 404, incomplete reports return 409, invalid inputs
return 422, provider failures return a sanitized 502, and the temporary
identity-binding boundary returns 403 when the actor header does not match the
review record. Durable decisions remain idempotent across API retries and
process restarts.

The `claim-polygraph-api` command runs a local zero-cost development server on
`127.0.0.1:8000` using deterministic providers and ignored SQLite files under
`data/`. Production provider and authentication wiring remain explicit future
deployment concerns.

### Stage 7.6 — Connected dashboard

Connect the Stage 7.0 console to the API. Add investigation list and creation,
live node updates, evidence/citation drill-down, review actions, failure states,
responsive behavior, keyboard access, and empty/loading states.

Exit gate: all visible values come from typed API payloads; the browser can
complete the fixture review journey without direct database access.

Status: **completed on 28 July 2026**.

The evidence console now submits claims through the authoritative
investigation endpoint, lists and selects persisted investigations, joins
evidence to stored source metadata, renders citation-audit and immutable
review-history records, exports the Markdown report, starts the durable
LangGraph workflow, follows its persisted node/state SSE stream, and submits
approve, revise, request-more-evidence, or reject decisions with the reviewer
identity boundary required by the API.

Static evidence and verdict fixtures were removed. The dashboard shows typed
API values or explicit loading, empty, disconnected, and error states. The API
address is configurable and retained only in local browser storage. The local
API allows the expected development and deployed dashboard origins; no direct
database access or paid provider call was added to the frontend.

### Stage 7.7 — End-to-end recovery demonstration

Run fixture-backed journeys for automatic completion, review approval, verdict
revision, request-more-evidence, rejection, provider failure, process restart,
and idempotent resume.

Exit gate: every path yields the expected state, audit trail, and report with
zero unintended repeated operations.

Status: **completed on 28 July 2026**.

The deterministic recovery harness exercises eight isolated journeys through
the real ASGI API, authoritative investigation service, SQLite repositories,
LangGraph checkpointer, and append-only review ledger: automatic completion,
approval, an approved verdict revision, request-more-evidence, rejection,
sanitized provider failure, application restart, and identical decision
replay. Restart uses a newly constructed application over the existing
databases; revision requires a distinct approver and retains the original
verdict; provider failure is followed by a successful health request.

All 8 journeys passed, every applicable audit chain verified, checkpoint
reconstruction matched the paused state, and the operation counters recorded
zero unintended repetitions. The frozen result is
`artifacts/evaluations/phase7-stage7.7-recovery-v1.json`. The run made zero
external model, search, network, page-fetch, or PDF calls and incurred no
provider cost.

### Stage 7.8 — Frozen evaluation

Replay the reviewed 20-claim set from saved packets. Compare the current
workflow and LangGraph wrapper for verdict/artifact equivalence, review-routing
recall, citation assurance, recovery, latency, and duplicate work.

Exit gate: zero verdict regressions, zero artifact loss, 100% required-review
recall, at least 95% sentence citation accuracy, zero duplicate paid calls,
and no more than 20% deterministic latency overhead.

Status: **completed on 28 July 2026**.

The frozen evaluator replays CPNG-001 through CPNG-020 from the reviewed
version-5 benchmark and the Stage 6 authoritative baseline through the
zero-cost durable LangGraph wrapper. It compares the saved authoritative
verdict, a canonical reviewed-packet hash, approved evidence identities,
saved citation-audit outcome, required-review route, operation counters, and
measured local wrapper latency for every case.

All promotion gates passed: 100% verdict equivalence, 100% reviewed-packet and
approved-evidence preservation, 100% required-review recall, 100% preservation
of the 20 authoritative citation-audit outcomes, zero duplicate deterministic
or paid operations, zero new verdict regressions, and approximately 0.10%
median deterministic latency overhead against the saved 29.377-second
authoritative median.

The result does not claim that the authoritative baseline itself is perfect.
Both paths retain its documented CPNG-006 and CPNG-019 reviewed-label
mismatches, so reviewed-label accuracy remains 90%; the wrapper adds no new
regression. All 20 packets require review, which establishes recall but not
over-routing specificity. The aggregate baseline also stores citation-full
outcomes rather than sentence text, so this gate verifies preservation of
those sentence-audit results rather than recomputing entailment.

The frozen output is
`artifacts/evaluations/phase7-stage7.8-frozen-comparison-v1.json`. No model,
search, retrieval, page-fetch, network, or PDF operation was performed.

### Stage 7.9 — Targeted human calibration and closure

Present only routing disagreements, citation-audit errors, and changed
authoritative outputs. Freeze hashes, run quality/security/accessibility
checks, write the ADR and completion report, and decide whether LangGraph
becomes the default orchestrator.

Exit gate: every gate is passed, failed, or explicitly waived with a named
approver and rationale. A failed LangGraph promotion retains the current
workflow and does not block delivery of diagnostic UI work.

Status: **engineering complete; one human approval gate remains pending**.

The targeted selector found no new routing disagreement, citation-audit error,
or changed authoritative output, so no CPNG case requires reannotation. The
known CPNG-006 and CPNG-019 baseline disagreements remain disclosed and
unchanged. Security checks cover provider-error sanitization, non-wildcard
CORS, actor identity, stale writes, SSRF-safe fetching, and provider secret
handling. Dashboard checks cover its production build, lint, document
language, landmarks, heading, explicit labels, named buttons, and keyboard
tab-order structure.

Fifteen release artifacts are frozen in the hash-verified Phase 7 manifest.
ADR 0014 proposes LangGraph as the default orchestrator while retaining the
existing investigation service as verdict authority and the direct workflow
as rollback. Codex has not invented a human decision: ADR 0014, the completion
report, and the closure audit explicitly record promotion approval as pending.
Until a named approver and date are supplied, Phase 7 is engineering-complete
but not finally closed, and LangGraph remains opt-in.

## 7. Cost controls

- Use mock providers and frozen evidence through Stage 7.7.
- Do not retrieve or call a model for UI changes.
- Reuse Phase 6 artifacts and reviewed packets.
- Cache provider operations by versioned input hash.
- Permit no paid call without a predeclared hypothesis and ceiling.
- Use at most three representative live cases before any broader run.
- Stop immediately on a verdict regression, citation leakage, repeated paid
  operation, or invalid checkpoint reconstruction.

## 8. Test strategy

- Contract tests for every state and command.
- Node tests using typed fixtures.
- Graph route and iteration-limit tests.
- SQLite migration, checkpoint, restart, and concurrency tests.
- API schema, stale-write, and duplicate-decision tests.
- Dashboard build and rendered-content tests.
- End-to-end fixture journeys.
- Frozen 20-claim equivalence and routing evaluation.
- Safe-fetcher, secret-handling, dependency, and accessibility checks.

## 9. Stage 7.0 prototype limitations

The dashboard is intentionally static. Its resume action changes local
interface state only; it does not yet invoke LangGraph, persist a reviewer
decision, or contact the Python backend. Those capabilities begin in Stage
7.1 and are promoted only after their respective gates pass.
