"""Stage 7.7 end-to-end recovery gate tests."""

import asyncio
import json

from claim_polygraph_ng.evaluation.phase7_recovery import (
    evaluate_phase7_recovery,
    export_phase7_recovery,
)


def test_every_recovery_journey_passes_without_duplicate_operations() -> None:
    evaluation = asyncio.run(evaluate_phase7_recovery())

    assert evaluation.all_paths_passed
    assert evaluation.passed_count == 8
    assert evaluation.failed_count == 0
    assert {item.journey_id for item in evaluation.journeys} == {
        "automatic_completion",
        "review_approval",
        "verdict_revision",
        "request_more_evidence",
        "review_rejection",
        "provider_failure",
        "process_restart",
        "idempotent_resume",
    }
    assert all(item.duplicate_operations == 0 for item in evaluation.journeys)
    assert all(item.audit_chain_valid for item in evaluation.journeys)
    assert evaluation.model_calls == evaluation.search_calls == evaluation.network_calls == 0
    assert evaluation.pdf_downloads == 0
    assert evaluation.estimated_cost_usd == 0


def test_recovery_artifact_round_trips(tmp_path) -> None:
    evaluation = asyncio.run(evaluate_phase7_recovery())
    output = export_phase7_recovery(evaluation, tmp_path / "recovery.json")

    assert json.loads(output.read_text(encoding="utf-8")) == evaluation.model_dump(mode="json")
