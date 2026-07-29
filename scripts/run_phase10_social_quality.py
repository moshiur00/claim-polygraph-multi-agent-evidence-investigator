"""Run the zero-cost Stage 10.5 social-quality safety gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_social_quality import (
    export_phase10_social_quality_audit,
    verify_phase10_social_quality_audit,
)


def main() -> None:
    root = Path(__file__).parents[1]
    audit = export_phase10_social_quality_audit(root)
    errors = verify_phase10_social_quality_audit(audit, root)
    print(
        f"Audit: {audit.audit_id}\n"
        f"Authority cases: {audit.exact_authority_count}/{audit.quality_case_count}\n"
        f"Badge promotions: {audit.badge_authority_promotion_count}\n"
        f"Engagement-driven changes: {audit.engagement_authority_change_count}\n"
        f"Shared-origin families: {audit.shared_origin_family_count}\n"
        f"Valid: {'yes' if not errors else 'no'}"
    )
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

