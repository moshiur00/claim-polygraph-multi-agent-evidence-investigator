"""Build a persisted provenance packet from retained investigation artifacts."""

from collections import defaultdict
from uuid import UUID

from claim_polygraph_ng.analysis.evidence_families import (
    FamilySourceRecord,
    infer_evidence_families,
)
from claim_polygraph_ng.analysis.independence_features import calculate_independence_features
from claim_polygraph_ng.analysis.source_quality import (
    SourceQualityMetadata,
    assess_source_quality,
)
from claim_polygraph_ng.domain import (
    DistributionMedium,
    Evidence,
    EvidenceEligibilityDecision,
    EvidentiaryUse,
    InvestigationPlan,
    InvestigationProvenance,
    ProvenanceDependency,
    ProvenanceFamily,
    ProvenanceQualityDimension,
    ProvenanceRequirementState,
    ProvenanceSourceQuality,
    SocialAccountType,
    SocialAuthenticityStatus,
    SocialCaptureMethod,
    SocialRiskCode,
    SocialRiskFinding,
    SocialRiskSeverity,
    Source,
)


def build_investigation_provenance(
    *,
    plan: InvestigationPlan,
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
) -> InvestigationProvenance:
    """Build deterministic, uncertainty-preserving provenance without model calls."""
    passages: dict[object, list[str]] = defaultdict(list)
    for item in evidence:
        passages[item.source_id].append(item.passage)

    usable_sources = tuple(
        source for source in sources if passages[source.source_id]
    )
    records = tuple(
        FamilySourceRecord(
            source_id=str(source.source_id),
            url=source.canonical_url,
            text="\n\n".join(passages[source.source_id]),
            published_at=source.publication_date,
            related_source_ids=_related_source_ids(source),
            origin_urls=_origin_urls(source),
        )
        for source in usable_sources
    )

    if records:
        inference = infer_evidence_families(str(plan.claim_id), records)
        features = calculate_independence_features(
            inference,
            raw_source_count=len(records),
            required_independent_families=plan.minimum_independent_families,
        )
        families = tuple(
            ProvenanceFamily(
                family_id=family.family_id,
                source_ids=tuple(_uuid(source_id) for source_id in family.source_ids),
                grouping_reasons=family.grouping_reasons,
            )
            for family in inference.families
        )
        dependencies = tuple(
            ProvenanceDependency(
                left_source_id=_uuid(edge.left_source_id),
                right_source_id=_uuid(edge.right_source_id),
                status=edge.status.value,
                confidence=edge.confidence,
                reasons=edge.reasons,
            )
            for edge in inference.dependency_edges
        )
        lower = features.confirmed_independent_lower_bound
        upper = features.possible_independent_upper_bound
        unresolved = features.unresolved_dependency_count
        state = ProvenanceRequirementState(features.requirement_state.value)
        inference_limitations = inference.limitations + features.limitations
    else:
        families = ()
        dependencies = ()
        lower = upper = unresolved = 0
        state = ProvenanceRequirementState.NOT_MET
        inference_limitations = (
            "No extracted evidence passages were available for family inference.",
        )

    quality = tuple(
        _quality_record(source)
        for source in usable_sources
    )
    social_risks = _social_risk_findings(usable_sources, evidence)
    social_risks += tuple(
        SocialRiskFinding(
            code=SocialRiskCode.SHARED_ORIGIN_REPETITION,
            severity=SocialRiskSeverity.CAUTION,
            reason=(
                "Multiple retained sources resolve to the same recorded origin and count "
                "as one evidence family."
            ),
            evidence_ids=tuple(
                item.evidence_id
                for item in evidence
                if item.source_id in family.source_ids
            ),
        )
        for family in families
        if "shared_origin_url" in family.grouping_reasons
        and len(family.source_ids) > 1
    )
    omitted = len(sources) - len(usable_sources)
    limitations = (
        *inference_limitations,
        "Source-quality dimensions use only metadata retained by this workflow.",
        "This packet is explanatory and is not an input to the stored verdict.",
    )
    if omitted:
        limitations = (
            *limitations,
            f"{omitted} source record(s) without retained evidence passages were excluded.",
        )
    return InvestigationProvenance(
        claim_id=plan.claim_id,
        source_ids=tuple(source.source_id for source in usable_sources),
        families=families,
        dependencies=dependencies,
        source_quality=quality,
        confirmed_independent_lower_bound=lower,
        possible_independent_upper_bound=upper,
        unresolved_dependency_count=unresolved,
        required_independent_families=plan.minimum_independent_families,
        requirement_state=state,
        limitations=limitations,
        social_risk_findings=social_risks,
    )


