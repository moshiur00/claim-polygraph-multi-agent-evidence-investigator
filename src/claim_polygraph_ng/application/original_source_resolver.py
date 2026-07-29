"""Safely resolve explicitly recorded links from social items to underlying records."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from claim_polygraph_ng.analysis.social_urls import (
    canonical_web_url,
    classify_social_url,
)
from claim_polygraph_ng.application.research_executor import SharedResearchOperations
from claim_polygraph_ng.domain import (
    DistributionMedium,
    ExtractionStatus,
    OriginalSourceResolutionRequest,
    OriginalSourceResolutionResult,
    OriginalSourceResolutionStatus,
    SocialOriginalSourceLink,
    Source,
    UnderlyingRecordKind,
    evaluate_social_evidence_eligibility,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository
from claim_polygraph_ng.retrieval import FetchError, extract_document_text


@dataclass(frozen=True)
class OriginalSourceResolutionBundle:
    """Resolved records plus the durable outcome; full fetched content stays cached."""

    social_source: Source
    underlying_source: Source | None
    result: OriginalSourceResolutionResult


class OriginalSourceResolutionIntegrityError(RuntimeError):
    """A durable outcome references source records that cannot be reconstructed."""


class OriginalSourceResolver:
    """Resolve one authorized, pre-recorded, non-social underlying link."""

    def __init__(
        self,
        *,
        repository: SQLiteResearchRepository,
        operations: SharedResearchOperations,
    ) -> None:
        self._repository = repository
        self._operations = operations

    async def resolve(
        self,
        social_source: Source,
        request: OriginalSourceResolutionRequest,
    ) -> OriginalSourceResolutionBundle:
        existing = self._repository.get_original_source_resolution(request.request_id)
        if existing is not None:
            if existing.status is not OriginalSourceResolutionStatus.RESOLVED:
                return OriginalSourceResolutionBundle(social_source, None, existing)
            assert existing.underlying_source_id is not None
            persisted = self._repository.get_sources(
                (existing.social_source_id, existing.underlying_source_id)
            )
            by_id = {source.source_id: source for source in persisted}
            updated_social = by_id.get(existing.social_source_id)
            underlying = by_id.get(existing.underlying_source_id)
            if updated_social is None or underlying is None:
                raise OriginalSourceResolutionIntegrityError(
                    "resolution outcome references missing persisted sources"
                )
            return OriginalSourceResolutionBundle(
                updated_social,
                underlying,
                existing,
            )
        blocked_reason = preflight_original_source_resolution(social_source, request)
        if blocked_reason:
            result = _failure_result(
                request,
                OriginalSourceResolutionStatus.BLOCKED,
                blocked_reason,
            )
            self._repository.save_original_source_resolution(result)
            return OriginalSourceResolutionBundle(social_source, None, result)

        try:
            document = await self._operations.fetch(str(request.target_url))
            content = extract_document_text(document)
        except (FetchError, ValueError) as error:
            result = _failure_result(
                request,
                OriginalSourceResolutionStatus.FAILED,
                f"{type(error).__name__}: {error}",
            )
            self._repository.save_original_source_resolution(result)
            return OriginalSourceResolutionBundle(social_source, None, result)

        content_hash = (
            hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None
        )
        underlying = Source(
            url=request.target_url,
            canonical_url=document.final_url,
            title=request.title,
            source_type=request.source_type,
            publisher=request.publisher,
            retrieved_at=document.retrieved_at,
            content_hash=content_hash,
            extraction_status=(
                ExtractionStatus.EXTRACTED if content else ExtractionStatus.PARTIAL
            ),
            distribution_medium=_medium(request.record_kind, document.content_type),
        )
        assert social_source.social_context is not None
        prior_link = social_source.social_context.original_source
        assert prior_link is not None
        resolved_link = SocialOriginalSourceLink(
            relationship=prior_link.relationship,
            source_id=underlying.source_id,
            url=document.final_url,
            resolved=True,
        )
        updated_context = social_source.social_context.model_copy(
            update={"original_source": resolved_link}
        )
        updated_social = Source.model_validate(
            {
                **social_source.model_dump(),
                "social_context": updated_context,
                "social_eligibility": evaluate_social_evidence_eligibility(
                    updated_context
                ),
            }
        )
        result = OriginalSourceResolutionResult(
            request_id=request.request_id,
            social_source_id=social_source.source_id,
            underlying_source_id=underlying.source_id,
            status=OriginalSourceResolutionStatus.RESOLVED,
            requested_url=request.target_url,
            final_url=document.final_url,
            relationship=request.relationship,
            record_kind=request.record_kind,
            content_type=document.content_type,
            byte_length=document.byte_length,
            content_hash=content_hash,
        )
        self._repository.save_source(updated_social)
        self._repository.save_source(underlying)
        self._repository.save_original_source_resolution(result)
        return OriginalSourceResolutionBundle(updated_social, underlying, result)


def preflight_original_source_resolution(
    source: Source,
    request: OriginalSourceResolutionRequest,
) -> str | None:
    if request.social_source_id != source.source_id:
        return "request social_source_id does not match supplied source"
    if (
        source.distribution_medium is not DistributionMedium.SOCIAL_PLATFORM
        or source.social_context is None
    ):
        return "resolution source is not classified social material"
    link = source.social_context.original_source
    if link is None or link.url is None:
        return "social source has no explicit underlying URL"
    if link.relationship is not request.relationship:
        return "request relationship does not match the recorded derivation"
    if link.resolved:
        return "underlying source link is already resolved"
    if canonical_web_url(str(link.url)) != canonical_web_url(str(request.target_url)):
        return "request target does not match the recorded underlying URL"
    if classify_social_url(str(request.target_url)) is not None:
        return "underlying resolver cannot follow another social URL"
    return None


def _failure_result(
    request: OriginalSourceResolutionRequest,
    status: OriginalSourceResolutionStatus,
    reason: str,
) -> OriginalSourceResolutionResult:
    return OriginalSourceResolutionResult(
        request_id=request.request_id,
        social_source_id=request.social_source_id,
        status=status,
        requested_url=request.target_url,
        relationship=request.relationship,
        record_kind=request.record_kind,
        failure_reason=reason,
    )


def _medium(
    record_kind: UnderlyingRecordKind,
    content_type: str,
) -> DistributionMedium:
    if record_kind is UnderlyingRecordKind.DATASET:
        return DistributionMedium.DATASET_OR_API
    if content_type == "application/pdf":
        return DistributionMedium.DOCUMENT
    return DistributionMedium.WEB_PAGE
