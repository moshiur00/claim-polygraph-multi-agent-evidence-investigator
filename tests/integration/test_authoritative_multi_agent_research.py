"""Stage 9.6 integration of genuine role fan-out into the authoritative graph."""

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from claim_polygraph_ng.application import (
    AuthoritativeMultiAgentResearchAdapter,
    InvestigationService,
    LangGraphResearchFanOutWorkflow,
    SharedResearchOperations,
    UnguardedPaidResearchError,
)
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.domain import (
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    ResearchBudget,
    ResearchResult,
    SearchResult,
    Source,
    SourceType,
)
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteResearchRepository,
)
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


class _SharedSearch:
    provider_id = "stage9-shared-search"

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, _request):
        self.calls += 1
        await asyncio.sleep(0.02)
        return (
            SearchResult(
                url="https://example.org/stage9-source",
                title="Stage 9 shared source",
                snippet="Candidate metadata.",
                inline_content="The fixture programme reduced waste in the measured period.",
                source_type=SourceType.OFFICIAL,
                publisher="Stage 9 Fixture",
            ),
        )


class _NeverFetch:
    provider_id = "stage9-never-fetch"

    async def fetch(self, _url):
        raise AssertionError("inline fixture content must not be fetched")


class _ConcurrentWorker:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.active = 0
        self.maximum_active = 0
        self.calls = 0

    async def run(self, assignment, operations):
        self.calls += 1
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            await asyncio.sleep(0.03)
            result = (await operations.search(_search_request(assignment.component_id)))[0]
            passage = result.inline_content or ""
            source = Source(
                url=result.url,
                canonical_url=result.url,
                title=result.title,
                source_type=result.source_type,
                publisher=result.publisher,
                retrieved_at=datetime.now(UTC),
                content_hash=hashlib.sha256(passage.encode()).hexdigest(),
                extraction_status=ExtractionStatus.EXTRACTED,
            )
            evidence = Evidence(
                claim_id=assignment.component_id,
                source_id=source.source_id,
                passage=passage,
                stance=(
                    EvidenceStance.QUALIFIES
                    if assignment.role.value == "challenger"
                    else EvidenceStance.SUPPORTS
                ),
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
                duration_seconds=0.03,
            )
        finally:
            self.active -= 1


def test_authoritative_graph_runs_concurrent_bounded_deduplicated_research(
    tmp_path,
) -> None:
    investigations = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    research_repository = SQLiteResearchRepository(tmp_path / "research.db")
    search = _SharedSearch()
    worker = _ConcurrentWorker(research_repository)
    adapter = AuthoritativeMultiAgentResearchAdapter(
        workflow=LangGraphResearchFanOutWorkflow(
            repository=research_repository,
            operations=SharedResearchOperations(
                repository=research_repository,
                search_provider=search,
                fetcher=_NeverFetch(),
            ),
            worker=worker,
        )
    )
    budget = ResearchBudget(
        maximum_rounds=1,
        maximum_concurrent_roles=3,
        maximum_role_activations_per_component=3,
        maximum_model_calls=0,
        maximum_cost_usd=0,
    )
    service = InvestigationService(
        repository=investigations,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    with AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "langgraph.db",
        state_checkpoint_path=tmp_path / "state.db",
        research_adapter=adapter,
        research_budget=budget,
    ) as workflow:
        result = asyncio.run(
            workflow.run_to_completion("The fixture programme reduced waste.")
        )

    assert worker.maximum_active == 3
    assert worker.calls == 3
    assert search.calls == 1
    assert {item.role.value for item in result.state.assignments} == {
        "primary_source",
        "general_evidence",
        "challenger",
    }
    assert len(result.state.research_results) == 3
    assert result.state.consumption.role_activations == 3
    assert result.state.consumption.search_calls == 3
    assert result.state.consumption.model_calls == 0
    assert result.state.consumption.estimated_cost_usd == 0
    assert result.state.paid_receipts == ()
    assert result.state.approved_evidence_ids
    assert result.state.evidence_families
    assert result.report.evidence
    assert set(result.state.approved_evidence_ids) == {
        item.evidence_id for item in result.report.evidence
    }


def test_paid_capable_research_cannot_start_without_receipt_ledger(tmp_path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "guard.db")
    with pytest.raises(UnguardedPaidResearchError, match="paid-operation ledger"):
        AuthoritativeMultiAgentResearchAdapter(
            workflow=LangGraphResearchFanOutWorkflow(
                repository=repository,
                operations=SharedResearchOperations(
                    repository=repository,
                    search_provider=_SharedSearch(),
                    fetcher=_NeverFetch(),
                ),
                worker=_ConcurrentWorker(repository),
            ),
            paid_capable=True,
        )


def _search_request(component_id):
    from claim_polygraph_ng.domain import ResearchPath, SearchRequest

    return SearchRequest(
        claim_id=component_id,
        query="shared stage9 evidence query",
        research_path=ResearchPath.GENERAL,
        maximum_results=3,
    )
