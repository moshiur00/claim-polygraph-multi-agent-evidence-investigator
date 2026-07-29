# Phase 10 Stage 10.9 — Recovery, Security, Audit, and Promotion

## Outcome

The deterministic mechanical audit passes. ADR 0023 was explicitly approved
by Md Moshiur Rahman on 30 July 2026. Phase 10 is therefore promoted and closed
for the bounded local deployment.

This recommendation promotes social-evidence governance and its safety
controls. It does not claim that social content is true, that the system is
ready for authenticated multi-tenant production, or that publication may
bypass human review.

## Recovery and safety gates

| Gate | Result |
|---|---|
| Phase 9 retry, restart, checkpoint, receipt, review, and SSE controls | Passed |
| Deleted and unavailable social-content handling | Passed |
| Typed social-state JSON reconstruction | Passed |
| Malicious HTML executable-content removal | Passed |
| OpenAI/Ollama untrusted-data prompt boundary | Passed |
| Telemetry PII and credential minimization | Passed |
| Reviewer identity binding and restricted CORS | Passed for bounded local scope |
| Public URL and redirect safety | Passed |
| Direct-workflow publication constraints | Passed |
| Authoritative LangGraph publication constraints | Passed |
| Provisional report and dashboard transparency | Passed |
| Stage 10.8 human calibration | Approved |
| Unsafe adversarial publication rate | 0% |
| Mandatory-review recall | 100% |
| Direct rollback | Retained |
| Paid provider calls for release audit | 0 |

The targeted Stage 10.9 suite contains eight passing tests. The complete Python
regression contains 565 passing tests. The dashboard production build, three
UI/accessibility tests, and ESLint gate also pass.

## Prompt-injection interpretation

HTML scripts and hidden executable markup are removed during readable-text
extraction. Visible adversarial instructions are deliberately not silently
deleted: they remain quoted evidence data. OpenAI and Ollama receive those
passages in the user-data payload under a system instruction that treats all
claims, passages, and metadata as untrusted data and forbids browsing, tool
calls, and invented citations.

Deterministic evidence eligibility, provenance, publication blocking, and
review routing remain authoritative even if a model produces an unexpected
classification.

## Privacy and access-control interpretation

Operational telemetry hashes claims, email addresses, provider credentials,
content, and URLs. Public identity information required to attribute an
evidence item may remain in the evidence packet; it is not copied into
operational telemetry.

The promoted scope is a bounded local deployment. It includes restricted CORS,
unsafe-URL blocking, and reviewer-header/body identity binding. That binding is
not cryptographic authentication. Authenticated multi-user or internet-facing
production remains explicitly outside the promotion decision.

## Promotion scope

Eligible:

- local Docker deployment;
- bounded single-host use;
- LangGraph as the authoritative orchestration thread;
- `InvestigationService` domain and persistence operations;
- direct sequential composition as rollback;
- human-reviewed publication;
- typed, constrained, transparently reported social evidence.

Not promoted:

- autonomous factual publication;
- private or restricted social-content retrieval;
- engagement counts or platform badges as authority or truth;
- authenticated multi-tenant production;
- unbounded distributed traffic;
- population-level factual-accuracy or confidence claims.

## Release artifacts

The final audit is written to
`artifacts/evaluations/phase10-stage10.9-final-audit-v1.json`.

The SHA-256 release manifest is written to
`artifacts/evaluations/phase10-stage10.9-release-manifest-v1.json`.

ADR 0023 records the accepted promotion decision. Phase 10 is closed within
the bounded scope documented above.
