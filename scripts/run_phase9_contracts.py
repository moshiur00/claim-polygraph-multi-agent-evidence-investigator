"""Build and verify the zero-cost Stage 9.1 operation contract manifest."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_contracts import (
    build_phase9_contract_manifest,
    verify_phase9_contract_manifest,
)


def main() -> None:
    root = Path(__file__).parents[1]
    manifest = build_phase9_contract_manifest(root)
    verification = verify_phase9_contract_manifest(manifest, root)
    print(
        f"Manifest: {manifest.manifest_id}\n"
        f"Operations: {manifest.operation_count}\n"
        f"Paid-capable operations: {manifest.paid_operation_count}\n"
        f"Schemas checked: {verification.checked_contract_count * 2}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if verification.valid else 'no'}"
    )
    if not verification.valid:
        raise SystemExit("\n".join(verification.errors))


if __name__ == "__main__":
    main()