def _quality_record(source: Source) -> ProvenanceSourceQuality:
    context = source.social_context
    account = context.account if context else None
    institutional_types = {
        SocialAccountType.INSTITUTION,
        SocialAccountType.GOVERNMENT,
        SocialAccountType.ACADEMIC_INSTITUTION,
        SocialAccountType.NEWS_ORGANIZATION,
    }
    authenticated = (
        account.authenticity_status is SocialAuthenticityStatus.AUTHENTICATED
        if account
        else None
    )
    institutional = account.account_type in institutional_types if account else None
    scope_recorded = bool(account and account.authority_scope)
    prohibited = _prohibited_social_signals(source)
    assessment = assess_source_quality(
        SourceQualityMetadata(
            source_id=source.source_id,
            source_type=source.source_type,
            publisher_identified=source.publisher is not None or bool(institutional),
            author_identified=source.author is not None
            or bool(account and account.identity_resolved),
            publication_date=source.publication_date,
            distribution_medium=source.distribution_medium,
            social_identity_resolved=account.identity_resolved if account else None,
            social_account_authenticated=authenticated,
            social_account_institutional=institutional,
            social_authority_scope_recorded=scope_recorded if account else None,
            institutional_authority_confirmed=(
                True
                if authenticated and institutional and scope_recorded
                else None
            ),
            prohibited_social_signals=prohibited,
        )
    )
    return ProvenanceSourceQuality(
        source_id=source.source_id,
        dimensions=tuple(
            ProvenanceQualityDimension(
                dimension=item.dimension.value,
                finding=item.finding.value,
                reason=item.reason,
                signals=item.signals,
            )
            for item in assessment.dimensions
        ),
        limitations=assessment.limitations,
        ignored_signals=prohibited,
    )


def _uuid(value: str) -> UUID:
    return UUID(value)


def _related_source_ids(source: Source) -> tuple[str, ...]:
    if source.social_context is None or source.social_context.original_source is None:
        return ()
    link = source.social_context.original_source
    if not link.resolved or link.source_id is None:
        return ()
    return (str(link.source_id),)


def _origin_urls(source: Source) -> tuple[object, ...]:
    if source.social_context is None or source.social_context.original_source is None:
        return ()
    link = source.social_context.original_source
    return (link.url,) if link.url is not None else ()


