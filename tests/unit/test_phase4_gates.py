from claim_polygraph_ng.evaluation.phase4_gates import (
    Phase4GateState,
    audit_phase4_gates,
)
from claim_polygraph_ng.evaluation.phase4_pilot import (
    Phase4DryRunSummary,
    Phase4PaidPilotSummary,
    Phase4PilotPreflight,
)


def test_failed_pilot_closes_phase_and_skips_expensive_runs():
    preflight = Phase4PilotPreflight(
        manifest_id="phase4-test",
        valid=True,
        pilot_case_ids=("A", "B", "C"),
        component_count=6,
        controls=(),
        phase3_control_cost_usd=0.05,
        maximum_phase4_cost_usd=0.1,
        phase3_median_latency_seconds=10,
        maximum_phase4_median_latency_seconds=25,
        estimated_role_activations=18,
        maximum_search_calls=36,
        maximum_fetched_pages=72,
    )
    dry_run = Phase4DryRunSummary(
        manifest_id="phase4-test",
        provider_mode="fixture",
        valid=True,
        case_count=3,
        completed_count=3,
        total_search_calls=6,
        total_fetch_calls=0,
        total_model_calls=0,
        estimated_cost_usd=0,
        results=(),
        limitations=(),
    )
    pilot = Phase4PaidPilotSummary(
        manifest_id="phase4-test",
        provider_mode="test",
        case_count=3,
        completed_count=3,
        verdict_accuracy=1,
        phase3_control_accuracy=2 / 3,
        improved_case_count=1,
        regressed_case_count=0,
        citation_full_rate=1,
        estimated_cost_usd=0.04,
        maximum_cost_usd=0.1,
        median_latency_seconds=20,
        maximum_median_latency_seconds=25,
        pilot_gate_passed=False,
        results=(),
        limitations=(),
    )

    audit = audit_phase4_gates(preflight, dry_run, pilot)

    assert audit.phase_complete
    assert not audit.multi_agent_promoted
    assert audit.default_workflow == "phase3_single_coordinator"
    assert audit.failed_count == 1
    assert audit.skipped_count == 2
    assert audit.gates[-1].state is Phase4GateState.SKIPPED
