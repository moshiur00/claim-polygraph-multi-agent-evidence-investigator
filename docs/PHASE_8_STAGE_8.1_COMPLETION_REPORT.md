# Phase 8 Stage 8.1 completion report

Date: 28 July 2026

Status: Complete for the atomic investigation contract

## Outcome

The atomic product path now has one runtime-checkable
`InvestigationOrchestrator` contract. Every implementation returns the
authoritative `InvestigationReport` and declares its orchestration mode and
authority.

| Mode | Responsibility | Authority effect |
|---|---|---|
| `langgraph` | Default durable graph, checkpoint, interruption and review routing | Preserves `InvestigationService` report |
| `direct` | Explicit rollback without graph side effects | Returns `InvestigationService` report directly |
| `multi_agent_experimental` | Runs the durable graph plus bounded experimental multi-agent research | Records experiment only; cannot replace authoritative output |

## Product wiring

- The development API defaults to `langgraph`.
- `CLAIM_POLYGRAPH_ORCHESTRATOR=direct` remains the rollback.
- `multi_agent_experimental` is an explicit API/configuration mode.
- `/health` reports the selected orchestrator and authoritative service.
- Investigation responses include `X-Claim-Polygraph-Orchestrator` and
  `X-Claim-Polygraph-Authority`.
- The CLI defaults to LangGraph for atomic claims, exposes direct rollback and
  prints the selected mode and authority.
- The dashboard reads typed health data, displays the mode and authority, and
  loads automatically created graph/review state instead of starting a
  duplicate graph.

## Isolation and idempotency

- All three adapters satisfy the common protocol.
- Deterministic reports retain equivalent authoritative verdicts.
- Multi-agent experimental output is supplied only to an optional recorder.
- Replaying one authoritative report reuses its graph checkpoint.
- Replaying one review-required report creates no duplicate review request.
- Direct mode creates no graph checkpoint.

## Deliberate limitation

`ComplexInvestigationService` remains its existing direct durable coordinator
and the CLI declares that authority. Stage 8.1 does not pretend the atomic
orchestrator protocol already covers the different
`ComplexInvestigationReport` contract. A typed complex graph adapter belongs
with Stage 8.3 durable multi-agent graph state.

## Cost and safety

No external model, network or PDF calls were used. Experimental-mode tests use
deterministic providers and the zero-cost budget. Existing evidence, judgment,
review and direct-rollback boundaries remain unchanged.

## Artifact integrity

The Stage 8.1 release manifest freezes the orchestrator contract, API and CLI
wiring, dashboard integration, configuration example, focused integration
test, evaluation result and this completion report.
