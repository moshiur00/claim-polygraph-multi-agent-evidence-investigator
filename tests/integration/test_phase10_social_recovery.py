"""Stage 10.9 social-state reconstruction and inherited recovery gates."""

import json
from datetime import UTC, datetime
from pathlib import Path

from claim_polygraph_ng.domain import (
    DistributionMedium,
    EvidenceEligibilityDecision,
    ExtractionStatus,
    SocialAccountIdentity,
    SocialCaptureMethod,
    SocialContentOriginStatus,
    SocialPostType,
    SocialSourceContext,
    Source,
    SourceType,
    evaluate_social_evidence_eligibility,
)
from claim_polygraph_ng.evaluation.phase10_final_audit import (
    build_phase10_final_audit,
)


def test_deleted_social_state_reconstructs_without_becoming_eligible() -> None:
    context = SocialSourceContext(
        account=SocialAccountIdentity(platform="fixture", identity_resolved=False),
        post_type=SocialPostType.ORIGINAL,
        capture_method=SocialCaptureMethod.COPIED_TEXT,
        content_origin_status=SocialContentOriginStatus.COPIED_TEXT_ONLY,
        unavailable_or_deleted=True,
    )
    source = Source(
        url="https://social.example/deleted/123",
        canonical_url="https://social.example/deleted/123",
        title="Deleted post fixture",
        source_type=SourceType.OTHER,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_context=context,
        social_eligibility=evaluate_social_evidence_eligibility(context),
    )

    reconstructed = Source.model_validate_json(source.model_dump_json())

    assert reconstructed == source
    assert reconstructed.social_context is not None
    assert reconstructed.social_context.unavailable_or_deleted
    assert reconstructed.social_eligibility is not None
    assert (
        reconstructed.social_eligibility.decision
        is EvidenceEligibilityDecision.INELIGIBLE
    )


def test_phase9_recovery_contract_remains_complete() -> None:
    root = Path(__file__).parents[2]
    recovery = json.loads(
        (
            root / "artifacts/evaluations/phase9-stage9.11-recovery-v1.json"
        ).read_text("utf-8")
    )
    controls = {
        key: value
        for key, value in recovery.items()
        if key
        not in {
            "evaluation_id",
            "external_model_calls",
            "live_search_calls",
            "network_fetches",
            "pdf_downloads",
        }
    }

    assert controls
    assert all(controls.values())
    assert recovery["external_model_calls"] == 0
    assert recovery["live_search_calls"] == 0


def test_final_audit_preserves_rollback_and_social_publication_gates() -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_final_audit(root)
    checks = {item.check_id: item.passed for item in audit.checks}

    assert checks["phase9_recovery_preserved"]
    assert checks["social_checkpoint_roundtrip"]
    assert checks["publication_controls_preserved"]
    assert checks["direct_rollback_retained"]
