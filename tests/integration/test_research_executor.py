import asyncio
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from claim_polygraph_ng.application import ResearchExecutor, SharedResearchOperations
from claim_polygraph_ng.domain import (
    ROLE_PERMISSIONS,
    ResearchAssignment,
    ResearchPath,
    ResearchResult,
    ResearchRole,
    SearchRequest,
    SearchResult,
    SourceType,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository
from claim_polygraph_ng.retrieval import FetchedDocument


class CountingSearchProvider:
    provider_id = "counting-search"

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, request):
        self.calls += 1
        await asyncio.sleep(0.01)
        return (
            SearchResult(
                url="https://example.org/evidence?b=2&a=1",
                title="Shared evidence",
                snippet=f"Evidence for {request.query}",
                source_type=SourceType.OFFICIAL,
            ),
        )


class CountingFetcher:
    provider_id = "counting-fetcher"

    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, url):
        self.calls += 1
        await asyncio.sleep(0.01)
        return FetchedDocument(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            text="Shared fetched evidence.",
            byte_length=24,
            retrieved_at=datetime.now(UTC),
        )


class SharedWorkWorker:
    def __init__(self, *, failing_role: ResearchRole | None = None) -> None:
        self.calls = Counter()
        self.active = 0
        self.maximum_active = 0
        self.failing_role = failing_role

    async def run(self, assignment, operations):
        self.calls[assignment.role] += 1
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            await asyncio.sleep(
                {
                    ResearchRole.PRIMARY_SOURCE: 0.03,
                    ResearchRole.GENERAL_EVIDENCE: 0.02,
                }.get(assignment.role, 0.01)
            )
            if assignment.role is self.failing_role:
                raise RuntimeError("simulated isolated role failure")
            results = await operations.search(
                SearchRequest(
                    claim_id=assignment.component_id,
                    query="  SHARED   evidence query ",
                    research_path=ResearchPath.GENERAL,
                    maximum_results=3,
                )
            )
            await operations.fetch(str(results[0].url))
            return ResearchResult(
                assignment_id=assignment.assignment_id,
                role=assignment.role,
                component_id=assignment.component_id,
                query_ids=(uuid4(),),
                candidate_ids=(uuid4(),),
                evidence_ids=(uuid4(),),
                search_call_count=1,
                fetch_call_count=1,
                model_call_count=0,
                estimated_cost_usd=0.0,
                duration_seconds=0.01,
            )
        finally:
            self.active -= 1


def test_executor_bounds_concurrency_coalesces_work_and_orders_results(tmp_path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "research.sqlite3")
    repository.initialize()
    search = CountingSearchProvider()
    fetcher = CountingFetcher()
    worker = SharedWorkWorker()
    assignments = _assignments()
    executor = _executor(repository, search, fetcher, worker, maximum_concurrency=2)

    results = asyncio.run(executor.execute(assignments))

    assert worker.maximum_active == 2
    assert search.calls == 1
    assert fetcher.calls == 1
    assert tuple(result.assignment_id for result in results) == tuple(
        assignment.assignment_id for assignment in assignments
    )
    assert all(result.failure_reason is None for result in results)


def test_executor_resume_reuses_assignment_search_and_fetch_checkpoints(tmp_path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "resume.sqlite3")
    repository.initialize()
    assignments = _assignments()
    first_search = CountingSearchProvider()
    first_fetcher = CountingFetcher()
    first_worker = SharedWorkWorker()

    first = asyncio.run(
        _executor(repository, first_search, first_fetcher, first_worker).execute(assignments)
    )

    second_search = CountingSearchProvider()
    second_fetcher = CountingFetcher()
    second_worker = SharedWorkWorker()
    resumed = asyncio.run(
        _executor(repository, second_search, second_fetcher, second_worker).execute(assignments)
    )

    assert resumed == first
    assert sum(second_worker.calls.values()) == 0
    assert second_search.calls == 0
    assert second_fetcher.calls == 0


def test_partial_role_failure_is_visible_and_does_not_discard_success(tmp_path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "partial.sqlite3")
    repository.initialize()
    assignments = _assignments()
    worker = SharedWorkWorker(failing_role=ResearchRole.GENERAL_EVIDENCE)

    results = asyncio.run(
        _executor(
            repository,
            CountingSearchProvider(),
            CountingFetcher(),
            worker,
        ).execute(assignments)
    )

    failures = tuple(result for result in results if result.failure_reason)
    successes = tuple(result for result in results if not result.failure_reason)
    assert len(failures) == 1
    assert failures[0].role is ResearchRole.GENERAL_EVIDENCE
    assert "simulated isolated role failure" in failures[0].failure_reason
    assert len(successes) == 2
    assert all(repository.get_result(item.assignment_id) is not None for item in assignments)


def _executor(
    repository,
    search,
    fetcher,
    worker,
    *,
    maximum_concurrency=3,
) -> ResearchExecutor:
    operations = SharedResearchOperations(
        repository=repository,
        search_provider=search,
        fetcher=fetcher,
    )
    return ResearchExecutor(
        repository=repository,
        operations=operations,
        worker=worker,
        maximum_concurrency=maximum_concurrency,
    )


def _assignments() -> tuple[ResearchAssignment, ...]:
    investigation_id = uuid4()
    parent_id = uuid4()
    component_id = uuid4()
    requirement_id = uuid4()
    return tuple(
        ResearchAssignment(
            investigation_id=investigation_id,
            parent_claim_id=parent_id,
            component_id=component_id,
            claim_text="The submitted material claim.",
            role=role,
            round_number=1,
            requirement_ids=(requirement_id,),
            permissions=ROLE_PERMISSIONS[role],
            query_limit=2,
            candidate_limit_per_query=10,
        )
        for role in (
            ResearchRole.PRIMARY_SOURCE,
            ResearchRole.GENERAL_EVIDENCE,
            ResearchRole.CHALLENGER,
        )
    )
