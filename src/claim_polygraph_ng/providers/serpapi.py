"""Hosted SerpAPI adapter for normalized organic search results."""

import re
import ssl
from typing import Any

import httpx
import truststore
from pydantic import ValidationError

from claim_polygraph_ng.domain import SearchRequest, SearchResult, SourceType
from claim_polygraph_ng.providers.result_normalization import (
    classify_candidate_distribution,
    retain_provider_metadata,
)
from claim_polygraph_ng.providers.searxng import SearchProviderError

_SEARCH_URL = "https://serpapi.com/search.json"
_SUPPORTED_ENGINES = frozenset({"google", "duckduckgo"})
_LOCALE_PATTERN = re.compile(r"^[a-z]{2}$")
_RETAINED_METADATA_KEYS = (
    "position",
    "source",
    "displayed_link",
    "date",
    "result_id",
    "about_this_result",
)


class SerpAPISearchProvider:
    """Query Google or DuckDuckGo through SerpAPI's structured API."""

    def __init__(
        self,
        *,
        api_key: str,
        engine: str = "google",
        language: str = "en",
        country: str = "us",
        safe_search: bool = True,
        timeout_seconds: float = 15.0,
        maximum_attempts: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        normalized_engine = engine.strip().casefold()
        normalized_language = language.strip().casefold()
        normalized_country = country.strip().casefold()
        if not api_key.strip() or any(character.isspace() for character in api_key):
            raise ValueError("SerpAPI API key must be non-empty and contain no whitespace")
        if normalized_engine not in _SUPPORTED_ENGINES:
            supported = ", ".join(sorted(_SUPPORTED_ENGINES))
            raise ValueError(f"SerpAPI engine must be one of: {supported}")
        if _LOCALE_PATTERN.fullmatch(normalized_language) is None:
            raise ValueError("SerpAPI language must be a two-letter code")
        if _LOCALE_PATTERN.fullmatch(normalized_country) is None:
            raise ValueError("SerpAPI country must be a two-letter code")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if maximum_attempts not in {1, 2}:
            raise ValueError("maximum_attempts must be 1 or 2")

        self.provider_id = f"serpapi:{normalized_engine}"
        self._api_key = api_key
        self._engine = normalized_engine
        self._language = normalized_language
        self._country = normalized_country
        self._safe_search = safe_search
        self._timeout = httpx.Timeout(timeout_seconds)
        self._maximum_attempts = maximum_attempts
        self._transport = transport
        self._ssl_context = ssl_context or truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Return normalized organic candidates in provider rank order."""
        params = self._parameters(request)
        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=False,
            transport=self._transport,
            trust_env=False,
            verify=self._ssl_context,
        ) as client:
            for attempt in range(1, self._maximum_attempts + 1):
                try:
                    response = await client.get(_SEARCH_URL, params=params)
                except (httpx.TimeoutException, httpx.NetworkError) as error:
                    if attempt < self._maximum_attempts:
                        continue
                    raise SearchProviderError(
                        f"SerpAPI request failed after {attempt} attempts: {error}"
                    ) from error

                if (
                    response.status_code in {408, 429} or response.status_code >= 500
                ) and attempt < self._maximum_attempts:
                    continue
                payload = self._validated_payload(response)
                return self._normalize_results(
                    payload,
                    request.maximum_results,
                    self.provider_id,
                )

        raise SearchProviderError("SerpAPI request failed without a response")

    def _parameters(self, request: SearchRequest) -> dict[str, str]:
        params = {
            "api_key": self._api_key,
            "engine": self._engine,
            "q": request.query,
            "output": "json",
        }
        if self._engine == "google":
            params.update(
                {
                    "hl": self._language,
                    "gl": self._country,
                    "safe": "active" if self._safe_search else "off",
                    "num": str(request.maximum_results),
                }
            )
        else:
            params.update(
                {
                    "kl": f"{self._country}-{self._language}",
                    "safe": "1" if self._safe_search else "-2",
                    "m": str(request.maximum_results),
                }
            )
        return params

    @staticmethod
    def _validated_payload(response: httpx.Response) -> dict[str, Any]:
        if response.status_code in {401, 403}:
            raise SearchProviderError("SerpAPI authentication was rejected")
        if response.status_code == 429:
            try:
                rate_payload = response.json()
            except ValueError:
                rate_payload = {}
            rate_error = rate_payload.get("error") if isinstance(rate_payload, dict) else None
            if isinstance(rate_error, str) and "activat" in rate_error.casefold():
                raise SearchProviderError(
                    "SerpAPI account activation is required; complete activation at "
                    "https://serpapi.com/users/welcome"
                )
            raise SearchProviderError("SerpAPI quota or rate limit was exceeded")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise SearchProviderError(f"SerpAPI returned HTTP {response.status_code}") from error
        try:
            payload = response.json()
        except ValueError as error:
            raise SearchProviderError("SerpAPI returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise SearchProviderError("SerpAPI returned an invalid JSON result shape")
        error_message = payload.get("error")
        if isinstance(error_message, str) and error_message.strip():
            raise SearchProviderError(f"SerpAPI returned an error: {error_message}")
        organic_results = payload.get("organic_results", [])
        if not isinstance(organic_results, list):
            raise SearchProviderError("SerpAPI returned an invalid organic-results shape")
        return payload

    @staticmethod
    def _normalize_results(
        payload: dict[str, Any],
        maximum_results: int,
        provider_id: str,
    ) -> tuple[SearchResult, ...]:
        normalized: list[SearchResult] = []
        for raw_result in payload.get("organic_results", []):
            result = SerpAPISearchProvider._normalize_result(raw_result, provider_id)
            if result is not None:
                normalized.append(result)
            if len(normalized) >= maximum_results:
                break
        return tuple(normalized)

    @staticmethod
    def _normalize_result(
        raw_result: Any,
        provider_id: str,
    ) -> SearchResult | None:
        if not isinstance(raw_result, dict):
            return None
        url = raw_result.get("link")
        title = raw_result.get("title")
        snippet = raw_result.get("snippet")
        if not all(isinstance(value, str) and value.strip() for value in (url, title, snippet)):
            return None
        publisher = raw_result.get("source")
        if not isinstance(publisher, str) or not publisher.strip():
            publisher = raw_result.get("displayed_link")
        try:
            distribution_medium, social_url = classify_candidate_distribution(url)
            return SearchResult(
                url=url,
                title=title,
                snippet=snippet,
                source_type=SourceType.OTHER,
                publisher=(
                    publisher.strip() if isinstance(publisher, str) and publisher.strip() else None
                ),
                distribution_medium=distribution_medium,
                social_url=social_url,
                provider_metadata=retain_provider_metadata(
                    provider_id=provider_id,
                    raw_result=raw_result,
                    attribute_keys=_RETAINED_METADATA_KEYS,
                    rank_key="position",
                    result_id_keys=("result_id",),
                ),
            )
        except (ValidationError, ValueError):
            return None
