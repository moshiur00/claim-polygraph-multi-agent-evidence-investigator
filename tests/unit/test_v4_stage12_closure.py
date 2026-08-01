import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
EVALUATIONS = ROOT / "artifacts/evaluations"


def _read(name: str) -> dict:
    return json.loads((EVALUATIONS / name).read_text(encoding="utf-8"))


def test_v4_stage12_failure_adjudication_is_fail_closed() -> None:
    audit = _read(
        "verification-construction-v4-stage12-failure-adjudication-v1.json"
    )
    assert audit["status"] == "passed"
    assert {item["case_id"] for item in audit["records"]} == {
        "V3-366",
        "V3-368",
        "V3-373",
    }
    assert all(
        item["safety_effect"] == "failed_closed_to_human_review"
        and not item["unsafe_construction_accepted"]
        for item in audit["records"]
    )
    assert audit["model_calls"] == 0
    assert audit["held_out_replays"] == 0


def test_v4_stage12_recovery_reuses_every_receipt() -> None:
    audit = _read("verification-construction-v4-stage12-recovery-audit-v1.json")
    assert audit["status"] == "passed"
    assert audit["persisted_receipts"] == 18
    assert audit["cached_resume_decisions"] == 18
    assert audit["verified_durable_results"] == 18
    assert audit["duplicate_paid_operations"] == 0
    assert audit["provider_calls"] == 0
    assert audit["held_out_replays"] == 0


def test_v4_stage12_is_closed_and_promoted_after_adr_approval() -> None:
    audit = _read("verification-construction-v4-stage12-final-audit-v1.json")
    assert audit["status"] == "closed_promoted"
    assert audit["engineering_closed"]
    assert audit["promotion_recommended"]
    assert not audit["promotion_pending_explicit_adr_approval"]
    assert audit["promoted"]
    assert audit["promotion_approval"]["adr"] == "0024"
    assert audit["gates"]["adr_0024_accepted"]
    assert not audit["failed_gates"]
    assert not audit["integrity_errors"]
    assert not audit["json_errors"]
    assert all(audit["gates"].values())
    assert audit["held_out_summary"]["construction_precision"] == 1.0
    assert audit["held_out_summary"]["construction_recall"] >= 0.75
    assert audit["held_out_summary"]["human_review_routing_recall"] == 1.0
    assert not audit["held_out_configuration_may_be_retuned"]
    assert not audit["held_out_cases_may_be_reused_for_future_promotion"]
