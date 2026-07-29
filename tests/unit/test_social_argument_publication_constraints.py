"""Stage 10.6 argument, judgment, review, and publication safeguards."""

from datetime import UTC, datetime
from uuid import uuid4

from claim_polygraph_ng.analysis.judgment_policy import enforce_judgment_policy
from claim_polygraph_ng.domain import (
    ArgumentLedger,
    AuthoritativePublicationStatus,
    CitationAssurancePacket,
    DistributionMedium,
    Evidence,
    EvidenceStance,
    EvidentiaryUse,
    ExtractionStatus,
    FullReportCitationAssurance,
    JudgmentReadiness,
    JudgmentReadinessState,
    MaterialProposition,
    PropositionArgument,
    PropositionResolution,
    PublicationGateStatus,
    SocialAccountIdentity,
    SocialAccountType,
    SocialAuthenticityEvidence,
    SocialAuthenticityEvidenceType,
    SocialAuthenticityStatus,
    SocialCaptureMethod,
    SocialConstraintCode,
    SocialContentOriginStatus,
    SocialEvidencePolicyResult,
    SocialPostType,
    SocialSourceContext,
    Source,
    SourceType,
    Verdict,
    VerdictLabel,
    decide_publication,
    evaluate_social_evidence_constraints,
    evaluate_social_evidence_eligibility,
)


def test_social_only_decisive_proposition_blocks_publication() -> None:
    claim_id = uuid4()
    social = _social_source()
    item = _evidence(
        claim_id, social, EvidentiaryUse.ATTRIBUTED_STATEMENT
    )
    ledger = _ledger(claim_id, (item,), PropositionResolution.SUPPORTED)

    result = evaluate_social_evidence_constraints(
        ledger=ledger,
        sources=(social,),
        evidence=(item,),
    )

    assert result.publication_blocked
    assert result.requires_human_review
    assert {
        finding.code for finding in result.findings
    } >= {
        SocialConstraintCode.DECISIVE_USE_NOT_ALLOWED,
        SocialConstraintCode.NON_SOCIAL_CORROBORATION_MISSING,
    }


def test_non_social_corroboration_removes_publication_block_but_keeps_review() -> None:
    claim_id = uuid4()
    social = _social_source()
    web = _web_source()
    social_item = _evidence(
        claim_id, social, EvidentiaryUse.ATTRIBUTED_STATEMENT
    )
    web_item = _evidence(claim_id, web, EvidentiaryUse.DECISIVE)
    ledger = _ledger(
        claim_id,
        (social_item, web_item),
        PropositionResolution.SUPPORTED,
    )

    result = evaluate_social_evidence_constraints(
        ledger=ledger,
        sources=(social, web),
        evidence=(social_item, web_item),
    )

    assert not result.publication_blocked
    assert result.requires_human_review
    assert SocialConstraintCode.NON_SOCIAL_CORROBORATION_MISSING not in {
        item.code for item in result.findings
    }


def test_unspecified_social_use_is_fail_closed() -> None:
    claim_id = uuid4()
    social = _social_source()
    item = _evidence(claim_id, social, EvidentiaryUse.UNSPECIFIED)

    result = evaluate_social_evidence_constraints(
        ledger=_ledger(claim_id, (item,), PropositionResolution.SUPPORTED),
        sources=(social,),
        evidence=(item,),
    )

    assert result.publication_blocked
    assert SocialConstraintCode.EVIDENTIARY_USE_UNSPECIFIED in {
        finding.code for finding in result.findings
    }


def test_judgment_trace_routes_social_policy_review_without_changing_label() -> None:
    claim_id = uuid4()
    item = _evidence(claim_id, _web_source(), EvidentiaryUse.DECISIVE)
    ledger = _ledger(claim_id, (item,), PropositionResolution.SUPPORTED)
    social_policy = SocialEvidencePolicyResult(
        claim_id=claim_id,
        findings=(),
        requires_human_review=True,
        publication_blocked=False,
    )
    proposed = Verdict(
        claim_id=claim_id,
        label=VerdictLabel.SUPPORTED,
        concise_explanation="The approved packet supports the material proposition.",
        detailed_reasoning="The approved packet supports the material proposition.",
        decisive_evidence_ids=(item.evidence_id,),
    )

    enforced, trace = enforce_judgment_policy(proposed, ledger, social_policy)

    assert enforced.label is VerdictLabel.SUPPORTED
    assert enforced.human_review_required
    assert trace.human_review_required


