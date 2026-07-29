"""Stage 10.5 shared-origin, quality, and readiness safeguards."""

from datetime import UTC, datetime
from uuid import uuid4

from claim_polygraph_ng.analysis import analyze_source_independence
from claim_polygraph_ng.analysis.investigation_provenance import (
    build_investigation_provenance,
)
from claim_polygraph_ng.analysis.readiness import calculate_judgment_readiness
from claim_polygraph_ng.domain import (
    ArgumentLedger,
    DistributionMedium,
    Evidence,
    EvidenceStance,
    EvidentiaryUse,
    ExtractionStatus,
    InvestigationPlan,
    JudgmentReadinessState,
    MaterialProposition,
    PropositionArgument,
    PropositionResolution,
    ProviderResultMetadata,
    ReadinessReasonCode,
    ResearchPath,
    SentenceAudit,
    SocialAccountIdentity,
    SocialAccountType,
    SocialAuthenticityEvidence,
    SocialAuthenticityEvidenceType,
    SocialAuthenticityStatus,
    SocialCaptureMethod,
    SocialContentOriginStatus,
    SocialOriginalSourceLink,
    SocialPostType,
    SocialRiskCode,
    SocialSourceContext,
    SocialSourceRelationship,
    Source,
    SourceType,
    SupportLevel,
    evaluate_social_evidence_eligibility,
)


def test_cross_platform_posts_and_underlying_web_record_form_one_family() -> None:
    claim_id = uuid4()
    origin = "https://authority.example/report?id=7&utm_source=social"
    sources = (
        _social_source("x", origin),
        _social_source("facebook", "https://authority.example/report?id=7"),
        _web_source("https://authority.example/report?id=7"),
    )
    evidence = tuple(
        Evidence(
            claim_id=claim_id,
            source_id=source.source_id,
            passage=f"Distinct retained passage {index} about the same origin.",
            stance=EvidenceStance.CONTEXT,
            relevance_score=0.8,
        )
        for index, source in enumerate(sources)
    )

    _, independence = analyze_source_independence(
        claim_id=claim_id,
        sources=sources,
        evidence=evidence,
        required_families=2,
    )

    assert independence.independent_family_count == 1
    assert "shared_origin_url" in independence.families[0].grouping_reasons
    assert not independence.requirement_met


def test_authenticated_scoped_account_authority_excludes_badge_and_engagement() -> None:
    claim_id = uuid4()
    source = _social_source(
        "x",
        "https://authority.example/report",
        authenticated=True,
        scoped=True,
        metadata={"verified": True, "follower_count": 9_999_999, "likes": 50_000},
    )
    evidence = _evidence(claim_id, source, EvidentiaryUse.ATTRIBUTED_STATEMENT)
    provenance = build_investigation_provenance(
        plan=_plan(claim_id),
        sources=(source, _web_source("https://independent.example/report")),
        evidence=(
            evidence,
            _evidence(
                claim_id,
                _web_source("https://unused.example"),
                EvidentiaryUse.CONTEXT,
            ).model_copy(update={"source_id": source.source_id}),
        ),
    )
    quality = provenance.source_quality[0]
    authority = next(item for item in quality.dimensions if item.dimension == "authority")

    assert authority.finding == "favorable"
    assert authority.signals == ("authenticated_account", "authority_scope_recorded")
    assert quality.ignored_signals == (
        "badge:verified",
        "engagement:follower_count",
        "engagement:likes",
    )
    assert all("verified" not in signal for signal in authority.signals)
    assert all("follower" not in signal for signal in authority.signals)


def test_platform_badge_without_authenticated_scope_does_not_create_authority() -> None:
    claim_id = uuid4()
    source = _social_source(
        "x",
        "https://authority.example/report",
        metadata={"verified": True, "view_count": 1_000_000},
    )
    provenance = build_investigation_provenance(
        plan=_plan(claim_id),
        sources=(source,),
        evidence=(_evidence(claim_id, source, EvidentiaryUse.CONTEXT),),
    )
    authority = next(
        item
        for item in provenance.source_quality[0].dimensions
        if item.dimension == "authority"
    )

    assert authority.finding == "unknown"
    assert "badge:verified" in provenance.source_quality[0].ignored_signals
    assert {
        item.code for item in provenance.social_risk_findings
    } >= {
        SocialRiskCode.ACCOUNT_UNAUTHENTICATED,
        SocialRiskCode.SOCIAL_ONLY_EVIDENCE_PACKET,
        SocialRiskCode.PLATFORM_BADGE_IGNORED,
        SocialRiskCode.ENGAGEMENT_SIGNAL_IGNORED,
    }


