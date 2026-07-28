"""Concurrent, cached and resumable LangGraph research fan-out tests."""

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from claim_polygraph_ng.analysis import route_research_roles
from claim_polygraph_ng.application import (
    LangGraphResearchFanOutWorkflow,
    ResearchExecutor,
    SharedResearchOperations,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    ClaimType,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    ResearchBudget,
    ResearchPath,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchResult,
    ResearchRole,
    ResearchRoutingRequest,
    SearchRequest,
    SearchResult,
    Source,
    SourceType,
    SufficiencyDecision,
)
from claim_polygraph_ng.domain.research import (
    MultiAgentWorkflowCheckpoint,
    MultiAgentWorkflowStage,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository


class SharedCandidateSearch:
    provider_id = "shared-fanout-search"

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, _request):
        self.calls += 1
        await asyncio.sleep(0.02)
        return (
            SearchResult(
                url="https://example.org/shared-candidate",
                title="Shared candidate",
                snippet="Candidate metadata only.",
                inline_content="The same retained fixture passage.",
                source_type=SourceType.PRIMARY_DOCUMENT,
                publisher="Fixture Publisher",
            ),
        )


class NeverFetch:
    provider_id = "never-fetch"

    async def fetch(self, _url):
        raise AssertionError("inline fixture content must not be fetched")


class ConcurrentFixtureWorker:
    def __init__(
        self,
        repository: SQLiteResearchRepository,
        *,
        fail_challenger: bool = False,
    ) -> None:
        self.repository = repository
        self.fail_challenger = fail_challenger
        self.active = 0
        self.maximum_active = 0
        self.calls = 0

    async def run(self, assignment, operations):
        self.calls += 1
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            await asyncio.sleep(0.03)
            if self.fail_challenger and assignment.role.value == "challenger":
                raise RuntimeError("isolated challenger fixture failure")
            results = await operations.search(_shared_request(assignment.component_id))
            passage = results[0].inline_content or ""
            source = Source(
                url=results[0].url,
                canonical_url=results[0].url,
                title=results[0].title,
                source_type=results[0].source_type,
                publisher=results[0].publisher,
                retrieved_at=datetime.now(UTC),
                content_hash=hashlib.sha256(passage.encode()).hexdigest(),
                extraction_status=ExtractionStatus.EXTRACTED,
            )
            evidence = Evidence(
                claim_id=assignment.component_id,
                source_id=source.source_id,
                passage=passage,
                stance=EvidenceStance.SUPPORTS,
                relevance_score=0.9,
            )
            self.repository.save_source(source)
            self.repository.save_evidence(evidence)
            return ResearchResult(
                assignment_id=assignment.assignment_id,
                role=assignment.role,
                component_id=assignment.component_id,
                query_ids=(uuid4(),),
                source_ids=(source.source_id,),
                evidence_ids=(evidence.evidence_id,),
                search_call_count=1,
                fetch_call_count=0,
                model_call_count=0,
                estimated_cost_usd=0,
                duration_seconds=0,
            )
        finally:
            self.active -= 1


class IterativeFixtureWorker:
    """Return the missing challenge only in a targeted second round."""

    def __init__(self, repository, *, resolve_second_round: bool) -> None:
        self.repository = repository
        self.resolve_second_round = resolve_second_round
        self.calls = []

    async def run(self, assignment, _operations):
        self.calls.append((assignment.round_number, assignment.role))
        source_type = (
            SourceType.OFFICIAL
            if assignment.role is ResearchRole.PRIMARY_SOURCE
            else SourceType.NEWS
        )
        source = Source(
            url=(f"https://{assignment.role.value}.example/round-{assignment.round_number}"),
            canonical_url=(
                f"https://{assignment.role.value}.example/round-{assignment.round_number}"
            ),
            title="Iterative fixture source",
            source_type=source_type,
            retrieved_at=datetime.now(UTC),
            extraction_status=ExtractionStatus.EXTRACTED,
        )
        stance = (
            EvidenceStance.QUALIFIES
            if (
                self.resolve_second_round
                and assignment.role is ResearchRole.CHALLENGER
                and assignment.round_number == 2
            )
            else EvidenceStance.SUPPORTS
        )
        evidence = Evidence(
            claim_id=assignment.component_id,
            source_id=source.source_id,
            passage=(
                f"Round {assignment.round_number} {assignment.role.value} "
                f"{stance.value} fixture evidence."
            ),
            stance=stance,
            relevance_score=0.9,
        )
        self.repository.save_source(source)
        self.repository.save_evidence(evidence)
        return ResearchResult(
            assignment_id=assignment.assignment_id,
            role=assignment.role,
            component_id=assignment.component_id,
            query_ids=(uuid4(),),
            source_ids=(source.source_id,),
            evidence_ids=(evidence.evidence_id,),
            search_call_count=1,
            fetch_call_count=0,
            model_call_count=0,
            estimated_cost_usd=0,
            duration_seconds=0.001,
        )


