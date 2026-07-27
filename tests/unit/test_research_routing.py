from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.analysis.research_routing import route_research_roles
from claim_polygraph_ng.domain import (
    ClaimType,
    ResearchBudget,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchRole,
    ResearchRoutingRequest,
    SourceType,
)


def test_factual_claim_uses_only_minimum_team() -> None:
    request = _request()

    route = route_research_roles(request)

    assert tuple(item.role for item in route.assignments) == (
        ResearchRole.PRIMARY_SOURCE,
        ResearchRole.GENERAL_EVIDENCE,
        ResearchRole.CHALLENGER,
    )
    assert route.deferred_roles == ()


def test_causal_claim_activates_academic_role() -> None:
    request = _request(
        claim_types=frozenset({ClaimType.CAUSAL}),
        requirements=(
            _requirement(ResearchRequirementKind.COMPONENT_COVERAGE),
            _requirement(
                ResearchRequirementKind.ACADEMIC_EVIDENCE,
                source_types=(SourceType.ACADEMIC,),
            ),
        ),
    )

    route = route_research_roles(request)

    assert tuple(item.role for item in route.assignments)[-1] is ResearchRole.ACADEMIC
    assert len(route.assignments) == 4


def test_fact_check_role_requires_explicit_signal() -> None:
    route = route_research_roles(_request(prior_fact_check_likely=True))

    assert route.assignments[-1].role is ResearchRole.FACT_CHECK


def test_activation_budget_defers_lower_priority_specialist() -> None:
    request = _request(
        claim_types=frozenset({ClaimType.SCIENTIFIC}),
        prior_fact_check_likely=True,
        budget=ResearchBudget(maximum_role_activations_per_component=4),
    )

    route = route_research_roles(request)

    assert len(route.assignments) == 4
    assert route.assignments[-1].role is ResearchRole.ACADEMIC
    assert route.deferred_roles == (ResearchRole.FACT_CHECK,)


def test_router_applies_query_and_candidate_limits() -> None:
    request = _request(
        budget=ResearchBudget(
            maximum_queries_per_role_per_round=1,
            maximum_candidates_per_query=4,
        )
    )

    route = route_research_roles(request)

    assert all(item.query_limit == 1 for item in route.assignments)
    assert all(item.candidate_limit_per_query == 4 for item in route.assignments)


def test_routing_rejects_requirement_for_another_component() -> None:
    with pytest.raises(ValidationError, match="must reference the component"):
        _request(
            requirements=(
                _requirement(
                    ResearchRequirementKind.COMPONENT_COVERAGE,
                    component_id=uuid4(),
                ),
            )
        )


def _requirement(
    kind: ResearchRequirementKind,
    *,
    component_id: UUID | None = None,
    source_types: tuple[SourceType, ...] = (),
) -> ResearchRequirement:
    return ResearchRequirement(
        component_id=component_id or _COMPONENT_ID,
        kind=kind,
        required_source_types=source_types,
        rationale="This requirement is material to the investigation.",
    )


_COMPONENT_ID = uuid4()


def _request(
    *,
    claim_types: frozenset[ClaimType] = frozenset({ClaimType.FACTUAL}),
    requirements: tuple[ResearchRequirement, ...] | None = None,
    prior_fact_check_likely: bool = False,
    budget: ResearchBudget | None = None,
) -> ResearchRoutingRequest:
    selected = requirements or (_requirement(ResearchRequirementKind.COMPONENT_COVERAGE),)
    return ResearchRoutingRequest(
        investigation_id=uuid4(),
        parent_claim_id=uuid4(),
        component_id=_COMPONENT_ID,
        claim_text="The submitted material claim.",
        claim_types=claim_types,
        requirements=selected,
        prior_fact_check_likely=prior_fact_check_likely,
        budget=budget or ResearchBudget(),
    )
