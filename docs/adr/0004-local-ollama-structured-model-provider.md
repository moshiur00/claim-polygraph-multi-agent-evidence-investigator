# ADR 0004: Use Ollama for the first real structured-model adapter

- Status: Accepted
- Date: 26 July 2026

## Context

The deterministic model provider validates orchestration but cannot analyze
claim meaning, evidence stance, verdicts, or citation support. The project needs
one real local adapter before additional agents or model runtimes are justified.

The adapter must preserve the local-first operating policy, return typed
artifacts, treat retrieved content as untrusted data, and prevent a model from
changing provenance identifiers or exact evidence passages.

## Decision

Ollama is the first real structured-model adapter. It calls the trusted local
`/api/chat` endpoint directly through HTTPX and:

- sends the Pydantic JSON schema in the API `format` field;
- disables streaming for simpler complete-response validation;
- sets temperature to zero and a fixed seed;
- includes a versioned system prompt that treats all input as untrusted data;
- gives each logical model task a narrow instruction;
- validates the returned JSON through the requested Pydantic model;
- enforces deterministic post-generation invariants for claim IDs, source IDs,
  chunk IDs, passage text, character offsets, retrieval score, approved
  evidence IDs, and audited sentence text;
- normalizes service, missing-model, and invalid-output failures.

The deterministic provider remains the default. Ollama is enabled only with an
explicit model name through `--ollama-model` or `OLLAMA_MODEL`.

Official API references:

- <https://docs.ollama.com/api/chat>
- <https://docs.ollama.com/capabilities/structured-outputs>
- <https://docs.ollama.com/api/errors>

## Consequences

### Positive

- The existing provider protocol remains unchanged.
- Local structured reasoning can be compared directly with the deterministic
  baseline.
- Model output cannot silently rewrite evidence provenance.
- Tests do not require a running model because HTTP transport is injectable.

### Negative

- Output quality depends on the selected model and available hardware.
- Schema compliance does not prove factual or citation correctness.
- One shared model currently performs every logical role.
- The local Ollama service and model lifecycle remain operator responsibilities.

## Follow-up

Record model identity, prompt version, latency, token counts, and generation
outcomes in trace events. Evaluate evidence classification first on reviewed
benchmark cases. Add another runtime only after this adapter establishes a
measurable baseline.
