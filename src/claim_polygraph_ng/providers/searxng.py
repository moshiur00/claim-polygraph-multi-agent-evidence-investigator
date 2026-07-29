"""SearXNG JSON search adapter."""

import re
from typing import Any

import httpx
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    ResearchPath,
    SearchRequest,
    SearchResult,
    SourceType,
)
from claim_polygraph_ng.providers.result_normalization import (
    classify_candidate_distribution,
    retain_provider_metadata,
)

_RETAINED_METADATA_KEYS = (
    "engine",
    "engines",
    "category",
    "score",
    "publishedDate",
    "template",
    "positions",
)


class SearchProviderError(RuntimeError):
    """Normalized failure returned by a search backend."""


class SearXNGSearchProvider:
    """Query a configured SearXNG instance through its JSON API."""

    provider_id = "searxng"

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        language: str = "en",
        safe_search: int = 2,
        engines: tuple[str, ...] = (),
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed_url = httpx.URL(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.host:
            raise ValueError("SearXNG base URL must be HTTP(S) with a hostname")
        if parsed_url.username or parsed_url.password:
            raise ValueError("SearXNG base URL cannot contain credentials")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if safe_search not in {0, 1, 2}:
            raise ValueError("safe_search must be 0, 1, or 2")
        if any(
            not engine.strip() or re.fullmatch(r"[a-zA-Z0-9 _-]+", engine.strip()) is None
            for engine in engines
        ):
            raise ValueError("SearXNG engine names contain unsupported characters")

        self._search_url = str(parsed_url).rstrip("/") + "/search"
        self._timeout = httpx.Timeout(timeout_seconds)
        self._language = language
        self._safe_search = safe_search
        self._engines = tuple(engine.strip() for engine in engines)
        self._transport = transport

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Return normalized candidate results in provider order."""
        params = {
            "q": request.query,
            "format": "json",
            "language": self._language,
            "safesearch": str(self._safe_search),
            "pageno": "1",
        }
        category = self._category_for(request.research_path)
        if category:
            params["categories"] = category
        if self._engines:
            params["engines"] = ",".join(self._engines)

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
                transport=self._transport,
                trust_env=False,
            ) as client:
                response = await client.get(self._search_url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SearchProviderError(f"SearXNG request failed: {error}") from error

        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise SearchProviderError("SearXNG returned an invalid JSON result shape")

        normalized: list[SearchResult] = []
        for raw_result in payload["results"]:
            result = self._normalize_result(raw_result)
            if result is not None:
                normalized.append(result)
            if len(normalized) >= request.maximum_results:
                break
        return tuple(normalized)

    @staticmethod
    def _normalize_result(raw_result: Any) -> SearchResult | None:
        if not isinstance(raw_result, dict):
            return None

        url = raw_result.get("url")
        title = raw_result.get("title")
        snippet = raw_result.get("content")
        if not all(isinstance(value, str) and value.strip() for value in (url, title, snippet)):
            return None

        try:
            distribution_medium, social_url = classify_candidate_distribution(url)
            return SearchResult(
                url=url,
                title=title,
                snippet=snippet,
                source_type=SearXNGSearchProvider._source_type(raw_result),
                publisher=SearXNGSearchProvider._publisher(raw_result),
                distribution_medium=distribution_medium,
                social_url=social_url,
                provider_metadata=retain_provider_metadata(
                    provider_id="searxng",
                    raw_result=raw_result,
                    attribute_keys=_RETAINED_METADATA_KEYS,
                    result_id_keys=("id",),
                ),
            )
        except (ValidationError, ValueError):
            return None

    @staticmethod
    def _category_for(research_path: ResearchPath) -> str | None:
        if research_path is ResearchPath.ACADEMIC:
            return "science"
        if research_path is ResearchPath.GENERAL:
            return "general"
        return None

    @staticmethod
    def _source_type(raw_result: dict[str, Any]) -> SourceType:
        category = str(raw_result.get("category", "")).lower()
        if category in {"science", "scientific publications"}:
            return SourceType.ACADEMIC
        if category == "news":
            return SourceType.NEWS
        return SourceType.OTHER

    @staticmethod
    def _publisher(raw_result: dict[str, Any]) -> str | None:
        engines = raw_result.get("engines")
        if isinstance(engines, list):
            values = [str(value) for value in engines if value]
            return ", ".join(values) or None
        engine = raw_result.get("engine")
        return str(engine) if engine else None