def test_langgraph_fanout_is_concurrent_cached_deduplicated_and_resumable(
    tmp_path,
) -> None:
    repository = SQLiteResearchRepository(tmp_path / "fanout.db")
    search = SharedCandidateSearch()
    worker = ConcurrentFixtureWorker(repository)
    workflow = LangGraphResearchFanOutWorkflow(
        repository=repository,
        operations=SharedResearchOperations(
            repository=repository,
            search_provider=search,
            fetcher=NeverFetch(),
        ),
        worker=worker,
    )
    claim = _claim()
    investigation_id = uuid4()

    first = asyncio.run(
        workflow.start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            requirements=_requirements(claim.claim_id),
            budget=_budget(),
        )
    )
    calls_after_first = worker.calls
    resumed = asyncio.run(
        workflow.start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            requirements=_requirements(claim.claim_id),
            budget=_budget(),
        )
    )

    assert worker.maximum_active == 3
    assert search.calls == 1
    assert len(first.assignments) == len(first.results) == len(first.role_metrics) == 3
    assert len(first.consolidation.evidence) < sum(len(item.evidence_ids) for item in first.results)
    assert all(item.duration_seconds > 0 for item in first.role_metrics)
    assert first.consumption.role_activations == 3
    assert first.consumption.estimated_cost_usd == 0
    assert not first.authoritative_output_applied
    assert resumed == first
    assert worker.calls == calls_after_first
    checkpoint = repository.get_workflow(investigation_id)
    assert checkpoint is not None
    assert checkpoint.role_metrics == first.role_metrics


def test_one_role_failure_is_checkpointed_and_other_roles_survive(tmp_path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "failure.db")
    worker = ConcurrentFixtureWorker(repository, fail_challenger=True)
    workflow = LangGraphResearchFanOutWorkflow(
        repository=repository,
        operations=SharedResearchOperations(
            repository=repository,
            search_provider=SharedCandidateSearch(),
            fetcher=NeverFetch(),
        ),
        worker=worker,
    )
    claim = _claim()

    report = asyncio.run(
        workflow.start_or_resume(
            investigation_id=uuid4(),
            claim=claim,
            requirements=_requirements(claim.claim_id),
            budget=_budget(),
        )
    )

    failures = [item for item in report.results if item.failure_reason]
    assert len(failures) == 1
    assert "isolated challenger fixture failure" in failures[0].failure_reason
    assert len(report.consolidation.evidence) >= 1
    assert report.unresolved_requirement_ids
    assert sum(item.successful for item in report.role_metrics) == 2


def test_mid_round_restart_reuses_completed_assignment_and_finishes_fanout(
    tmp_path,
) -> None:
    repository = SQLiteResearchRepository(tmp_path / "mid-round.db")
    repository.initialize()
    search = SharedCandidateSearch()
    operations = SharedResearchOperations(
        repository=repository,
        search_provider=search,
        fetcher=NeverFetch(),
    )
    worker = ConcurrentFixtureWorker(repository)
    claim = _claim()
    requirements = _requirements(claim.claim_id)
    budget = _budget()
    investigation_id = uuid4()
    route = route_research_roles(
        ResearchRoutingRequest(
            investigation_id=investigation_id,
            parent_claim_id=claim.claim_id,
            component_id=claim.claim_id,
            claim_text=claim.text,
            retained_context=claim.retained_context,
            claim_types=frozenset({claim.claim_type}),
            requirements=requirements,
            budget=budget,
        )
    )
    repository.save_workflow(
        MultiAgentWorkflowCheckpoint(
            investigation_id=investigation_id,
            claim=claim,
            requirements=requirements,
            budget=budget,
            stage=MultiAgentWorkflowStage.PLANNED,
            assignments=route.assignments,
        )
    )
    first_result = asyncio.run(
        ResearchExecutor(
            repository=repository,
            operations=operations,
            worker=worker,
            maximum_concurrency=3,
        ).execute((route.assignments[0],))
    )[0]
    calls_at_restart = worker.calls

    report = asyncio.run(
        LangGraphResearchFanOutWorkflow(
            repository=repository,
            operations=operations,
            worker=worker,
        ).start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            requirements=requirements,
            budget=budget,
        )
    )

    assert report.results[0] == first_result
    assert worker.calls - calls_at_restart == 2
    assert search.calls == 1
    assert len(report.results) == 3


