"""Tests for raw search snapshot recording and deterministic replay."""

import asyncio
from pathlib import Path

import pytest

from claim_polygraph_ng.domain import ResearchPath, SearchRequest, SearchResult, SourceType
from claim_polygraph_ng.evaluation import (
    RecordingSearchProvider,
    SnapshotReplaySearchProvider,
    build_retrieval_snapshot,
    export_retrieval_snapshot,
    load_benchmark,
    load_retrieval_snapshot,
    run_retrieval_evaluation,
)
from claim_polygraph_ng.providers import SearchProviderError

BENCHMARK = Path(__file__).parents[2] / "benchmarks" / "initial_claims_v1.json"


def test_snapshot_records_and_replays_strategy_queries(tmp_path) -> None:
    dataset = load_benchmark(BENCHMARK)

    class FakeSearchProvider:
        provider_id = "fake-live-search"

        def __init__(self) -> None:
            self.call_count = 0

        async def search(self, request):
            self.call_count += 1
            slug = str(self.call_count)
            return (
                SearchResult(
                    url=f"https://result.example/{slug}",
                    title=f"Result {slug}",
                    snippet=f"Evidence returned for {request.query}",
                    source_type=SourceType.OTHER,
                ),
            )

    live = FakeSearchProvider()
    recorder = RecordingSearchProvider(live)
    asyncio.run(
        run_retrieval_evaluation(
            dataset,
            recorder,
            limit=1,
            top_k=10,
            query_strategy="guarded_fusion",
        )
    )
    snapshot = build_retrieval_snapshot(dataset, recorder, top_k=10)
    path = export_retrieval_snapshot(snapshot, tmp_path / "snapshot.json")
    loaded = load_retrieval_snapshot(path)

    assert live.call_count == 3
    assert loaded.provider_id == "fake-live-search"
    assert len(loaded.queries) == 3

    replay = SnapshotReplaySearchProvider(loaded)
    first = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            replay,
            limit=1,
            top_k=10,
            query_strategy="claim_only",
        )
    )
    second = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            replay,
            limit=1,
            top_k=10,
            query_strategy="claim_only",
        )
    )

    assert first.provider_id == "snapshot:fake-live-search"
    assert first.results[0].candidates == second.results[0].candidates
    assert first.exact_url_recall_at_k == second.exact_url_recall_at_k
    assert live.call_count == 3


def test_snapshot_replay_rejects_missing_query_and_larger_budget() -> None:
    dataset = load_benchmark(BENCHMARK)

    class OneResultProvider:
        provider_id = "one-result"

        async def search(self, request):
            return (
                SearchResult(
                    url="https://result.example/one",
                    title="One result",
                    snippet="One captured result.",
                    source_type=SourceType.OTHER,
                ),
            )

    recorder = RecordingSearchProvider(OneResultProvider())
    captured_request = SearchRequest(
        claim_id="00000000-0000-0000-0000-000000000001",
        query="captured query",
        research_path=ResearchPath.GENERAL,
        maximum_results=5,
    )
    asyncio.run(recorder.search(captured_request))
    replay = SnapshotReplaySearchProvider(build_retrieval_snapshot(dataset, recorder, top_k=5))

    missing_request = captured_request.model_copy(update={"query": "missing query"})
    with pytest.raises(SearchProviderError, match="absent from snapshot"):
        asyncio.run(replay.search(missing_request))

    larger_request = captured_request.model_copy(update={"maximum_results": 6})
    with pytest.raises(SearchProviderError, match="snapshot top-k is 5"):
        asyncio.run(replay.search(larger_request))
