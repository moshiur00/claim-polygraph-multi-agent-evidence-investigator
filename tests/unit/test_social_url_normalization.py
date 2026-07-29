"""Stage 10.2 deterministic social URL and provider-metadata tests."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from claim_polygraph_ng.analysis.social_urls import (
    canonical_web_url,
    classify_social_url,
)
from claim_polygraph_ng.domain import (
    DistributionMedium,
    ProviderResultMetadata,
    ResearchPath,
    SearchRequest,
    SearchResult,
    SocialPlatform,
    SocialUrlKind,
)
from claim_polygraph_ng.providers import SearXNGSearchProvider, SerpAPISearchProvider


def test_recorded_social_url_fixtures_are_deterministic_and_fetch_free() -> None:
    path = (
        Path(__file__).parents[2]
        / "benchmarks/phase10_social_url_fixtures_v1.json"
    )
    fixture = json.loads(path.read_text(encoding="utf-8"))

    assert fixture["network_calls_permitted"] == 0
    assert len(fixture["cases"]) == 15
    for case in fixture["cases"]:
        result = classify_social_url(case["input_url"])
        if case["platform"] is None:
            assert result is None, case["case_id"]
            continue
        assert result is not None, case["case_id"]
        assert result.platform.value == case["platform"]
        assert result.url_kind.value == case["url_kind"]
        assert str(result.canonical_url) == case["canonical_url"]
        assert result.account_handle == case["account_handle"]
        assert result.platform_post_id == case["platform_post_id"]
        assert result.content_fetch_attempted is False


def test_url_normalizer_rejects_credentials_and_removes_only_tracking_data() -> None:
    with pytest.raises(ValueError, match="credentials"):
        classify_social_url("https://user:secret@x.com/account/status/123")

    assert canonical_web_url(
        "HTTPS://Example.ORG/report/?id=7&utm_source=x#fragment"
    ) == "https://example.org/report?id=7"


def test_provider_metadata_is_bounded_and_cannot_retain_credentials() -> None:
    metadata = ProviderResultMetadata(
        provider_id="fixture",
        rank=2,
        result_id="result-2",
        attributes={"score": 0.95, "engines": ["a", "b"]},
    )
    assert metadata.attributes["score"] == 0.95

    with pytest.raises(ValidationError, match="credential"):
        ProviderResultMetadata(
            provider_id="fixture",
            attributes={"api_key": "must-not-be-retained"},
        )


def test_legacy_search_result_uses_unknown_additive_defaults() -> None:
    result = SearchResult.model_validate(
        {
            "url": "https://example.org/report",
            "title": "Legacy search result",
            "snippet": "A legacy provider snippet.",
            "source_type": "other",
        }
    )

    assert result.distribution_medium is DistributionMedium.UNKNOWN
    assert result.social_url is None
    assert result.provider_metadata is None


def test_serpapi_preserves_allowlisted_metadata_and_classifies_social_url() -> None:
    raw_result = {
        "position": 3,
        "result_id": "organic-3",
        "title": "Public post",
        "link": "https://twitter.com/WHO/status/1234567890?utm_source=search",
        "snippet": "A provider-supplied snippet.",
        "source": "X",
        "date": "Jul 29, 2026",
        "unretained_internal_value": "not copied",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"organic_results": [raw_result]})

    provider = SerpAPISearchProvider(
        api_key="test-secret",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(provider.search(_request()))[0]

    assert result.distribution_medium is DistributionMedium.SOCIAL_PLATFORM
    assert result.social_url is not None
    assert result.social_url.platform is SocialPlatform.X
    assert result.social_url.url_kind is SocialUrlKind.POST
    assert result.provider_metadata is not None
    assert result.provider_metadata.provider_id == "serpapi:google"
    assert result.provider_metadata.rank == 3
    assert result.provider_metadata.result_id == "organic-3"
    assert result.provider_metadata.attributes == {
        "position": 3,
        "source": "X",
        "date": "Jul 29, 2026",
        "result_id": "organic-3",
    }


def test_searxng_preserves_engine_metadata_without_fetching_social_page() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://bsky.app/profile/example.org/post/3kxyz",
                        "title": "Bluesky post",
                        "content": "Search-index snippet only.",
                        "engines": ["bing", "mojeek"],
                        "category": "general",
                        "score": 1.25,
                    }
                ]
            },
        )

    provider = SearXNGSearchProvider(
        "http://searxng.local:8080",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(provider.search(_request()))[0]

    assert result.distribution_medium is DistributionMedium.SOCIAL_PLATFORM
    assert result.social_url is not None
    assert result.social_url.platform is SocialPlatform.BLUESKY
    assert result.provider_metadata is not None
    assert result.provider_metadata.provider_id == "searxng"
    assert result.provider_metadata.attributes == {
        "engines": ["bing", "mojeek"],
        "category": "general",
        "score": 1.25,
    }


def _request() -> SearchRequest:
    return SearchRequest(
        claim_id="00000000-0000-0000-0000-000000000001",
        query="example public evidence",
        research_path=ResearchPath.GENERAL,
        maximum_results=3,
    )
