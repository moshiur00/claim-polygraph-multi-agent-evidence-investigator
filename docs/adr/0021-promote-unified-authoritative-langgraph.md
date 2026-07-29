# ADR 0021: Promote the unified authoritative LangGraph workflow

Date: 29 July 2026

Status: Accepted

## Context

Phase 9 replaced the graph-around-a-completed-service arrangement with one
durable graph whose nodes invoke typed authoritative operations. Multi-agent
research, verification, arguments, judgment, citation assurance, review and
publication now share one checkpointed lifecycle.

The frozen 20-claim replay reached 100% verdict equivalence with the direct
workflow, 100% required-review recall, 100% mean reviewed-evidence coverage,
seven material challenger gains and zero duplicate paid operations. Recovery,
security, citation, API, dashboard and accessibility gates passed.

The deterministic fixture judge matched reviewed nuanced taxonomy labels in
40% of cases. That is not a regression—the unified and direct workflows are
equivalent—but it prevents interpreting this orchestration decision as factual
quality calibration.

## Recommended decision

Promote the unified authoritative LangGraph as the default local and
observational orchestration path.

Md Moshiur Rahman explicitly approved this ADR on 29 July 2026.

## Required boundaries

- `InvestigationService` remains authoritative for domain operations and
  persistence.
- The direct sequential composition remains tested rollback.
- Only approved persisted evidence may affect verification, arguments or
  verdicts.
- Unsupported critical report assertions block publication.
- Paid providers remain protected by durable idempotent receipts and budgets.
- Readiness remains distinct from probability.
- SQLite is approved only for the measured bounded single-host target.
- Distributed or higher-concurrency production deployment requires the
  PostgreSQL/queue decision to be revisited.
- This ADR does not claim calibrated production verdict accuracy.

## Rollback triggers

Roll back to direct composition if any release or monitoring window observes:

- authoritative verdict divergence;
- duplicate paid operations;
- checkpoint corruption or non-idempotent resume;
- publication of unsupported critical assertions;
- lost or mutable human-review history;
- sustained latency above the declared comparison boundary;
- SQLite lock failures inside the approved local concurrency envelope.

## Human approval record

Reviewer identity: Md Moshiur Rahman  
Review date: 29 July 2026  
Decision: `approve`  
Rationale: Explicit approval of ADR 0021 after the Stage 9.13 audit.  
Distinct approver: optional unless workspace policy requires one
