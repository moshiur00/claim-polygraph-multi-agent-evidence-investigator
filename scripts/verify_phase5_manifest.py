"""Verify the locked Phase 5 manifest without network or model access."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_manifest import (
    load_phase5_manifest,
    verify_phase5_manifest,
)

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "artifacts/evaluations/phase5-source-intelligence-manifest-v1.json"


def main() -> int:
    result = verify_phase5_manifest(load_phase5_manifest(MANIFEST), ROOT)
    print(f"Manifest: {result.manifest_id}")
    print(f"Artifacts checked: {result.checked_artifact_count}")
    print(f"Benchmark reviewed: {result.benchmark_reviewed}")
    print(f"Valid: {result.valid}")
    for error in result.errors:
        print(f"- {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
