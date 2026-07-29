# Phase 9 compatibility contract inventory

Baseline date: 29 July 2026

## Compatibility rule

Phase 9 may add fields and endpoints, but it must keep existing records
readable and preserve the meaning of existing fields. Removing, renaming, or
changing a field requires a versioned adapter and an explicit migration.

## Public and persistence-sensitive surfaces

| Contract | Compatibility-sensitive content |
|---|---|
| `InvestigationReport` JSON | `investigation`, `claim`, `plan`, `sources`, `evidence`, `independence_analysis`, `provenance`, `verification_packet`, `argument_ledger`, `judgment_policy`, `readiness`, `context_verification`, `verdict`, `audits`, `full_report_assurance` |
| Investigation status | IDs, parent/component links, input claim, status, stage, timestamps and failure reason |
| Evidence endpoint | Evidence/source/chunk IDs, stance, passage and offsets, relevance, quality and provenance fields |
| Markdown report | Development notice, verdict, reasoning, evidence/citations, limitations and audit/publication behavior |
| Durable job API/SSE | Job identity/status, investigation link, sequenced audit events, `job_event` and `job_state` event names |
| Graph/review API | Thread snapshot, interrupt, append-only decision/approval/revision records and resume semantics |
| Dashboard | Investigation list/detail, unified progress, evidence and report panels, review actions, telemetry and cost fields |

## Endpoint inventory

- `POST /api/investigations` remains the synchronous rollback-compatible path.
- `POST /api/investigation-jobs` remains the durable asynchronous submission path.
- Job, investigation, graph and review event streams retain reconnect cursors.
- Existing investigation, evidence and JSON/Markdown report reads remain valid.
- Existing graph-run and review endpoints remain readable during migration.

The generated Stage 9 manifest fingerprints the Pydantic schemas for
`InvestigationReport`, `Investigation`, and `Evidence`. It also records the
non-schema SSE and Markdown guarantees above so tests can distinguish a
deliberate version change from accidental drift.
