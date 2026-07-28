"""Semantic Scholar academic search adapter with bounded result metadata."""

import ssl
from typing import Any

import httpx
import truststore
from pydantic import ValidationError

from claim_polygraph_ng.domain import ResearchPath, SearchRequest, SearchResult, SourceType
from claim_polygraph_ng.domain.research import ROLE_PERMISSIONS, ResearchRole
from claim_polygraph_ng.domain.specialist import (
    AcademicSearchPage,
    AcademicSearchResult,
    ProviderRatePolicy,
    SpecialistSearchRequest,
)
from claim_polygraph_ng.providers.rate_limit import AsyncRequestRateGate
from claim_polygraph_ng.providers.searxng import SearchProviderError

_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "paperId,title,url,abstract,authors,year,publicationDate,journal,externalIds"


class SemanticScholarAcademicSearchProvider:
    """Search Semantic Scholar while preserving scholarly identifiers."""

    provider_id = "semantic-scholar:graph"
    role = ResearchRole.ACADEMIC
    permissions = ROLE_PERMISSIONS[ResearchRole.ACADEMIC]

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 15,
        rate_policy: ProviderRatePolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if api_key and any(character.isspace() for character in api_key):
            raise ValueError("Semantic Scholar API key cannot contain whitespace")
        self._api_key = api_key.strip() if api_key else None
        self._timeout = httpx.Timeout(timeout_seconds)
        self._rate_policy = rate_policy or ProviderRatePolicy(
            maximum_requests_per_operation=1,
            maximum_results_per_operation=20,
            declared_requests_per_second=1,
        )
        self._transport = transport
        self._ssl_context = ssl_context or truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._rate_gate = AsyncRequestRateGate(
            self._rate_policy.declared_requests_per_second
        )

    async def search_academic(
        self, request: SpecialistSearchRequest
    ) -> AcademicSearchPage:
        limit = min(
            request.maximum_results,
            self._rate_policy.maximum_results_per_operation,
        )
        offset = _cursor_offset(request.cursor)
        headers = {"x-api-key": self._api_key} if self._api_key else {}
        try:
            await self._rate_gate.wait()
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
                transport=self._transport,
                trust_env=False,
                verify=self._ssl_context,
            ) as client:
                response = await client.get(
                    _SEARCH_URL,
                    params={
                        "query": request.query,
                        "limit": str(limit),
                        "offset": str(offset),
                        "fields": _FIELDS,
                    },
                    headers=headers,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise SearchProviderError(
                f"Semantic Scholar request failed: {type(error).__name__}"
            ) from error
        if response.status_code == 429:
            raise SearchProviderError("Semantic Scholar rate limit was exceeded")
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPStatusError, ValueError) as error:
            raise SearchProviderError(
                f"Semantic Scholar returned an invalid response: HTTP {response.status_code}"
            ) from error
        if not isinstance(payload, dict) or not isinstance(payload.get("data", []), list):
            raise SearchProviderError("Semantic Scholar returned an invalid result shape")
        total = _nonnegative_int(payload.get("total", 0))
        results = _normalize_papers(payload.get("data", []), limit)
        next_offset = offset + len(payload.get("data", []))
        return AcademicSearchPage(
            results=results,
            next_cursor=str(next_offset) if next_offset < total else None,
            request_count=1,
        )

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        if request.research_path is not ResearchPath.ACADEMIC:
            raise SearchProviderError("Semantic Scholar requires the academic research path")
        page = await self.search_academic(
            SpecialistSearchRequest(
                query=request.query,
                maximum_results=request.maximum_results,
            )
        )
        return tuple(item.candidate for item in page.results)


def _normalize_papers(
    papers: list[Any],
    maximum_results: int,
) -> tuple[AcademicSearchResult, ...]:
    normalized = []
    for paper in papers:
        if not isinstance(paper, dict):
            continue
        paper_id = paper.get("paperId")
        title = paper.get("title")
        url = paper.get("url")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (paper_id, title, url)
        ):
            continue
        journal = paper.get("journal")
        journal_name = journal.get("name") if isinstance(journal, dict) else None
        external_ids = paper.get("externalIds")
        doi = external_ids.get("DOI") if isinstance(external_ids, dict) else None
        abstract = paper.get("abstract")
        snippet = (
            abstract[:10_000]
            if isinstance(abstract, str) and abstract.strip()
            else "Semantic Scholar indexed publication."
        )
        try:
            normalized.append(
                AcademicSearchResult(
                    candidate=SearchResult(
                        url=url,
                        title=title,
                        snippet=snippet,
                        source_type=SourceType.ACADEMIC,
                        publisher="Semantic Scholar",
                    ),
                    provider_record_id=paper_id,
                    doi=doi if isinstance(doi, str) else None,
                    journal=journal_name if isinstance(journal_name, str) else None,
                    publication_date_text=_publication_date(paper),
                    authors=tuple(
                        author["name"]
                        for author in paper.get("authors", [])
                        if isinstance(author, dict)
                        and isinstance(author.get("name"), str)
                    ),
                    publication_types=(),
                )
            )
        except ValidationError:
            continue
        if len(normalized) >= maximum_results:
            break
    return tuple(normalized)


def _publication_date(paper: dict[str, Any]) -> str | None:
    value = paper.get("publicationDate")
    if isinstance(value, str) and value.strip():
        return value
    year = paper.get("year")
    return str(year) if isinstance(year, int) else None


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    if not cursor.isdigit():
        raise ValueError("Semantic Scholar cursor must be a non-negative integer")
    return int(cursor)


def _nonnegative_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise SearchProviderError("Semantic Scholar result count is invalid") from error
    if parsed < 0:
        raise SearchProviderError("Semantic Scholar result count is invalid")
    return parsed
