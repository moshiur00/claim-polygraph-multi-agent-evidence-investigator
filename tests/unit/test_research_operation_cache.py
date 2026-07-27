import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from claim_polygraph_ng.application import SharedResearchOperations
from claim_polygraph_ng.domain import ResearchPath, SearchRequest, SearchResult, SourceType
from claim_polygraph_ng.persistence import SQLiteResearchRepository
from claim_polygraph_ng.retrieval import FetchedDocument


class SearchStub:
    provider_id = "search"

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, request):
        self.calls += 1
        return (
            SearchResult(
                url="https://example.org/result",
                title="Result",
                snippet=request.query,
                source_type=SourceType.OTHER,
            ),
        )


class FetchStub:
    provider_id = "fetch"

    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, url):
        self.calls += 1
        return FetchedDocument(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/plain",
            text="result",
            byte_length=6,
            retrieved_at=datetime.now(UTC),
        )


def test_durable_query_cache_normalizes_case_and_whitespace(tmp_path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "cache.sqlite3")
    repository.initialize()
    provider = SearchStub()
    fetcher = FetchStub()
    operations = SharedResearchOperations(
        repository=repository,
        search_provider=provider,
        fetcher=fetcher,
    )
    first = SearchRequest(
        claim_id=uuid4(),
        query="Shared   Query",
        research_path=ResearchPath.GENERAL,
        maximum_results=3,
    )
    second = SearchRequest(
        claim_id=uuid4(),
        query=" shared query ",
        research_path=ResearchPath.GENERAL,
        maximum_results=3,
    )

    asyncio.run(operations.search(first))
    asyncio.run(operations.search(second))

    assert provider.calls == 1


def test_durable_fetch_cache_canonicalizes_url(tmp_path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "fetch.sqlite3")
    repository.initialize()
    provider = SearchStub()
    fetcher = FetchStub()
    operations = SharedResearchOperations(
        repository=repository,
        search_provider=provider,
        fetcher=fetcher,
    )

    asyncio.run(operations.fetch("HTTPS://EXAMPLE.ORG:443/page?b=2&a=1#first"))
    asyncio.run(operations.fetch("https://example.org/page?a=1&b=2#second"))

    assert fetcher.calls == 1
