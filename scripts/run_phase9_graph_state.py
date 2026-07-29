"""Build and verify the zero-cost Stage 9.3 graph-state manifest."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_graph_state import (
    build_phase9_graph_state_manifest,
    verify_phase9_graph_state_manifest,
)


def main() -> None:
    root = Path(__file__).parents[1]
    manifest = build_phase9_graph_state_manifest(root)
    verification = verify_phase9_graph_state_manifest(manifest, root)
    print(
        f"Manifest: {manifest.manifest_id}\n"
        f"Graph version: {manifest.graph_version}\n"
        f"Monotonic invariants: {manifest.invariant_count}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if verification.valid else 'no'}"
    )
    if not verification.valid:
        raise SystemExit("\n".join(verification.errors))


if __name__ == "__main__":
    main()
