"""Concurrent LangGraph map/reduce research subgraph for Stage 8.5."""

import operator
from typing import Annotated, Any, TypedDict
from uuid import NAMESPACE_URL, UUID, uuid5

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from claim_polygraph_ng.analysis import (
    assess_evidence_sufficiency,
    calculate_evidence_gain,
    consolidate_evidence,
    route_research_roles,
    route_targeted_research_roles,
    targeted_roles,
)
from claim_polygraph_ng.analysis.sufficiency import satisfied_requirement_ids
from claim_polygraph_ng.application.research_executor import (
    ResearchExecutor,
    ResearchWorker,
    SharedResearchOperations,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    EvidenceGain,
    EvidenceProgressSnapshot,
    EvidenceStance,
    MultiAgentFanOutReport,
    ResearchAssignment,
    ResearchBudget,
    ResearchConsumption,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchResult,
    ResearchRoundAudit,
    ResearchRoutingRequest,
    RoleResearchMetric,
    SufficiencyContext,
    SufficiencyDecision,
)
from claim_polygraph_ng.domain.research import (
    MultiAgentWorkflowCheckpoint,
    MultiAgentWorkflowStage,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository
from claim_polygraph_ng.telemetry import TelemetryCollector


class _FanOutState(TypedDict, total=False):
    assignments: list[dict[str, Any]]
    results: Annotated[list[dict[str, Any]], operator.add]
    unique_results: list[dict[str, Any]]
    duplicate_result_references_removed: int


class LangGraphResearchFanOutWorkflow:
    """Map assignments to concurrent role nodes and reduce stored artifacts."""

    def __init__(
        self,
        *,
        repository: SQLiteResearchRepository,
        operations: SharedResearchOperations,
        worker: ResearchWorker,
        telemetry: TelemetryCollector | None = None,
    ) -> None:
        self._repository = repository
        self._operations = operations
        self._worker = worker
        self._telemetry = telemetry
        self._repository.initialize()

    async def start_or_resume(
        self,
        *,
        investigation_id: UUID,
        claim: AtomicClaim,
        requirements: tuple[ResearchRequirement, ...],
        budget: ResearchBudget,
    ) -> MultiAgentFanOutReport:
        checkpoint = self._repository.get_workflow(investigation_id)
        if checkpoint is None:
            route = route_research_roles(
                ResearchRoutingRequest(
                    investigation_id=investigation_id,
                    parent_claim_id=claim.parent_claim_id or claim.claim_id,
                    component_id=claim.claim_id,
                    claim_text=claim.text,
                    retained_context=claim.retained_context,
                    claim_types=frozenset({claim.claim_type}),
                    requirements=requirements,
                    budget=budget,
                )
            )
            checkpoint = MultiAgentWorkflowCheckpoint(
                investigation_id=investigation_id,
                claim=claim,
                requirements=requirements,
                budget=budget,
                stage=MultiAgentWorkflowStage.PLANNED,
                assignments=route.assignments,
            )
            self._repository.save_workflow(checkpoint)
        elif checkpoint.claim.claim_id != claim.claim_id:
            raise ValueError("research checkpoint claim does not match investigation")

        while checkpoint.stage is not MultiAgentWorkflowStage.COMPLETE:
            if checkpoint.stage is MultiAgentWorkflowStage.PLANNED:
                checkpoint = await self._execute_current_round(checkpoint)
            if checkpoint.stage is MultiAgentWorkflowStage.RESEARCHED:
                checkpoint = checkpoint.model_copy(
                    update={
                        "stage": MultiAgentWorkflowStage.CONSOLIDATED,
                        "consolidation": _consolidate(self._repository, checkpoint),
                    }
                )
                self._repository.save_workflow(checkpoint)
            if checkpoint.stage is MultiAgentWorkflowStage.CONSOLIDATED:
                checkpoint = self._assess_current_round(checkpoint)
            if checkpoint.stage is MultiAgentWorkflowStage.ASSESSED:
                checkpoint = self._continue_or_stop(checkpoint)

        if checkpoint.consolidation is None:
            raise ValueError("research fan-in checkpoint has no consolidation")
        report = _report(checkpoint)
        if (
            checkpoint.role_metrics != report.role_metrics
            or checkpoint.duplicate_result_references_removed
            != report.duplicate_result_references_removed
        ):
            checkpoint = checkpoint.model_copy(
                update={
                    "role_metrics": report.role_metrics,
                    "duplicate_result_references_removed": (
                        report.duplicate_result_references_removed
                    ),
                }
            )
            self._repository.save_workflow(checkpoint)
        return report

    async def _execute_current_round(
        self,
        checkpoint: MultiAgentWorkflowCheckpoint,
    ) -> MultiAgentWorkflowCheckpoint:
        round_number = max(item.round_number for item in checkpoint.assignments)
        completed_ids = {item.assignment_id for item in checkpoint.results}
        pending_assignments = tuple(
            item
            for item in checkpoint.assignments
            if item.round_number == round_number and item.assignment_id not in completed_ids
        )
        pending = _apply_shared_candidate_budget(checkpoint, pending_assignments)
        output: dict[str, Any] = {"unique_results": []}
        if pending:
            executor = ResearchExecutor(
                repository=self._repository,
                operations=self._operations,
                worker=self._worker,
                maximum_concurrency=checkpoint.budget.maximum_concurrent_roles,
                telemetry=self._telemetry,
            )
            output = await _build_graph(executor).ainvoke(
                {
                    "assignments": [item.model_dump(mode="json") for item in pending],
                    "results": [],
                }
            )
        new_results = tuple(
            ResearchResult.model_validate(item) for item in output.get("unique_results", [])
        )
        admitted_ids = {item.assignment_id for item in pending}
        budget_stopped_results = tuple(
            ResearchResult(
                assignment_id=item.assignment_id,
                role=item.role,
                component_id=item.component_id,
                failure_reason="shared page/model budget exhausted before assignment",
            )
            for item in pending_assignments
            if item.assignment_id not in admitted_ids
        )
        for result in budget_stopped_results:
            self._repository.save_result(result)
        new_results = (*new_results, *budget_stopped_results)
        updated = checkpoint.model_copy(
            update={
                "stage": MultiAgentWorkflowStage.RESEARCHED,
                "results": (*checkpoint.results, *new_results),
                "duplicate_result_references_removed": (
                    checkpoint.duplicate_result_references_removed
                    + int(output.get("duplicate_result_references_removed", 0))
                ),
            }
        )
        self._repository.save_workflow(updated)
        return updated

    def _assess_current_round(
        self,
        checkpoint: MultiAgentWorkflowCheckpoint,
    ) -> MultiAgentWorkflowCheckpoint:
        if checkpoint.consolidation is None:
            raise ValueError("research round cannot be assessed before consolidation")
        round_number = max(item.round_number for item in checkpoint.assignments)
        consumption = _consumption(checkpoint)
        base_context = _sufficiency_context(
            checkpoint,
            consumption=consumption,
            last_round_gain=EvidenceGain(newly_covered_component_ids=(checkpoint.claim.claim_id,)),
        )
        satisfied = satisfied_requirement_ids(base_context)
        progress = _progress_snapshot(checkpoint, satisfied)
        before = checkpoint.rounds[-1].progress if checkpoint.rounds else EvidenceProgressSnapshot()
        gain = calculate_evidence_gain(before, progress)
        context = base_context.model_copy(update={"last_round_gain": gain})
        assessment = assess_evidence_sufficiency(context)
        assignments = tuple(
            item for item in checkpoint.assignments if item.round_number == round_number
        )
        result_by_assignment = {item.assignment_id: item for item in checkpoint.results}
        audit = ResearchRoundAudit(
            round_number=round_number,
            assignment_ids=tuple(item.assignment_id for item in assignments),
            result_ids=tuple(
                result_by_assignment[item.assignment_id].result_id for item in assignments
            ),
            progress=progress,
            gain=gain,
            consumption=consumption,
            assessment=assessment,
            routing_rationale=checkpoint.pending_routing_rationale,
        )
        updated = checkpoint.model_copy(
            update={
                "stage": MultiAgentWorkflowStage.ASSESSED,
                "assessment": assessment,
                "rounds": (*checkpoint.rounds, audit),
            }
        )
        self._repository.save_workflow(updated)
        return updated

    def _continue_or_stop(
        self,
        checkpoint: MultiAgentWorkflowCheckpoint,
    ) -> MultiAgentWorkflowCheckpoint:
        if checkpoint.assessment is None or not checkpoint.rounds:
            raise ValueError("assessed research checkpoint lacks controller artifacts")
        context = _sufficiency_context(
            checkpoint,
            consumption=checkpoint.rounds[-1].consumption,
            last_round_gain=checkpoint.rounds[-1].gain,
        )
        roles = targeted_roles(context, checkpoint.assessment)
        if not roles:
            updated = checkpoint.model_copy(update={"stage": MultiAgentWorkflowStage.COMPLETE})
            self._repository.save_workflow(updated)
            return updated
        missing = set(checkpoint.assessment.missing_requirement_ids)
        requirements = tuple(
            item for item in checkpoint.requirements if item.requirement_id in missing
        )
        remaining = checkpoint.budget.maximum_role_activations_per_component - len(
            checkpoint.assignments
        )
        route = route_targeted_research_roles(
            ResearchRoutingRequest(
                investigation_id=checkpoint.investigation_id,
                parent_claim_id=(checkpoint.claim.parent_claim_id or checkpoint.claim.claim_id),
                component_id=checkpoint.claim.claim_id,
                claim_text=checkpoint.claim.text,
                retained_context=checkpoint.claim.retained_context,
                claim_types=frozenset({checkpoint.claim.claim_type}),
                requirements=requirements,
                round_number=checkpoint.rounds[-1].round_number + 1,
                budget=checkpoint.budget,
            ),
            roles,
            remaining_activation_slots=remaining,
        )
        if not route.assignments:
            updated = checkpoint.model_copy(update={"stage": MultiAgentWorkflowStage.COMPLETE})
        else:
            updated = checkpoint.model_copy(
                update={
                    "stage": MultiAgentWorkflowStage.PLANNED,
                    "assignments": (*checkpoint.assignments, *route.assignments),
                    "pending_routing_rationale": route.rationale,
                    "assessment": None,
                }
            )
        self._repository.save_workflow(updated)
        return updated


def _build_graph(executor: ResearchExecutor):
    builder = StateGraph(_FanOutState)

    async def research_role(state: _FanOutState) -> dict[str, list[dict[str, Any]]]:
        assignment = state["assignments"][0]
        typed_assignment = ResearchAssignment.model_validate(assignment)
        result = (await executor.execute((typed_assignment,)))[0]
        return {"results": [result.model_dump(mode="json")]}

    def fan_in(state: _FanOutState) -> dict[str, object]:
        unique = {}
        for raw in state.get("results", []):
            unique.setdefault(raw["result_id"], raw)
        return {
            "unique_results": list(unique.values()),
            "duplicate_result_references_removed": len(state.get("results", [])) - len(unique),
        }

    builder.add_node("plan_minimum_team", lambda _state: {})
    builder.add_node("research_role", research_role)
    builder.add_node("fan_in_deduplicate", fan_in)
    builder.add_edge(START, "plan_minimum_team")
    builder.add_conditional_edges("plan_minimum_team", _send_assignments)
    builder.add_edge("research_role", "fan_in_deduplicate")
    builder.add_edge("fan_in_deduplicate", END)
    return builder.compile()


def _send_assignments(state: _FanOutState) -> list[Send]:
    return [
        Send("research_role", {"assignments": [assignment], "results": []})
        for assignment in state["assignments"]
    ]


def _consolidate(
    repository: SQLiteResearchRepository,
    checkpoint: MultiAgentWorkflowCheckpoint,
):
    source_ids = tuple(
        dict.fromkeys(source_id for result in checkpoint.results for source_id in result.source_ids)
    )
    evidence_ids = tuple(
        dict.fromkeys(
            evidence_id for result in checkpoint.results for evidence_id in result.evidence_ids
        )
    )
    sources = repository.get_sources(source_ids)
    evidence = repository.get_evidence(evidence_ids)
    if len(sources) != len(source_ids) or len(evidence) != len(evidence_ids):
        raise ValueError("research fan-in references unstored source or evidence")
    required_families = max(
        (
            item.minimum_independent_families
            for item in checkpoint.requirements
            if item.kind is ResearchRequirementKind.INDEPENDENT_CORROBORATION
        ),
        default=1,
    )
    return consolidate_evidence(
        claim_id=checkpoint.claim.claim_id,
        sources=sources,
        evidence=evidence,
        required_families=required_families,
    )


def _report(
    checkpoint: MultiAgentWorkflowCheckpoint,
) -> MultiAgentFanOutReport:
    assert checkpoint.consolidation is not None
    if checkpoint.assessment is None or not checkpoint.rounds:
        raise ValueError("completed research checkpoint has no sufficiency decision")
    retained_ids = {item.evidence_id for item in checkpoint.consolidation.evidence}
    result_by_assignment = {item.assignment_id: item for item in checkpoint.results}
    metrics = tuple(
        RoleResearchMetric(
            assignment_id=assignment.assignment_id,
            role=assignment.role,
            successful=result.failure_reason is None,
            source_count=len(result.source_ids),
            evidence_count=len(result.evidence_ids),
            retained_evidence_count=len(set(result.evidence_ids) & retained_ids),
            independent_family_gain=sum(
                bool(set(result.evidence_ids) & set(family.evidence_ids))
                for family in checkpoint.consolidation.independence.families
            ),
            search_calls=result.search_call_count,
            fetch_calls=result.fetch_call_count,
            model_calls=result.model_call_count,
            token_count=result.token_count,
            estimated_cost_usd=result.estimated_cost_usd,
            duration_seconds=result.duration_seconds,
        )
        for assignment in checkpoint.assignments
        for result in (result_by_assignment[assignment.assignment_id],)
    )
    unresolved = tuple(sorted(checkpoint.assessment.missing_requirement_ids, key=str))
    human_review_required = checkpoint.assessment.decision is not SufficiencyDecision.SUFFICIENT
    human_review_reason = (
        (
            "Automated research stopped without satisfying every material "
            f"requirement: {checkpoint.assessment.decision.value}. "
            f"{checkpoint.assessment.rationale}"
        )
        if human_review_required
        else None
    )
    return MultiAgentFanOutReport(
        investigation_id=checkpoint.investigation_id,
        parent_claim_id=checkpoint.claim.parent_claim_id or checkpoint.claim.claim_id,
        component_id=checkpoint.claim.claim_id,
        assignments=checkpoint.assignments,
        results=checkpoint.results,
        consolidation=checkpoint.consolidation,
        role_metrics=metrics,
        consumption=checkpoint.rounds[-1].consumption,
        rounds=checkpoint.rounds,
        final_assessment=checkpoint.assessment,
        human_review_required=human_review_required,
        human_review_reason=human_review_reason,
        unresolved_requirement_ids=unresolved,
        duplicate_result_references_removed=(checkpoint.duplicate_result_references_removed),
    )


def _consumption(checkpoint: MultiAgentWorkflowCheckpoint) -> ResearchConsumption:
    return ResearchConsumption(
        completed_rounds=max(item.round_number for item in checkpoint.assignments),
        role_activations=len(checkpoint.assignments),
        search_calls=sum(item.search_call_count for item in checkpoint.results),
        fetched_pages=sum(item.fetch_call_count for item in checkpoint.results),
        model_calls=sum(item.model_call_count for item in checkpoint.results),
        total_tokens=sum(item.token_count for item in checkpoint.results),
        duration_seconds=sum(item.duration_seconds for item in checkpoint.results),
        estimated_cost_usd=sum(item.estimated_cost_usd for item in checkpoint.results),
    )


def _apply_shared_candidate_budget(
    checkpoint: MultiAgentWorkflowCheckpoint,
    assignments: tuple[ResearchAssignment, ...],
) -> tuple[ResearchAssignment, ...]:
    """Allocate the component-wide page/model ceiling before concurrent fan-out."""
    if not assignments:
        return assignments
    consumed_pages = sum(item.fetch_call_count for item in checkpoint.results)
    page_capacity = max(
        0,
        checkpoint.budget.maximum_pages_per_component - consumed_pages,
    )
    consumed_models = sum(item.model_call_count for item in checkpoint.results)
    model_capacity = max(0, checkpoint.budget.maximum_model_calls - consumed_models)
    candidate_capacity = page_capacity
    if checkpoint.budget.maximum_model_calls > 0:
        candidate_capacity = min(candidate_capacity, model_capacity)
    quotient, remainder = divmod(candidate_capacity, len(assignments))
    bounded: list[ResearchAssignment] = []
    for index, assignment in enumerate(assignments):
        allowance = quotient + (1 if index < remainder else 0)
        # A zero allowance cannot be represented by the typed assignment contract.
        # Omit it; the sufficiency controller will preserve the unmet requirement.
        if allowance < 1:
            continue
        bounded.append(
            assignment.model_copy(
                update={
                    "candidate_limit_per_query": min(
                        assignment.candidate_limit_per_query,
                        allowance,
                    )
                }
            )
        )
    return tuple(bounded)


def _sufficiency_context(
    checkpoint: MultiAgentWorkflowCheckpoint,
    *,
    consumption: ResearchConsumption,
    last_round_gain: EvidenceGain,
) -> SufficiencyContext:
    if checkpoint.consolidation is None:
        raise ValueError("sufficiency context requires consolidated evidence")
    return SufficiencyContext(
        investigation_id=checkpoint.investigation_id,
        component_id=checkpoint.claim.claim_id,
        requirements=checkpoint.requirements,
        sources=checkpoint.consolidation.sources,
        evidence=checkpoint.consolidation.evidence,
        independence=checkpoint.consolidation.independence,
        attempted_roles=frozenset(item.role for item in checkpoint.assignments),
        last_round_gain=last_round_gain,
        consumption=consumption,
        budget=checkpoint.budget,
    )


def _progress_snapshot(
    checkpoint: MultiAgentWorkflowCheckpoint,
    satisfied: frozenset[UUID],
) -> EvidenceProgressSnapshot:
    assert checkpoint.consolidation is not None
    evidence = checkpoint.consolidation.evidence
    return EvidenceProgressSnapshot(
        covered_component_ids=(frozenset({checkpoint.claim.claim_id}) if evidence else frozenset()),
        satisfied_requirement_ids=satisfied,
        independent_family_ids=frozenset(
            uuid5(
                NAMESPACE_URL,
                "|".join(sorted(family.hostnames))
                or "|".join(sorted(str(item) for item in family.source_ids)),
            )
            for family in checkpoint.consolidation.independence.families
            if family.source_ids
        ),
        challenge_evidence_ids=frozenset(
            item.evidence_id
            for item in evidence
            if item.stance in {EvidenceStance.CONTRADICTS, EvidenceStance.QUALIFIES}
        ),
    )
