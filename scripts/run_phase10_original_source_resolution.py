"""Run the zero-network Stage 10.4 original-source resolution gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_original_source_resolution import (
    export_phase10_original_source_audit,
    verify_phase10_original_source_audit,
)


def main() -> None:
    root = Path(__file__).parents[1]
    audit = export_phase10_original_source_audit(root)
    errors = verify_phase10_original_source_audit(audit, root)
    print(
        f"Audit: {audit.audit_id}\n"
        f"Preflight fixtures: {audit.case_count}\n"
        f"Exact decisions: {audit.exact_preflight_count}\n"
        f"Allowed / blocked: {audit.allowed_count} / {audit.blocked_count}\n"
        f"Resolved pair families: {audit.resolved_pair_family_count}\n"
        f"Network calls: {audit.network_calls}\n"
        f"Valid: {'yes' if not errors else 'no'}"
    )
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

