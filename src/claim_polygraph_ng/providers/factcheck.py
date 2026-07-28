"""Google Fact Check Claim Search specialist adapter."""

import ssl
from datetime import date
from typing import Any

import httpx
import truststore
from pydantic import ValidationError

from claim_polygraph_ng.domain import ResearchPath, SearchRequest, SearchResult, SourceType
from claim_polygraph_ng.domain.research import ROLE_PERMISSIONS, ResearchRole
from claim_polygraph_ng.domain.specialist import (
    FactCheckSearchPage,
    FactCheckSearchResult,
    ProviderRatePolicy,
    SpecialistSearchRequest,
)
from claim_polygraph_ng.providers.rate_limit import AsyncRequestRateGate
from claim_polygraph_ng.providers.searxng import SearchProviderError

_SEARCH_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


class GoogleFactCheckSearchProvider:
    """Search reviewed claims while retaining ratings and review provenance."""

    provider_id = "google:fact-check-tools"
    role = ResearchRole.FACT_CHECK
    permissions = ROLE_PERMISSIONS[ResearchRole.FACT_CHECK]

    def __init__(
        self,
        *,
        api_key: str,
        language_code: str = "en",
        timeout_seconds: float = 15,
        rate_policy: ProviderRatePolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        if not api_key.strip() or any(character.isspace() for character in api_key):
            raise ValueError("Fact Check API key must be non-empty and contain no whitespace")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._api_key = api_key
        self._language_code = language_code.strip()
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

    async def search_fact_checks(
        self, request: SpecialistSearchRequest
    ) -> FactCheckSearchPage:
        limit = min(
            request.maximum_results,
            self._rate_policy.maximum_results_per_operation,
        )
        params = {
            "key": self._api_key,
            "query": request.query,
            "pageSize": str(limit),
            "languageCode": self._language_code,
        }
        if request.cursor:
            params["pageToken"] = request.cursor
        try:
            await self._rate_gate.wait()
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
                transport=self._transport,
                trust_env=False,
                verify=self._ssl_context,
            ) as client:
                response = await client.get(_SEARCH_URL, params=params)
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise SearchProviderError(
                f"Fact Check request failed: {type(error).__name__}"
            ) from error
        if response.status_code == 429:
            raise SearchProviderError("Fact Check API rate limit was exceeded")
        if response.status_code in {401, 403}:
            raise SearchProviderError("Fact Check API authentication was rejected")
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPStatusError, ValueError) as error:
            raise SearchProviderError(
                f"Fact Check API returned an invalid response: HTTP {response.status_code}"
            ) from error
        if not isinstance(payload, dict):
            raise SearchProviderError("Fact Check API returned a non-object JSON response")
        claims = payload.get("claims", [])
        if not isinstance(claims, list):
            raise SearchProviderError("Fact Check API returned an invalid claims shape")
        return FactCheckSearchPage(
            results=_normalize_claims(claims, limit),
            next_cursor=_optional_string(payload.get("nextPageToken")),
            request_count=1,
        )

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Adapt reviews to safe-fetch candidates for the existing evidence pipeline."""
        if request.research_path is not ResearchPath.FACT_CHECK:
            raise SearchProviderError("Fact Check API requires the fact-check research path")
        page = await self.search_fact_checks(
            SpecialistSearchRequest(
                query=request.query,
                maximum_results=request.maximum_results,
            )
        )
        return tuple(item.candidate for item in page.results)


def _normalize_claims(
    claims: list[Any],
    maximum_results: int,
) -> tuple[FactCheckSearchResult, ...]:
    normalized = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_text = claim.get("text")
        reviews = claim.get("claimReview", [])
        if (
            not isinstance(claim_text, str)
            or not claim_text.strip()
            or not isinstance(reviews, list)
        ):
            continue
        for review in reviews:
            result = _normalize_review(claim, claim_text, review)
            if result is not None:
                normalized.append(result)
            if len(normalized) >= maximum_results:
                return tuple(normalized)
    return tuple(normalized)


def _normalize_review(
    claim: dict[str, Any],
    claim_text: str,
    review: Any,
) -> FactCheckSearchResult | None:
    if not isinstance(review, dict):
        return None
    publisher = review.get("publisher")
    publisher_name = publisher.get("name") if isinstance(publisher, dict) else None
    url = review.get("url")
    rating = review.get("textualRating")
    if not all(
        isinstance(value, str) and value.strip()
        for value in (publisher_name, url, rating)
    ):
        return None
    title = f"{publisher_name}: {claim_text}"
    try:
        return FactCheckSearchResult(
            candidate=SearchResult(
                url=url,
                title=title[:1_000],
                snippet=f"Reviewed rating: {rating}",
                source_type=SourceType.FACT_CHECK,
                publisher=publisher_name,
            ),
            provider_record_id=str(url),
            claim_text=claim_text,
            claimant=_optional_string(claim.get("claimant")),
            claim_date=_date_prefix(claim.get("claimDate")),
            review_publisher=publisher_name,
            textual_rating=rating,
            review_date=_date_prefix(review.get("reviewDate")),
            language_code=_optional_string(review.get("languageCode")),
        )
    except ValidationError:
        return None


def _date_prefix(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
