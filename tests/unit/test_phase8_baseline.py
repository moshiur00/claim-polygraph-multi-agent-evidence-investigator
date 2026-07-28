"""Stage 8.0 baseline and routing-specificity gates."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase8_baseline import (
    build_phase8_baseline,
    evaluate_phase8_routing_controls,
    verify_phase8_baseline,
)


def test_review_routing_controls_measure_recall_and_specificity() -> None:
    root = Path(__file__).parents[2]
    result = evaluate_phase8_routing_controls(
        root / "benchmarks/phase8_review_routing_controls_v1.json"
    )

    assert result.case_count == 10
    assert result.required_review_count == 5
    assert result.automatic_count == 5
    assert result.recall == 1
    assert result.specificity >= 0.8
    assert result.route_accuracy >= 0.9
    assert result.gate_passed


def test_phase8_baseline_manifest_is_hash_valid(tmp_path) -> None:
    files = (
        "benchmarks/initial_claims_v1.json",
        "benchmarks/phase8_review_routing_controls_v1.json",
        "artifacts/evaluations/phase7-final-closure-audit-v1.json",
        "artifacts/evaluations/phase7-stage7.8-frozen-comparison-v1.json",
        "docs/adr/0014-promote-langgraph-as-default-orchestrator.md",
        "docs/adr/0015-dashboard-root-monorepo.md",
        "docs/PHASE_8_STAGE_8.0_DASHBOARD_INVENTORY.md",
        "dashboard-history/dashboard-pre-monorepo-4651a05.bundle",
        "dashboard/package.json",
        "dashboard/eslint.config.mjs",
        "dashboard/scripts/run-vinext.mjs",
        "README.md",
        "benchmarks/README.md",
        "docs/PHASE_8_TRUE_MULTI_AGENT_EXECUTION_PLAN.md",
        "docs/PHASE_8_STAGE_8.0_COMPLETION_REPORT.md",
    )
    for relative in files:
        candidate = tmp_path / relative
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(relative, encoding="utf-8")

    manifest = build_phase8_baseline(tmp_path)
    verification = verify_phase8_baseline(manifest, tmp_path)

    assert manifest.default_orchestrator == "langgraph"
    assert manifest.rollback_orchestrator == "direct"
    assert manifest.resource_ceilings.fixture_model_calls == 0
    assert verification.valid
    assert verification.checked_artifact_count == 15
