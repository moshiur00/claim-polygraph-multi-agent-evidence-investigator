"""Tests for bounded page fetching and passage evaluation."""

import asyncio
import json
from pathlib import Path

from claim_polygraph_ng.domain import SearchResult, SourceType
from claim_polygraph_ng.evaluation import (
    export_page_fetch_evaluation,
    load_benchmark,
    run_page_fetch_evaluation,
    run_retrieval_evaluation,
)
from claim_polygraph_ng.retrieval import FetchedDocument

BENCHMARK = Path(__file__).parents[2] / "benchmarks" / "initial_claims_v1.json"


def test_page_evaluation_separates_fetch_extraction_duplicates_and_passages(
    tmp_path,
) -> None:
    dataset = load_benchmark(BENCHMARK)
    reference = dataset.cases[0].candidate_evidence[1]

    class ThreeCandidateSearch:
        provider_id = "three-candidates"

        async def search(self, request):
            del request
            return tuple(
                SearchResult(
                    url=f"https://page.example/{number}",
                    title=f"Candidate {number}",
                    snippet="A candidate about calendar and Julian years.",
                    source_type=SourceType.OTHER,
                )
                for number in range(1, 4)
            )

    retrieval = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            ThreeCandidateSearch(),
            limit=1,
            top_k=3,
        )
    )

    class FakeFetcher:
        provider_id = "fake-fetcher"

        async def fetch(self, url):
            if url.endswith("/3"):
                raise RuntimeError("publisher blocked the request")
            text = (
                "<html><main><p>"
                f"{reference.excerpt} "
                "This official definition distinguishes the two conventions."
                "</p></main></html>"
            )
            return FetchedDocument(
                requested_url=url,
                final_url=url,
                status_code=200,
                content_type="text/html",
                text=text,
                byte_length=len(text.encode()),
            )

    summary = asyncio.run(
        run_page_fetch_evaluation(
            dataset,
            retrieval,
            FakeFetcher(),
            retrieval_input="retrieval.json",
            candidate_top_n=3,
            passage_top_k=2,
            passage_lexical_threshold=0.2,
        )
    )
    output = export_page_fetch_evaluation(summary, tmp_path / "pages.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert summary.attempted_page_count == 3
    assert summary.fetched_page_count == 2
    assert summary.extracted_page_count == 2
    assert summary.duplicate_page_count == 1
    assert summary.fetch_success_rate == 0.666667
    assert summary.extraction_success_rate == 0.666667
    assert summary.duplicate_content_rate == 0.5
    assert summary.matched_reference_count >= 1
    assert summary.case_passage_success_rate == 1.0
    assert summary.results[0].pages[1].duplicate_of_url is not None
    assert summary.results[0].pages[0].reference_matches
    assert summary.results[0].pages[2].error_type == "RuntimeError"
    assert payload["limitations"]
