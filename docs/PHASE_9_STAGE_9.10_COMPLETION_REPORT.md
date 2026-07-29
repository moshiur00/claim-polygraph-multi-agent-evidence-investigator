# Phase 9 Stage 9.10 — API and dashboard completion

## Outcome

The dashboard now submits one durable authoritative LangGraph job. The same
thread owns research, verification, defender/challenger arguments, judgment,
citation assurance, readiness, human interruption and publication. The API
returns one combined view of the durable job, latest graph checkpoint, review
trail, interruption and publication status.

## Public write path

- `POST /api/authoritative-jobs` admits a durable, idempotent investigation.
- `GET /api/authoritative-jobs/{job_id}` reconstructs current state without
  executing completed nodes.
- `GET /api/authoritative-jobs/{job_id}/events` streams real checkpoint and job
  events through SSE; it does not synthesize percentage progress.
- `POST /api/authoritative-jobs/{job_id}/review` persists a typed decision and
  resumes the same interrupted thread.
- `POST /api/authoritative-jobs/{job_id}/cancel` uses the existing safe durable
  cancellation boundary.

## Compatibility and rollback

Existing investigation, report, evidence, review, legacy graph and telemetry
read endpoints remain available. The synchronous investigation endpoint and
the configured direct orchestrator remain intact as rollback surfaces. The
dashboard no longer creates a second review graph after research.

## User-visible behavior

The console presents one 12-phase workflow from creation through publication,
uses checkpoint phases for live progress, restores active jobs after reload,
shows interruption and immutable review history, and exposes publication
blocking rather than treating a completed research packet as automatically
publishable.

## Validation

- Authoritative API integration covers admission, checkpoints, SSE,
  interruption, same-thread review and legacy reads.
- Existing API, human-review and durable-job regression tests pass.
- The dashboard production build succeeds.
- The gate uses deterministic providers only: zero external model, search, PDF
  or network calls.
