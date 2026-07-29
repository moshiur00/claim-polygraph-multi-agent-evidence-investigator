"""Stage 10.5 reproducible social-quality gate tests."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_social_quality import (
    build_phase10_social_quality_audit,
    verify_phase10_social_quality_audit,
)


def test_phase10_social_quality_gate_is_complete() -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_social_quality_audit(root)

    assert audit.exact_authority_count == audit.quality_case_count == 3
    assert audit.badge_authority_promotion_count == 0
    assert audit.engagement_authority_change_count == 0
    assert audit.shared_origin_source_count == 3
    assert audit.shared_origin_family_count == 1
    assert audit.shared_origin_reason_present
    assert verify_phase10_social_quality_audit(audit, root) == ()

