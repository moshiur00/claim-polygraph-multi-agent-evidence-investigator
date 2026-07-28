"""NCBI PubMed specialist search adapter with bounded metadata normalization."""

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

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedAcademicSearchProvider:
    """Search PubMed while retaining identifiers and publication metadata."""

    provider_id = "ncbi:pubmed"
    role = ResearchRole.ACADEMIC
    permissions = ROLE_PERMISSIONS[ResearchRole.ACADEMIC]

    def __init__(
        self,
        *,
        tool: str = "claim-polygraph-ng",
        email: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 15,
        rate_policy: ProviderRatePolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        if not tool.strip() or any(character.isspace() for character in tool):
            raise ValueError("NCBI tool name cannot be empty or contain whitespace")
        if email and any(character.isspace() for character in email):
            raise ValueError("NCBI email cannot contain whitespace")
        if api_key and any(character.isspace() for character in api_key):
            raise ValueError("NCBI API key cannot contain whitespace")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._tool = tool.strip()
        self._email = email.strip() if email else None
        self._api_key = api_key.strip() if api_key else None
        self._timeout = httpx.Timeout(timeout_seconds)
        self._rate_policy = rate_policy or ProviderRatePolicy(
            maximum_requests_per_operation=2,
            maximum_results_per_operation=20,
            declared_requests_per_second=3,
        )
        if self._rate_policy.maximum_requests_per_operation < 2:
            raise ValueError("PubMed search requires a two-request operation budget")
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
        common = {"retmode": "json", "tool": self._tool}
        if self._email:
            common["email"] = self._email
        if self._api_key:
            common["api_key"] = self._api_key
        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=False,
            transport=self._transport,
            trust_env=False,
            verify=self._ssl_context,
        ) as client:
            await self._rate_gate.wait()
            search_payload = await _get_json(
                client,
                f"{_BASE_URL}/esearch.fcgi",
                {
                    **common,
                    "db": "pubmed",
                    "term": request.query,
                    "retmax": str(limit),
                    "retstart": str(offset),
                },
            )
            search_result = search_payload.get("esearchresult")
            if not isinstance(search_result, dict):
                raise SearchProviderError("PubMed returned an invalid search-result shape")
            raw_ids = search_result.get("idlist", [])
            if not isinstance(raw_ids, list) or any(
                not isinstance(item, str) or not item.isdigit() for item in raw_ids
            ):
                raise SearchProviderError("PubMed returned invalid record identifiers")
            ids = raw_ids[:limit]
            total = _nonnegative_int(search_result.get("count"), "PubMed result count")
            if not ids:
                return AcademicSearchPage(
                    results=(),
                    next_cursor=None,
                    request_count=1,
                )
            await self._rate_gate.wait()
            summary_payload = await _get_json(
                client,
                f"{_BASE_URL}/esummary.fcgi",
                {**common, "db": "pubmed", "id": ",".join(ids)},
            )
        results = _normalize_summaries(summary_payload, ids)
        next_offset = offset + len(ids)
        return AcademicSearchPage(
            results=results,
            next_cursor=str(next_offset) if next_offset < total else None,
            request_count=2,
        )

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Adapt specialist records to safe-fetch candidates for existing workflows."""
        if request.research_path is not ResearchPath.ACADEMIC:
            raise SearchProviderError("PubMed requires the academic research path")
        page = await self.search_academic(
            SpecialistSearchRequest(
                query=request.query,
                maximum_results=request.maximum_results,
            )
        )
        return tuple(item.candidate for item in page.results)


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str],
) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params)
    except (httpx.TimeoutException, httpx.NetworkError) as error:
        raise SearchProviderError(f"PubMed request failed: {type(error).__name__}") from error
    if response.status_code == 429:
        raise SearchProviderError("PubMed rate limit was exceeded")
    try:
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPStatusError, ValueError) as error:
        raise SearchProviderError(
            f"PubMed returned an invalid response: HTTP {response.status_code}"
        ) from error
    if not isinstance(payload, dict):
        raise SearchProviderError("PubMed returned a non-object JSON response")
    return payload


def _normalize_summaries(
    payload: dict[str, Any],
    ids: list[str],
) -> tuple[AcademicSearchResult, ...]:
    raw_results = payload.get("result")
    if not isinstance(raw_results, dict):
        raise SearchProviderError("PubMed returned an invalid summary-result shape")
    normalized = []
    for record_id in ids:
        raw = raw_results.get(record_id)
        if not isinstance(raw, dict):
            continue
        title = raw.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        publication_types = _string_tuple(raw.get("pubtype"))
        article_ids = raw.get("articleids", [])
        doi = next(
            (
                item.get("value")
                for item in article_ids
                if isinstance(item, dict)
                and item.get("idtype") == "doi"
                and isinstance(item.get("value"), str)
            ),
            None,
        )
        snippet = " · ".join(
            value
            for value in (
                raw.get("fulljournalname"),
                raw.get("pubdate"),
                ", ".join(publication_types),
            )
            if isinstance(value, str) and value.strip()
        ) or "PubMed indexed publication."
        try:
            normalized.append(
                AcademicSearchResult(
                    candidate=SearchResult(
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{record_id}/",
                        title=title.strip(),
                        snippet=snippet,
                        source_type=SourceType.ACADEMIC,
                        publisher="PubMed / NCBI",
                    ),
                    provider_record_id=record_id,
                    doi=doi,
                    journal=_optional_string(raw.get("fulljournalname")),
                    publication_date_text=_optional_string(raw.get("pubdate")),
                    authors=tuple(
                        author["name"]
                        for author in raw.get("authors", [])
                        if isinstance(author, dict)
                        and isinstance(author.get("name"), str)
                    ),
                    publication_types=publication_types,
                    retracted=any("retracted" in value.casefold() for value in publication_types),
                    corrected=any(
                        "corrected" in value.casefold() or "erratum" in value.casefold()
                        for value in publication_types
                    ),
                )
            )
        except ValidationError:
            continue
    return tuple(normalized)


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    if not cursor.isdigit():
        raise ValueError("PubMed cursor must be a non-negative integer")
    return int(cursor)


def _nonnegative_int(value: object, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise SearchProviderError(f"{label} is invalid") from error
    if parsed < 0:
        raise SearchProviderError(f"{label} is invalid")
    return parsed


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
