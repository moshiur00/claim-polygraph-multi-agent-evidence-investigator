"""Build and verify the zero-cost Stage 10.0 social-evidence baseline."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_social_baseline import (
    build_phase10_social_baseline,
    verify_phase10_social_baseline,
)


def main() -> None:
    root = Path(__file__).parents[1]
    manifest = build_phase10_social_baseline(root)
    verification = verify_phase10_social_baseline(manifest, root)
    print(
        f"Manifest: {manifest.manifest_id}\n"
        f"Current-behavior observations: {len(manifest.observations)}\n"
        f"Policy rules checked: {verification.checked_policy_rule_count}\n"
        f"Safeguards frozen: {len(manifest.non_negotiable_safeguards)}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"External calls: {sum(manifest.resource_policy.model_dump().values())}\n"
        f"Valid: {'yes' if verification.valid else 'no'}"
    )
    if not verification.valid:
        for error in verification.errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

