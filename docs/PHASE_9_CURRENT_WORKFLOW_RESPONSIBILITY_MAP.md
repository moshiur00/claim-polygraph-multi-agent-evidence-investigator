# Phase 9 current workflow responsibility map

Baseline date: 29 July 2026

## Current execution boundary

The promoted `LangGraphOrchestrator` currently invokes
`InvestigationService.investigate()` as one authoritative operation and then
uses the durable graph for review/publication disposition. The direct
orchestrator invokes the same service without that wrapper. Consequently,
LangGraph does not yet checkpoint normalization, planning, research,
verification, judgment, or citation assurance independently.

```text
API or durable job
  -> InvestigationOrchestrator
     -> LangGraph wrapper (default) or direct rollback
        -> InvestigationService.investigate()
           -> normalize -> plan -> research -> verify
           -> ledger -> verdict -> citation audit -> readiness
        -> review/publication graph
```

## Authoritative responsibility inventory

| Responsibility | Current implementation | Persisted artifacts | Writes / events | Paid-capable |
|---|---|---|---|---|
| Create and transition investigation | `investigate`, `_transition` | — | investigation rows; lifecycle events | No |
| Normalize claim | `_generate(NORMALIZE_CLAIM)` | claim | artifact/provider/usage events | Yes |
| Plan investigation | `_generate(PLAN_INVESTIGATION)` | plan | artifact/provider/usage events | Yes |
| Search, fetch, segment, rank and classify | `_research`, `_search`, `_result_content` | source, chunk, evidence, independence | artifact/provider/failure/usage events | Yes |
| Analyze provenance | `build_investigation_provenance` | provenance | artifact event | No |
| Verify numerical/temporal context | `verify_claim_context`, legacy bridge | context verification, verification packet | artifact events | No |
| Build claim-to-evidence ledger | `build_argument_ledger` | argument ledger | artifact event | No |
| Draft and constrain verdict | model judgment, safeguards, judgment policy | judgment policy, verdict | artifact/provider/usage events | Yes |
| Audit sentence and full report | model audit/revision, `assure_full_report` | audit, full-report assurance | artifact/provider/usage events | Yes |
| Assess readiness | `calculate_judgment_readiness` | readiness | artifact event | No |
| Complete or fail | `investigate` exception boundary | — | investigation row; terminal event | No |

## Migration implication

Stage 9.1 must assign each row to one typed authoritative operation. Stage 9.2
may change composition, but it must not change these artifacts, lifecycle
semantics, budget enforcement, or failure persistence. Search and model calls
need durable receipts before graph-level retry is enabled.
