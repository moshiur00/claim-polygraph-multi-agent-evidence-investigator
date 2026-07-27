# ADR 0007: Task-based OpenAI model routing

- Status: Accepted
- Date: 2026-07-26

## Context

Focused extraction and classification tasks do not require the same model
capability as investigation planning and evidence-grounded verdict judgment.
Using `gpt-5.4-mini` for every task spends more than necessary, while using a
smaller 4-series model for the final verdict may reduce reasoning quality.

The models also have different request capabilities. GPT-5 reasoning models
accept a reasoning-effort control; `gpt-4o-mini` does not use that parameter.

## Decision

Route OpenAI tasks by role:

- `gpt-4o-mini`: claim normalization, evidence classification, and review
  critique.
- `gpt-5.4-mini`: investigation planning, final verdict judgment, semantic
  passage evaluation, and sentence-level citation auditing.

`OPENAI_MODEL` configures the planning/verdict model.
`OPENAI_FAST_MODEL` configures the focused-task model. The corresponding CLI
options are `--openai-model` and `--openai-fast-model`.

The provider omits the reasoning parameter for compatible 4-series requests
and sends low reasoning effort for GPT-5 requests. Trace events record the
concrete model selected for each task. A single-model configuration remains
supported by omitting the fast model.

## Consequences

Focused tasks use the cheaper model, while tasks with the greatest effect on
research strategy, conclusions, semantic retrieval measurement, and citation
validity retain the stronger model. There is no fallback between models:
failure of the routed model remains an explicit investigation failure.

The route is provisional until evaluated on the reviewed benchmark. Cost,
latency, schema reliability, citation validity, and verdict quality must be
measured separately.
