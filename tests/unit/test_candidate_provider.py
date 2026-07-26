"""Tests for replaying ranked retrieval candidates through live page fetching."""

import asyncio
from uuid import uuid4

from claim_polygraph_ng.domain import ResearchPath, SearchRequest, SourceType
from claim_polygraph_ng.evaluation import (
    RetrievalCandidate,
    RetrievalCandidateSearchProvider,
    RetrievalCaseResult,
)


def _candidate(
    rank: int,
    *,
    source_type: SourceType = SourceType.OTHER,
    query: str = "claim",
) -> RetrievalCandidate:
    return RetrievalCandidate(
        rank=rank,
        url=f"https://example{rank}.org/evidence",
        title=f"Evidence {rank}",
        snippet=f"Passage candidate {rank}.",
        source_type=source_type,
        publisher=f"publisher-{rank}",
        fusion_score=1 / rank,
        query_ranks={query: rank},
        quality_score=0.8,
        quality_features={},
    )


def _case(*candidates: RetrievalCandidate) -> RetrievalCaseResult:
    return RetrievalCaseResult(
        case_id="CPNG-TEST",
        queries=("claim",),
        query_errors={},
        result_count=len(candidates),
        reference_count=0,
        exact_url_hit_count=0,
        reviewed_host_hit_count=0,
        lexical_hit_count=0,
        reciprocal_rank_exact_url=0,
        reciprocal_rank_reviewed_host=0,
        candidates=candidates,
        references=(),
        duration_seconds=0,
    )


def test_candidate_provider_prioritizes_paths_and_never_reuses_results() -> None:
    provider = RetrievalCandidateSearchProvider(
        _case(
            _candidate(1),
            _candidate(2, query="claim counterevidence fact check"),
            _candidate(3, source_type=SourceType.OFFICIAL),
        ),
        "frozen",
    )

    contradiction = asyncio.run(
        provider.search(
            SearchRequest(
                claim_id=uuid4(),
                query="counter query",
                research_path=ResearchPath.CONTRADICTION,
                maximum_results=1,
            )
        )
    )
    primary = asyncio.run(
        provider.search(
            SearchRequest(
                claim_id=uuid4(),
                query="primary query",
                research_path=ResearchPath.PRIMARY,
                maximum_results=2,
            )
        )
    )
    exhausted = asyncio.run(
        provider.search(
            SearchRequest(
                claim_id=uuid4(),
                query="general query",
                research_path=ResearchPath.GENERAL,
                maximum_results=3,
            )
        )
    )

    assert provider.provider_id == "retrieval-candidates:frozen:CPNG-TEST"
    assert str(contradiction[0].url) == "https://example2.org/evidence"
    assert [str(result.url) for result in primary] == [
        "https://example3.org/evidence",
        "https://example1.org/evidence",
    ]
    assert exhausted == ()