def _social_risk_findings(
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
) -> tuple[SocialRiskFinding, ...]:
    findings: list[SocialRiskFinding] = []
    social_sources = tuple(
        source
        for source in sources
        if source.distribution_medium is DistributionMedium.SOCIAL_PLATFORM
        and source.social_context is not None
    )
    evidence_by_source = {
        source.source_id: tuple(
            item for item in evidence if item.source_id == source.source_id
        )
        for source in social_sources
    }
    for source in social_sources:
        context = source.social_context
        assert context is not None
        account = context.account
        source_evidence = evidence_by_source[source.source_id]
        evidence_ids = tuple(item.evidence_id for item in source_evidence)
        if not account.identity_resolved:
            findings.append(
                _risk(
                    SocialRiskCode.IDENTITY_UNRESOLVED,
                    SocialRiskSeverity.CAUTION,
                    "The represented social account identity is unresolved.",
                    source,
                    evidence_ids,
                )
            )
        if account.authenticity_status is not SocialAuthenticityStatus.AUTHENTICATED:
            findings.append(
                _risk(
                    SocialRiskCode.ACCOUNT_UNAUTHENTICATED,
                    SocialRiskSeverity.CAUTION,
                    "Account ownership is not authenticated by retained evidence.",
                    source,
                    evidence_ids,
                )
            )
        if (
            account.account_type
            in {
                SocialAccountType.INSTITUTION,
                SocialAccountType.GOVERNMENT,
                SocialAccountType.ACADEMIC_INSTITUTION,
                SocialAccountType.NEWS_ORGANIZATION,
            }
            and not account.authority_scope
        ):
            findings.append(
                _risk(
                    SocialRiskCode.AUTHORITY_SCOPE_MISSING,
                    SocialRiskSeverity.CAUTION,
                    "Institutional account authority is not scoped to the assertion.",
                    source,
                    evidence_ids,
                )
            )
        link = context.original_source
        if link is not None and not link.resolved:
            findings.append(
                _risk(
                    SocialRiskCode.ORIGIN_UNRESOLVED,
                    SocialRiskSeverity.CAUTION,
                    "The social item has a recorded but unresolved original-source link.",
                    source,
                    evidence_ids,
                )
            )
        if context.capture_method in {
            SocialCaptureMethod.SCREENSHOT,
            SocialCaptureMethod.COPIED_TEXT,
        }:
            findings.append(
                _risk(
                    SocialRiskCode.SCREENSHOT_OR_COPY,
                    SocialRiskSeverity.BLOCKING,
                    "Screenshot or copied text is not authenticated original content.",
                    source,
                    evidence_ids,
                )
            )
        archive_verified = bool(
            context.archive_reference
            and context.archive_reference.reliability_verified
        )
        if context.unavailable_or_deleted and not archive_verified:
            findings.append(
                _risk(
                    SocialRiskCode.UNAVAILABLE_WITHOUT_VERIFIED_ARCHIVE,
                    SocialRiskSeverity.BLOCKING,
                    "The original is unavailable and no verified archive is retained.",
                    source,
                    evidence_ids,
                )
            )
        eligibility = source.social_eligibility
        if (
            source_evidence
            and eligibility
            and eligibility.decision is EvidenceEligibilityDecision.INELIGIBLE
        ):
            findings.append(
                _risk(
                    SocialRiskCode.INELIGIBLE_SOCIAL_EVIDENCE_USED,
                    SocialRiskSeverity.BLOCKING,
                    "Retained evidence references a social source that is lead-only.",
                    source,
                    evidence_ids,
                )
            )
        if eligibility and any(
            item.evidentiary_use is EvidentiaryUse.DECISIVE for item in source_evidence
        ) and not eligibility.decisive_use_allowed:
            findings.append(
                _risk(
                    SocialRiskCode.UNAUTHORIZED_DECISIVE_USE,
                    SocialRiskSeverity.BLOCKING,
                    "A decisive use exceeds the source's deterministic eligibility.",
                    source,
                    evidence_ids,
                )
            )
        prohibited = _prohibited_social_signals(source)
        if any("engagement" in item for item in prohibited):
            findings.append(
                _risk(
                    SocialRiskCode.ENGAGEMENT_SIGNAL_IGNORED,
                    SocialRiskSeverity.INFO,
                    "Engagement metadata was ignored for quality and authority.",
                    source,
                    evidence_ids,
                )
            )
        if any("badge" in item for item in prohibited):
            findings.append(
                _risk(
                    SocialRiskCode.PLATFORM_BADGE_IGNORED,
                    SocialRiskSeverity.INFO,
                    "Platform badge metadata was ignored as an authority signal.",
                    source,
                    evidence_ids,
                )
            )
    if social_sources and len(social_sources) == len(sources):
        findings.append(
            SocialRiskFinding(
                code=SocialRiskCode.SOCIAL_ONLY_EVIDENCE_PACKET,
                severity=SocialRiskSeverity.BLOCKING,
                reason=(
                    "Every retained evidence-bearing source is social material; "
                    "independent non-social corroboration is absent."
                ),
                evidence_ids=tuple(
                    item.evidence_id
                    for source in social_sources
                    for item in evidence_by_source[source.source_id]
                ),
            )
        )
    return tuple(findings)


def _prohibited_social_signals(source: Source) -> tuple[str, ...]:
    if source.discovery_metadata is None:
        return ()
    engagement_tokens = (
        "like",
        "share",
        "view",
        "follower",
        "retweet",
        "repost",
        "engagement",
    )
    badge_tokens = ("verified", "verification_badge", "blue_badge")
    ignored: list[str] = []
    for key in source.discovery_metadata.attributes:
        normalized = key.casefold()
        if any(token in normalized for token in engagement_tokens):
            ignored.append(f"engagement:{key}")
        if any(token in normalized for token in badge_tokens):
            ignored.append(f"badge:{key}")
    return tuple(sorted(set(ignored)))


def _risk(
    code: SocialRiskCode,
    severity: SocialRiskSeverity,
    reason: str,
    source: Source,
    evidence_ids: tuple[UUID, ...],
) -> SocialRiskFinding:
    return SocialRiskFinding(
        code=code,
        severity=severity,
        reason=reason,
        source_id=source.source_id,
        evidence_ids=evidence_ids,
    )
