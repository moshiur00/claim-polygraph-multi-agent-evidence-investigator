# ADR 0019: Hold multi-agent authority promotion pending targeted human review

Date: 28 July 2026

Status: Superseded by ADR 0020

ADR 0020 records the completed Stage 8.14 review and promotes multi-agent
research as the default observational subgraph while retaining
InvestigationService authority.

## Context

Stage 8.13 tested the complete controlled path after introducing real
LangGraph research fan-out, defender/challenger argument roles, durable jobs,
review interruption, recovery and distributed trace continuity.

The locked five-case pilot passed every mechanical gate:

- zero authoritative verdict regressions;
- additional candidate evidence and evidence families in all five cases;
- challenger-only gain in all five cases;
- 100% approved-packet preservation;
- 100% sentence citation support and material-sentence audit coverage;
- zero invented or out-of-packet evidence;
- zero duplicate paid operations;
- deterministic termination;
- 1.0x paid cost and 1.809x median local latency;
- all eight review/recovery journeys; and
- job recovery, specialist escalation and trace continuity.

Because the pilot passed, a ten-case comparison was run. It also recorded zero
authoritative regressions, candidate gain in all ten cases, full citation and
audit coverage, deterministic termination and no invented or duplicated paid
operation.

The composite journey passed from a traced durable job through the API,
LangGraph coordinator, concurrent research agents and providers, checkpoint
close/reopen and paid-operation replay protection.

## Decision

Do not yet allow multi-agent candidate research to alter authoritative
evidence or verdicts.

Keep LangGraph as the default orchestrator and keep `InvestigationService`
authoritative. Continue running the multi-agent research and adversarial
subgraphs observationally until Stage 8.14 completes targeted human review of
the changed evidence packets.

The mechanical gate establishes safety and evidence-adequacy signals, not
human-perceived relevance or factual quality. Deterministic fixtures produce
regular candidate gains and cannot independently prove that those candidates
are better evidence.

## Promotion condition

Stage 8.14 may promote multi-agent research only if human reviewers confirm
that its added evidence materially improves at least two locked cases without
reducing relevance, source quality, independence, citation support or verdict
correctness. Mandatory-review routing must also be checked on positive cases;
Stage 8.13's five pilot cases are negative controls only.

If that review fails, retain the current authority boundary. No code rollback
is needed because the direct workflow and authoritative service remain intact.

## Consequences

- The system genuinely executes multiple bounded agents and challenger roles.
- Their candidate results remain visible, durable and measurable.
- No agent can silently promote its own evidence into the authoritative
  packet.
- The ten-case expansion is complete; a twenty-case stability repeat is
  deferred until quality promotion passes.
- Stage 8.14 owns the final promotion ADR and Phase 8 closure.
