# Phase 8 Stage 8.3 completion report

Date: 28 July 2026

Status: Complete

## Outcome

The promoted LangGraph checkpoint can now carry the durable coordination state
needed by a genuine multi-agent research subgraph. The state is graph-native
and authority-preserving: it records coordination references but does not
embed evidence text, provider objects, mutable repositories, or a competing
verdict.

## Persisted state

- Parent investigation and parent claim identifiers
- Up to eight material component references with bounded claim summaries
- Typed research-requirement references
- Role assignment references, round number and requirement scope
- Result references linked to stored source and evidence identifiers
- Evidence-family membership references
- Declared research budget and observed consumption
- Bounded unresolved questions linked to components and requirements
- Schema version for future migrations

## Validation boundary

The contract fails closed when IDs are duplicated; references point to unknown
or mismatched components, requirements, assignments, sources or evidence;
families invent artifacts; or observed search, model, round or cost usage
exceeds its declared budget. The graph request also proves that checkpointed
evidence remains within the authoritative approved-evidence packet.

## Integration and recovery

`LangGraphInvestigationOrchestrator` projects each authoritative report into
this bounded state before the graph starts. The API exposes it as part of the
existing graph snapshot. Direct rollback creates no graph state.

SQLite checkpoint restart tests reconstruct a completed research round,
including assignment and result identity, without provider or repository
calls. Operation counts remain one, proving reconstruction does not repeat
graph work. Existing Stage 7 checkpoints remain backward compatible because
the research payload is optional when absent.

## Cost and authority

This stage executed no search, model, network or PDF operations.
`InvestigationService` remains the sole evidence and verdict authority. The
new state is infrastructure for later agent fan-out; it does not claim that
specialist agents have already executed through LangGraph.

## Verification

- Cross-reference and budget contract tests
- Provider-free serialization/reconstruction test
- SQLite process-restart and idempotency test
- Promoted API exposure and direct-rollback isolation test
- Existing interruption, review, resume and orchestrator regression tests
- Complete project suite: 399 passing tests
- Python lint, dashboard lint and dashboard production build

## Next boundary

Stage 8.4 can now add dedicated academic and fact-check provider adapters. Their
future assignments and results can be checkpointed through this state without
placing provider responses or full document content inside LangGraph.
