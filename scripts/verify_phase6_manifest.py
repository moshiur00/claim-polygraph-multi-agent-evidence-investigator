"""Verify the locked Phase 6 manifest without external calls."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase6_manifest import (
    load_phase6_manifest,
    verify_phase6_manifest,
)

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "artifacts/evaluations/phase6-experiment-manifest-v1.json"


def main() -> int:
    result = verify_phase6_manifest(load_phase6_manifest(MANIFEST), ROOT)
    print(f"Manifest: {result.manifest_id}")
    print(f"Artifacts checked: {result.checked_artifact_count}")
    print(f"Benchmark reviewed: {result.benchmark_reviewed}")
    print(f"Valid: {result.valid}")
    for error in result.errors:
        print(f"- {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
