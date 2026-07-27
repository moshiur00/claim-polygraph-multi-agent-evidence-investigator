import asyncio
from pathlib import Path

from claim_polygraph_ng.evaluation import (
    build_phase4_pilot_preflight,
    load_benchmark,
    load_phase4_manifest,
    run_phase4_structural_dry_run,
)


def test_locked_pilot_preflight_extracts_matched_control_and_ceilings() -> None:
    root = Path(__file__).parents[2]
    manifest = load_phase4_manifest(
        root / "artifacts/evaluations/phase4-experiment-manifest-v1.json"
    )
    dataset = load_benchmark(root / "benchmarks/initial_claims_v1.json")

    preflight = build_phase4_pilot_preflight(
        manifest=manifest,
        dataset=dataset,
        phase3_run_path=root / "artifacts/evaluations/phase3-v5-final-run-a.json",
        project_root=root,
    )

    assert preflight.valid
    assert preflight.pilot_case_ids == ("CPNG-014", "CPNG-016", "CPNG-020")
    assert preflight.component_count == 6
    assert len(preflight.controls) == 3
    assert preflight.phase3_control_cost_usd == 0.05665305
    assert preflight.maximum_phase4_cost_usd == 0.1133061
    assert preflight.estimated_role_activations == 22
    assert preflight.maximum_search_calls == 44
    assert preflight.maximum_fetched_pages == 72
    assert preflight.paid_calls_authorized is False


def test_structural_dry_run_is_zero_cost_and_grounded(tmp_path) -> None:
    root = Path(__file__).parents[2]
    manifest = load_phase4_manifest(
        root / "artifacts/evaluations/phase4-experiment-manifest-v1.json"
    )
    dataset = load_benchmark(root / "benchmarks/initial_claims_v1.json")

    summary = asyncio.run(
        run_phase4_structural_dry_run(
            manifest=manifest,
            dataset=dataset,
            working_directory=tmp_path,
        )
    )

    assert summary.valid
    assert summary.case_count == 3
    assert summary.completed_count == 3
    assert summary.total_fetch_calls == 0
    assert summary.total_model_calls == 0
    assert summary.estimated_cost_usd == 0
    assert all(item.citations_grounded for item in summary.results)
