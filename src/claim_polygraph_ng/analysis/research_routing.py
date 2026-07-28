"""Deterministic, budget-bounded Phase 4 research-role routing."""

from claim_polygraph_ng.domain import ClaimType, EvidenceStance, SourceType
from claim_polygraph_ng.domain.research import (
    ROLE_PERMISSIONS,
    ResearchAssignment,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchRole,
    ResearchRoute,
    ResearchRoutingRequest,
)


def route_research_roles(request: ResearchRoutingRequest) -> ResearchRoute:
    """Select the minimum team and conditionally add useful specialists."""
    roles = [
        ResearchRole.PRIMARY_SOURCE,
        ResearchRole.GENERAL_EVIDENCE,
        ResearchRole.CHALLENGER,
    ]
    rationale = [
        "Minimum team includes primary, general, and adversarial research.",
    ]

    academic_needed = _requires_academic(request)
    fact_check_needed = request.prior_fact_check_likely or _has_requirement(
        request.requirements, ResearchRequirementKind.PRIOR_FACT_CHECK
    )
    if academic_needed:
        roles.append(ResearchRole.ACADEMIC)
        rationale.append("Academic research activated by claim type or evidence requirement.")
    if fact_check_needed:
        roles.append(ResearchRole.FACT_CHECK)
        rationale.append("Fact-check research activated by an explicit structured signal.")

    maximum = request.budget.maximum_role_activations_per_component
    active_roles = roles[:maximum]
    deferred_roles = roles[maximum:]
    if deferred_roles:
        rationale.append("Lower-priority specialist roles were deferred by the activation budget.")

    assignments = tuple(
        ResearchAssignment(
            investigation_id=request.investigation_id,
            parent_claim_id=request.parent_claim_id,
            component_id=request.component_id,
            claim_text=request.claim_text,
            retained_context=request.retained_context,
            role=role,
            round_number=request.round_number,
            requirement_ids=_requirements_for_role(request.requirements, role),
            permissions=ROLE_PERMISSIONS[role],
            query_limit=request.budget.maximum_queries_per_role_per_round,
            candidate_limit_per_query=request.budget.maximum_candidates_per_query,
        )
        for role in active_roles
    )
    return ResearchRoute(
        assignments=assignments,
        deferred_roles=tuple(deferred_roles),
        rationale=tuple(rationale),
    )


def route_targeted_research_roles(
    request: ResearchRoutingRequest,
    roles: tuple[ResearchRole, ...],
    *,
    remaining_activation_slots: int,
) -> ResearchRoute:
    """Create only requirement-directed continuation assignments."""
    active_roles = roles[: max(0, remaining_activation_slots)]
    deferred_roles = roles[len(active_roles) :]
    rationale = [
        (
            f"Round {request.round_number} activates {role.value} only for "
            "requirements still missing after deterministic assessment."
        )
        for role in active_roles
    ]
    if deferred_roles:
        rationale.append("Additional targeted roles were deferred by the hard activation budget.")
    assignments = tuple(
        ResearchAssignment(
            investigation_id=request.investigation_id,
            parent_claim_id=request.parent_claim_id,
            component_id=request.component_id,
            claim_text=request.claim_text,
            retained_context=request.retained_context,
            role=role,
            round_number=request.round_number,
            requirement_ids=_requirements_for_role(request.requirements, role),
            permissions=ROLE_PERMISSIONS[role],
            query_limit=request.budget.maximum_queries_per_role_per_round,
            candidate_limit_per_query=request.budget.maximum_candidates_per_query,
        )
        for role in active_roles
    )
    return ResearchRoute(
        assignments=assignments,
        deferred_roles=tuple(deferred_roles),
        rationale=tuple(rationale),
    )


def _requires_academic(request: ResearchRoutingRequest) -> bool:
    if request.claim_types & {ClaimType.SCIENTIFIC, ClaimType.CAUSAL}:
        return True
    if _has_requirement(request.requirements, ResearchRequirementKind.ACADEMIC_EVIDENCE):
        return True
    return any(SourceType.ACADEMIC in item.required_source_types for item in request.requirements)


def _has_requirement(
    requirements: tuple[ResearchRequirement, ...],
    kind: ResearchRequirementKind,
) -> bool:
    return any(item.kind is kind for item in requirements)


def _requirements_for_role(
    requirements: tuple[ResearchRequirement, ...],
    role: ResearchRole,
) -> tuple:
    matched = tuple(
        item.requirement_id
        for item in requirements
        if (
            role is ResearchRole.PRIMARY_SOURCE
            and item.kind
            in {
                ResearchRequirementKind.COMPONENT_COVERAGE,
                ResearchRequirementKind.PRIMARY_SOURCE,
                ResearchRequirementKind.TEMPORAL_CONTEXT,
                ResearchRequirementKind.NUMERICAL_CONTEXT,
            }
        )
        or (
            role is ResearchRole.GENERAL_EVIDENCE
            and item.kind
            in {
                ResearchRequirementKind.COMPONENT_COVERAGE,
                ResearchRequirementKind.INDEPENDENT_CORROBORATION,
                ResearchRequirementKind.TEMPORAL_CONTEXT,
                ResearchRequirementKind.NUMERICAL_CONTEXT,
            }
        )
        or (
            role is ResearchRole.CHALLENGER
            and (
                item.kind is ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION
                or EvidenceStance.CONTRADICTS in item.required_stances
                or EvidenceStance.QUALIFIES in item.required_stances
            )
        )
        or (
            role is ResearchRole.ACADEMIC
            and (
                item.kind is ResearchRequirementKind.ACADEMIC_EVIDENCE
                or SourceType.ACADEMIC in item.required_source_types
            )
        )
        or (
            role is ResearchRole.FACT_CHECK
            and item.kind is ResearchRequirementKind.PRIOR_FACT_CHECK
        )
    )
    if matched:
        return matched
    # Every minimum-team assignment remains tied to the component-coverage
    # requirement instead of receiving an unscoped task.
    return (requirements[0].requirement_id,)
