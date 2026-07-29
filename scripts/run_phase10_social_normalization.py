"""Run the zero-network Stage 10.2 social normalization gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_social_normalization import (
    export_phase10_social_normalization_audit,
    verify_phase10_social_normalization_audit,
)


def main() -> None:
    root = Path(__file__).parents[1]
    audit = export_phase10_social_normalization_audit(root)
    errors = verify_phase10_social_normalization_audit(audit, root)
    print(
        f"Audit: {audit.audit_id}\n"
        f"Fixture cases: {audit.case_count}\n"
        f"Exact matches: {audit.exact_match_count}\n"
        f"Platforms covered: {audit.platform_count}\n"
        f"Social-page fetches: {audit.social_page_fetches}\n"
        f"Valid: {'yes' if not errors else 'no'}"
    )
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

