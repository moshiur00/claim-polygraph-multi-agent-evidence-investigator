"""Audit the immutable V4.7 paid development result without model calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    result_path = evaluations / "verification-construction-v4-stage7-development-v1.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    ledger = SQLitePaidOperationLedger(root / "data/v4-stage7-paid-operations.db")
    experiment_id = uuid5(NAMESPACE_URL, "claim-polygraph/v4.7/development/v1")
    receipts = ledger.list_receipts(experiment_id)

    positive_results = [item for item in result["results"] if item["gold_positive"]]
    eligible_positive = [
        item for item in positive_results if item["disposition"] != "human_review_ineligible"
    ]
    false_exclusions = [
        item["case_id"]
        for item in positive_results
        if item["disposition"] == "human_review_ineligible"
    ]
    safe_failures = [
        item for item in result["results"] if item["disposition"] == "human_review_safe_failure"
    ]
    eligibility_recall = len(eligible_positive) / len(positive_results)
    failed_receipts = [item for item in receipts if item.status.value == "failed"]
    failed_cost_observable = all(
        item.usage_disposition.value != "unknown" or item.estimated_cost_upper_bound_usd is not None
        for item in failed_receipts
    )
    gates = {
        "development_call_limit": result["provider_attempts"] <= 18,
        "unsafe_accepted_constructions_zero": result["unsafe_accepted_constructions"] == 0,
        "construction_precision": result["construction_precision"] == 1.0,
        "constructible_eligibility_recall": eligibility_recall >= 1.0,
        "overall_construction_recall": result["construction_recall"] >= 1.0,
        "human_review_routing_recall": result["human_review_routing_recall"] >= 1.0,
        "duplicate_paid_operations_zero": result["duplicate_paid_operations"] == 0,
        "failed_response_cost_observability": failed_cost_observable,
        "calibration_remained_sealed": result["calibration_cases_loaded"] == 0,
        "held_out_remained_sealed": result["held_out_cases_loaded"] == 0,
    }
    audit = {
        "audit_id": "verification-construction-v4-stage7-development-audit-v1",
        "status": "passed" if all(gates.values()) else "failed_safe",
        "exit_criterion_met": all(gates.values()),
        "promotion_authorized": all(gates.values()),
        "result_sha256": _hash(result_path),
        "metrics": {
            "cases": result["case_count"],
            "positive_gold_cases": len(positive_results),
            "constructible_eligibility_recall": eligibility_recall,
            "construction_precision": result["construction_precision"],
            "construction_recall": result["construction_recall"],
            "human_review_routing_recall": result["human_review_routing_recall"],
            "unsafe_accepted_constructions": result["unsafe_accepted_constructions"],
            "provider_attempts": result["provider_attempts"],
            "completed_paid_operations": result["completed_paid_operations"],
            "failed_paid_operations": result["failed_paid_operations"],
            "duplicate_paid_operations": result["duplicate_paid_operations"],
            "estimated_cost_usd": result["estimated_cost_usd"],
            "development_calls_remaining": result["development_calls_remaining"],
        },
        "false_eligibility_exclusion_case_ids": false_exclusions,
        "safe_failure_case_ids": [item["case_id"] for item in safe_failures],
        "gates": gates,
        "dataset_exposure": {
            "development_cases": result["case_count"],
            "calibration_cases": 0,
            "held_out_cases": 0,
        },
        "next_stage": (
            "V4.8 fresh calibration collection"
            if all(gates.values())
            else "V4.7b development-result remediation"
        ),
        "remediation_scope": (
            "Align V4 candidate routing with assisted eligibility; repair scalar and "
            "temporal evidence binding; normalize nullable tolerance; use only "
            "development results and synthetic fixtures; do not rerun V4.7."
        ),
    }
    destination = evaluations / "verification-construction-v4-stage7-development-audit-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} eligibility_recall={eligibility_recall:.4f} "
        f"construction_recall={result['construction_recall']:.4f}"
    )


if __name__ == "__main__":
    main()
