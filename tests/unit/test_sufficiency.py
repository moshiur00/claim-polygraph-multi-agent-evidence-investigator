from datetime import UTC, datetime
from uuid import UUID, uuid4

from claim_polygraph_ng.analysis import (
    assess_evidence_sufficiency,
    calculate_evidence_gain,
    targeted_roles,
)
from claim_polygraph_ng.domain import (
    Evidence,
    EvidenceFamily,
    EvidenceGain,
    EvidenceProgressSnapshot,
    EvidenceStance,
    ExtractionStatus,
    IndependenceAnalysis,
    ResearchBudget,
    ResearchConsumption,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchRole,
    Source,
    SourceType,
    SufficiencyContext,
    SufficiencyDecision,
)


def test_all_requirements_satisfied_stops_research() -> None:
    component_id = uuid4()
    primary = _source(SourceType.OFFICIAL)
    challenger = _source(SourceType.NEWS)
    supporting = _evidence(component_id, primary, EvidenceStance.SUPPORTS)
    qualifying = _evidence(component_id, challenger, EvidenceStance.QUALIFIES)
    requirements = (
        _requirement(component_id, ResearchRequirementKind.COMPONENT_COVERAGE),
        _requirement(component_id, ResearchRequirementKind.PRIMARY_SOURCE),
        _requirement(
            component_id,
            ResearchRequirementKind.INDEPENDENT_CORROBORATION,
            minimum_families=2,
        ),
        _requirement(
            component_id,
            ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION,
        ),
        _requirement(component_id, ResearchRequirementKind.TEMPORAL_CONTEXT),
    )
    context = _context(
        component_id,
        requirements,
        sources=(primary, challenger),
        evidence=(supporting, qualifying),
        independence=_independence(component_id, (primary, challenger), (supporting, qualifying)),
        attempted_roles=frozenset({ResearchRole.CHALLENGER}),
        resolved_context_requirement_ids=frozenset({requirements[-1].requirement_id}),
    )

    assessment = assess_evidence_sufficiency(context)

    assert assessment.decision is SufficiencyDecision.SUFFICIENT
    assert assessment.missing_requirement_ids == ()
    assert targeted_roles(context, assessment) == ()


def test_missing_primary_routes_only_primary_research() -> None:
    component_id = uuid4()
    requirement = _requirement(component_id, ResearchRequirementKind.PRIMARY_SOURCE)
    context = _context(component_id, (requirement,))

    assessment = assess_evidence_sufficiency(context)

    assert assessment.decision is SufficiencyDecision.CONTINUE_MISSING_PRIMARY
    assert targeted_roles(context, assessment) == (ResearchRole.PRIMARY_SOURCE,)


def test_missing_independence_routes_general_research() -> None:
    component_id = uuid4()
    source = _source(SourceType.NEWS)
    evidence = _evidence(component_id, source, EvidenceStance.SUPPORTS)
    requirement = _requirement(
        component_id,
        ResearchRequirementKind.INDEPENDENT_CORROBORATION,
        minimum_families=2,
    )
    context = _context(
        component_id,
        (requirement,),
        sources=(source,),
        evidence=(evidence,),
        independence=_independence(component_id, (source,), (evidence,)),
    )

    assessment = assess_evidence_sufficiency(context)

    assert assessment.decision is SufficiencyDecision.CONTINUE_MISSING_INDEPENDENT
    assert targeted_roles(context, assessment) == (ResearchRole.GENERAL_EVIDENCE,)


def test_challenge_requires_attempt_and_qualifying_or_contradictory_evidence() -> None:
    component_id = uuid4()
    source = _source(SourceType.NEWS)
    requirement = _requirement(
        component_id,
        ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION,
    )
    context = _context(
        component_id,
        (requirement,),
        sources=(source,),
        evidence=(_evidence(component_id, source, EvidenceStance.SUPPORTS),),
        attempted_roles=frozenset({ResearchRole.CHALLENGER}),
    )

    assessment = assess_evidence_sufficiency(context)

    assert assessment.decision is SufficiencyDecision.CONTINUE_MISSING_CHALLENGE
    assert targeted_roles(context, assessment) == (ResearchRole.CHALLENGER,)


def test_budget_exhaustion_precedes_another_round() -> None:
    component_id = uuid4()
    context = _context(
        component_id,
        (_requirement(component_id, ResearchRequirementKind.COMPONENT_COVERAGE),),
        consumption=ResearchConsumption(
            completed_rounds=1,
            role_activations=3,
            search_calls=24,
            fetched_pages=0,
            model_calls=0,
            estimated_cost_usd=0,
        ),
    )

    assessment = assess_evidence_sufficiency(context)

    assert assessment.decision is SufficiencyDecision.STOP_BUDGET_EXHAUSTED


def test_zero_model_and_cost_budgets_disable_paid_operations_without_stopping() -> None:
    component_id = uuid4()
    context = _context(
        component_id,
        (_requirement(component_id, ResearchRequirementKind.PRIMARY_SOURCE),),
        consumption=ResearchConsumption(
            completed_rounds=1,
            role_activations=3,
            search_calls=3,
            fetched_pages=0,
            model_calls=0,
            estimated_cost_usd=0,
        ),
    )

    assessment = assess_evidence_sufficiency(context)

    assert assessment.decision is SufficiencyDecision.CONTINUE_MISSING_PRIMARY


