"""Contracts and policies for untrusted web retrieval."""

from datetime import datetime

from pydantic import AnyHttpUrl, Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import utc_now


class UrlSafetyPolicy(DomainModel):
    """Hard limits applied to every user-controlled document fetch."""

    allowed_schemes: frozenset[str] = frozenset({"http", "https"})
    allowed_ports: frozenset[int] = frozenset({80, 443})
    allowed_content_types: frozenset[str] = frozenset(
        {"text/html", "text/plain", "application/xhtml+xml"}
    )
    maximum_redirects: int = Field(default=3, ge=0, le=10)
    maximum_response_bytes: int = Field(
        default=2_000_000,
        ge=1_024,
        le=20_000_000,
    )
    timeout_seconds: float = Field(default=10.0, ge=0.1, le=120.0)
    user_agent: str = Field(
        default="ClaimPolygraphNG/0.1 (+local evidence investigator)",
        min_length=1,
        max_length=300,
    )


class FetchedDocument(DomainModel):
    """Validated textual response from an untrusted public URL."""

    requested_url: AnyHttpUrl
    final_url: AnyHttpUrl
    status_code: int = Field(ge=200, le=299)
    content_type: str = Field(min_length=1, max_length=200)
    text: str
    byte_length: int = Field(ge=0)
    redirect_chain: tuple[AnyHttpUrl, ...] = ()
    retrieved_at: datetime = Field(default_factory=utc_now)
