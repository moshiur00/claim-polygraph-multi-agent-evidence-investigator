"""Run the zero-cost Phase 4 pilot preflight and structural dry run."""

import asyncio
from pathlib import Path

from claim_polygraph_ng.evaluation import (
    build_phase4_pilot_preflight,
    export_phase4_pilot_artifact,
    load_benchmark,
    load_phase4_manifest,
    run_phase4_structural_dry_run,
)

ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / "artifacts/evaluations/phase4-experiment-manifest-v1.json"
DATASET_PATH = ROOT / "benchmarks/initial_claims_v1.json"
CONTROL_PATH = ROOT / "artifacts/evaluations/phase3-v5-final-run-a.json"
PREFLIGHT_PATH = ROOT / "artifacts/evaluations/phase4-pilot-preflight.json"
DRY_RUN_PATH = ROOT / "artifacts/evaluations/phase4-pilot-dry-run.json"
WORKING_DIRECTORY = ROOT / "data/phase4-pilot-dry-run"


async def main() -> int:
    """Generate both artifacts without live retrieval or model access."""
    manifest = load_phase4_manifest(MANIFEST_PATH)
    dataset = load_benchmark(DATASET_PATH)
    preflight = build_phase4_pilot_preflight(
        manifest=manifest,
        dataset=dataset,
        phase3_run_path=CONTROL_PATH,
        project_root=ROOT,
    )
    dry_run = await run_phase4_structural_dry_run(
        manifest=manifest,
        dataset=dataset,
        working_directory=WORKING_DIRECTORY,
    )
    export_phase4_pilot_artifact(preflight, PREFLIGHT_PATH)
    export_phase4_pilot_artifact(dry_run, DRY_RUN_PATH)
    print(f"Preflight valid: {preflight.valid}")
    print(f"Paid calls authorized: {preflight.paid_calls_authorized}")
    print(f"Maximum pilot cost: ${preflight.maximum_phase4_cost_usd:.6f}")
    print(f"Dry run valid: {dry_run.valid}")
    print(f"Dry-run calls: {dry_run.total_search_calls} search, 0 fetch, 0 model")
    return 0 if preflight.valid and dry_run.valid else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
