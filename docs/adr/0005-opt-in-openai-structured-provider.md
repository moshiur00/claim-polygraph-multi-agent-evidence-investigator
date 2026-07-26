# ADR 0005: Opt-in OpenAI structured-model provider

- Status: Accepted
- Date: 2026-07-26

## Context

Local Ollama inference preserves the local-first design but can be slow on
developer hardware. The project needs a faster route for iteration and delivery
without turning a paid hosted dependency into the default or weakening evidence
provenance contracts.

## Decision

Add an explicit OpenAI provider using the Responses API and strict JSON Schema
outputs.

- The deterministic provider remains the default.
- `--openai-model` or `OPENAI_MODEL` explicitly selects hosted processing.
- `OPENAI_API_KEY` is loaded from the process environment or Git-ignored
  `.env`; secrets are not accepted as command-line arguments.
- OpenAI and Ollama are mutually exclusive for one run.
- Requests set `store` to `false`, use low reasoning effort, and impose a
  per-task timeout and output-token limit.
- Model output supplies semantics only where identity and provenance must be
  protected. The application injects source IDs, chunk IDs, passage offsets,
  and other immutable fields.
- Every response is schema-validated and checked against the existing
  task-specific invariants. Refusals and incomplete responses are explicit
  failures; there is no silent provider fallback.

The initial recommended model is `gpt-5.6-luna`, selected for the
cost-sensitive workflow. The model remains configurable so evaluation can
compare quality, latency, and cost.

## Consequences

Hosted inference can shorten iteration time and avoids local model resource
constraints. It also transmits claim and evidence content to a paid external
service. Users must configure OpenAI project budgets and usage alerts
separately; this milestone does not claim application-level monetary-cap
enforcement.

The direct HTTP adapter reuses the existing `httpx` dependency, keeping the
earliest vertical slice free from an additional SDK dependency. Mock transports
provide deterministic, no-cost contract tests.
