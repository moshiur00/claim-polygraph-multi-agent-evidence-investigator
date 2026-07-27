"""Case-scoped search provider backed by reviewed benchmark evidence."""

import re

from claim_polygraph_ng.domain import EvidenceStance, ResearchPath, SearchRequest, SearchResult
from claim_polygraph_ng.domain.enums import SourceType
from claim_polygraph_ng.evaluation.models import BenchmarkCase, BenchmarkEvidenceAnnotation

_PRIMARY_TYPES = {
    SourceType.OFFICIAL,
    SourceType.PRIMARY_DOCUMENT,
    SourceType.DATASET,
    SourceType.LAW_OR_REGULATION,
}


class BenchmarkEvidenceSearchProvider:
    """Serve each curated evidence annotation once through the search protocol."""

    def __init__(
        self,
        case: BenchmarkCase,
        *,
        component_number: int | None = None,
    ) -> None:
        suffix = f":component-{component_number}" if component_number is not None else ""
        self.provider_id = f"benchmark-evidence:{case.case_id}{suffix}"
        self._remaining = [
            annotation
            for annotation in case.candidate_evidence
            if component_number is None or component_number in annotation.material_component_numbers
        ]

    @classmethod
    def for_component(
        cls,
        case: BenchmarkCase,
        component_text: str,
    ) -> "BenchmarkEvidenceSearchProvider":
        """Create an independent evidence pool for the closest expected component."""
        if not case.expected_components:
            return cls(case)
        component_tokens = _tokens(component_text)
        scores = [
            _jaccard(component_tokens, _tokens(expected)) for expected in case.expected_components
        ]
        component_number = max(range(len(scores)), key=scores.__getitem__) + 1
        return cls(case, component_number=component_number)

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Return the best unserved annotation for the requested research path."""
        if not self._remaining:
            return ()

        index = min(
            range(len(self._remaining)),
            key=lambda item_index: (
                self._path_priority(self._remaining[item_index], request.research_path),
                item_index,
            ),
        )
        annotation = self._remaining.pop(index)
        return (
            SearchResult(
                url=annotation.source_url,
                title=annotation.source_title,
                snippet=annotation.evidence_summary,
                inline_content=annotation.excerpt,
                source_type=annotation.source_type,
                publisher=annotation.publisher,
            ),
        )

    @staticmethod
    def _path_priority(
        annotation: BenchmarkEvidenceAnnotation,
        research_path: ResearchPath,
    ) -> int:
        if (
            research_path is ResearchPath.CONTRADICTION
            and annotation.stance is EvidenceStance.CONTRADICTS
        ):
            return 0
        if research_path is ResearchPath.GENERAL and annotation.stance in {
            EvidenceStance.QUALIFIES,
            EvidenceStance.SUPPORTS,
            EvidenceStance.CONTEXT,
        }:
            return 0
        if research_path is ResearchPath.PRIMARY and annotation.source_type in _PRIMARY_TYPES:
            return 0
        if research_path is ResearchPath.ACADEMIC and annotation.source_type is SourceType.ACADEMIC:
            return 0
        if (
            research_path is ResearchPath.FACT_CHECK
            and annotation.source_type is SourceType.FACT_CHECK
        ):
            return 0
        return 1


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0
