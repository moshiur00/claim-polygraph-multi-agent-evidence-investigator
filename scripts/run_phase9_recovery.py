"""Export and verify the Stage 9.11 recovery gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_recovery import (
    Phase9RecoveryGate,
    build_release_manifest,
    export_gate,
    verify_release_manifest,
)

root = Path(__file__).resolve().parents[1]
export_gate(
    Phase9RecoveryGate(),
    root / "artifacts/evaluations/phase9-stage9.11-recovery-v1.json",
)
manifest = build_release_manifest(root)
verification = verify_release_manifest(manifest, root)
print(f"Evaluation: {Phase9RecoveryGate().evaluation_id}")
print(f"Artifacts checked: {verification.checked_artifact_count}")
print(f"Valid: {'yes' if verification.valid else 'no'}")
for error in verification.errors:
    print(f"Error: {error}")
raise SystemExit(0 if verification.valid else 1)
