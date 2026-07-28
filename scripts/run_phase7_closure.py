"""Build and verify the Stage 7.9 pending-human-approval closure audit."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase7_closure import (
    build_phase7_closure,
    verify_phase7_manifest,
)

ROOT = Path(__file__).parents[1]


def main() -> int:
    calibration, manifest, audit = build_phase7_closure(ROOT)
    verification = verify_phase7_manifest(manifest, ROOT)
    print(f"Targeted cases: {len(calibration.targeted_case_ids)}")
    print(f"Artifacts checked: {verification.checked_artifact_count}")
    print(f"Manifest valid: {verification.valid}")
    print(f"Engineering complete: {audit.engineering_complete}")
    print(f"Phase complete: {audit.phase_complete}")
    print(f"Promotion approval: {audit.promotion_approval_status}")
    return 0 if verification.valid and audit.engineering_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
