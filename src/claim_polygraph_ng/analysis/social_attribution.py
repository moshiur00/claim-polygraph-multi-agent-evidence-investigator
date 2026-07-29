"""Conservative candidate-to-source attribution without social content access."""

from __future__ import annotations

from datetime import datetime

from claim_polygraph_ng.domain import (
    DistributionMedium,
    ExtractionStatus,
    SearchResult,
    SocialAccountIdentity,
    SocialAttributionScope,
    SocialAuthenticityStatus,
    SocialCaptureMethod,
    SocialContentOriginStatus,
    SocialPostType,
    SocialSourceContext,
    SocialUrlKind,
    Source,
    evaluate_social_evidence_eligibility,
)


def source_from_search_result(
    result: SearchResult,
    *,
    canonical_url: str,
    retrieved_at: datetime,
    extraction_status: ExtractionStatus,
    content_hash: str | None = None,
) -> Source:
    """Persist provider discovery metadata and conservative social attribution."""

    context = social_context_from_search_result(result)
    eligibility = (
        evaluate_social_evidence_eligibility(context) if context is not None else None
    )
    return Source(
        url=result.url,
        canonical_url=canonical_url,
        title=result.title,
        source_type=result.source_type,
        publisher=result.publisher,
        retrieved_at=retrieved_at,
        content_hash=content_hash,
        extraction_status=extraction_status,
        distribution_medium=result.distribution_medium,
        social_context=context,
        social_eligibility=eligibility,
        discovery_metadata=result.provider_metadata,
    )


def social_context_from_search_result(
    result: SearchResult,
) -> SocialSourceContext | None:
    """Build unresolved attribution from URL metadata, never from snippet assertions."""

    candidate = result.social_url
    if candidate is None:
        return None
    handle = candidate.account_handle
    identity_resolved = bool(handle)
    account = SocialAccountIdentity(
        platform=candidate.platform.value,
        identity_resolved=identity_resolved,
        handle=handle if identity_resolved else None,
        profile_url=(
            candidate.canonical_url
            if candidate.url_kind is SocialUrlKind.ACCOUNT and identity_resolved
            else None
        ),
        authenticity_status=SocialAuthenticityStatus.UNKNOWN,
    )
    return SocialSourceContext(
        account=account,
        post_type=SocialPostType.UNKNOWN,
        platform_post_id=candidate.platform_post_id,
        capture_method=SocialCaptureMethod.SEARCH_RESULT_SNIPPET,
        content_origin_status=SocialContentOriginStatus.UNKNOWN,
        attribution_scope=SocialAttributionScope.LINKED_SOURCE_DISCOVERY,
        eyewitness_claim=False,
        unavailable_or_deleted=False,
    )


def is_social_candidate(result: SearchResult) -> bool:
    return (
        result.distribution_medium is DistributionMedium.SOCIAL_PLATFORM
        and result.social_url is not None
    )

