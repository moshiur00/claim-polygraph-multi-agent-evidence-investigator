"""Stage 10.3 authenticity, attribution, persistence, and access tests."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from claim_polygraph_ng.analysis.social_attribution import (
    source_from_search_result,
)
from claim_polygraph_ng.analysis.social_urls import classify_social_url
from claim_polygraph_ng.application import SharedResearchOperations
from claim_polygraph_ng.domain import (
    DistributionMedium,
    ExtractionStatus,
    ProviderResultMetadata,
    SearchResult,
    SocialSourceContext,
    SourceType,
    evaluate_social_evidence_eligibility,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository


def test_recorded_authenticity_and_attribution_fixtures() -> None:
    fixture = json.loads(
        (
            Path(__file__).parents[2]
            / "benchmarks/phase10_social_attribution_fixtures_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert fixture["network_calls_permitted"] == 0
    for case in fixture["cases"]:
        context = SocialSourceContext.model_validate(case["context"])
        eligibility = evaluate_social_evidence_eligibility(context)
        assert eligibility.decision.value == case["decision"], case["case_id"]
        assert [item.value for item in eligibility.allowed_uses] == case[
            "allowed_uses"
        ], case["case_id"]
        assert (
            eligibility.requires_human_review == case["requires_human_review"]
        ), case["case_id"]
        assert not eligibility.decisive_use_allowed


def test_search_candidate_becomes_persisted_unverified_social_lead(tmp_path: Path) -> None:
    social_url = classify_social_url(
        "https://twitter.com/WHO/status/1234567890?utm_source=search"
    )
    assert social_url is not None
    result = SearchResult(
        url="https://twitter.com/WHO/status/1234567890?utm_source=search",
        title="Indexed social result",
        snippet="Search-provider snippet; not authenticated post content.",
        source_type=SourceType.OTHER,
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_url=social_url,
        provider_metadata=ProviderResultMetadata(
            provider_id="fixture-search",
            rank=1,
            attributes={"position": 1},
        ),
    )
    source = source_from_search_result(
        result,
        canonical_url=str(social_url.canonical_url),
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.PARTIAL,
    )
    repository = SQLiteResearchRepository(tmp_path / "research.sqlite3")
    repository.initialize()
    repository.save_source(source)
    restored = repository.get_sources((source.source_id,))[0]

    assert restored == source
    assert restored.extraction_status is ExtractionStatus.PARTIAL
    assert restored.social_context is not None
    assert restored.social_context.account.handle == "WHO"
    assert restored.social_context.account.authenticity_status.value == "unknown"
    assert restored.social_context.capture_method.value == "search_result_snippet"
    assert restored.social_eligibility is not None
    assert restored.social_eligibility.reason_codes == (
        "search_snippet_not_authenticity_evidence",
    )
    assert restored.discovery_metadata == result.provider_metadata


def test_social_post_without_account_handle_keeps_identity_unresolved() -> None:
    social_url = classify_social_url("https://www.instagram.com/reel/ABC123")
    assert social_url is not None
    result = SearchResult(
        url="https://www.instagram.com/reel/ABC123",
        title="Indexed reel",
        snippet="Provider snippet.",
        source_type=SourceType.OTHER,
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_url=social_url,
    )
    source = source_from_search_result(
        result,
        canonical_url=str(social_url.canonical_url),
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.PARTIAL,
    )

    assert source.social_context is not None
    assert not source.social_context.account.identity_resolved
    assert source.social_context.account.handle is None
    assert source.social_eligibility is not None
    assert not source.social_eligibility.independent_proof_allowed


def test_shared_generic_fetch_refuses_social_urls_before_fetcher_call(
    tmp_path: Path,
) -> None:
    class SearchStub:
        provider_id = "search"

        async def search(self, request):
            del request
            return ()

    class FetchStub:
        provider_id = "fetch"

        def __init__(self) -> None:
            self.calls = 0

        async def fetch(self, url):
            del url
            self.calls += 1
            raise AssertionError("social URL must not reach generic fetcher")

    repository = SQLiteResearchRepository(tmp_path / "fetch.sqlite3")
    repository.initialize()
    fetcher = FetchStub()
    operations = SharedResearchOperations(
        repository=repository,
        search_provider=SearchStub(),
        fetcher=fetcher,
    )

    with pytest.raises(ValueError, match="prohibited"):
        asyncio.run(operations.fetch("https://x.com/agency/status/123456"))
    assert fetcher.calls == 0

