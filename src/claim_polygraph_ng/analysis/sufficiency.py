"""Deterministic evidence sufficiency and diminishing-return control."""

from uuid import UUID

from claim_polygraph_ng.domain import EvidenceStance, SourceType
from claim_polygraph_ng.domain.research import (
    EvidenceGain,
    EvidenceProgressSnapshot,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchRole,
    SufficiencyAssessment,
    SufficiencyContext,
    SufficiencyDecision,
)

_PRIMARY_TYPES = frozenset(
    {
        SourceType.OFFICIAL,
        SourceType.PRIMARY_DOCUMENT,
        SourceType.DATASET,
        SourceType.LAW_OR_REGULATION,
    }
)
_CONTEXT_KINDS = frozenset(
    {
        ResearchRequirementKind.TEMPORAL_CONTEXT,
        ResearchRequirementKind.NUMERICAL_CONTEXT,
    }
)


def assess_evidence_sufficiency(context: SufficiencyContext) -> SufficiencyAssessment:
    """Return one auditable terminal or targeted continuation decision."""
    satisfied = satisfied_requirement_ids(context)
    declared = {item.requirement_id for item in context.requirements}
    missing = declared - satisfied
    common = {
        "investigation_id": context.investigation_id,
        "component_id": context.component_id,
        "round_number": max(1, context.consumption.completed_rounds),
        "satisfied_requirement_ids": tuple(sorted(satisfied, key=str)),
        "missing_requirement_ids": tuple(sorted(missing, key=str)),
    }

    if not missing:
        return SufficiencyAssessment(
            **common,
            decision=SufficiencyDecision.SUFFICIENT,
            rationale="Every declared material evidence requirement is satisfied.",
        )
    if context.human_review_reason:
        return SufficiencyAssessment(
            **common,
            decision=SufficiencyDecision.HUMAN_REVIEW_REQUIRED,
            rationale=context.human_review_reason,
        )
    if missing <= context.unresolvable_requirement_ids:
        return SufficiencyAssessment(
            **common,
            decision=SufficiencyDecision.STOP_UNRESOLVABLE,
            rationale="Every remaining requirement is explicitly marked unresolvable.",
        )
    if _budget_exhausted(context):
        return SufficiencyAssessment(
            **common,
            decision=SufficiencyDecision.STOP_BUDGET_EXHAUSTED,
            rationale="At least one hard research budget prevents another bounded round.",
        )
    if (
        context.consumption.completed_rounds > 0
        and context.last_round_gain is not None
        and context.last_round_gain.material_gain_count == 0
    ):
        return SufficiencyAssessment(
            **common,
            decision=SufficiencyDecision.STOP_DIMINISHING_RETURN,
            rationale="The completed research round produced no material evidence gain.",
        )

    decision = _continuation_decision(context.requirements, missing)
    return SufficiencyAssessment(
        **common,
        decision=decision,
        rationale=_continuation_rationale(decision),
    )


def satisfied_requirement_ids(context: SufficiencyContext) -> frozenset[UUID]:
    """Evaluate each declared requirement against consolidated typed evidence."""
    sources = {source.source_id: source for source in context.sources}
    relevant = tuple(
        item for item in context.evidence if item.stance is not EvidenceStance.IRRELEVANT
    )
    satisfied: set[UUID] = set()
    for requirement in context.requirements:
        if (requirement.kind is ResearchRequirementKind.COMPONENT_COVERAGE and relevant) or (
            requirement.kind is ResearchRequirementKind.PRIMARY_SOURCE
            and any(
                _source_matches(requirement, sources.get(item.source_id), primary=True)
                for item in relevant
            )
        ):
            satisfied.add(requirement.requirement_id)
        elif requirement.kind is ResearchRequirementKind.INDEPENDENT_CORROBORATION:
            if (
                context.independence is not None
                and context.independence.independent_family_count
                >= requirement.minimum_independent_families
            ):
                satisfied.add(requirement.requirement_id)
        elif requirement.kind is ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION:
            if ResearchRole.CHALLENGER in context.attempted_roles and any(
                item.stance in {EvidenceStance.CONTRADICTS, EvidenceStance.QUALIFIES}
                for item in relevant
            ):
                satisfied.add(requirement.requirement_id)
        elif (
            (
                requirement.kind is ResearchRequirementKind.ACADEMIC_EVIDENCE
                and any(
                    _source_matches(requirement, sources.get(item.source_id), academic=True)
                    for item in relevant
                )
            )
            or (
                requirement.kind is ResearchRequirementKind.PRIOR_FACT_CHECK
                and any(
                    _source_matches(requirement, sources.get(item.source_id), fact_check=True)
                    for item in relevant
                )
            )
            or (
                requirement.kind in _CONTEXT_KINDS
                and requirement.requirement_id in context.resolved_context_requirement_ids
            )
        ):
            satisfied.add(requirement.requirement_id)
    return frozenset(satisfied)


