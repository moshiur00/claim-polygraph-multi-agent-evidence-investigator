"""Audit V3.6a replacement integrity and decide whether held-out may open."""

import hashlib
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).parents[1]
    freeze_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6a-replacement-calibration-freeze-v1.json"
    )
    result_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6a-replacement-calibration-v1.json"
    )
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    for artifact in freeze["artifacts"]:
        if hashlib.sha256((root / artifact["path"]).read_bytes()).hexdigest() != artifact[
            "sha256"
        ]:
            raise ValueError(f"frozen artifact changed: {artifact['path']}")
    if result["freeze_manifest_sha256"] != hashlib.sha256(
        freeze_path.read_bytes()
    ).hexdigest():
        raise ValueError("result does not reference the frozen replacement manifest")
    if result["calibration_executions"] != 1:
        raise ValueError("replacement calibration execution count is not one")
    if (
        result["original_held_out_cases_loaded"]
        or result["original_held_out_cases_exposed_to_model"]
    ):
        raise ValueError("original held-out data crossed the V3.6a boundary")
    failed = [
        name for name, passed in result["promotion_gates"].items() if not passed
    ]
    eligible = not failed
    audit = {
        "audit_id": (
            "verification-construction-v3-stage6a-replacement-calibration-audit-v1"
        ),
        "status": "passed_promoted" if eligible else "passed_not_promoted",
        "freeze_integrity": True,
        "calibration_executions": 1,
        "configuration_changed_after_freeze": False,
        "thresholds_changed_after_results": False,
        "provider_attempts": result["provider_attempts"],
        "estimated_cost_usd": result["estimated_cost_usd"],
        "construction_precision": result["construction_precision"],
        "overall_construction_recall": result["overall_construction_recall"],
        "incremental_recall_gain": result["incremental_recall_gain"],
        "human_review_routing_recall": result["human_review_routing_recall"],
        "unsafe_accepted_constructions": result[
            "unsafe_accepted_constructions"
        ],
        "failed_gates": failed,
        "eligible_for_original_held_out": eligible,
        "original_held_out_cases_loaded": 0,
        "original_held_out_cases_exposed_to_model": 0,
        "decision": (
            "The replacement calibration passed every frozen gate. The original "
            "held-out split may now be opened exactly once."
            if eligible
            else "Keep the original held-out split sealed. The replacement "
            "calibration did not pass every frozen promotion gate."
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
        "verification-construction-v3-stage6a-replacement-calibration-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(f"eligible_for_original_held_out={eligible} failed_gates={len(failed)}")


if __name__ == "__main__":
    main()
