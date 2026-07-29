"""Run the zero-provider Stage 10.8 adversarial and calibration gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_social_calibration import (
    export_phase10_social_calibration_audit,
    verify_phase10_social_calibration_audit,
)


def main() -> None:
    root = Path(__file__).parents[1]
    audit = export_phase10_social_calibration_audit(root)
    errors = verify_phase10_social_calibration_audit(audit, root)
    print(
        f"Audit: {audit.audit_id}\n"
        f"Cases/categories: {audit.case_count}/{audit.category_count}\n"
        f"Eligibility precision: {audit.eligibility_precision:.1%}\n"
        f"Unsafe-publication rate: {audit.unsafe_publication_rate:.1%}\n"
        f"Origin-resolution rate: {audit.origin_resolution_rate:.1%}\n"
        f"Independence inflation cases: "
        f"{audit.independence_inflation_case_count}\n"
        f"Mandatory-review recall: {audit.review_routing_recall:.1%}\n"
        f"Verdict stability: {audit.verdict_stability_rate:.1%}\n"
        f"Machine gate: {'pass' if audit.machine_gate_passed else 'fail'}\n"
        f"Human calibration: {audit.human_calibration_status}\n"
        f"Stage exit ready: {'yes' if audit.stage_exit_ready else 'no'}"
    )
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
