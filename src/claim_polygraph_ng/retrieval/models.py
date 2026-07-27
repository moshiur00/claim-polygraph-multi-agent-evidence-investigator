"""Contracts and policies for untrusted web retrieval."""

import re
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, Field, field_validator, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import ResearchPath
from claim_polygraph_ng.domain.investigation import utc_now


class UrlSafetyPolicy(DomainModel):
    """Hard limits applied to every user-controlled document fetch."""

    allowed_schemes: frozenset[str] = frozenset({"http", "https"})
    allowed_ports: frozenset[int] = frozenset({80, 443})
    allowed_content_types: frozenset[str] = frozenset(
        {"text/html", "text/plain", "application/xhtml+xml", "application/pdf"}
    )
    allowed_pdf_hosts: frozenset[str] = frozenset()
    maximum_redirects: int = Field(default=3, ge=0, le=10)
    maximum_response_bytes: int = Field(
        default=2_000_000,
        ge=1_024,
        le=20_000_000,
    )
    maximum_pdf_response_bytes: int = Field(
        default=20_000_000,
        ge=1_024,
        le=50_000_000,
    )
    timeout_seconds: float = Field(default=10.0, ge=0.1, le=120.0)
    user_agent: str = Field(
        default="ClaimPolygraphNG/0.1 (+local evidence investigator)",
        min_length=1,
        max_length=300,
    )

    @field_validator("allowed_pdf_hosts")
    @classmethod
    def normalize_pdf_hosts(cls, hosts: frozenset[str]) -> frozenset[str]:
        normalized = frozenset(host.casefold().rstrip(".") for host in hosts)
        if any(not host or re.fullmatch(r"[a-z0-9.-]+", host) is None for host in normalized):
            raise ValueError("PDF allowlist entries must be hostnames without schemes or paths")
        return normalized


class FetchedDocument(DomainModel):
    """Validated textual or PDF response from an untrusted public URL."""

    requested_url: AnyHttpUrl
    final_url: AnyHttpUrl
    status_code: int = Field(ge=200, le=299)
    content_type: str = Field(min_length=1, max_length=200)
    text: str
    raw_content: bytes | None = Field(default=None, repr=False)
    byte_length: int = Field(ge=0)
    redirect_chain: tuple[AnyHttpUrl, ...] = ()
    retrieved_at: datetime = Field(default_factory=utc_now)


class PdfExtractionPolicy(DomainModel):
    """Hard limits applied before and during PDF text extraction."""

    maximum_pages: int = Field(default=500, ge=1, le=2_000)
    maximum_extracted_characters: int = Field(
        default=500_000,
        ge=1_000,
        le=5_000_000,
    )


class ChunkingPolicy(DomainModel):
    """Deterministic boundaries for evidence-sized text chunks."""

    maximum_characters: int = Field(default=1_200, ge=200, le=5_000)
    minimum_characters: int = Field(default=80, ge=1, le=1_000)

    @model_validator(mode="after")
    def minimum_must_fit_maximum(self) -> "ChunkingPolicy":
        if self.minimum_characters > self.maximum_characters:
            raise ValueError("minimum_characters cannot exceed maximum_characters")
        return self


class DocumentChunk(DomainModel):
    """An exact source-relative text span available for ranking."""

    chunk_id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    research_path: ResearchPath
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=5_000)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    content_hash: str = Field(pattern=r"^[a-fA-F0-9]{64}$")

    @model_validator(mode="after")
    def offsets_must_match_text(self) -> "DocumentChunk":
        if self.end_char <= self.start_char:
            raise ValueError("end_char must be greater than start_char")
        if self.end_char - self.start_char != len(self.text):
            raise ValueError("chunk offsets must match text length")
        return self


class RankedPassage(DomainModel):
    """A chunk selected by deterministic claim-passage ranking."""

    chunk: DocumentChunk
    rank: int = Field(ge=1)
    score: float = Field(ge=0.0)
    matched_terms: tuple[str, ...] = ()
