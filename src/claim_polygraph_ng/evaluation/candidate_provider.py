"""Case-scoped search provider backed by frozen retrieval candidates."""

from claim_polygraph_ng.domain import ResearchPath, SearchRequest, SearchResult, SourceType
from claim_polygraph_ng.evaluation.models import RetrievalCandidate, RetrievalCaseResult


class RetrievalCandidateSearchProvider:
    """Serve disjoint frozen candidates through the real page-fetch path."""

    def __init__(self, case: RetrievalCaseResult, provider_id: str) -> None:
        self.provider_id = f"retrieval-candidates:{provider_id}:{case.case_id}"
        self._remaining = list(case.candidates)

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        ordered = sorted(
            self._remaining,
            key=lambda candidate: (
                self._path_priority(candidate, request.research_path),
                candidate.rank,
            ),
        )
        selected = ordered[: request.maximum_results]
        selected_ids = {str(candidate.url) for candidate in selected}
        self._remaining = [
            candidate
            for candidate in self._remaining
            if str(candidate.url) not in selected_ids
        ]
        return tuple(
            SearchResult(
                url=candidate.url,
                title=candidate.title,
                snippet=candidate.snippet,
                source_type=candidate.source_type,
                publisher=candidate.publisher,
            )
            for candidate in selected
        )

    @staticmethod
    def _path_priority(
        candidate: RetrievalCandidate,
        research_path: ResearchPath,
    ) -> int:
        queries = " ".join(candidate.query_ranks).casefold()
        if research_path is ResearchPath.CONTRADICTION:
            return 0 if "counterevidence fact check" in queries else 1
        if research_path is ResearchPath.PRIMARY:
            if candidate.source_type in {
                SourceType.OFFICIAL,
                SourceType.PRIMARY_DOCUMENT,
                SourceType.DATASET,
                SourceType.LAW_OR_REGULATION,
            }:
                return 0
            return 0 if "official authoritative source" in queries else 1
        if research_path is ResearchPath.ACADEMIC:
            return 0 if candidate.source_type is SourceType.ACADEMIC else 1
        if research_path is ResearchPath.FACT_CHECK:
            return 0 if candidate.source_type is SourceType.FACT_CHECK else 1
        return 0
