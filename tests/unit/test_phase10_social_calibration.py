"""Stage 10.8 adversarial replay and honest human-calibration gate."""

import json
from pathlib import Path

import claim_polygraph_ng.evaluation.phase10_social_calibration as calibration
from claim_polygraph_ng.evaluation.phase10_social_calibration import (
    build_phase10_social_calibration_audit,
    verify_phase10_social_calibration_audit,
)


def test_adversarial_social_benchmark_meets_every_machine_safety_gate() -> None:
    root = Path(__file__).parents[2]

    audit = build_phase10_social_calibration_audit(root)

    assert audit.case_count == 12
    assert audit.category_count == 6
    assert audit.exact_eligibility_count == audit.case_count
    assert audit.eligibility_precision == 1
    assert audit.unsafe_case_count > 0
    assert audit.unsafe_publication_count == 0
    assert audit.unsafe_publication_rate == 0
    assert audit.origin_resolution_accuracy == 1
    assert audit.origin_resolution_rate == 1
    assert audit.independence_inflation_case_count == 0
    assert audit.maximum_family_inflation == 0
    assert audit.review_routing_recall == 1
    assert audit.verdict_stability_rate == 1
    assert audit.machine_gate_passed
    assert verify_phase10_social_calibration_audit(audit, root) == ()


def test_human_calibration_is_not_fabricated_or_auto_approved(
    monkeypatch,
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[2]
    packet_path = tmp_path / "pending-human-calibration-packet.json"
    monkeypatch.setattr(calibration, "_REVIEW_PACKET", str(packet_path))

    audit = build_phase10_social_calibration_audit(root)
    packet = json.loads(packet_path.read_text("utf-8"))

    assert audit.human_calibration_status == "pending"
    assert not audit.stage_exit_ready
    assert packet["status"] == "pending"
    assert packet["annotator_identity"] is None
    assert packet["distinct_approver_identity"] is None
    assert packet["cases"]
    assert all(item["review_decision"] is None for item in packet["cases"])
    assert packet["approval"]["decision"] is None


def test_every_required_social_scenario_enters_targeted_review_packet() -> None:
    root = Path(__file__).parents[2]
    build_phase10_social_calibration_audit(root)
    packet = json.loads(
        (
            root
            / "artifacts/reviews/"
            "phase10-stage10.8-human-calibration-packet-v1.json"
        ).read_text("utf-8")
    )

    categories = {item["category"] for item in packet["cases"]}
    assert categories == {
        "official_announcement",
        "eyewitness_post",
        "manipulated_screenshot",
        "repost_cascade",
        "deleted_post",
        "primary_document_link",
    }
