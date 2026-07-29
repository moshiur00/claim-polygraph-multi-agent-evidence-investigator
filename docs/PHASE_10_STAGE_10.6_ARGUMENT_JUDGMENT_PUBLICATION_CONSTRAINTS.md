# Phase 10 Stage 10.6 — Argument, Judgment, and Publication Constraints

## Outcome

Stage 10.6 adds a deterministic, persisted policy between argument reconciliation
and judgment. It does not ask a model to decide whether social material is safe.

## Enforced rules

1. Every social evidence item referenced by the argument ledger must have an
   explicit `evidentiary_use`.
2. That use must appear in the source's deterministic `allowed_uses`.
3. Ineligible social material cannot support an argument.
4. Social material that is not approved for decisive use cannot independently
   resolve a material proposition.
5. A supported or contradicted material proposition containing social evidence
   requires corroborating non-social evidence on the decisive side.
6. Persisted unresolved social risks force human review.
7. A blocking social-policy finding blocks publication even when citation
   assurance itself passes.

## Workflow integration

The direct and authoritative LangGraph workflows both evaluate and persist a
`SocialEvidencePolicyResult` after defender/challenger reconciliation. The
result is consumed by:

- judgment policy, to route review without silently changing the verdict label;
- readiness, to expose policy finding and blocking counts;
- publication, to fail closed on critical social-evidence dependence;
- report reconstruction and Markdown rendering, to show reviewers the exact
  policy reasons.

The Phase 9 operation manifest remains backward-compatible: policy evaluation
is a deterministic output of the existing reconciliation responsibility rather
than a new paid or independently retryable operation.

## Non-goals

- Social engagement and platform badges remain excluded from authority.
- Corroboration does not make dependent copies independent.
- The policy does not infer authenticity, truth, or authority with an LLM.
- The policy does not fetch private, restricted, or unavailable content.

## Gate

Targeted tests cover social-only decisive support, explicit-use enforcement,
non-social corroboration, judgment review routing, the direct workflow
contract, and the authoritative LangGraph workflow.
