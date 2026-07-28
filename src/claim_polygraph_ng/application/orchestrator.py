"""One authority-preserving contract for every investigation orchestration mode."""

from collections.abc import Awaitable, Callable
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import NAMESPACE_URL, UUID, uuid5

from claim_polygraph_ng.application.langgraph_argument import (
    LangGraphAdversarialArgumentWorkflow,
)
from claim_polygraph_ng.application.langgraph_durable import (
    DurableFixtureLangGraphWorkflow,
    ExistingGraphThreadError,
)
from claim_polygraph_ng.application.langgraph_research import (
    LangGraphResearchFanOutWorkflow,
)
from claim_polygraph_ng.application.multi_agent_service import MultiAgentInvestigationService
from claim_polygraph_ng.domain.graph import (
    DurableAssignmentReference,
    DurableComponentReference,
    DurableEvidenceFamilyReference,
    DurableMultiAgentGraphState,
    DurableRequirementReference,
    DurableResultReference,
    DurableUnresolvedQuestion,
    FixtureGraphRequest,
)
from claim_polygraph_ng.domain.investigation import InvestigationReport
from claim_polygraph_ng.domain.research import (
    MultiAgentFanOutReport,
    MultiAgentInvestigationReport,
    ResearchBudget,
    ResearchConsumption,
    ResearchRequirement,
    ResearchRequirementKind,
)
from claim_polygraph_ng.domain.review import ReviewRequest
from claim_polygraph_ng.persistence.review import SQLiteReviewLedger
from claim_polygraph_ng.telemetry import TelemetryCollector


class OrchestratorMode(StrEnum):
    """Closed product-facing orchestration choices."""

    LANGGRAPH = "langgraph"
    DIRECT = "direct"
    MULTI_AGENT_EXPERIMENTAL = "multi_agent_experimental"


@runtime_checkable
class InvestigationOrchestrator(Protocol):
    """Common boundary that always returns the authoritative investigation report."""

    mode: OrchestratorMode
    authoritative_service: str

    async def investigate(self, claim: str) -> InvestigationReport: ...


class DirectInvestigationOrchestrator:
    """Explicit rollback adapter with no graph or experimental research side effects."""

    mode = OrchestratorMode.DIRECT
    authoritative_service = "InvestigationService"

    def __init__(
        self,
        investigate_authoritatively: Callable[[str], Awaitable[InvestigationReport]],
    ) -> None:
        self._investigate_authoritatively = investigate_authoritatively

    async def investigate(self, claim: str) -> InvestigationReport:
        return await self._investigate_authoritatively(claim)


