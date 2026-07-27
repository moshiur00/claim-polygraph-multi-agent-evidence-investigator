"""Tests for SerpAPI request construction, retry, and result normalization."""

import asyncio

import httpx
import pytest

from claim_polygraph_ng.domain import ResearchPath, SearchRequest, SourceType
from claim_polygraph_ng.providers import SearchProviderError, SerpAPISearchProvider


def _request(maximum_results: int = 2) -> SearchRequest:
    return SearchRequest(
        claim_id="00000000-0000-0000-0000-000000000001",
        query="example evidence",
        research_path=ResearchPath.PRIMARY,
        maximum_results=maximum_results,
    )


def test_serpapi_google_normalizes_results_and_respects_limit() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(
            "https://serpapi.com/search.json",
            params=request.url.params,
        )
        assert request.url.params["api_key"] == "test-secret"
        assert request.url.params["engine"] == "google"
        assert request.url.params["q"] == "example evidence"
        assert request.url.params["hl"] == "en"
        assert request.url.params["gl"] == "us"
        assert request.url.params["safe"] == "active"
        assert request.url.params["num"] == "2"
        return httpx.Response(
            200,
            json={
                "search_metadata": {"status": "Success"},
                "organic_results": [
                    {
                        "position": 1,
                        "title": "First result",
                        "link": "https://one.example/report",
                        "snippet": "First evidence snippet.",
                        "source": "Example Authority",
                    },
                    {
                        "position": 2,
                        "title": "Unsafe result",
                        "link": "javascript:alert(1)",
                        "snippet": "Unsafe URL.",
                    },
                    {
                        "position": 3,
                        "title": "Second result",
                        "link": "https://two.example/data",
                        "snippet": "Second evidence snippet.",
                        "displayed_link": "two.example",
                    },
                    {
                        "position": 4,
                        "title": "Third result",
                        "link": "https://three.example/extra",
                        "snippet": "Should exceed the normalized result limit.",
                    },
                ],
            },
        )

    provider = SerpAPISearchProvider(
        api_key="test-secret",
        transport=httpx.MockTransport(handler),
    )
    results = asyncio.run(provider.search(_request()))

    assert provider.provider_id == "serpapi:google"
    assert len(results) == 2
    assert results[0].publisher == "Example Authority"
    assert results[0].source_type is SourceType.OTHER
    assert results[1].title == "Second result"
    assert results[1].publisher == "two.example"


def test_serpapi_duckduckgo_uses_engine_specific_parameters() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["engine"] == "duckduckgo"
        assert request.url.params["kl"] == "de-en"
        assert request.url.params["safe"] == "-2"
        assert request.url.params["m"] == "3"
        assert "num" not in request.url.params
        return httpx.Response(200, json={"organic_results": []})

    provider = SerpAPISearchProvider(
        api_key="test-secret",
        engine="duckduckgo",
        country="de",
        safe_search=False,
        transport=httpx.MockTransport(handler),
    )

    assert asyncio.run(provider.search(_request(3))) == ()
    assert provider.provider_id == "serpapi:duckduckgo"


def test_serpapi_retries_one_transient_failure() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        del request
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(
            200,
            json={
                "organic_results": [
                    {
                        "title": "Recovered result",
                        "link": "https://example.org/recovered",
                        "snippet": "The bounded retry recovered this result.",
                    }
                ]
            },
        )

    provider = SerpAPISearchProvider(
        api_key="test-secret",
        transport=httpx.MockTransport(handler),
    )

    results = asyncio.run(provider.search(_request()))

    assert calls == 2
    assert results[0].title == "Recovered result"


@pytest.mark.parametrize(
    ("response", "message"),
    (
        (httpx.Response(401, json={"error": "Invalid API key"}), "authentication"),
        (httpx.Response(429, json={"error": "Rate limit"}), "quota or rate limit"),
        (httpx.Response(200, text="not json"), "invalid JSON"),
        (
            httpx.Response(200, json={"organic_results": {}}),
            "invalid organic-results shape",
        ),
        (
            httpx.Response(200, json={"error": "Account limit reached"}),
            "SerpAPI returned an error",
        ),
    ),
)
def test_serpapi_normalizes_provider_failures(
    response: httpx.Response,
    message: str,
) -> None:
    provider = SerpAPISearchProvider(
        api_key="test-secret",
        maximum_attempts=1,
        transport=httpx.MockTransport(lambda request: response),
    )

    with pytest.raises(SearchProviderError, match=message) as captured:
        asyncio.run(provider.search(_request()))

    assert "test-secret" not in str(captured.value)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"api_key": ""},
        {"api_key": "secret", "engine": "unsupported"},
        {"api_key": "secret", "language": "english"},
        {"api_key": "secret", "country": "usa"},
        {"api_key": "secret", "timeout_seconds": 0},
        {"api_key": "secret", "maximum_attempts": 3},
    ),
)
def test_serpapi_rejects_invalid_configuration(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        SerpAPISearchProvider(**kwargs)
