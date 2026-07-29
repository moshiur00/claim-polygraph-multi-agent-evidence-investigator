"""Typed contracts for explicitly authorized underlying-source resolution."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import SocialSourceRelationship, SourceType


class UnderlyingRecordKind(StrEnum):
    """Permitted categories of records linked from social material."""

    REPORT = "report"
    DATASET = "dataset"
    RULING = "ruling"
    PAPER = "paper"
    TRANSCRIPT = "transcript"
    OFFICIAL_ANNOUNCEMENT = "official_announcement"
    OTHER = "other"


class OriginalSourceResolutionStatus(StrEnum):
    """Durable terminal state for one bounded resolution request."""

    RESOLVED = "resolved"
    BLOCKED = "blocked"
    FAILED = "failed"


class OriginalSourceResolutionPermission(DomainModel):
    """Explicit authority to follow one public underlying-record link."""

    authorized: bool = False
    authorized_by: str = Field(min_length=1, max_length=300)
    authorized_at: datetime
    purpose: str = Field(min_length=5, max_length=1_000)
    public_access_expected: bool = True
    pdf_download_authorized: bool = False


class OriginalSourceResolutionRequest(DomainModel):
    """One request tied to a pre-recorded social derivation link."""

    request_id: UUID = Field(default_factory=uuid4)
    social_source_id: UUID
    target_url: AnyHttpUrl
    relationship: SocialSourceRelationship
    record_kind: UnderlyingRecordKind
    source_type: SourceType
    title: str = Field(min_length=1, max_length=1_000)
    publisher: str | None = Field(default=None, max_length=500)
    permission: OriginalSourceResolutionPermission

    @model_validator(mode="after")
    def allow_only_underlying_links(self) -> OriginalSourceResolutionRequest:
        if self.relationship not in {
            SocialSourceRelationship.UNDERLYING_RECORD,
            SocialSourceRelationship.LINKS_TO,
        }:
            raise ValueError("resolution only follows underlying-record or link targets")
        if not self.permission.authorized:
            raise ValueError("original-source resolution requires explicit authorization")
        if not self.permission.public_access_expected:
            raise ValueError("resolution cannot target non-public content")
        if (
            str(self.target_url).casefold().split("?", maxsplit=1)[0].endswith(".pdf")
            and not self.permission.pdf_download_authorized
        ):
            raise ValueError("PDF target requires explicit download authorization")
        allowed_types = {
            UnderlyingRecordKind.REPORT: {
                SourceType.OFFICIAL,
                SourceType.PRIMARY_DOCUMENT,
                SourceType.ORGANIZATION,
                SourceType.OTHER,
            },
            UnderlyingRecordKind.DATASET: {SourceType.DATASET},
            UnderlyingRecordKind.RULING: {SourceType.LAW_OR_REGULATION},
            UnderlyingRecordKind.PAPER: {SourceType.ACADEMIC},
            UnderlyingRecordKind.TRANSCRIPT: {SourceType.PRIMARY_DOCUMENT},
            UnderlyingRecordKind.OFFICIAL_ANNOUNCEMENT: {SourceType.OFFICIAL},
            UnderlyingRecordKind.OTHER: {SourceType.OTHER},
        }
        if self.source_type not in allowed_types[self.record_kind]:
            raise ValueError("source_type is incompatible with the underlying record kind")
        return self


class OriginalSourceResolutionResult(DomainModel):
    """Persisted outcome without retaining full copyrighted source content."""

    resolution_id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    social_source_id: UUID
    underlying_source_id: UUID | None = None
    status: OriginalSourceResolutionStatus
    requested_url: AnyHttpUrl
    final_url: AnyHttpUrl | None = None
    relationship: SocialSourceRelationship
    record_kind: UnderlyingRecordKind
    content_type: str | None = Field(default=None, max_length=200)
    byte_length: int | None = Field(default=None, ge=0)
    content_hash: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    cache_reused: bool = False
    failure_reason: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_terminal_result(self) -> OriginalSourceResolutionResult:
        if self.status is OriginalSourceResolutionStatus.RESOLVED:
            if self.underlying_source_id is None or self.final_url is None:
                raise ValueError("resolved outcome requires underlying source and final URL")
            if self.failure_reason is not None:
                raise ValueError("resolved outcome cannot contain failure_reason")
        elif not self.failure_reason:
            raise ValueError("blocked or failed resolution requires failure_reason")
        return self