class LangGraphInvestigationOrchestrator:
    """Run authoritative investigation work, then durably orchestrate its disposition."""

    mode = OrchestratorMode.LANGGRAPH
    authoritative_service = "InvestigationService"

    def __init__(
        self,
        *,
        investigate_authoritatively: Callable[[str], Awaitable[InvestigationReport]],
        checkpoint_path: str | Path,
        reviews: SQLiteReviewLedger,
        research_fan_out: LangGraphResearchFanOutWorkflow | None = None,
        argument_workflow: LangGraphAdversarialArgumentWorkflow | None = None,
        review_created_by: str = "langgraph-review-router",
        telemetry: TelemetryCollector | None = None,
    ) -> None:
        self._investigate_authoritatively = investigate_authoritatively
        self._checkpoint_path = Path(checkpoint_path)
        self._reviews = reviews
        self._research_fan_out = research_fan_out
        self._argument_workflow = argument_workflow
        self._review_created_by = review_created_by
        self._telemetry = telemetry
        self._reviews.initialize()

    async def investigate(self, claim: str) -> InvestigationReport:
        """Preserve the authoritative report while making LangGraph the default journey."""
        report = await self._investigate_authoritatively(claim)
        investigation_id = report.investigation.investigation_id
        requirements = _requirements(report)
        research_state = _durable_research_state(report, requirements)
        research_review_required = False
        research_review_reason = None
        if self._research_fan_out is not None:
            fan_out = await self._research_fan_out.start_or_resume(
                investigation_id=investigation_id,
                claim=report.claim,
                requirements=requirements,
                budget=ResearchBudget(
                    maximum_rounds=2,
                    maximum_concurrent_roles=3,
                    maximum_role_activations_per_component=5,
                    maximum_pages_per_component=50,
                    maximum_model_calls=0,
                    maximum_cost_usd=0,
                ),
            )
            research_state = _merge_fan_out_state(research_state, fan_out)
            research_review_required = fan_out.human_review_required
            research_review_reason = fan_out.human_review_reason
        argument_review_required = False
        argument_review_reason = None
        if self._argument_workflow is not None:
            argument_report = await self._argument_workflow.start_or_resume(
                investigation_id=investigation_id,
                claim=report.claim,
                approved_evidence=report.evidence,
                authoritative_ledger=report.argument_ledger,
                verification=report.verification_packet,
                provenance=report.provenance,
            )
            research_state = research_state.model_copy(
                update={
                    "argument_role_result_ids": tuple(
                        item.result_id for item in argument_report.results
                    ),
                    "reconciled_argument_ledger": argument_report.reconciled_ledger,
                }
            )
            argument_review_required = argument_report.human_review_required
            argument_review_reason = argument_report.human_review_reason
        request = FixtureGraphRequest(
            graph_run_id=investigation_id,
            claim_text=report.claim.text,
            approved_evidence_ids=tuple(item.evidence_id for item in report.evidence),
            authoritative_verdict=report.verdict.label,
            review_required=(
                report.verdict.human_review_required
                or research_review_required
                or argument_review_required
            ),
            review_reason=(
                report.verdict.review_reason or research_review_reason or argument_review_reason
            ),
            research_state=research_state,
        )
        with DurableFixtureLangGraphWorkflow(
            self._checkpoint_path,
            enabled=True,
            telemetry=self._telemetry,
        ) as workflow:
            try:
                snapshot = workflow.start(request)
            except ExistingGraphThreadError:
                snapshot = workflow.snapshot(str(investigation_id))
        if snapshot.interrupt is not None and not self._review_exists(investigation_id):
            self._reviews.create_request(
                ReviewRequest(
                    investigation_id=investigation_id,
                    graph_thread_id=str(investigation_id),
                    claim_id=report.claim.claim_id,
                    reason=snapshot.interrupt.route_reason,
                    created_by=self._review_created_by,
                )
            )
        return report

    def _review_exists(self, investigation_id: UUID) -> bool:
        return any(
            item.investigation_id == investigation_id for item in self._reviews.list_requests()
        )


class ExperimentalMultiAgentInvestigationOrchestrator:
    """Run bounded multi-agent research without changing authoritative outputs."""

    mode = OrchestratorMode.MULTI_AGENT_EXPERIMENTAL
    authoritative_service = "InvestigationService"

    def __init__(
        self,
        *,
        investigate_authoritatively: Callable[[str], Awaitable[InvestigationReport]],
        multi_agent_service: MultiAgentInvestigationService,
        record_result: Callable[[InvestigationReport, MultiAgentInvestigationReport], None]
        | None = None,
        budget: ResearchBudget | None = None,
    ) -> None:
        self._investigate_authoritatively = investigate_authoritatively
        self._multi_agent_service = multi_agent_service
        self._record_result = record_result
        self._budget = budget or ResearchBudget(
            maximum_rounds=2,
            maximum_concurrent_roles=4,
            maximum_cost_usd=0,
        )

    async def investigate(self, claim: str) -> InvestigationReport:
        authoritative = await self._investigate_authoritatively(claim)
        experimental = await self._multi_agent_service.investigate(
            authoritative.claim,
            _requirements(authoritative),
            budget=self._budget,
        )
        if self._record_result is not None:
            self._record_result(authoritative, experimental)
        return authoritative