def test_ineligible_social_evidence_forces_human_review() -> None:
    claim_id = uuid4()
    source = _screenshot_source()
    evidence = _evidence(claim_id, source, EvidentiaryUse.DECISIVE)
    provenance = build_investigation_provenance(
        plan=_plan(claim_id),
        sources=(source,),
        evidence=(evidence,),
    )
    proposition_id = uuid4()
    ledger = ArgumentLedger(
        claim_id=claim_id,
        approved_evidence_ids=(evidence.evidence_id,),
        propositions=(
            MaterialProposition(
                proposition_id=proposition_id,
                claim_id=claim_id,
                text="A material factual proposition.",
            ),
        ),
        arguments=(
            PropositionArgument(
                proposition_id=proposition_id,
                resolution=PropositionResolution.SUPPORTED,
                supporting_evidence_ids=(evidence.evidence_id,),
            ),
        ),
    )
    audit = SentenceAudit(
        sentence="The material sentence is cited.",
        cited_evidence_ids=(evidence.evidence_id,),
        support_level=SupportLevel.FULL,
    )

    readiness = calculate_judgment_readiness(
        ledger=ledger,
        provenance=provenance,
        audits=(audit,),
    )

    assert readiness.state is JudgmentReadinessState.HUMAN_REVIEW_REQUIRED
    assert readiness.blocking_social_risk_count >= 3
    assert (
        ReadinessReasonCode.BLOCKING_SOCIAL_EVIDENCE_RISK
        in readiness.reason_codes
    )
    assert readiness.confidence_score is None


def _social_source(
    platform: str,
    origin_url: str,
    *,
    authenticated: bool = False,
    scoped: bool = False,
    metadata: dict[str, object] | None = None,
) -> Source:
    auth_evidence = (
        (
            SocialAuthenticityEvidence(
                evidence_type=SocialAuthenticityEvidenceType.OFFICIAL_WEBSITE_LINK,
                reference_url="https://authority.example/social",
                observed_at=datetime.now(UTC),
                description="Official website links to this account.",
            ),
        )
        if authenticated
        else ()
    )
    account = SocialAccountIdentity(
        platform=platform,
        handle="authority",
        account_type=SocialAccountType.GOVERNMENT,
        authority_scope=(
            "Announcements about the institution's own status." if scoped else None
        ),
        authenticity_status=(
            SocialAuthenticityStatus.AUTHENTICATED
            if authenticated
            else SocialAuthenticityStatus.UNKNOWN
        ),
        authenticity_evidence=auth_evidence,
    )
    link = SocialOriginalSourceLink(
        relationship=SocialSourceRelationship.LINKS_TO,
        url=origin_url,
        resolved=False,
    )
    context = SocialSourceContext(
        account=account,
        post_type=SocialPostType.LINK_SHARE,
        original_source=link,
        capture_method=SocialCaptureMethod.DIRECT_PUBLIC_PAGE,
        content_origin_status=SocialContentOriginStatus.ORIGINAL_ACCESSIBLE,
    )
    return Source(
        url=f"https://{platform}.example/authority/post/123",
        canonical_url=f"https://{platform}.example/authority/post/123",
        title="Institutional social post",
        source_type=SourceType.OTHER,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_context=context,
        social_eligibility=evaluate_social_evidence_eligibility(context),
        discovery_metadata=(
            ProviderResultMetadata(provider_id="fixture", attributes=metadata)
            if metadata
            else None
        ),
    )


def _screenshot_source() -> Source:
    account = SocialAccountIdentity(platform="x", handle="unknown")
    context = SocialSourceContext(
        account=account,
        post_type=SocialPostType.SCREENSHOT,
        original_source=SocialOriginalSourceLink(
            relationship=SocialSourceRelationship.SCREENSHOT_OF,
            url="https://x.com/original/status/123456",
            resolved=False,
        ),
        capture_method=SocialCaptureMethod.SCREENSHOT,
        content_origin_status=SocialContentOriginStatus.SCREENSHOT_ONLY,
    )
    return Source(
        url="https://example.org/uploaded-screenshot",
        canonical_url="https://example.org/uploaded-screenshot",
        title="Unverified screenshot",
        source_type=SourceType.OTHER,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.PARTIAL,
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_context=context,
        social_eligibility=evaluate_social_evidence_eligibility(context),
    )


def _web_source(url: str) -> Source:
    return Source(
        url=url,
        canonical_url=url,
        title="Independent web record",
        source_type=SourceType.OFFICIAL,
        publisher="Independent publisher",
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
        distribution_medium=DistributionMedium.WEB_PAGE,
    )


def _evidence(
    claim_id,
    source: Source,
    use: EvidentiaryUse,
) -> Evidence:
    return Evidence(
        claim_id=claim_id,
        source_id=source.source_id,
        passage="A retained passage used for deterministic evaluation.",
        stance=EvidenceStance.SUPPORTS,
        relevance_score=0.9,
        evidentiary_use=use,
    )


def _plan(claim_id) -> InvestigationPlan:
    return InvestigationPlan(
        claim_id=claim_id,
        required_research_paths=(ResearchPath.PRIMARY, ResearchPath.CONTRADICTION),
        minimum_independent_families=2,
    )

