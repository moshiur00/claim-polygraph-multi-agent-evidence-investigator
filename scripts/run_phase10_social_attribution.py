"""Run the zero-network Stage 10.3 authenticity and attribution gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_social_attribution import (
    export_phase10_social_attribution_audit,
    verify_phase10_social_attribution_audit,
)


def main() -> None:
    root = Path(__file__).parents[1]
    audit = export_phase10_social_attribution_audit(root)
    errors = verify_phase10_social_attribution_audit(audit, root)
    print(
        f"Audit: {audit.audit_id}\n"
        f"Fixture cases: {audit.case_count}\n"
        f"Exact matches: {audit.exact_match_count}\n"
        f"Decision counts: {audit.decision_counts}\n"
        f"Decisive permissions: {audit.decisive_permission_count}\n"
        f"Social-page fetches: {audit.social_page_fetches}\n"
        f"Valid: {'yes' if not errors else 'no'}"
    )
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

