"""Tests for reviewed-source retrieval evaluation."""

import asyncio
import json
from pathlib import Path

from claim_polygraph_ng.domain import SearchResult, SourceType
from claim_polygraph_ng.evaluation import (
    export_retrieval_evaluation,
    load_benchmark,
    run_retrieval_evaluation,
)

BENCHMARK = Path(__file__).parents[2] / "benchmarks" / "initial_claims_v1.json"


def test_retrieval_evaluation_measures_exact_and_host_recall(tmp_path) -> None:
    dataset = load_benchmark(BENCHMARK)
    calendar_reference = dataset.cases[0].candidate_evidence[1]
    water_reference = dataset.cases[1].candidate_evidence[0]

    class FakeSearchProvider:
        provider_id = "fake-search"

        async def search(self, request):
            if "calendar year" in request.query:
                return (
                    SearchResult(
                        url="https://unrelated.example/article",
                        title="Unrelated result",
                        snippet="No matching reviewed evidence here.",
                        source_type=SourceType.OTHER,
                    ),
                    SearchResult(
                        url=calendar_reference.source_url,
                        title="Astronomical Almanac Glossary",
                        snippet="Definitions of calendar and Julian years.",
                        source_type=SourceType.OFFICIAL,
                    ),
                )
            return (
                SearchResult(
                    url="https://nvlpubs.nist.gov/different-page",
                    title="NIST water reference",
                    snippet="A different page on the reviewed source host.",
                    source_type=SourceType.OFFICIAL,
                ),
            )

    summary = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            FakeSearchProvider(),
            limit=2,
            top_k=10,
            lexical_threshold=0.99,
        )
    )
    output = export_retrieval_evaluation(summary, tmp_path / "retrieval.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert summary.completed_case_count == 2
    assert summary.reference_count == 5
    assert summary.exact_url_recall_at_k == 0.2
    assert summary.reviewed_host_recall_at_k == 0.4
    assert summary.exact_url_mrr == 0.25
    assert summary.reviewed_host_mrr == 0.75
    assert summary.case_success_at_k == 1.0
    assert summary.lexical_proxy_recall_at_k == 0.0
    assert summary.query_strategy.value == "claim_only"
    assert summary.search_call_count == 2
    assert summary.results[0].queries == (dataset.cases[0].claim,)
    assert summary.results[0].candidates[1].rank == 2
    assert summary.results[0].candidates[1].title == "Astronomical Almanac Glossary"
    assert summary.results[0].candidates[1].query_ranks == {dataset.cases[0].claim: 2}
    assert summary.results[0].references[1].exact_url_rank == 2
    assert summary.results[1].references[0].reviewed_host_rank == 1
    assert str(water_reference.source_url).startswith("https://nvlpubs.nist.gov/")
    assert payload["limitations"]


def test_retrieval_evaluation_records_provider_failures() -> None:
    dataset = load_benchmark(BENCHMARK)

    class FailingSearchProvider:
        provider_id = "failing-search"

        async def search(self, request):
            del request
            raise RuntimeError("search unavailable")

    summary = asyncio.run(run_retrieval_evaluation(dataset, FailingSearchProvider(), limit=1))

    assert summary.completed_case_count == 0
    assert summary.completion_rate == 0.0
    assert summary.exact_url_recall_at_k == 0.0
    assert summary.results[0].error_type == "SearchProviderError"
    assert summary.results[0].error_message == "all retrieval queries failed"
    assert "RuntimeError: search unavailable" in summary.results[0].query_errors.values()


def test_balanced_strategy_fuses_queries_with_the_same_final_candidate_budget() -> None:
    dataset = load_benchmark(BENCHMARK)
    reference = dataset.cases[0].candidate_evidence[1]

    class StrategySearchProvider:
        provider_id = "strategy-search"

        async def search(self, request):
            common = SearchResult(
                url="https://common.example/year",
                title="Common year result",
                snippet="A recurring result about years.",
                source_type=SourceType.OTHER,
            )
            if "official authoritative source" in request.query:
                return (
                    common,
                    SearchResult(
                        url=reference.source_url,
                        title=reference.source_title,
                        snippet=reference.excerpt,
                        source_type=reference.source_type,
                    ),
                )
            return (common,)

    summary = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            StrategySearchProvider(),
            limit=1,
            top_k=2,
            query_strategy="balanced",
        )
    )
    result = summary.results[0]

    assert summary.query_strategy.value == "balanced"
    assert summary.search_call_count == 3
    assert len(result.queries) == 3
    assert len(result.candidates) == 2
    assert result.candidates[0].url.host == "common.example"
    assert len(result.candidates[0].query_ranks) == 3
    assert result.references[1].exact_url_rank == 2


