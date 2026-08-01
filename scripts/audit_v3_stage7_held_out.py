"""Audit the single V3.7 held-out execution and its frozen boundaries."""

import hashlib
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).parents[1]
    freeze_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage7-held-out-freeze-v1.json"
    )
    result_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage7-held-out-v1.json"
    )
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    for artifact in freeze["artifacts"]:
        actual = hashlib.sha256((root / artifact["path"]).read_bytes()).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"frozen artifact changed: {artifact['path']}")
    if result["freeze_manifest_sha256"] != hashlib.sha256(
        freeze_path.read_bytes()
    ).hexdigest():
        raise ValueError("held-out result does not reference its frozen manifest")
    if result["held_out_executions"] != 1:
        raise ValueError("held-out execution count is not exactly one")
    if result["case_count"] != freeze["case_count"]:
        raise ValueError("held-out result case count differs from freeze")
    if result["thresholds_changed_after_results"]:
        raise ValueError("held-out thresholds changed after results")
    failed = [
        name for name, passed in result["promotion_gates"].items() if not passed
    ]
    passed = not failed
    audit = {
        "audit_id": "verification-construction-v3-stage7-held-out-audit-v1",
        "status": "passed" if passed else "passed_not_promoted",
        "freeze_integrity": True,
        "held_out_executions": 1,
        "configuration_changed_after_calibration": False,
        "thresholds_changed_after_results": False,
        "case_count": result["case_count"],
        "provider_attempts": result["provider_attempts"],
        "estimated_cost_usd": result["estimated_cost_usd"],
        "construction_precision": result["construction_precision"],
        "overall_construction_recall": result["overall_construction_recall"],
        "incremental_recall_gain": result["incremental_recall_gain"],
        "human_review_routing_recall": result["human_review_routing_recall"],
        "unsafe_accepted_constructions": result[
            "unsafe_accepted_constructions"
        ],
        "duplicate_paid_operations": result["duplicate_paid_operations"],
        "failed_gates": failed,
        "eligible_for_v3_8_adjudication": passed,
        "decision": (
            "Proceed to V3.8 human adjudication and ablation."
            if passed
            else "Do not promote this configuration; preserve held-out results "
            "and perform failure analysis without retuning on held-out cases."
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
        "verification-construction-v3-stage7-held-out-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(f"status={audit['status']} failed_gates={len(failed)}")


if __name__ == "__main__":
    main()
