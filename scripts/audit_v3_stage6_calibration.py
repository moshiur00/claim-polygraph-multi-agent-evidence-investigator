"""Audit V3.6 freeze integrity and the one-time calibration decision."""

import hashlib
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).parents[1]
    freeze_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6-calibration-freeze-v1.json"
    )
    result_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6-calibration-v1.json"
    )
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    for artifact in freeze["artifacts"]:
        actual = hashlib.sha256((root / artifact["path"]).read_bytes()).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"post-calibration frozen artifact changed: {artifact['path']}")
    expected_freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    if result["freeze_manifest_sha256"] != expected_freeze_hash:
        raise ValueError("calibration result references a different freeze")
    if result["configuration_changed_after_freeze"]:
        raise ValueError("configuration changed during calibration")
    if result["thresholds_changed_after_results"]:
        raise ValueError("thresholds changed after calibration")
    if result["held_out_cases_loaded"] or result["held_out_cases_exposed_to_model"]:
        raise ValueError("held-out data crossed the V3.6 boundary")
    if result["eligible_for_held_out"]:
        raise ValueError("failed calibration was incorrectly promoted")

    audit = {
        "audit_id": "verification-construction-v3-stage6-calibration-audit-v1",
        "status": "passed_not_promoted",
        "freeze_integrity": True,
        "configuration_changed_after_freeze": False,
        "thresholds_changed_after_results": False,
        "calibration_executions": 1,
        "provider_attempts": result["provider_attempts"],
        "completed_paid_operations": result["completed_paid_operations"],
        "estimated_cost_usd": result["estimated_cost_usd"],
        "unsafe_accepted_constructions": result["unsafe_accepted_constructions"],
        "human_review_routing_recall": result["human_review_routing_recall"],
        "overall_construction_recall": result["overall_construction_recall"],
        "fallback_recall_gain": result["fallback_recall_gain"],
        "eligible_for_held_out": False,
        "held_out_cases_loaded": 0,
        "held_out_cases_exposed_to_model": 0,
        "failed_gates": [
            name for name, passed in result["promotion_gates"].items() if not passed
        ],
        "decision": (
            "Do not execute V3.7 held-out evaluation with this configuration. "
            "The frozen eligibility preflight is safe but materially under-covers "
            "the reviewed numerical and temporal construction space."
        ),
        "artifacts": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in (freeze_path, result_path)
        ],
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6-calibration-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=passed_not_promoted held_out=false provider_attempts=0")


if __name__ == "__main__":
    main()
