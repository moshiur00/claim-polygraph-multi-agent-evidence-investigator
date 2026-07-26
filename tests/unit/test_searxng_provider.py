"""Tests for SearXNG request construction and normalization."""

import asyncio

import httpx
import pytest

from claim_polygraph_ng.domain import ResearchPath, SearchRequest, SourceType
from claim_polygraph_ng.providers import SearchProviderError, SearXNGSearchProvider


def test_searxng_normalizes_valid_results_and_respects_limit() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert request.url.params["q"] == "example evidence"
        assert request.url.params["format"] == "json"
        assert request.url.params["safesearch"] == "2"
        assert request.url.params["categories"] == "general"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://one.example/report",
                        "title": "First result",
                        "content": "First evidence snippet.",
                        "category": "news",
                        "engines": ["engine-a", "engine-b"],
                    },
                    {"url": "javascript:alert(1)", "title": "Unsafe", "content": "Bad"},
                    {
                        "url": "https://two.example/data",
                        "title": "Second result",
                        "content": "Second evidence snippet.",
                        "engine": "engine-c",
                    },
                    {
                        "url": "https://three.example/extra",
                        "title": "Third result",
                        "content": "Should exceed the requested limit.",
                    },
                ]
            },
        )

    provider = SearXNGSearchProvider(
        "http://searxng.local:8080",
        transport=httpx.MockTransport(handler),
    )
    results = asyncio.run(
        provider.search(
            SearchRequest(
                claim_id="00000000-0000-0000-0000-000000000001",
                query="example evidence",
                research_path=ResearchPath.GENERAL,
                maximum_results=2,
            )
        )
    )

    assert len(results) == 2
    assert results[0].source_type is SourceType.NEWS
    assert results[0].publisher == "engine-a, engine-b"
    assert results[1].title == "Second result"
    assert results[1].inline_content is None


def test_searxng_normalizes_http_and_payload_errors() -> None:
    unavailable = SearXNGSearchProvider(
        "https://searxng.example",
        transport=httpx.MockTransport(lambda request: httpx.Response(503, text="unavailable")),
    )
    request = SearchRequest(
        claim_id="00000000-0000-0000-0000-000000000001",
        query="example evidence",
        research_path=ResearchPath.PRIMARY,
    )
    with pytest.raises(SearchProviderError, match="request failed"):
        asyncio.run(unavailable.search(request))

    invalid = SearXNGSearchProvider(
        "https://searxng.example",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"unexpected": []})),
    )
    with pytest.raises(SearchProviderError, match="invalid JSON result shape"):
        asyncio.run(invalid.search(request))


@pytest.mark.parametrize(
    ("base_url", "safe_search"),
    (
        ("file:///tmp/searxng", 2),
        ("https://user:secret@searxng.example", 2),
        ("https://searxng.example", 3),
    ),
)
def test_searxng_rejects_invalid_configuration(
    base_url: str,
    safe_search: int,
) -> None:
    with pytest.raises(ValueError):
        SearXNGSearchProvider(base_url, safe_search=safe_search)
