"""Stage 10.1 backward compatibility and social-evidence policy tests."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    DistributionMedium,
    Evidence,
    EvidenceEligibilityDecision,
    EvidenceStance,
    EvidentiaryUse,
    SocialAccountIdentity,
    SocialAccountType,
    SocialAuthenticityStatus,
    SocialEvidenceEligibility,
    SocialOriginalSourceLink,
    SocialPostType,
    SocialSourceContext,
    SocialSourceRelationship,
    Source,
    SourceType,
    evaluate_social_evidence_eligibility,
)


def _legacy_source_payload() -> dict[str, object]:
    return {
        "url": "https://social.example/post/1",
        "canonical_url": "https://social.example/post/1",
        "title": "Legacy generic result",
        "source_type": "other",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "extraction_status": "extracted",
    }


def _account(
    *,
    account_type: SocialAccountType = SocialAccountType.INDIVIDUAL,
    authenticity: SocialAuthenticityStatus = SocialAuthenticityStatus.UNKNOWN,
    authority_scope: str | None = None,
) -> SocialAccountIdentity:
    return SocialAccountIdentity(
        platform="Example Social",
        handle="@source",
        account_type=account_type,
        authority_scope=authority_scope,
        authenticity_status=authenticity,
        authenticity_basis=(
            "Matched from the institution's official website."
            if authenticity
            in {
                SocialAuthenticityStatus.AUTHENTICATED,
                SocialAuthenticityStatus.DISPUTED,
            }
            else None
        ),
    )


def test_legacy_source_and_evidence_deserialize_with_conservative_defaults() -> None:
    source = Source.model_validate(_legacy_source_payload())
    restored = Source.model_validate_json(source.model_dump_json())
    evidence = Evidence(
        claim_id=uuid4(),
        source_id=source.source_id,
        passage="A retained passage from a legacy artifact.",
        stance=EvidenceStance.CONTEXT,
        relevance_score=0.7,
    )

    assert restored == source
    assert source.source_type is SourceType.OTHER
    assert source.distribution_medium is DistributionMedium.UNKNOWN
    assert source.social_context is None
    assert source.social_eligibility is None
    assert evidence.evidentiary_use is EvidentiaryUse.UNSPECIFIED


def test_explicit_social_source_requires_context_and_exact_policy_result() -> None:
    context = SocialSourceContext(
        account=_account(),
        post_type=SocialPostType.ORIGINAL,
    )
    expected = evaluate_social_evidence_eligibility(context)
    source = Source(
        **_legacy_source_payload(),
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_context=context,
        social_eligibility=expected,
    )

    assert source.social_eligibility == expected
    assert expected.decision is EvidenceEligibilityDecision.CONDITIONAL
    assert not expected.decisive_use_allowed
    assert not expected.independent_proof_allowed

    forged = SocialEvidenceEligibility(
        decision=EvidenceEligibilityDecision.ELIGIBLE,
        allowed_uses=(EvidentiaryUse.DECISIVE,),
        decisive_use_allowed=True,
        independent_proof_allowed=True,
        requires_corroboration=False,
        reason_codes=("caller_override",),
    )
    with pytest.raises(ValidationError, match="deterministic policy"):
        Source(
            **_legacy_source_payload(),
            distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
            social_context=context,
            social_eligibility=forged,
        )


def test_repost_and_screenshot_are_leads_even_when_origin_is_resolved() -> None:
    link = SocialOriginalSourceLink(
        relationship=SocialSourceRelationship.REPOST_OF,
        source_id=uuid4(),
        url="https://social.example/post/original",
        resolved=True,
    )
    context = SocialSourceContext(
        account=_account(authenticity=SocialAuthenticityStatus.AUTHENTICATED),
        post_type=SocialPostType.REPOST,
        original_source=link,
    )
    decision = evaluate_social_evidence_eligibility(context)

    assert decision.decision is EvidenceEligibilityDecision.INELIGIBLE
    assert decision.allowed_uses == (EvidentiaryUse.DISCOVERY_LEAD,)
    assert not decision.independent_proof_allowed
    assert not decision.decisive_use_allowed

    with pytest.raises(ValidationError, match="original_source"):
        SocialSourceContext(
            account=_account(),
            post_type=SocialPostType.SCREENSHOT,
        )


def test_institutional_account_needs_authentication_and_recorded_scope() -> None:
    no_scope = SocialSourceContext(
        account=_account(
            account_type=SocialAccountType.GOVERNMENT,
            authenticity=SocialAuthenticityStatus.AUTHENTICATED,
        ),
        post_type=SocialPostType.ORIGINAL,
    )
    scoped = SocialSourceContext(
        account=_account(
            account_type=SocialAccountType.GOVERNMENT,
            authenticity=SocialAuthenticityStatus.AUTHENTICATED,
            authority_scope="Announcements about the agency's own emergency designation.",
        ),
        post_type=SocialPostType.ORIGINAL,
    )

    unscoped_decision = evaluate_social_evidence_eligibility(no_scope)
    scoped_decision = evaluate_social_evidence_eligibility(scoped)

    assert unscoped_decision.decision is EvidenceEligibilityDecision.CONDITIONAL
    assert unscoped_decision.requires_human_review
    assert not unscoped_decision.independent_proof_allowed
    assert scoped_decision.decision is EvidenceEligibilityDecision.ELIGIBLE
    assert scoped_decision.independent_proof_allowed
    assert not scoped_decision.decisive_use_allowed
    assert scoped_decision.allowed_uses == (
        EvidentiaryUse.ATTRIBUTED_STATEMENT,
        EvidentiaryUse.CONTEXT,
    )


def test_eyewitness_social_content_is_qualified_and_requires_review() -> None:
    context = SocialSourceContext(
        account=_account(authenticity=SocialAuthenticityStatus.AUTHENTICATED),
        post_type=SocialPostType.ORIGINAL,
        eyewitness_claim=True,
    )
    decision = evaluate_social_evidence_eligibility(context)

    assert decision.decision is EvidenceEligibilityDecision.CONDITIONAL
    assert decision.allowed_uses == (
        EvidentiaryUse.QUALIFIED_OBSERVATION,
        EvidentiaryUse.CONTEXT,
    )
    assert decision.requires_corroboration
    assert decision.requires_human_review


def test_social_fields_are_rejected_on_non_social_sources() -> None:
    context = SocialSourceContext(
        account=_account(),
        post_type=SocialPostType.ORIGINAL,
    )
    with pytest.raises(ValidationError, match="require social distribution"):
        Source(
            **_legacy_source_payload(),
            distribution_medium=DistributionMedium.WEB_PAGE,
            social_context=context,
            social_eligibility=evaluate_social_evidence_eligibility(context),
        )
