# ADR 0001: Adopt a lightweight-first architecture

- Status: Accepted
- Date: 26 July 2026

## Context

The target architecture includes PostgreSQL, Redis, LangGraph, pgvector,
SearXNG, several local model runtimes, and a web workspace. Building all of
that infrastructure before validating the investigation workflow would delay
evidence-quality measurement and make early failures harder to isolate.

At the same time, the project must preserve a credible migration path toward
durable, concurrent, multi-agent execution.

## Decision

The first implementation will use:

- Python application services executed in process;
- Pydantic domain contracts;
- SQLite and JSON artifacts for initial persistence;
- one model provider and one search provider behind protocols;
- structured trace events;
- JSON and readable reports before a full frontend.

Core investigation logic will depend on domain contracts and provider
interfaces rather than concrete infrastructure.

Production components will be introduced when a demonstrated requirement
justifies them:

- LangGraph for durable checkpoints, bounded graph routing, and human
  interrupts;
- PostgreSQL for larger relational and concurrent workloads;
- Redis or an equivalent queue for distributed execution;
- pgvector for semantic retrieval at scale;
- SearXNG for controlled local metasearch;
- additional model-runtime adapters for deployment and benchmark needs;
- a web workspace after the evidence engine and citation audit are reliable.

## Consequences

### Positive

- The first evidence-to-verdict workflow can be built and evaluated sooner.
- Failures can be attributed to investigation logic instead of distributed
  infrastructure.
- Tests can use deterministic mock providers.
- Production migration remains possible through stable contracts.

### Negative

- The initial version will not support distributed workers or sophisticated
  pause-and-resume behavior.
- Some persistence and execution adapters will later be replaced.
- Interface discipline is required to prevent infrastructure details from
  leaking into the domain layer.

## Guardrail

Infrastructure may be added before its planned phase only when a concrete
requirement cannot be met safely by the lightweight implementation and the
trade-off is documented in another ADR.