def test_iterative_controller_routes_only_missing_requirement_and_recovers(
    tmp_path,
) -> None:
    repository = SQLiteResearchRepository(tmp_path / "iterative-recovery.db")
    worker = IterativeFixtureWorker(repository, resolve_second_round=True)
    claim = _claim()
    report = asyncio.run(
        LangGraphResearchFanOutWorkflow(
            repository=repository,
            operations=SharedResearchOperations(
                repository=repository,
                search_provider=SharedCandidateSearch(),
                fetcher=NeverFetch(),
            ),
            worker=worker,
        ).start_or_resume(
            investigation_id=uuid4(),
            claim=claim,
            requirements=_requirements(claim.claim_id),
            budget=ResearchBudget(
                maximum_rounds=2,
                maximum_concurrent_roles=3,
                maximum_role_activations_per_component=4,
                maximum_model_calls=0,
                maximum_cost_usd=0,
            ),
        )
    )

    assert [item.role for item in report.assignments if item.round_number == 2] == [
        ResearchRole.CHALLENGER
    ]
    assert report.final_assessment.decision is SufficiencyDecision.SUFFICIENT
    assert len(report.rounds) == report.consumption.completed_rounds == 2
    assert not report.human_review_required
    assert report.rounds[1].routing_rationale


def test_iterative_controller_stops_on_zero_gain_and_escalates_review(
    tmp_path,
) -> None:
    repository = SQLiteResearchRepository(tmp_path / "iterative-no-gain.db")
    worker = IterativeFixtureWorker(repository, resolve_second_round=False)
    claim = _claim()
    investigation_id = uuid4()
    workflow = LangGraphResearchFanOutWorkflow(
        repository=repository,
        operations=SharedResearchOperations(
            repository=repository,
            search_provider=SharedCandidateSearch(),
            fetcher=NeverFetch(),
        ),
        worker=worker,
    )
    budget = ResearchBudget(
        maximum_rounds=3,
        maximum_concurrent_roles=3,
        maximum_role_activations_per_component=5,
        maximum_model_calls=0,
        maximum_cost_usd=0,
    )
    report = asyncio.run(
        workflow.start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            requirements=_requirements(claim.claim_id),
            budget=budget,
        )
    )
    resumed = asyncio.run(
        workflow.start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            requirements=_requirements(claim.claim_id),
            budget=budget,
        )
    )

    assert report.final_assessment.decision is SufficiencyDecision.STOP_DIMINISHING_RETURN
    assert report.rounds[-1].gain.material_gain_count == 0
    assert report.human_review_required
    assert "stop_diminishing_return" in (report.human_review_reason or "")
    assert resumed == report
    checkpoint = repository.get_workflow(investigation_id)
    assert checkpoint is not None
    assert checkpoint.stage is MultiAgentWorkflowStage.COMPLETE
    assert checkpoint.rounds == report.rounds


def _claim() -> AtomicClaim:
    return AtomicClaim(
        text="The programme improved outcomes for every participant.",
        claim_type=ClaimType.FACTUAL,
        retained_context=("Universal wording is material.",),
        checkworthiness=0.9,
    )


def _requirements(component_id):
    return tuple(
        ResearchRequirement(
            component_id=component_id,
            kind=kind,
            rationale=f"The component requires {kind.value.replace('_', ' ')} evidence.",
        )
        for kind in (
            ResearchRequirementKind.COMPONENT_COVERAGE,
            ResearchRequirementKind.PRIMARY_SOURCE,
            ResearchRequirementKind.INDEPENDENT_CORROBORATION,
            ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION,
        )
    )


def _budget() -> ResearchBudget:
    return ResearchBudget(
        maximum_rounds=1,
        maximum_concurrent_roles=3,
        maximum_role_activations_per_component=3,
        maximum_model_calls=0,
        maximum_cost_usd=0,
    )


def _shared_request(component_id):
    return SearchRequest(
        claim_id=component_id,
        query="shared fanout evidence query",
        research_path=ResearchPath.GENERAL,
        maximum_results=3,
    )