def parse_orchestrator_mode(value: str) -> OrchestratorMode:
    """Validate external configuration without accepting aliases or silent fallback."""
    try:
        return OrchestratorMode(value.strip().casefold())
    except ValueError as error:
        choices = ", ".join(item.value for item in OrchestratorMode)
        raise ValueError(f"orchestrator must be one of: {choices}") from error


def _requirements(report: InvestigationReport) -> tuple[ResearchRequirement, ...]:
    claim_id = report.claim.claim_id
    def requirement_id(kind: ResearchRequirementKind) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"claim-polygraph:{claim_id}:research-requirement:{kind.value}",
        )

    requirements = [
        ResearchRequirement(
            requirement_id=requirement_id(ResearchRequirementKind.COMPONENT_COVERAGE),
            component_id=claim_id,
            kind=ResearchRequirementKind.COMPONENT_COVERAGE,
            rationale="The material claim requires directly relevant evidence.",
        ),
        ResearchRequirement(
            requirement_id=requirement_id(
                ResearchRequirementKind.INDEPENDENT_CORROBORATION
            ),
            component_id=claim_id,
            kind=ResearchRequirementKind.INDEPENDENT_CORROBORATION,
            minimum_independent_families=report.plan.minimum_independent_families,
            rationale="The claim requires independently produced corroboration.",
        ),
        ResearchRequirement(
            requirement_id=requirement_id(
                ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION
            ),
            component_id=claim_id,
            kind=ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION,
            rationale="A challenger must seek contradiction and material qualification.",
        ),
    ]
    if any(path.value == "primary" for path in report.plan.required_research_paths):
        requirements.append(
            ResearchRequirement(
                requirement_id=requirement_id(ResearchRequirementKind.PRIMARY_SOURCE),
                component_id=claim_id,
                kind=ResearchRequirementKind.PRIMARY_SOURCE,
                rationale="The authoritative plan requires primary-source evidence.",
            )
        )
    if any(path.value == "academic" for path in report.plan.required_research_paths):
        requirements.append(
            ResearchRequirement(
                requirement_id=requirement_id(ResearchRequirementKind.ACADEMIC_EVIDENCE),
                component_id=claim_id,
                kind=ResearchRequirementKind.ACADEMIC_EVIDENCE,
                rationale="The authoritative plan requires academic evidence.",
            )
        )
    if any(path.value == "fact_check" for path in report.plan.required_research_paths):
        requirements.append(
            ResearchRequirement(
                requirement_id=requirement_id(ResearchRequirementKind.PRIOR_FACT_CHECK),
                component_id=claim_id,
                kind=ResearchRequirementKind.PRIOR_FACT_CHECK,
                rationale="The authoritative plan requires prior fact-check evidence.",
            )
        )
    return tuple(requirements)