def test_guarded_fusion_preserves_leaders_and_limits_expansion() -> None:
    dataset = load_benchmark(BENCHMARK)
    reference = dataset.cases[0].candidate_evidence[1]

    class GuardedSearchProvider:
        provider_id = "guarded-search"

        async def search(self, request):
            if request.query == dataset.cases[0].claim:
                return tuple(
                    SearchResult(
                        url=f"https://control.example/result-{number}",
                        title=f"Control result {number}",
                        snippet="Claim-only candidate.",
                        source_type=SourceType.OTHER,
                    )
                    for number in range(1, 6)
                )
            if "official authoritative source" in request.query:
                return (
                    SearchResult(
                        url=reference.source_url,
                        title=reference.source_title,
                        snippet=reference.excerpt,
                        source_type=reference.source_type,
                    ),
                )
            return (
                SearchResult(
                    url="https://counter.example/year",
                    title="Counterevidence result",
                    snippet="A counterevidence candidate.",
                    source_type=SourceType.FACT_CHECK,
                ),
            )

    summary = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            GuardedSearchProvider(),
            limit=1,
            top_k=5,
            query_strategy="guarded_fusion",
        )
    )
    result = summary.results[0]

    assert [candidate.url.host for candidate in result.candidates[:2]] == [
        "control.example",
        "control.example",
    ]
    assert len(result.candidates) == 5
    assert result.references[1].exact_url_rank == 3
    assert result.candidates[3].url.host == "counter.example"
    assert result.candidates[0].fusion_score > result.candidates[2].fusion_score


def test_quality_rerank_promotes_authority_and_penalizes_social_results() -> None:
    dataset = load_benchmark(BENCHMARK)
    claim = dataset.cases[0].claim

    class QualitySearchProvider:
        provider_id = "quality-search"

        async def search(self, request):
            if request.query == claim:
                return (
                    SearchResult(
                        url="https://facebook.com/post/year",
                        title=claim,
                        snippet="A social post repeating the exact claim.",
                        source_type=SourceType.OTHER,
                    ),
                    SearchResult(
                        url="https://science.gov/calendar-year",
                        title="Government calendar year definition",
                        snippet="An official explanation of calendar year length.",
                        source_type=SourceType.OTHER,
                    ),
                    SearchResult(
                        url="https://science.gov/year-data",
                        title="Government year data",
                        snippet="Official year measurements and definitions.",
                        source_type=SourceType.OTHER,
                    ),
                )
            if "official authoritative source" in request.query:
                return (
                    SearchResult(
                        url="https://pmc.ncbi.nlm.nih.gov/articles/example/",
                        title="Peer-reviewed analysis",
                        snippet="Academic analysis of the exact numerical claim.",
                        source_type=SourceType.OTHER,
                    ),
                )
            return (
                SearchResult(
                    url="https://reddit.com/r/example/year",
                    title="Forum counterclaim",
                    snippet="A forum discussion of the claim.",
                    source_type=SourceType.OTHER,
                ),
            )

    control = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            QualitySearchProvider(),
            limit=1,
            top_k=3,
            query_strategy="claim_only",
        )
    )
    reranked = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            QualitySearchProvider(),
            limit=1,
            top_k=3,
            query_strategy="quality_rerank",
        )
    )

    reranked_hosts = [candidate.url.host for candidate in reranked.results[0].candidates]
    assert reranked_hosts[0] == "science.gov"
    assert "pmc.ncbi.nlm.nih.gov" in reranked_hosts
    assert "facebook.com" not in reranked_hosts
    assert reranked.mean_candidate_quality_score > control.mean_candidate_quality_score
    assert reranked.low_quality_candidate_rate < control.low_quality_candidate_rate
    assert all(candidate.quality_features for candidate in reranked.results[0].candidates)


