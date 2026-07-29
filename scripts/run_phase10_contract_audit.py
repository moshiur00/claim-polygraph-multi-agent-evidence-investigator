"""Build and verify the Stage 10.1 typed social-contract audit."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_contract_audit import (
    build_phase10_contract_audit,
    verify_phase10_contract_audit,
)


def main() -> None:
    root = Path(__file__).parents[1]
    audit = build_phase10_contract_audit(root)
    errors = verify_phase10_contract_audit(audit)
    print(
        f"Audit: {audit.audit_id}\n"
        f"Contracts hashed: {len(audit.schemas)}\n"
        f"Legacy Source loads: {'yes' if audit.legacy_source_loads else 'no'}\n"
        f"Legacy Evidence loads: {'yes' if audit.legacy_evidence_loads else 'no'}\n"
        f"External calls: {audit.model_calls + audit.search_calls}\n"
        f"Valid: {'yes' if not errors else 'no'}"
    )
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

