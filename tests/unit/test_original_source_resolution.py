"""Stage 10.4 safe original-source resolution and family grouping tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.analysis import analyze_source_independence
from claim_polygraph_ng.analysis.investigation_provenance import (
    build_investigation_provenance,
)
from claim_polygraph_ng.application import (
    OriginalSourceResolver,
    SharedResearchOperations,
)
from claim_polygraph_ng.domain import (
    DistributionMedium,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    InvestigationPlan,
    OriginalSourceResolutionPermission,
    OriginalSourceResolutionRequest,
    OriginalSourceResolutionStatus,
    ResearchPath,
    SocialAccountIdentity,
    SocialCaptureMethod,
    SocialContentOriginStatus,
    SocialEvidenceEligibility,
    SocialOriginalSourceLink,
    SocialPostType,
    SocialSourceContext,
    SocialSourceRelationship,
    Source,
    SourceType,
    UnderlyingRecordKind,
    evaluate_social_evidence_eligibility,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository
from claim_polygraph_ng.retrieval import FetchedDocument


class SearchStub:
    provider_id = "search"

    async def search(self, request):
        del request
        return ()


class FetchStub:
    provider_id = "fetch"

    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, url):
        self.calls += 1
        return FetchedDocument(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            text="<article><p>Official underlying record text.</p></article>",
            byte_length=57,
            retrieved_at=datetime.now(UTC),
        )


def test_authorized_underlying_record_is_resolved_persisted_and_linked(
    tmp_path,
) -> None:
    repository, fetcher, resolver = _resolver(tmp_path)
    social = _social_source("https://authority.example/report")
    repository.save_source(social)
    request = _request(social, "https://authority.example/report")

    bundle = asyncio.run(resolver.resolve(social, request))

    assert bundle.result.status is OriginalSourceResolutionStatus.RESOLVED
    assert bundle.underlying_source is not None
    assert bundle.underlying_source.source_type is SourceType.OFFICIAL
    assert bundle.underlying_source.content_hash is not None
    assert bundle.social_source.social_context is not None
    link = bundle.social_source.social_context.original_source
    assert link is not None and link.resolved
    assert link.source_id == bundle.underlying_source.source_id
    assert fetcher.calls == 1
    assert repository.get_original_source_resolution(request.request_id) == bundle.result
    restored = repository.get_sources(
        (bundle.social_source.source_id, bundle.underlying_source.source_id)
    )
    assert restored == (bundle.social_source, bundle.underlying_source)


def test_same_resolution_request_is_idempotent_and_does_not_refetch(tmp_path) -> None:
    _, fetcher, resolver = _resolver(tmp_path)
    social = _social_source("https://authority.example/report")
    request = _request(social, "https://authority.example/report")

    first = asyncio.run(resolver.resolve(social, request))
    second = asyncio.run(resolver.resolve(social, request))

    assert second == first
    assert fetcher.calls == 1
    assert second.underlying_source is not None
    assert first.underlying_source is not None
    assert second.underlying_source.source_id == first.underlying_source.source_id


@pytest.mark.parametrize(
    "target",
    (
        "https://other.example/not-recorded",
        "https://x.com/authority/status/123456",
    ),
)
def test_unrecorded_or_social_target_is_blocked_before_fetch(tmp_path, target) -> None:
    repository, fetcher, resolver = _resolver(tmp_path)
    social = _social_source("https://authority.example/report")
    request = _request(social, target)

    bundle = asyncio.run(resolver.resolve(social, request))

    assert bundle.result.status is OriginalSourceResolutionStatus.BLOCKED
    assert bundle.underlying_source is None
    assert fetcher.calls == 0
    assert repository.get_original_source_resolution(request.request_id) == bundle.result


def test_pdf_target_requires_explicit_download_authorization() -> None:
    social = _social_source("https://authority.example/report.pdf")
    with pytest.raises(ValidationError, match="PDF target"):
        _request(social, "https://authority.example/report.pdf")


def test_record_kind_rejects_incompatible_claimed_source_type() -> None:
    social = _social_source("https://authority.example/dataset")
    payload = _request(social, "https://authority.example/dataset").model_dump()
    payload["record_kind"] = UnderlyingRecordKind.DATASET
    payload["source_type"] = SourceType.NEWS

    with pytest.raises(ValidationError, match="incompatible"):
        OriginalSourceResolutionRequest.model_validate(payload)


def test_resolved_social_and_underlying_evidence_share_one_family(tmp_path) -> None:
    _, _, resolver = _resolver(tmp_path)
    social = _social_source("https://authority.example/report")
    bundle = asyncio.run(
        resolver.resolve(
            social,
            _request(social, "https://authority.example/report"),
        )
    )
    underlying = bundle.underlying_source
    assert underlying is not None
    claim_id = uuid4()
    evidence = (
        Evidence(
            claim_id=claim_id,
            source_id=bundle.social_source.source_id,
            passage="The social account links to its official report.",
            stance=EvidenceStance.CONTEXT,
            relevance_score=0.7,
        ),
        Evidence(
            claim_id=claim_id,
            source_id=underlying.source_id,
            passage="The official report contains the controlling factual record.",
            stance=EvidenceStance.SUPPORTS,
            relevance_score=0.95,
        ),
    )

    updated, independence = analyze_source_independence(
        claim_id=claim_id,
        sources=(bundle.social_source, underlying),
        evidence=evidence,
        required_families=2,
    )

    assert independence.independent_family_count == 1
    assert not independence.requirement_met
    assert "resolved_original_source" in independence.families[0].grouping_reasons
    assert "shared_origin_url" in independence.families[0].grouping_reasons
    assert len({item.evidence_family_id for item in updated}) == 1


def test_resolved_link_also_groups_the_provenance_bound_analysis(tmp_path) -> None:
    _, _, resolver = _resolver(tmp_path)
    social = _social_source("https://authority.example/report")
    bundle = asyncio.run(
        resolver.resolve(
            social,
            _request(social, "https://authority.example/report"),
        )
    )
    underlying = bundle.underlying_source
    assert underlying is not None
    claim_id = uuid4()
    evidence = (
        Evidence(
            claim_id=claim_id,
            source_id=bundle.social_source.source_id,
            passage="This post links to the underlying report.",
            stance=EvidenceStance.CONTEXT,
            relevance_score=0.7,
        ),
        Evidence(
            claim_id=claim_id,
            source_id=underlying.source_id,
            passage="A distinct passage from the underlying report.",
            stance=EvidenceStance.SUPPORTS,
            relevance_score=0.9,
        ),
    )
    plan = InvestigationPlan(
        claim_id=claim_id,
        required_research_paths=(ResearchPath.PRIMARY, ResearchPath.CONTRADICTION),
        minimum_independent_families=2,
    )

    provenance = build_investigation_provenance(
        plan=plan,
        sources=(bundle.social_source, underlying),
        evidence=evidence,
    )

    assert len(provenance.families) == 1
    assert provenance.possible_independent_upper_bound == 1
    assert provenance.dependencies[0].status == "confirmed_dependent"
    assert provenance.dependencies[0].reasons == ("resolved_original_source",)


def _resolver(tmp_path):
    repository = SQLiteResearchRepository(tmp_path / "research.sqlite3")
    repository.initialize()
    fetcher = FetchStub()
    operations = SharedResearchOperations(
        repository=repository,
        search_provider=SearchStub(),
        fetcher=fetcher,
    )
    return (
        repository,
        fetcher,
        OriginalSourceResolver(repository=repository, operations=operations),
    )


def _social_source(target_url: str) -> Source:
    link = SocialOriginalSourceLink(
        relationship=SocialSourceRelationship.LINKS_TO,
        url=target_url,
        resolved=False,
    )
    context = SocialSourceContext(
        account=SocialAccountIdentity(platform="x", handle="authority"),
        post_type=SocialPostType.LINK_SHARE,
        original_source=link,
        capture_method=SocialCaptureMethod.SEARCH_RESULT_SNIPPET,
        content_origin_status=SocialContentOriginStatus.UNKNOWN,
    )
    eligibility: SocialEvidenceEligibility = evaluate_social_evidence_eligibility(
        context
    )
    return Source(
        url="https://x.com/authority/status/123456",
        canonical_url="https://x.com/authority/status/123456",
        title="Social link to an official report",
        source_type=SourceType.OTHER,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.PARTIAL,
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_context=context,
        social_eligibility=eligibility,
    )


def _request(
    social: Source,
    target_url: str,
) -> OriginalSourceResolutionRequest:
    return OriginalSourceResolutionRequest(
        social_source_id=social.source_id,
        target_url=target_url,
        relationship=SocialSourceRelationship.LINKS_TO,
        record_kind=UnderlyingRecordKind.REPORT,
        source_type=SourceType.OFFICIAL,
        title="Official underlying report",
        publisher="Example Authority",
        permission=OriginalSourceResolutionPermission(
            authorized=True,
            authorized_by="fixture-policy",
            authorized_at=datetime.now(UTC),
            purpose="Resolve an explicitly recorded public underlying report.",
        ),
    )
