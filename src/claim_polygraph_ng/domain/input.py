"""Typed user-input and claim-extraction contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import ContentRetention, RightsStatus


class InvestigationInputKind(StrEnum):
    MANUAL_CLAIM = "manual_claim"
    ARTICLE_TEXT = "article_text"
    PUBLIC_URL = "public_url"


class ManualClaimInput(DomainModel):
    kind: Literal[InvestigationInputKind.MANUAL_CLAIM] = InvestigationInputKind.MANUAL_CLAIM
    claim: str = Field(min_length=3, max_length=10_000)


class ArticleTextInput(DomainModel):
    kind: Literal[InvestigationInputKind.ARTICLE_TEXT] = InvestigationInputKind.ARTICLE_TEXT
    text: str = Field(min_length=20, max_length=500_000)
    title: str | None = Field(default=None, max_length=1_000)


class PublicUrlInput(DomainModel):
    kind: Literal[InvestigationInputKind.PUBLIC_URL] = InvestigationInputKind.PUBLIC_URL
    url: AnyHttpUrl


InvestigationInput = Annotated[
    ManualClaimInput | ArticleTextInput | PublicUrlInput,
    Field(discriminator="kind"),
]


class ExtractedClaimCandidate(DomainModel):
    candidate_id: UUID = Field(default_factory=uuid4)
    text: str = Field(min_length=3, max_length=2_000)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    context_before: str = Field(default="", max_length=2_000)
    context_after: str = Field(default="", max_length=2_000)
    checkworthiness: float = Field(ge=0, le=1)
    ranking_reasons: tuple[str, ...] = ()
    rank: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> "ExtractedClaimCandidate":
        if self.end_char - self.start_char != len(self.text):
            raise ValueError("candidate offsets must match exact claim text length")
        return self


class ClaimExtractionPacket(DomainModel):
    extraction_id: UUID = Field(default_factory=uuid4)
    input_kind: InvestigationInputKind
    source_url: AnyHttpUrl | None = None
    canonical_url: AnyHttpUrl | None = None
    title: str | None = Field(default=None, max_length=1_000)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_length: int = Field(ge=3, le=500_000)
    retrieved_at: datetime | None = None
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    content_retention: ContentRetention = ContentRetention.EVIDENCE_PASSAGES_ONLY
    candidates: tuple[ExtractedClaimCandidate, ...]
    automatic_investigation_started: bool = False
    model_calls: int = 0

    @model_validator(mode="after")
    def validate_url_provenance(self) -> "ClaimExtractionPacket":
        is_url = self.input_kind is InvestigationInputKind.PUBLIC_URL
        if is_url != bool(self.source_url and self.canonical_url and self.retrieved_at):
            raise ValueError("public URL extraction requires complete retrieval provenance")
        if self.automatic_investigation_started:
            raise ValueError("claim extraction cannot automatically start an investigation")
        return self