def test_quality_rerank_reserves_safe_counterevidence_in_early_access_window() -> None:
    dataset = load_benchmark(BENCHMARK)
    claim = dataset.cases[0].claim

    class CounterSearchProvider:
        provider_id = "counter-coverage-search"

        async def search(self, request):
            if "counterevidence fact check" in request.query:
                return (
                    SearchResult(
                        url="https://independent.example/counter-analysis",
                        title="Independent counterevidence",
                        snippet="Evidence directly qualifying the exact claim.",
                        source_type=SourceType.OTHER,
                    ),
                )
            return tuple(
                SearchResult(
                    url=f"https://official.gov/report-{number}",
                    title=f"Official report {number}",
                    snippet=f"{claim} authoritative documentation",
                    source_type=SourceType.OFFICIAL,
                )
                for number in range(1, 5)
            )

    summary = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            CounterSearchProvider(),
            limit=1,
            top_k=5,
            query_strategy="quality_rerank",
        )
    )

    leading_hosts = [candidate.url.host for candidate in summary.results[0].candidates[:3]]
    assert "independent.example" in leading_hosts


def test_expansion_queries_follow_claim_shape_without_reviewed_evidence() -> None:
    dataset = load_benchmark(BENCHMARK)

    class QueryCapture:
        provider_id = "query-capture"

        def __init__(self):
            self.queries = []

        async def search(self, request):
            self.queries.append(request.query)
            return ()

    provider = QueryCapture()
    asyncio.run(
        run_retrieval_evaluation(
            dataset,
            provider,
            limit=5,
            top_k=3,
            query_strategy="quality_rerank",
        )
    )

    assert "measurement standard units" in provider.queries[1]
    assert "exceptions variability qualification" in provider.queries[2]
    assert "exceptions variability qualification" in provider.queries[8]
    assert "current status dated statement" in provider.queries[10]
    assert "ended superseded timeline" in provider.queries[11]


def test_component_queries_report_completion_candidates_and_reviewed_recovery() -> None:
    source = load_benchmark(BENCHMARK)
    case = source.cases[10]
    dataset = source.model_copy(update={"cases": (case,)})
    reviewed = case.candidate_evidence[0]

    class ComponentSearchProvider:
        provider_id = "component-search"

        async def search(self, request):
            if request.query == case.expected_components[0]:
                return (
                    SearchResult(
                        url=reviewed.source_url,
                        title=reviewed.source_title,
                        snippet=reviewed.excerpt,
                        source_type=reviewed.source_type,
                    ),
                )
            if request.query == case.expected_components[1]:
                return (
                    SearchResult(
                        url="https://unrelated.example/energy",
                        title="Unrelated energy result",
                        snippet="A candidate that does not recover reviewed evidence.",
                        source_type=SourceType.OTHER,
                    ),
                )
            if request.query == case.expected_components[2]:
                raise RuntimeError("component search failed")
            return ()

    summary = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            ComponentSearchProvider(),
            top_k=10,
            include_component_queries=True,
        )
    )

    assert summary.component_query_enabled is True
    assert summary.material_component_count == 3
    assert summary.search_call_count == 4
    assert summary.component_query_completion_rate == 0.666667
    assert summary.component_candidate_rate == 0.666667
    assert summary.component_reviewed_evidence_rate == 0.333333
    assert summary.results[0].components[0].reviewed_evidence_found is True
    assert summary.results[0].components[1].candidate_found is True
    assert summary.results[0].components[1].reviewed_evidence_found is False
    assert summary.results[0].components[2].query_completed is False
    assert "RuntimeError: component search failed" in (
        summary.results[0].components[2].error_message or ""
    )
