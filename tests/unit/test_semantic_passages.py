"""Tests for bounded semantic recovery of borderline passages."""

import asyncio
from pathlib import Path

from claim_polygraph_ng.domain import ModelTask, SearchResult, SourceType
from claim_polygraph_ng.evaluation import (
    SemanticPassageJudgment,
    load_benchmark,
    run_page_fetch_evaluation,
    run_retrieval_evaluation,
    run_semantic_passage_evaluation,
)
from claim_polygraph_ng.retrieval import FetchedDocument

BENCHMARK = Path(__file__).parents[2] / "benchmarks" / "initial_claims_v1.json"


def test_semantic_evaluation_recovers_only_borderline_unmatched_references() -> None:
    dataset = load_benchmark(BENCHMARK)

    class SearchProvider:
        provider_id = "semantic-search"

        async def search(self, request):
            del request
            return (
                SearchResult(
                    url="https://evidence.example/year",
                    title="Year evidence",
                    snippet="Calendar conventions and year lengths.",
                    source_type=SourceType.OTHER,
                ),
            )

    retrieval = asyncio.run(
        run_retrieval_evaluation(dataset, SearchProvider(), limit=1, top_k=1)
    )

    class Fetcher:
        provider_id = "semantic-fetcher"

        async def fetch(self, url):
            text = (
                "The ordinary civil calendar uses 365 days, with 366 in leap years. "
                "Different astronomical conventions use fractional average lengths."
            )
            return FetchedDocument(
                requested_url=url,
                final_url=url,
                status_code=200,
                content_type="text/plain",
                text=text,
                byte_length=len(text.encode()),
            )

    pages = asyncio.run(
        run_page_fetch_evaluation(
            dataset,
            retrieval,
            Fetcher(),
            retrieval_input="retrieval.json",
            candidate_top_n=1,
            passage_top_k=1,
            passage_lexical_threshold=0.95,
        )
    )

    class SemanticProvider:
        provider_id = "semantic-model"
        prompt_version = "semantic-test-v1"

        def model_for_task(self, task):
            assert task is ModelTask.EVALUATE_PASSAGE
            return "semantic-test-model"

        def take_last_usage(self):
            return None

        async def generate(self, *, task, response_model, inputs):
            assert task is ModelTask.EVALUATE_PASSAGE
            assert response_model is SemanticPassageJudgment
            assert inputs["retrieved_passage"]
            return SemanticPassageJudgment(
                relationship="equivalent",
                rationale=(
                    "The retrieved passage establishes the same distinction between ordinary "
                    "calendar years and fractional conventions."
                ),
                matched_points=("Ordinary years use 365 or 366 days.",),
                missing_or_conflicting_points=(),
            )

    summary = asyncio.run(
        run_semantic_passage_evaluation(
            dataset,
            pages,
            SemanticProvider(),
            page_evaluation_input="pages.json",
            lower_lexical_threshold=0.1,
        )
    )

    assert summary.reference_count == 2
    assert summary.semantic_candidate_count >= 1
    assert summary.equivalent_count == summary.evaluated_count
    assert summary.combined_match_count == (
        summary.lexical_match_count + summary.equivalent_count
    )
    assert summary.model == "semantic-test-model"
    assert all(
        result.judgment is not None
        for result in summary.results
        if result.evaluated
    )
