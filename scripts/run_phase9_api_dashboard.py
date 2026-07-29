"""Export and verify the Stage 9.10 release gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_api_dashboard import (
    Phase9ApiDashboardGate,
    build_release_manifest,
    export_gate,
    verify_release_manifest,
)

root = Path(__file__).resolve().parents[1]
export_gate(
    Phase9ApiDashboardGate(),
    root / "artifacts/evaluations/phase9-stage9.10-api-dashboard-v1.json",
)
manifest = build_release_manifest(root)
verification = verify_release_manifest(manifest, root)
print(manifest.model_dump_json(indent=2))
print(verification.model_dump_json(indent=2))
raise SystemExit(0 if verification.valid else 1)
