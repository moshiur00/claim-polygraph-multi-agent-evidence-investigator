# ADR 0006: Cost-first OpenAI model selection

- Status: Accepted
- Date: 2026-07-26

## Context

ADR 0005 introduced `gpt-5.6-luna` as the initial hosted model recommendation.
During the current delivery phase, reducing API cost is more important than
using the newest model family, provided the selected model still supports the
Responses API and strict structured outputs.

## Decision

Use `gpt-5.4-mini` as the recommended OpenAI model for development and early
benchmark runs.

The provider remains model-configurable, and deterministic reasoning remains
the no-cost default unless OpenAI is explicitly selected.

## Consequences

The official list price is lower than `gpt-5.6-luna`, but model quality may also
be lower. We will measure verdict quality, schema reliability, latency, and
token usage on the reviewed benchmark before promoting a model for production.

This decision supersedes only the model recommendation in ADR 0005. It does not
change the provider architecture, security boundary, or validation rules.
