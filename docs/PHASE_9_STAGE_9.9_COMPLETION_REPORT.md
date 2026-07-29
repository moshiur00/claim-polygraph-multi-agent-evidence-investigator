# Phase 9 Stage 9.9 completion report

Date: 29 July 2026

Status: Complete

## Outcome

Human review now interrupts and resumes the same authoritative LangGraph
thread. Review requests, decisions, approvals and verdict revisions are stored
in the existing append-only, tamper-evident review ledger. Completed graph
operations and paid-operation receipts are retained without replay.

## Review lifecycle

```text
route review
  -> persist review request
  -> LangGraph interrupt
  -> typed reviewer decision
     ├─ approve -> distinct approval -> finalization
     ├─ revise -> distinct approval -> versioned verdict
     │            -> deterministic citation re-assurance -> finalization
     ├─ request evidence -> remain awaiting evidence, no final report
     └─ reject -> cancelled, no final report
```

The public `start` operation returns the typed interrupt and current
authoritative state. `resume` accepts a `ReviewDecision` and optional distinct
approver identity, then invokes `Command(resume=...)` on exactly the same
LangGraph thread.

## Append-only review authority

The review ledger records one hash-chained event for each request, decision,
approval and revision. Database triggers prevent updates and deletes.
Deterministic request, approval, revision and revised-verdict identifiers make
crash replay idempotent. Reusing an accepted decision returns the current graph
state; submitting a different second decision is rejected.

Approval and revision require a distinct approver. Revision records preserve
the original verdict ID and label, the new label, rationale and authoritative
change type.

## Publication behavior

Approval can release a `review_required` publication decision, but it cannot
override unsupported critical citations. A revised verdict is deterministically
re-audited against the same approved evidence packet. If citation assurance
still fails, publication remains blocked.

More-evidence requests and rejection do not produce a final report. They also
do not repeat research, verification, judgment, citation or provider work.

## Compatibility

`run_to_completion` remains as a fixture compatibility helper and uses two
distinct synthetic identities to approve an interrupt. Production callers can
use `start` and `resume`. The direct `InvestigationService` workflow remains the
rollback path.

## Verification

The Stage 9.9 gate covers all four dispositions, same-thread resume,
idempotent replay, conflicting-decision rejection, distinct approval,
versioned revision, citation re-assurance, append-only chain validity,
operation non-replay and paid-receipt non-replay.

## Cost

No OpenAI, SerpAPI, live network, document download or PDF operation was used.

## Exit decision

Stage 9.9 passes. Human review is now a durable part of the authoritative
LangGraph lifecycle rather than an auto-approved fixture interruption.
