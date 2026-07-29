"""Build and verify the Stage 10.9 final audit and release manifest."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_final_audit import (
    build_phase10_release_manifest,
    export_phase10_final_audit,
    verify_phase10_release_manifest,
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    audit = export_phase10_final_audit(root)
    manifest = build_phase10_release_manifest(root)
    errors = verify_phase10_release_manifest(manifest, root)
    print(f"Audit: {audit.audit_id}")
    print(f"Checks passed: {sum(item.passed for item in audit.checks)}/{len(audit.checks)}")
    print(f"Mechanical gates: {'pass' if audit.mechanical_gates_passed else 'fail'}")
    human_status = (
        "approved" if audit.stage10_8_human_calibration_approved else "pending"
    )
    print(f"Human calibration: {human_status}")
    print(f"Recommendation: {audit.recommended_decision}")
    print(f"Promotion status: {audit.promotion_status}")
    print(f"Artifacts hashed: {len(manifest.artifacts)}")
    print(f"Manifest: {'valid' if not errors else 'invalid'}")
    for error in errors:
        print(f"- {error}")
    return 0 if audit.mechanical_gates_passed and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