def calculate_evidence_gain(
    before: EvidenceProgressSnapshot,
    after: EvidenceProgressSnapshot,
) -> EvidenceGain:
    """Count only new set members representing material progress."""
    return EvidenceGain(
        newly_covered_component_ids=_new(before.covered_component_ids, after.covered_component_ids),
        newly_satisfied_requirement_ids=_new(
            before.satisfied_requirement_ids,
            after.satisfied_requirement_ids,
        ),
        new_independent_family_ids=_new(
            before.independent_family_ids,
            after.independent_family_ids,
        ),
        new_challenge_evidence_ids=_new(
            before.challenge_evidence_ids,
            after.challenge_evidence_ids,
        ),
        resolved_context_requirement_ids=_new(
            before.resolved_context_requirement_ids,
            after.resolved_context_requirement_ids,
        ),
    )


def targeted_roles(
    context: SufficiencyContext,
    assessment: SufficiencyAssessment,
) -> tuple[ResearchRole, ...]:
    """Select only roles relevant to missing requirements after a continue decision."""
    if not assessment.decision.value.startswith("continue_"):
        return ()
    missing = set(assessment.missing_requirement_ids)
    kinds = {item.kind for item in context.requirements if item.requirement_id in missing}
    roles: list[ResearchRole] = []
    if ResearchRequirementKind.PRIMARY_SOURCE in kinds:
        roles.append(ResearchRole.PRIMARY_SOURCE)
    if ResearchRequirementKind.INDEPENDENT_CORROBORATION in kinds:
        roles.append(ResearchRole.GENERAL_EVIDENCE)
    if ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION in kinds:
        roles.append(ResearchRole.CHALLENGER)
    if ResearchRequirementKind.ACADEMIC_EVIDENCE in kinds:
        roles.append(ResearchRole.ACADEMIC)
    if ResearchRequirementKind.PRIOR_FACT_CHECK in kinds:
        roles.append(ResearchRole.FACT_CHECK)
    if kinds & _CONTEXT_KINDS:
        roles.extend((ResearchRole.PRIMARY_SOURCE, ResearchRole.GENERAL_EVIDENCE))
    if ResearchRequirementKind.COMPONENT_COVERAGE in kinds:
        roles.extend(
            (
                ResearchRole.PRIMARY_SOURCE,
                ResearchRole.GENERAL_EVIDENCE,
                ResearchRole.CHALLENGER,
            )
        )
    return tuple(dict.fromkeys(roles))


def _source_matches(
    requirement: ResearchRequirement,
    source,
    *,
    primary: bool = False,
    academic: bool = False,
    fact_check: bool = False,
) -> bool:
    if source is None:
        return False
    if (
        requirement.required_source_types
        and source.source_type not in requirement.required_source_types
    ):
        return False
    if primary:
        return source.source_type in _PRIMARY_TYPES
    if academic:
        return source.source_type is SourceType.ACADEMIC
    if fact_check:
        return source.source_type is SourceType.FACT_CHECK
    return True


def _budget_exhausted(context: SufficiencyContext) -> bool:
    consumption = context.consumption
    budget = context.budget
    return (
        consumption.completed_rounds >= budget.maximum_rounds
        or consumption.role_activations >= budget.maximum_role_activations_per_component
        or consumption.search_calls >= budget.maximum_search_calls
        or consumption.fetched_pages >= budget.maximum_pages_per_component
        or (
            consumption.model_calls >= budget.maximum_model_calls and budget.maximum_model_calls > 0
        )
        or (
            consumption.total_tokens >= budget.maximum_total_tokens
            and budget.maximum_total_tokens > 0
        )
        or consumption.duration_seconds >= budget.maximum_duration_seconds
        or (
            consumption.estimated_cost_usd >= budget.maximum_cost_usd
            and budget.maximum_cost_usd > 0
        )
    )


def _continuation_decision(
    requirements: tuple[ResearchRequirement, ...],
    missing: set[UUID],
) -> SufficiencyDecision:
    kinds = {item.kind for item in requirements if item.requirement_id in missing}
    if ResearchRequirementKind.PRIMARY_SOURCE in kinds:
        return SufficiencyDecision.CONTINUE_MISSING_PRIMARY
    if ResearchRequirementKind.INDEPENDENT_CORROBORATION in kinds:
        return SufficiencyDecision.CONTINUE_MISSING_INDEPENDENT
    if ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION in kinds:
        return SufficiencyDecision.CONTINUE_MISSING_CHALLENGE
    if kinds & _CONTEXT_KINDS:
        return SufficiencyDecision.CONTINUE_CONTEXT_MISMATCH
    return SufficiencyDecision.CONTINUE_MISSING_COMPONENT


def _continuation_rationale(decision: SufficiencyDecision) -> str:
    return {
        SufficiencyDecision.CONTINUE_MISSING_PRIMARY: (
            "A suitable primary source remains missing within the research budget."
        ),
        SufficiencyDecision.CONTINUE_MISSING_INDEPENDENT: (
            "Independent corroboration remains below the declared requirement."
        ),
        SufficiencyDecision.CONTINUE_MISSING_CHALLENGE: (
            "Contradictory or qualifying evidence remains missing after routing checks."
        ),
        SufficiencyDecision.CONTINUE_CONTEXT_MISMATCH: (
            "A temporal or numerical context requirement remains unresolved."
        ),
        SufficiencyDecision.CONTINUE_MISSING_COMPONENT: (
            "A material component or specialist evidence requirement remains uncovered."
        ),
    }[decision]


def _new(before: frozenset[UUID], after: frozenset[UUID]) -> tuple[UUID, ...]:
    return tuple(sorted(after - before, key=str))