def test_token_and_duration_limits_are_hard_round_admission_gates() -> None:
    component_id = uuid4()
    requirement = _requirement(component_id, ResearchRequirementKind.PRIMARY_SOURCE)
    budget = ResearchBudget(
        maximum_total_tokens=100,
        maximum_duration_seconds=10,
    )
    base = _context(component_id, (requirement,))
    token_limited = base.model_copy(
        update={
            "budget": budget,
            "consumption": base.consumption.model_copy(update={"total_tokens": 100}),
        }
    )
    duration_limited = base.model_copy(
        update={
            "budget": budget,
            "consumption": base.consumption.model_copy(update={"duration_seconds": 10}),
        }
    )

    assert (
        assess_evidence_sufficiency(token_limited).decision
        is SufficiencyDecision.STOP_BUDGET_EXHAUSTED
    )
    assert (
        assess_evidence_sufficiency(duration_limited).decision
        is SufficiencyDecision.STOP_BUDGET_EXHAUSTED
    )


def test_zero_material_gain_stops_before_targeted_continuation() -> None:
    component_id = uuid4()
    context = _context(
        component_id,
        (_requirement(component_id, ResearchRequirementKind.PRIMARY_SOURCE),),
        last_round_gain=EvidenceGain(),
    )

    assessment = assess_evidence_sufficiency(context)

    assert assessment.decision is SufficiencyDecision.STOP_DIMINISHING_RETURN


def test_unresolvable_and_human_review_are_explicit_terminal_states() -> None:
    component_id = uuid4()
    requirement = _requirement(component_id, ResearchRequirementKind.COMPONENT_COVERAGE)
    unresolvable = _context(
        component_id,
        (requirement,),
        unresolvable_requirement_ids=frozenset({requirement.requirement_id}),
    )
    review = unresolvable.model_copy(
        update={"human_review_reason": "Conflicting controlling sources require human review."}
    )

    assert (
        assess_evidence_sufficiency(unresolvable).decision is SufficiencyDecision.STOP_UNRESOLVABLE
    )
    assert assess_evidence_sufficiency(review).decision is SufficiencyDecision.HUMAN_REVIEW_REQUIRED


def test_gain_counts_only_new_material_set_members() -> None:
    existing = uuid4()
    new_requirement = uuid4()
    new_challenge = uuid4()
    before = EvidenceProgressSnapshot(
        satisfied_requirement_ids=frozenset({existing}),
    )
    after = EvidenceProgressSnapshot(
        satisfied_requirement_ids=frozenset({existing, new_requirement}),
        challenge_evidence_ids=frozenset({new_challenge}),
    )

    gain = calculate_evidence_gain(before, after)
    duplicate_only = calculate_evidence_gain(after, after)

    assert gain.material_gain_count == 2
    assert gain.newly_satisfied_requirement_ids == (new_requirement,)
    assert duplicate_only.material_gain_count == 0


def _context(
    component_id: UUID,
    requirements: tuple[ResearchRequirement, ...],
    *,
    sources: tuple[Source, ...] = (),
    evidence: tuple[Evidence, ...] = (),
    independence: IndependenceAnalysis | None = None,
    attempted_roles: frozenset[ResearchRole] = frozenset(),
    resolved_context_requirement_ids: frozenset[UUID] = frozenset(),
    unresolvable_requirement_ids: frozenset[UUID] = frozenset(),
    last_round_gain: EvidenceGain | None = None,
    consumption: ResearchConsumption | None = None,
) -> SufficiencyContext:
    return SufficiencyContext(
        investigation_id=uuid4(),
        component_id=component_id,
        requirements=requirements,
        sources=sources,
        evidence=evidence,
        independence=independence,
        attempted_roles=attempted_roles,
        resolved_context_requirement_ids=resolved_context_requirement_ids,
        unresolvable_requirement_ids=unresolvable_requirement_ids,
        last_round_gain=last_round_gain
        if last_round_gain is not None
        else EvidenceGain(newly_satisfied_requirement_ids=(uuid4(),)),
        consumption=consumption
        or ResearchConsumption(
            completed_rounds=1,
            role_activations=3,
            search_calls=3,
            fetched_pages=2,
            model_calls=0,
            estimated_cost_usd=0,
        ),
        budget=ResearchBudget(),
    )


def _requirement(
    component_id: UUID,
    kind: ResearchRequirementKind,
    *,
    minimum_families: int = 1,
) -> ResearchRequirement:
    return ResearchRequirement(
        component_id=component_id,
        kind=kind,
        minimum_independent_families=minimum_families,
        rationale="This is a material evidence requirement for the component.",
    )


def _source(source_type: SourceType) -> Source:
    source_id = uuid4()
    return Source(
        source_id=source_id,
        url=f"https://{source_id}.example/report",
        canonical_url=f"https://{source_id}.example/report",
        title="Evidence source",
        source_type=source_type,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
    )


def _evidence(component_id: UUID, source: Source, stance: EvidenceStance) -> Evidence:
    return Evidence(
        claim_id=component_id,
        source_id=source.source_id,
        passage=f"Material {stance.value} evidence from the stored source.",
        stance=stance,
        relevance_score=0.9,
    )


def _independence(
    component_id: UUID,
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
) -> IndependenceAnalysis:
    families = tuple(
        EvidenceFamily(
            family_id=uuid4(),
            source_ids=(source.source_id,),
            evidence_ids=tuple(
                item.evidence_id for item in evidence if item.source_id == source.source_id
            ),
            hostnames=(f"{source.source_id}.example",),
            grouping_reasons=("distinct_source",),
        )
        for source in sources
    )
    return IndependenceAnalysis(
        claim_id=component_id,
        required_independent_families=1,
        families=families,
    )
