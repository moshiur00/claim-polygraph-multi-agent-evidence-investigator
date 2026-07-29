"""Build and verify the zero-cost Stage 9.0 migration baseline."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_baseline import (
    build_phase9_baseline,
    verify_phase9_baseline,
)


def main() -> None:
    root = Path(__file__).parents[1]
    manifest = build_phase9_baseline(root)
    verification = verify_phase9_baseline(manifest, root)
    print(
        f"Manifest: {manifest.manifest_id}\n"
        f"Cases frozen: {manifest.case_count}\n"
        f"Responsibilities mapped: {len(manifest.responsibilities)}\n"
        f"Compatibility contracts checked: {verification.checked_contract_count}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if verification.valid else 'no'}"
    )
    if not verification.valid:
        for error in verification.errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
