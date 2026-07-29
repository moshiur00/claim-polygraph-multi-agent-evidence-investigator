# Phase 9 Stage 9.5 completion report

Date: 29 July 2026

Status: Complete

## Outcome

Metered model and search operations now have an atomic, durable receipt and
cost ledger. Completed operations return stored validated results rather than
calling a provider again. OpenAI and SerpAPI are not yet connected to the
authoritative graph; the safety boundary is proven with counted fake providers.

## Receipt state machine

```text
reserved
  -> in_progress
     -> completed
     -> failed_retryable
     -> failed_permanent
  -> cancelled

stale reserved -> safely reclaimed
stale in_progress -> ambiguous -> manual recovery only
```

The distinction between `reserved` and `in_progress` is critical. A process
crash before the provider starts cannot have incurred a charge and can safely
reclaim its reservation. A crash during the provider call or after provider
success but before the local commit may have incurred a charge; it becomes
`ambiguous` and is never repeated automatically.

## Durable data

Every receipt records:

- Investigation, node, provider, model/engine and logical task.
- Canonical input hash and unique operation key.
- Lease owner, expiry and attempt number.
- Provider-start and completion times.
- Durable result reference and result hash.
- Input, cached-input and output tokens.
- Duration and estimated cost.
- Sanitized failure class and summary.

Result payloads are stored once in a separate table and verified against their
SHA-256 hash before replay. The cost ledger aggregates only unique completed
receipts, so cache replay cannot double-count cost.

## Provider decorators

`IdempotentStructuredModelProvider` preserves typed response validation and
compatible `ModelCallUsage`. Cached calls expose zero incremental token cost.
`IdempotentSearchProvider` stores and reconstructs typed `SearchResult`
collections. Both reject active, ambiguous and permanently failed receipts
without invoking their wrapped provider.

## Failure gates

Tests cover:

- Duplicate model submission.
- Duplicate metered search.
- Concurrent worker claim.
- Safe stale reservation recovery before a call.
- Retryable provider failure.
- Crash during a provider call.
- Crash after provider success but before receipt completion.
- Ambiguous-operation manual authorization.
- Result replay and unique cost aggregation.

## Scope boundary

The decorators are ready but are not enabled for OpenAI or SerpAPI in the
authoritative graph. Stage 9.6 can connect the research subgraph only after
providing the investigation/node context required by these decorators.

## Cost

No external model, live search, network or PDF call was made.

## Exit decision

Stage 9.5 passes when completed work never repeats, ambiguous work never retries
automatically, concurrent claims cannot both execute, cost is counted once,
stored results validate, crash tests pass, and release hashes verify.
