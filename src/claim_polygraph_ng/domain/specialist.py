"""Typed metadata contracts for specialist academic and fact-check search."""

from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import ContentRetention, RightsStatus
from claim_polygraph_ng.domain.investigation import SearchResult


class SpecialistSearchRequest(DomainModel):
    """Provider-neutral bounded specialist query with an opaque page cursor."""

    query: str = Field(min_length=3, max_length=1_000)
    maximum_results: int = Field(default=5, ge=1, le=20)
    cursor: str | None = Field(default=None, max_length=500)


class ProviderRatePolicy(DomainModel):
    """Explicit per-operation call and result ceilings."""

    maximum_requests_per_operation: int = Field(default=2, ge=1, le=5)
    maximum_results_per_operation: int = Field(default=20, ge=1, le=100)
    declared_requests_per_second: float = Field(default=3.0, gt=0, le=100)


class AcademicSearchResult(DomainModel):
    """Academic candidate plus metadata unavailable from general web search."""

    kind: Literal["academic"] = "academic"
    candidate: SearchResult
    provider_record_id: str = Field(min_length=1, max_length=200)
    doi: str | None = Field(default=None, max_length=500)
    journal: str | None = Field(default=None, max_length=1_000)
    publication_date_text: str | None = Field(default=None, max_length=200)
    authors: tuple[str, ...] = Field(default=(), max_length=100)
    publication_types: tuple[str, ...] = Field(default=(), max_length=50)
    retracted: bool = False
    corrected: bool = False
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    content_retention: ContentRetention = ContentRetention.EVIDENCE_PASSAGES_ONLY


class FactCheckSearchResult(DomainModel):
    """Fact-check candidate with claimant, rating and review provenance."""

    kind: Literal["fact_check"] = "fact_check"
    candidate: SearchResult
    provider_record_id: str = Field(min_length=1, max_length=500)
    claim_text: str = Field(min_length=3, max_length=5_000)
    claimant: str | None = Field(default=None, max_length=500)
    claim_date: date | None = None
    review_publisher: str = Field(min_length=1, max_length=500)
    textual_rating: str = Field(min_length=1, max_length=500)
    review_date: date | None = None
    language_code: str | None = Field(default=None, max_length=30)
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    content_retention: ContentRetention = ContentRetention.EVIDENCE_PASSAGES_ONLY


SpecialistSearchResult = Annotated[
    AcademicSearchResult | FactCheckSearchResult,
    Field(discriminator="kind"),
]


class AcademicSearchPage(DomainModel):
    """One bounded academic page and its opaque continuation cursor."""

    results: tuple[AcademicSearchResult, ...]
    next_cursor: str | None = Field(default=None, max_length=500)
    request_count: int = Field(ge=0, le=5)


class FactCheckSearchPage(DomainModel):
    """One bounded fact-check page and its opaque continuation cursor."""

    results: tuple[FactCheckSearchResult, ...]
    next_cursor: str | None = Field(default=None, max_length=500)
    request_count: int = Field(ge=0, le=5)
