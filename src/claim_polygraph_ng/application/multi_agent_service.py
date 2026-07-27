"""Minimum offline-verifiable Phase 4 multi-agent workflow."""

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from claim_polygraph_ng.analysis import (
    assess_evidence_sufficiency,
    consolidate_evidence,
    route_research_roles,
)
from claim_polygraph_ng.application.research_executor import (
    ResearchExecutor,
    ResearchWorker,
    SharedResearchOperations,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    AuditIssue,
    Evidence,
    EvidenceGain,
    EvidenceStance,
    ExtractionStatus,
    ModelTask,
    ResearchBudget,
    ResearchConsumption,
    ResearchPath,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchResult,
    ResearchRole,
    ResearchRoutingRequest,
    SearchRequest,
    SentenceAudit,
    Source,
    SufficiencyContext,
    SufficiencyDecision,
    SupportLevel,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.domain.research import (
    MultiAgentInvestigationReport,
    MultiAgentWorkflowCheckpoint,
    MultiAgentWorkflowStage,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository
from claim_polygraph_ng.providers import StructuredModelProvider

_ROLE_PATH = {
    ResearchRole.PRIMARY_SOURCE: ResearchPath.PRIMARY,
    ResearchRole.GENERAL_EVIDENCE: ResearchPath.GENERAL,
    ResearchRole.CHALLENGER: ResearchPath.CONTRADICTION,
    ResearchRole.ACADEMIC: ResearchPath.ACADEMIC,
    ResearchRole.FACT_CHECK: ResearchPath.FACT_CHECK,
}


class DeterministicResearchWorker:
    """Development worker that turns retrieved fixture text into stored evidence."""

    def __init__(self, repository: SQLiteResearchRepository) -> None:
        self._repository = repository

    async def run(self, assignment, operations: SharedResearchOperations) -> ResearchResult:
        path = _ROLE_PATH[assignment.role]
        query = f"{path.value}: {assignment.claim_text}"[:1_000]
        query_id = uuid4()
        results = await operations.search(
            SearchRequest(
                claim_id=assignment.component_id,
                query=query,
                research_path=path,
                maximum_results=min(assignment.candidate_limit_per_query, 20),
            )
        )
        source_ids: list[UUID] = []
        evidence_ids: list[UUID] = []
        fetch_calls = 0
        for result in results[: assignment.candidate_limit_per_query]:
            if result.inline_content:
                passage = result.inline_content
                final_url = str(result.url)
                retrieved_at = datetime.now(UTC)
            else:
                document = await operations.fetch(str(result.url))
                passage = document.text
                final_url = str(document.final_url)
                retrieved_at = document.retrieved_at
                fetch_calls += 1
            if not passage.strip():
                continue
            source = Source(
                url=result.url,
                canonical_url=final_url,
                title=result.title,
                source_type=result.source_type,
                publisher=result.publisher,
                retrieved_at=retrieved_at,
                content_hash=hashlib.sha256(passage.encode()).hexdigest(),
                extraction_status=ExtractionStatus.EXTRACTED,
            )
            stance = (
                EvidenceStance.QUALIFIES
                if assignment.role is ResearchRole.CHALLENGER
                else EvidenceStance.SUPPORTS
            )
            evidence = Evidence(
                claim_id=assignment.component_id,
                source_id=source.source_id,
                passage=passage[:20_000],
                stance=stance,
                relevance_score=0.9,
            )
            self._repository.save_source(source)
            self._repository.save_evidence(evidence)
            source_ids.append(source.source_id)
            evidence_ids.append(evidence.evidence_id)
        return ResearchResult(
            assignment_id=assignment.assignment_id,
            role=assignment.role,
            component_id=assignment.component_id,
            query_ids=(query_id,),
            source_ids=tuple(source_ids),
            evidence_ids=tuple(evidence_ids),
            search_call_count=1,
            fetch_call_count=fetch_calls,
            model_call_count=0,
            estimated_cost_usd=0.0,
            duration_seconds=0.0,
        )


class StructuredResearchWorker(DeterministicResearchWorker):
    """Classify retrieved passages with one schema-constrained model call each."""

    def __init__(
        self,
        repository: SQLiteResearchRepository,
        model_provider: StructuredModelProvider,
    ) -> None:
        super().__init__(repository)
        self._model_provider = model_provider
        self._repository = repository
        self._model_lock = asyncio.Lock()

    async def run(self, assignment, operations: SharedResearchOperations) -> ResearchResult:
        path = _ROLE_PATH[assignment.role]
        query = f"{path.value}: {assignment.claim_text}"[:1_000]
        query_id = uuid4()
        results = await operations.search(
            SearchRequest(
                claim_id=assignment.component_id,
                query=query,
                research_path=path,
                maximum_results=min(assignment.candidate_limit_per_query, 20),
            )
        )
        source_ids: list[UUID] = []
        evidence_ids: list[UUID] = []
        fetch_calls = 0
        model_calls = 0
        estimated_cost = 0.0
        for result in results[: assignment.candidate_limit_per_query]:
            if result.inline_content:
                passage = result.inline_content
                final_url = str(result.url)
                retrieved_at = datetime.now(UTC)
            else:
                document = await operations.fetch(str(result.url))
                passage = document.text
                final_url = str(document.final_url)
                retrieved_at = document.retrieved_at
                fetch_calls += 1
            passage = passage.strip()[:20_000]
            if not passage:
                continue
            source = Source(
                url=result.url,
                canonical_url=final_url,
                title=result.title,
                source_type=result.source_type,
                publisher=result.publisher,
                retrieved_at=retrieved_at,
                content_hash=hashlib.sha256(passage.encode()).hexdigest(),
                extraction_status=ExtractionStatus.EXTRACTED,
            )
            chunk_id = uuid4()
            async with self._model_lock:
                evidence = await self._model_provider.generate(
                    task=ModelTask.CLASSIFY_EVIDENCE,
                    response_model=Evidence,
                    inputs={
                        "claim_id": str(assignment.component_id),
                        "claim": {
                            "text": assignment.claim_text,
                            "retained_context": list(assignment.retained_context),
                        },
                        "source_id": str(source.source_id),
                        "chunk_id": str(chunk_id),
                        "passage": passage,
                        "passage_start_char": 0,
                        "passage_end_char": len(passage),
                        "retrieval_score": 1.0,
                        "research_path": path.value,
                    },
                )
                model_calls += 1
                take_usage = getattr(self._model_provider, "take_last_usage", None)
                if callable(take_usage):
                    usage = take_usage()
                    if usage is not None and usage.estimated_cost_usd is not None:
                        estimated_cost += usage.estimated_cost_usd
            self._repository.save_source(source)
            self._repository.save_evidence(evidence)
            source_ids.append(source.source_id)
            evidence_ids.append(evidence.evidence_id)
        return ResearchResult(
            assignment_id=assignment.assignment_id,
            role=assignment.role,
            component_id=assignment.component_id,
            query_ids=(query_id,),
            source_ids=tuple(source_ids),
            evidence_ids=tuple(evidence_ids),
            search_call_count=1,
            fetch_call_count=fetch_calls,
            model_call_count=model_calls,
            estimated_cost_usd=round(estimated_cost, 9),
            duration_seconds=0.0,
        )


class MultiAgentInvestigationService:
    """Coordinate the minimum team while preserving a resumable typed packet."""

    def __init__(
        self,
        *,
        repository: SQLiteResearchRepository,
        operations: SharedResearchOperations,
        worker: ResearchWorker | None = None,
    ) -> None:
        self._repository = repository
        self._operations = operations
        self._worker = worker or DeterministicResearchWorker(repository)
        self._repository.initialize()

    async def investigate(
        self,
        claim: AtomicClaim,
        requirements: tuple[ResearchRequirement, ...],
        *,
        budget: ResearchBudget | None = None,
    ) -> MultiAgentInvestigationReport:
        active_budget = budget or ResearchBudget()
        investigation_id = uuid4()
        route = route_research_roles(
            ResearchRoutingRequest(
                investigation_id=investigation_id,
                parent_claim_id=claim.parent_claim_id or claim.claim_id,
                component_id=claim.claim_id,
                claim_text=claim.text,
                retained_context=claim.retained_context,
                claim_types=frozenset({claim.claim_type}),
                requirements=requirements,
                budget=active_budget,
            )
        )
        checkpoint = MultiAgentWorkflowCheckpoint(
            investigation_id=investigation_id,
            claim=claim,
            requirements=requirements,
            budget=active_budget,
            stage=MultiAgentWorkflowStage.PLANNED,
            assignments=route.assignments,
        )
        self._repository.save_workflow(checkpoint)
        return await self.resume(investigation_id)

    async def resume(self, investigation_id: UUID) -> MultiAgentInvestigationReport:
        checkpoint = self._repository.get_workflow(investigation_id)
        if checkpoint is None:
            raise ValueError(f"multi-agent workflow not found: {investigation_id}")
        if checkpoint.stage is MultiAgentWorkflowStage.PLANNED:
            executor = ResearchExecutor(
                repository=self._repository,
                operations=self._operations,
                worker=self._worker,
                maximum_concurrency=checkpoint.budget.maximum_concurrent_roles,
            )
            results = await executor.execute(checkpoint.assignments)
            checkpoint = checkpoint.model_copy(
                update={
                    "stage": MultiAgentWorkflowStage.RESEARCHED,
                    "results": results,
                }
            )
            self._repository.save_workflow(checkpoint)

        if checkpoint.stage is MultiAgentWorkflowStage.RESEARCHED:
            source_ids = tuple(
                dict.fromkeys(
                    source_id for result in checkpoint.results for source_id in result.source_ids
                )
            )
            evidence_ids = tuple(
                dict.fromkeys(
                    evidence_id
                    for result in checkpoint.results
                    for evidence_id in result.evidence_ids
                )
            )
            sources = self._repository.get_sources(source_ids)
            evidence = self._repository.get_evidence(evidence_ids)
            if len(sources) != len(source_ids) or len(evidence) != len(evidence_ids):
                raise ValueError("research result references an unstored source or evidence item")
            required_families = max(
                (
                    item.minimum_independent_families
                    for item in checkpoint.requirements
                    if item.kind is ResearchRequirementKind.INDEPENDENT_CORROBORATION
                ),
                default=1,
            )
            consolidation = consolidate_evidence(
                claim_id=checkpoint.claim.claim_id,
                sources=sources,
                evidence=evidence,
                required_families=required_families,
            )
            checkpoint = checkpoint.model_copy(
                update={
                    "stage": MultiAgentWorkflowStage.CONSOLIDATED,
                    "consolidation": consolidation,
                }
            )
            self._repository.save_workflow(checkpoint)

        if checkpoint.stage is MultiAgentWorkflowStage.CONSOLIDATED:
            assert checkpoint.consolidation is not None
            successful = tuple(item for item in checkpoint.results if item.failure_reason is None)
            gain = EvidenceGain(
                newly_covered_component_ids=(
                    (checkpoint.claim.claim_id,) if checkpoint.consolidation.evidence else ()
                ),
                newly_satisfied_requirement_ids=(uuid4(),)
                if checkpoint.consolidation.evidence
                else (),
            )
            assessment = assess_evidence_sufficiency(
                SufficiencyContext(
                    investigation_id=checkpoint.investigation_id,
                    component_id=checkpoint.claim.claim_id,
                    requirements=checkpoint.requirements,
                    sources=checkpoint.consolidation.sources,
                    evidence=checkpoint.consolidation.evidence,
                    independence=checkpoint.consolidation.independence,
                    attempted_roles=frozenset(item.role for item in successful),
                    last_round_gain=gain,
                    consumption=ResearchConsumption(
                        completed_rounds=1,
                        role_activations=len(checkpoint.assignments),
                        search_calls=sum(item.search_call_count for item in checkpoint.results),
                        fetched_pages=sum(item.fetch_call_count for item in checkpoint.results),
                        model_calls=sum(item.model_call_count for item in checkpoint.results),
                        estimated_cost_usd=sum(
                            item.estimated_cost_usd for item in checkpoint.results
                        ),
                    ),
                    budget=checkpoint.budget,
                )
            )
            checkpoint = checkpoint.model_copy(
                update={
                    "stage": MultiAgentWorkflowStage.ASSESSED,
                    "assessment": assessment,
                }
            )
            self._repository.save_workflow(checkpoint)

        if checkpoint.stage is MultiAgentWorkflowStage.ASSESSED:
            assert checkpoint.consolidation is not None
            assert checkpoint.assessment is not None
            verdict, audit = _build_grounded_verdict(
                checkpoint.claim,
                checkpoint.consolidation.evidence,
                checkpoint.assessment,
            )
            checkpoint = checkpoint.model_copy(
                update={
                    "stage": MultiAgentWorkflowStage.COMPLETE,
                    "verdict": verdict,
                    "audit": audit,
                }
            )
            self._repository.save_workflow(checkpoint)

        assert checkpoint.consolidation is not None
        assert checkpoint.assessment is not None
        assert checkpoint.verdict is not None
        assert checkpoint.audit is not None
        return MultiAgentInvestigationReport(
            investigation_id=checkpoint.investigation_id,
            claim=checkpoint.claim,
            requirements=checkpoint.requirements,
            assignments=checkpoint.assignments,
            results=checkpoint.results,
            consolidation=checkpoint.consolidation,
            assessment=checkpoint.assessment,
            verdict=checkpoint.verdict,
            audit=checkpoint.audit,
        )


def _build_grounded_verdict(
    claim: AtomicClaim,
    evidence: tuple[Evidence, ...],
    assessment,
) -> tuple[Verdict, SentenceAudit]:
    usable = tuple(item for item in evidence if item.stance is not EvidenceStance.IRRELEVANT)
    stances = {item.stance for item in usable}
    if not usable:
        label = VerdictLabel.UNVERIFIABLE
    elif EvidenceStance.CONTRADICTS in stances and EvidenceStance.SUPPORTS not in stances:
        label = VerdictLabel.CONTRADICTED
    elif EvidenceStance.SUPPORTS in stances and stances <= {
        EvidenceStance.SUPPORTS,
        EvidenceStance.CONTEXT,
    }:
        label = VerdictLabel.SUPPORTED
    elif EvidenceStance.QUALIFIES in stances and EvidenceStance.SUPPORTS not in stances:
        label = VerdictLabel.MISLEADING
    else:
        label = VerdictLabel.MIXED
    cited = tuple(item.evidence_id for item in usable)
    explanation = f"The approved evidence packet yields a {label.value} assessment for the claim."
    verdict = Verdict(
        claim_id=claim.claim_id,
        label=label,
        concise_explanation=explanation,
        detailed_reasoning=(
            "The verdict is deterministically constrained to stored evidence identifiers; "
            "the research roles cannot introduce external evidence at judgment time."
        ),
        decisive_evidence_ids=cited,
        human_review_required=assessment.decision is not SufficiencyDecision.SUFFICIENT,
        review_reason=(
            assessment.rationale
            if assessment.decision is not SufficiencyDecision.SUFFICIENT
            else None
        ),
    )
    if cited:
        audit = SentenceAudit(
            sentence=explanation,
            cited_evidence_ids=cited,
            support_level=SupportLevel.FULL,
        )
    else:
        audit = SentenceAudit(
            sentence=explanation,
            support_level=SupportLevel.NONE,
            issue_type=AuditIssue.MISSING_CITATION,
            explanation="No stored evidence passage is available to support a material verdict.",
        )
    return verdict, audit