def _durable_research_state(
    report: InvestigationReport,
    requirements: tuple[ResearchRequirement, ...],
) -> DurableMultiAgentGraphState:
    """Project authoritative artifacts into bounded graph checkpoint references."""

    claim = report.claim
    parent_claim_id = claim.parent_claim_id or claim.claim_id
    families = (
        tuple(
            DurableEvidenceFamilyReference(
                family_id=family.family_id,
                source_ids=family.source_ids,
                evidence_ids=family.evidence_ids,
                grouping_summary=(
                    f"Potentially dependent evidence from {', '.join(family.hostnames[:3])}."
                    if family.hostnames
                    else "Potentially dependent evidence family."
                ),
            )
            for family in report.independence_analysis.families
        )
        if report.independence_analysis is not None
        else ()
    )
    return DurableMultiAgentGraphState(
        investigation_id=report.investigation.investigation_id,
        parent_claim_id=parent_claim_id,
        components=(
            DurableComponentReference(
                component_id=claim.claim_id,
                parent_claim_id=parent_claim_id,
                claim_summary=claim.text[:500],
            ),
        ),
        requirements=tuple(
            DurableRequirementReference(
                requirement_id=item.requirement_id,
                component_id=item.component_id,
                kind=item.kind,
                rationale_summary=item.rationale[:500],
            )
            for item in requirements
        ),
        stored_source_ids=tuple(item.source_id for item in report.sources),
        stored_evidence_ids=tuple(item.evidence_id for item in report.evidence),
        approved_evidence_ids=tuple(item.evidence_id for item in report.evidence),
        evidence_families=families,
        budget=ResearchBudget(maximum_cost_usd=0),
        consumption=ResearchConsumption(
            completed_rounds=0,
            role_activations=0,
            search_calls=0,
            fetched_pages=0,
            model_calls=0,
            estimated_cost_usd=0,
        ),
        unresolved_questions=tuple(
            DurableUnresolvedQuestion(
                component_id=claim.claim_id,
                question_summary=question[:500],
            )
            for question in report.verdict.unresolved_questions
        ),
    )


def _merge_fan_out_state(
    state: DurableMultiAgentGraphState,
    fan_out: MultiAgentFanOutReport,
) -> DurableMultiAgentGraphState:
    """Attach authority-isolated candidate research references to graph state."""

    candidate_families = tuple(
        DurableEvidenceFamilyReference(
            family_id=family.family_id,
            source_ids=family.source_ids,
            evidence_ids=family.evidence_ids,
            grouping_summary="Candidate family produced by LangGraph research fan-in.",
        )
        for family in fan_out.consolidation.independence.families
    )
    unresolved = tuple(
        DurableUnresolvedQuestion(
            component_id=fan_out.component_id,
            requirement_ids=(requirement_id,),
            question_summary="A routed research requirement remains unresolved.",
        )
        for requirement_id in fan_out.unresolved_requirement_ids
    )
    merged = state.model_copy(
        update={
            "assignments": tuple(
                DurableAssignmentReference(
                    assignment_id=item.assignment_id,
                    component_id=item.component_id,
                    role=item.role,
                    round_number=item.round_number,
                    requirement_ids=item.requirement_ids,
                )
                for item in fan_out.assignments
            ),
            "results": tuple(
                DurableResultReference(
                    result_id=item.result_id,
                    assignment_id=item.assignment_id,
                    component_id=item.component_id,
                    source_ids=item.source_ids,
                    evidence_ids=item.evidence_ids,
                    unresolved_requirement_ids=item.unresolved_requirement_ids,
                    failure_summary=item.failure_reason,
                )
                for item in fan_out.results
            ),
            "stored_source_ids": tuple(
                dict.fromkeys(
                    (
                        *state.stored_source_ids,
                        *(
                            source_id
                            for result in fan_out.results
                            for source_id in result.source_ids
                        ),
                        *(item.source_id for item in fan_out.consolidation.sources),
                    )
                )
            ),
            "stored_evidence_ids": tuple(
                dict.fromkeys(
                    (
                        *state.stored_evidence_ids,
                        *(
                            evidence_id
                            for result in fan_out.results
                            for evidence_id in result.evidence_ids
                        ),
                        *(item.evidence_id for item in fan_out.consolidation.evidence),
                    )
                )
            ),
            "evidence_families": tuple(
                {
                    item.family_id: item for item in (*state.evidence_families, *candidate_families)
                }.values()
            ),
            "budget": ResearchBudget(
                maximum_rounds=2,
                maximum_concurrent_roles=3,
                maximum_role_activations_per_component=5,
                maximum_pages_per_component=50,
                maximum_model_calls=0,
                maximum_cost_usd=0,
            ),
            "consumption": fan_out.consumption,
            "unresolved_questions": (*state.unresolved_questions, *unresolved),
        }
    )
    return DurableMultiAgentGraphState.model_validate(merged.model_dump())
