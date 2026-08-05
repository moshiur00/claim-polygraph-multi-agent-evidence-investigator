# UI Stabilization — Stage UI.0 Baseline and Acceptance Contract

## Objective

Freeze the current journalist-facing dashboard before reliability, navigation,
cost, V4 transparency, accessibility, identity, component, and visual changes.
This stage changes no runtime behavior and authorizes no provider, model,
retrieval, or benchmark calls.

## Product boundary

The dashboard is a presentation and review surface. It must not infer a verdict,
verification state, publication state, evidence eligibility, source
independence, cost, or graph completion from visual convenience. Every displayed
decision value must come from an authoritative persisted artifact or be visibly
labelled as a compatibility fallback.

## Frozen user journeys

1. Submit one manual factual claim.
2. Extract candidate claims from article text.
3. Extract candidate claims from a permitted public URL.
4. Observe a durable authoritative job from queue through interruption or
   completion.
5. Inspect a provisional report before human review.
6. Inspect exact evidence, social-evidence governance, decision rationale,
   verification, citation assurance, review history, and architecture.
7. Approve, revise, request more evidence, or reject when permitted.
8. Resume after browser refresh or API restart without replaying paid work.
9. Export only the report form permitted by the publication decision.

## Supported viewport targets

| Class | Width | Primary expectation |
|---|---:|---|
| Wide desktop | 1440 px | Full sidebar and two-column evidence/review layouts |
| Laptop | 1280 px | Complete information without horizontal page scrolling |
| Compact desktop | 1024 px | Collapsed sidebar and single-column detail fallbacks |
| Tablet | 768 px | Touch-safe navigation and readable report cards |
| Mobile | 390 px | One-column reading and horizontally scrollable graph only |

The 12-node graph may scroll horizontally at narrow widths. The page itself,
forms, review controls, evidence passages, and tabs must not require horizontal
page scrolling.

## Canonical artifact authority map

| Dashboard area | Canonical authority | Allowed fallback |
|---|---|---|
| Investigation identity and status | persisted investigation and authoritative job | none |
| Workflow progress | authoritative LangGraph state and checkpointed nodes | persisted investigation stage while no graph exists |
| Verdict | graph final verdict, then constrained judgment-policy label | persisted legacy verdict, explicitly labelled |
| Publication readiness | authoritative publication decision and full-report assurance | fail closed |
| Evidence | approved persisted evidence packet and source records | none |
| Social evidence | social context, eligibility, quality and policy artifacts | explicit “not evaluated” state |
| Numerical/temporal verification | `verification_packet` assertion-level artifacts | labelled `context_verification` diagnostic only |
| Citation support | final full-report citation-assurance audit | labelled legacy sentence audit |
| Independence | persisted independence analysis and evidence families | unknown, never page count |
| Human review | append-only review history and current interruption | none |
| Cost | job/investigation receipt-derived ledger | global telemetry only when labelled lifetime scope |
| System health | API health, provider configuration and telemetry | unavailable state |

## Frozen known defects

### Critical trust and reliability

- A saved API address is overwritten during startup.
- An IPv6 hostname can be interpolated into an invalid unbracketed URL.
- SSE handlers close permanently on the first error, disabling automatic
  recovery and allowing silently stale progress.
- The visible cost total is global telemetry but can be mistaken for the
  selected investigation's cost.
- V4 assisted-construction origin, validation, receipt and cost are not yet
  fully exposed to reviewers.

### Interaction and accessibility

- Review Queue and System Health controls are visually interactive but inert.
- The report tablist lacks arrow, Home/End, `aria-controls`, panel IDs and
  managed tab focus.
- Reviewer and approver identities are hardcoded development defaults.
- SSE payload parsing has no guarded malformed-event path.
- Annotation Studio has two unstable hook-dependency warnings.

### Maintainability

- The main dashboard page combines transport, SSE recovery, selectors, forms,
  review commands and all report views in one component.
- Canonical artifact selection is implemented in local functions rather than a
  dedicated tested selector boundary.

## Stage sequence and mutation boundaries

1. UI.1 may change only API configuration and connection-state handling.
2. UI.2 may introduce durable event-stream recovery and fallback polling.
3. UI.3 may change navigation and route/state structure.
4. UI.4 may change cost APIs and presentation after scope is typed.
5. UI.5 may expose V4 artifacts without changing verification policy.
6. UI.6 may change interaction semantics and focus behavior.
7. UI.7 may replace development identity defaults with typed identity context.
8. UI.8 may refactor components only after behavior has regression tests.
9. UI.9 may change visual presentation after correctness work is stable.
10. UI.10 performs end-to-end closure and promotion audit.

No UI stage may weaken publication blocking, invent missing values, trigger a
paid operation during rendering, or bypass the authoritative API.

## Frozen acceptance gates

### Correctness

- Production dashboard build passes.
- Dashboard regression tests pass.
- Lint has zero errors; all existing warnings are recorded and must reach zero
  by UI.10.
- Canonical artifact precedence tests pass.
- No displayed missing or unknown value is converted to zero, “passed,” or
  “ready.”

### Reliability

- Saved API configuration survives reload.
- IPv4, hostname and IPv6 API addresses normalize safely.
- Progress reconnects from the last persisted sequence.
- Refresh, API restart and malformed SSE events cannot fabricate progress or
  repeat paid work.

### Accessibility

- Primary investigation and review journeys are keyboard operable.
- Tabs implement the WAI-ARIA interaction pattern.
- Status is not communicated by color alone.
- Critical live status is announced without excessive repetition.
- No critical automated or targeted accessibility finding remains.

### Responsive product quality

- All five viewport targets pass without page-level horizontal overflow,
  clipped controls, overlapping text or inaccessible actions.
- Technical diagnostics remain available but do not dominate the journalist's
  decision path.

### Cost and external effects

- UI regression tests make zero model, search and network-provider calls.
- Investigation, job, session and lifetime costs are never conflated.
- Unknown cost remains unknown with its conservative upper bound.
- Duplicate paid operations remain zero.

## Rollback conditions

Rollback an individual UI stage when it causes any canonical-authority
regression, publication-state mismatch, lost review action, duplicate external
operation, unrecoverable progress stream, inaccessible critical action, or
failure at a previously supported viewport.

## Baseline evidence

The machine-readable baseline is
`artifacts/evaluations/ui-stabilization-stage0-baseline-v1.json`. It records
source hashes, build/test/lint results, known defects, authority mapping,
viewport targets, zero-call constraints and the visual-capture limitation.

Rendered screenshot capture is deferred because the configured in-app browser
runtime could not initialize in this session. Existing screenshots are not
silently reused as if they represented the current build. UI.1 may proceed;
fresh desktop and mobile captures remain mandatory before UI.9 closure.