def test_publication_gate_fails_closed_on_blocking_social_policy() -> None:
    claim_id = uuid4()
    investigation_id = uuid4()
    item = _evidence(claim_id, _web_source(), EvidentiaryUse.DECISIVE)
    ledger = _ledger(claim_id, (item,), PropositionResolution.SUPPORTED)
    verdict = Verdict(
        claim_id=claim_id,
        label=VerdictLabel.SUPPORTED,
        concise_explanation="The approved packet supports the material proposition.",
        detailed_reasoning="The approved packet supports the material proposition.",
        decisive_evidence_ids=(item.evidence_id,),
    )
    _, trace = enforce_judgment_policy(verdict, ledger)
    social_policy = SocialEvidencePolicyResult(
        claim_id=claim_id,
        findings=(),
        requires_human_review=True,
        publication_blocked=True,
        blocking_reasons=("A critical conclusion lacks non-social corroboration.",),
    )
    assurance = FullReportCitationAssurance.model_construct(
        claim_id=claim_id,
        publication_status=PublicationGateStatus.READY,
        blocking_reasons=(),
        revisions=(),
        final_audit=CitationAssurancePacket.model_construct(full_support_rate=1.0),
        critical_failure_count=0,
    )
    readiness = JudgmentReadiness.model_construct(
        claim_id=claim_id,
        state=JudgmentReadinessState.READY,
    )

    decision = decide_publication(
        investigation_id=investigation_id,
        proposed_verdict=verdict,
        enforced_verdict=verdict,
        policy=trace,
        assurance=assurance,
        readiness=readiness,
        social_policy=social_policy,
    )

    assert decision.status is AuthoritativePublicationStatus.BLOCKED
    assert not decision.publication_allowed
    assert decision.reason_codes == ("social_evidence_policy_blocked",)


def _ledger(
    claim_id,
    evidence: tuple[Evidence, ...],
    resolution: PropositionResolution,
) -> ArgumentLedger:
    proposition_id = uuid4()
    ids = tuple(item.evidence_id for item in evidence)
    return ArgumentLedger(
        claim_id=claim_id,
        approved_evidence_ids=ids,
        propositions=(
            MaterialProposition(
                proposition_id=proposition_id,
                claim_id=claim_id,
                text="A material factual proposition under investigation.",
            ),
        ),
        arguments=(
            PropositionArgument(
                proposition_id=proposition_id,
                resolution=resolution,
                supporting_evidence_ids=ids,
            ),
        ),
    )


def _evidence(claim_id, source: Source, use: EvidentiaryUse) -> Evidence:
    return Evidence(
        claim_id=claim_id,
        source_id=source.source_id,
        passage="A retained passage relevant to the material proposition.",
        stance=EvidenceStance.SUPPORTS,
        relevance_score=0.9,
        evidentiary_use=use,
    )


def _social_source() -> Source:
    context = SocialSourceContext(
        account=SocialAccountIdentity(
            platform="x",
            handle="agency",
            account_type=SocialAccountType.GOVERNMENT,
            authority_scope="Statements about the agency's own actions.",
            authenticity_status=SocialAuthenticityStatus.AUTHENTICATED,
            authenticity_evidence=(
                SocialAuthenticityEvidence(
                    evidence_type=(
                        SocialAuthenticityEvidenceType.OFFICIAL_WEBSITE_LINK
                    ),
                    reference_url="https://agency.example/social",
                    observed_at=datetime.now(UTC),
                    description="The official website links to this account.",
                ),
            ),
        ),
        post_type=SocialPostType.ORIGINAL,
        capture_method=SocialCaptureMethod.DIRECT_PUBLIC_PAGE,
        content_origin_status=SocialContentOriginStatus.ORIGINAL_ACCESSIBLE,
    )
    return Source(
        url="https://x.com/agency/status/123",
        canonical_url="https://x.com/agency/status/123",
        title="Agency statement",
        source_type=SourceType.OTHER,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_context=context,
        social_eligibility=evaluate_social_evidence_eligibility(context),
    )


def _web_source() -> Source:
    return Source(
        url="https://independent.example/report",
        canonical_url="https://independent.example/report",
        title="Independent report",
        source_type=SourceType.NEWS,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
        distribution_medium=DistributionMedium.WEB_PAGE,
    )
