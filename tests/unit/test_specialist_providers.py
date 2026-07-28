"""Recorded-fixture tests for academic and fact-check specialist adapters."""

import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from claim_polygraph_ng.domain import (
    ResearchPath,
    SearchRequest,
    SourceType,
    SpecialistSearchRequest,
)
from claim_polygraph_ng.domain.research import ROLE_PERMISSIONS, ResearchRole
from claim_polygraph_ng.providers import (
    GoogleFactCheckSearchProvider,
    PubMedAcademicSearchProvider,
    SearchProviderError,
    SemanticScholarAcademicSearchProvider,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "providers"


def _fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_pubmed_preserves_metadata_paginates_and_normalizes_safe_candidates() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = (
            _fixture("pubmed_esearch_page1.json")
            if request.url.path.endswith("esearch.fcgi")
            else _fixture("pubmed_esummary_page1.json")
        )
        return httpx.Response(200, json=payload)

    provider = PubMedAcademicSearchProvider(transport=httpx.MockTransport(handler))
    page = asyncio.run(
        provider.search_academic(
            SpecialistSearchRequest(query="population intervention", maximum_results=2)
        )
    )

    assert len(requests) == page.request_count == 2
    assert page.next_cursor == "2"
    assert page.results[0].doi == "10.1000/fixture.1"
    assert page.results[0].journal == "Journal of Recorded Fixtures"
    assert page.results[1].corrected
    assert all(item.candidate.source_type is SourceType.ACADEMIC for item in page.results)
    assert all(item.candidate.inline_content is None for item in page.results)
    assert provider.role is ResearchRole.ACADEMIC
    assert provider.permissions == ROLE_PERMISSIONS[ResearchRole.ACADEMIC]


def test_pubmed_empty_page_uses_one_request_and_wrong_path_fails() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_fixture("pubmed_esearch_empty.json"))

    provider = PubMedAcademicSearchProvider(transport=httpx.MockTransport(handler))
    page = asyncio.run(
        provider.search_academic(SpecialistSearchRequest(query="no recorded result"))
    )

    assert page.results == ()
    assert page.request_count == calls == 1
    with pytest.raises(SearchProviderError, match="academic research path"):
        asyncio.run(
            provider.search(
                SearchRequest(
                    claim_id="7a638e26-fbbe-487c-bbd6-c405959754e1",
                    query="wrong role path",
                    research_path=ResearchPath.GENERAL,
                )
            )
        )


def test_fact_check_preserves_rating_metadata_cursor_and_safe_candidate() -> None:
    observed_query = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed_query.update(parse_qs(request.url.query.decode()))
        return httpx.Response(200, json=_fixture("factcheck_page1.json"))

    provider = GoogleFactCheckSearchProvider(
        api_key="fixture-key",
        transport=httpx.MockTransport(handler),
    )
    page = asyncio.run(
        provider.search_fact_checks(
            SpecialistSearchRequest(
                query="emissions claim",
                maximum_results=3,
                cursor="opaque-page-1",
            )
        )
    )

    result = page.results[0]
    assert page.request_count == 1
    assert page.next_cursor == "opaque-page-2"
    assert observed_query["pageToken"] == ["opaque-page-1"]
    assert result.textual_rating == "Needs context"
    assert result.review_publisher == "Fixture Fact Check"
    assert result.candidate.source_type is SourceType.FACT_CHECK
    assert result.candidate.inline_content is None
    assert provider.role is ResearchRole.FACT_CHECK
    assert provider.permissions == ROLE_PERMISSIONS[ResearchRole.FACT_CHECK]


def test_fact_check_empty_and_rate_limit_are_typed() -> None:
    empty = GoogleFactCheckSearchProvider(
        api_key="fixture-key",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json=_fixture("factcheck_empty.json"),
            )
        ),
    )
    limited = GoogleFactCheckSearchProvider(
        api_key="fixture-key",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(429, json={"error": "quota"})
        ),
    )

    page = asyncio.run(
        empty.search_fact_checks(SpecialistSearchRequest(query="no reviewed claim"))
    )
    assert page.results == ()
    with pytest.raises(SearchProviderError, match="rate limit"):
        asyncio.run(
            limited.search_fact_checks(
                SpecialistSearchRequest(query="limited reviewed claim")
            )
        )


def test_semantic_scholar_preserves_identifiers_and_paginates_in_one_call() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=_fixture("semantic_scholar_page1.json"),
        )

    provider = SemanticScholarAcademicSearchProvider(
        transport=httpx.MockTransport(handler)
    )
    page = asyncio.run(
        provider.search_academic(
            SpecialistSearchRequest(query="intervention evidence", maximum_results=2)
        )
    )

    assert len(requests) == page.request_count == 1
    assert page.next_cursor == "2"
    assert page.results[0].provider_record_id == "S2-PAPER-1"
    assert page.results[0].doi == "10.1000/semantic.fixture"
    assert page.results[0].journal == "Fixture Science"
    assert page.results[1].publication_date_text == "2024"
    assert all(item.candidate.inline_content is None for item in page.results)
    assert provider.permissions == ROLE_PERMISSIONS[ResearchRole.ACADEMIC]


def test_semantic_scholar_malformed_payload_fails_closed() -> None:
    provider = SemanticScholarAcademicSearchProvider(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"data": "not-a-list"})
        )
    )

    with pytest.raises(SearchProviderError, match="invalid result shape"):
        asyncio.run(
            provider.search_academic(
                SpecialistSearchRequest(query="malformed provider response")
            )
        )
