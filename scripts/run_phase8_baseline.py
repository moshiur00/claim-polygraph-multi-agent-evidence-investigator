"""Build and verify the zero-cost Phase 8 Stage 8.0 artifacts."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase8_baseline import (
    build_phase8_baseline,
    evaluate_phase8_routing_controls,
    export_phase8_routing,
    verify_phase8_baseline,
)


def main() -> None:
    root = Path(__file__).parents[1]
    routing = evaluate_phase8_routing_controls(
        root / "benchmarks/phase8_review_routing_controls_v1.json"
    )
    export_phase8_routing(
        routing,
        root / "artifacts/evaluations/phase8-stage8.0-routing-controls-v1.json",
    )
    manifest = build_phase8_baseline(root)
    verification = verify_phase8_baseline(manifest, root)
    print(
        f"Manifest: {manifest.manifest_id}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if verification.valid else 'no'}\n"
        f"Routing gate: {'passed' if routing.gate_passed else 'failed'}"
    )
    if not verification.valid or not routing.gate_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
