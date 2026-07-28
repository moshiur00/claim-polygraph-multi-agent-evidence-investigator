# Phase 8 Stage 8.6 completion report

Date: 28 July 2026

Status: Complete

## Outcome

The promoted LangGraph research subgraph now runs a bounded evidence-sufficiency
control loop. After every research round it consolidates candidate evidence,
recomputes material progress, evaluates every declared requirement and either
stops or dispatches only the role needed for a named gap.

The loop remains authority-isolated: candidate evidence can trigger human
review, but it cannot approve evidence or change the `InvestigationService`
verdict. Direct orchestration remains the rollback path.

## Deterministic control loop

1. Persist the initial minimum-team assignments before dispatch.
2. Execute only unfinished assignments and persist each terminal result.
3. Consolidate all stored candidate sources and evidence.
4. Compute duplicate-resistant progress for component coverage, satisfied
   requirements, independent families and challenge evidence.
5. Persist an immutable round audit containing assignments, results, gain,
   cumulative consumption, the sufficiency decision and routing rationale.
6. Stop on sufficiency, a hard budget, zero material gain, an unresolvable gap
   or explicit human-review requirement.
7. Otherwise dispatch only roles mapped to the missing requirement IDs.
8. On every non-sufficient terminal outcome, provide a deterministic
   human-review escalation reason.

## Hard bounds

The controller admits no further round after reaching the configured limits
for rounds, role activations, search calls, fetched pages, model calls, total
tokens, cumulative role duration or estimated cost. Role concurrency, query
count and candidates per query remain bounded by assignment contracts.

A zero model-call, token or monetary limit denotes a zero-paid-operation
development path; it no longer incorrectly marks a zero-use run as exhausted.

## Durable recovery and audit

SQLite checkpoints now retain all assignments and results across rounds, each
round audit, the latest assessment, cumulative consumption, duplicate counts
and the final terminal stage. Reopening a completed investigation returns the
same report without executing another role.

Every continuation therefore answers:

- which requirements were missing;
- which role was activated;
- which assignments and results belonged to the round;
- what material evidence gain occurred;
- which budget was consumed; and
- why the controller continued or stopped.

## Verification

- A missing challenge requirement activated only the challenger in round two.
- New qualifying evidence in that targeted round reached `sufficient`.
- Repeated supporting evidence produced zero material gain and stopped with
  `stop_diminishing_return`.
- Non-sufficient terminal states produced human-review escalation.
- A one-round budget stopped with `stop_budget_exhausted`.
- Token and duration limits were verified as hard next-round admission gates.
- Complete restart returned an identical report with no additional role work.
- Candidate evidence remained separate from authoritative approved evidence.
- Complete project suite: 413 passing tests.
- Python lint passed.

No live search, hosted-model, network-fetch or PDF operation was used.

## Deliberate limits

The controller measures deterministic sufficiency, not calibrated probability.
Context requirements remain unresolved until typed temporal or numerical
verification results are connected to the research state. The default
development workers use fixtures, and candidate research remains
non-authoritative pending the later benchmark promotion gate.
