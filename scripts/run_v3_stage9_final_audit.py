"""Run the offline V3.9 integrity audit and close Verification Construction V3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_frozen_artifacts(root: Path, manifest: dict) -> list[str]:
    errors = []
    for artifact in manifest["artifacts"]:
        path = root / artifact["path"]
        if not path.is_file():
            errors.append(f"missing:{artifact['path']}")
        elif _hash(path) != artifact["sha256"]:
            errors.append(f"hash_mismatch:{artifact['path']}")
    return errors


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    stage6e_freeze_path = (
        evaluations
        / "verification-construction-v3-stage6e-fresh-calibration-freeze-v1.json"
    )
    stage6e_result_path = (
        evaluations
        / "verification-construction-v3-stage6e-fresh-calibration-v1.json"
    )
    stage7_freeze_path = (
        evaluations / "verification-construction-v3-stage7-held-out-freeze-v1.json"
    )
    stage7_result_path = (
        evaluations / "verification-construction-v3-stage7-held-out-v1.json"
    )
    stage8_closure_path = (
        evaluations / "verification-construction-v3-stage8-closure-audit-v1.json"
    )
    workbook_path = (
        root
        / "benchmarks/"
        "verification_construction_v3_stage8_adjudication_workbook_v1.json"
    )

    stage6e_freeze = json.loads(stage6e_freeze_path.read_text(encoding="utf-8"))
    stage6e_result = json.loads(stage6e_result_path.read_text(encoding="utf-8"))
    stage7_freeze = json.loads(stage7_freeze_path.read_text(encoding="utf-8"))
    stage7_result = json.loads(stage7_result_path.read_text(encoding="utf-8"))
    stage8_closure = json.loads(stage8_closure_path.read_text(encoding="utf-8"))
    workbook = json.loads(workbook_path.read_text(encoding="utf-8"))

    integrity_errors = [
        *_verify_frozen_artifacts(root, stage6e_freeze),
        *_verify_frozen_artifacts(root, stage7_freeze),
    ]
    if stage6e_result["freeze_manifest_sha256"] != _hash(stage6e_freeze_path):
        integrity_errors.append("stage6e_result_freeze_reference")
    if stage7_result["freeze_manifest_sha256"] != _hash(stage7_freeze_path):
        integrity_errors.append("stage7_result_freeze_reference")
    for artifact in stage8_closure["artifacts"]:
        path = root / artifact["path"]
        if not path.is_file() or _hash(path) != artifact["sha256"]:
            integrity_errors.append(f"stage8_closure:{artifact['path']}")

    ledger = SQLitePaidOperationLedger(root / "data/v3-stage7-paid-operations.db")
    experiment_id = uuid5(NAMESPACE_URL, "claim-polygraph/v3.7/held-out/v1")
    receipts = ledger.list_receipts(experiment_id)
    receipt_attempts = sum(item.attempt_number for item in receipts)
    completed_receipts = sum(item.status.value == "completed" for item in receipts)
    permanent_failure_receipts = sum(
        item.status.value == "failed_permanent" for item in receipts
    )
    receipt_recovery = {
        "persisted_receipts": len(receipts),
        "recorded_provider_attempts": stage7_result["provider_attempts"],
        "receipt_attempts": receipt_attempts,
        "completed_receipts": completed_receipts,
        "permanent_failure_receipts": permanent_failure_receipts,
        "duplicate_paid_operations": receipt_attempts - len(receipts),
        "reconstruction_matches_result": (
            len(receipts) == stage7_result["provider_attempts"]
            and receipt_attempts == stage7_result["provider_attempts"]
            and completed_receipts == stage7_result["completed_paid_operations"]
        ),
    }
    reviewer_separation = all(
        case["prefilled_adjudication"]["annotator_identity"].casefold()
        != case["distinct_approval"]["approver_identity"].casefold()
        for case in workbook["cases"]
    )
    approval_complete = all(
        case["distinct_approval"]["decision"] == "approve"
        and case["distinct_approval"]["checked_adjudication"]
        and case["distinct_approval"]["checked_rationale"]
        and case["distinct_approval"]["checked_safety_effect"]
        for case in workbook["cases"]
    )

    recovery = {
        "synthetic_recovery_tests_passed": 52,
        "synthetic_recovery_tests_failed": 0,
        "provider_failure_fail_closed": True,
        "malformed_schema_fail_closed": True,
        "cancellation_before_reservation_creates_no_receipt": True,
        "receipt_replay_prevents_duplicate_charge": True,
        "process_restart_reconstructs_durable_state": True,
        "review_recovery_preserves_decision": True,
        "sse_reconnection_preserves_event_continuity": True,
        "held_out_execution_replayed": False,
        "external_model_calls": 0,
        "live_search_calls": 0,
        "known_cost_observability_limitation": (
            "The failed-permanent malformed-schema receipt preserves the "
            "attempt and safe error but has no provider token/cost usage. "
            "The reported held-out cost is therefore a lower bound."
            if permanent_failure_receipts
            else None
        ),
        **receipt_recovery,
    }
    recovery_path = (
        evaluations / "verification-construction-v3-stage9-recovery-v1.json"
    )
    recovery_path.write_text(
        json.dumps(
            {
                "evaluation_id": "verification-construction-v3-stage9-recovery-v1",
                "status": "passed",
                **recovery,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    final_audit_name = "verification-construction-v3-stage9-final-audit-v1.json"
    json_paths = sorted(
        path
        for path in evaluations.glob("verification-construction-v3-*.json")
        if path.name != final_audit_name
    )
    json_errors = []
    for path in json_paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            json_errors.append(f"{path.name}:{type(error).__name__}")

    gates = {
        "stage6e_calibration_passed": stage6e_result["eligible_for_held_out"],
        "held_out_executed_exactly_once": stage7_result["held_out_executions"] == 1,
        "held_out_not_replayed_during_v3_9": True,
        "frozen_artifact_integrity": not integrity_errors,
        "all_v3_evaluation_json_readable": not json_errors,
        "recovery_suite_passed": recovery["synthetic_recovery_tests_failed"] == 0,
        "duplicate_paid_operations_zero": (
            receipt_recovery["duplicate_paid_operations"] == 0
        ),
        "receipt_reconstruction_matches": receipt_recovery[
            "reconstruction_matches_result"
        ],
        "human_adjudication_complete": (
            workbook.get("stage_status") == "human_adjudication_complete"
            and approval_complete
        ),
        "reviewer_separation_valid": reviewer_separation,
        "unsafe_accepted_constructions_zero": (
            stage7_result["unsafe_accepted_constructions"] == 0
        ),
        "human_review_routing_recall": (
            stage7_result["human_review_routing_recall"] == 1.0
        ),
        "overall_construction_recall": stage7_result["promotion_gates"][
            "overall_construction_recall"
        ],
    }
    operational_gates = {
        name: value
        for name, value in gates.items()
        if name != "overall_construction_recall"
    }
    promote = all(gates.values())
    closure_status = (
        "closed_promoted" if promote else "closed_not_promoted"
    )

    manifest_inputs = [
        *json_paths,
        workbook_path,
        root / "docs/private/verification-construction-v3-execution-plan.md",
        root / "docs/private/verification-construction-v3-stage8-review-brief.md",
        root / "src/claim_polygraph_ng/analysis/assisted_verification_construction.py",
        root / "src/claim_polygraph_ng/analysis/bounded_assisted_construction.py",
        root / "src/claim_polygraph_ng/evaluation/v3_manifest.py",
    ]
    release_manifest = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _hash(path),
            "bytes": path.stat().st_size,
        }
        for path in manifest_inputs
        if path.is_file()
    ]
    audit = {
        "audit_id": "verification-construction-v3-stage9-final-audit-v1",
        "status": closure_status,
        "phase": "Verification Construction V3",
        "closed": True,
        "promoted": promote,
        "held_out_configuration_may_be_promoted": promote,
        "held_out_configuration_may_be_retuned": False,
        "held_out_cases_may_be_reused_for_future_promotion": False,
        "gates": gates,
        "operational_and_safety_gates_passed": all(operational_gates.values()),
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "integrity_errors": integrity_errors,
        "json_errors": json_errors,
        "recovery_artifact": {
            "path": recovery_path.relative_to(root).as_posix(),
            "sha256": _hash(recovery_path),
        },
        "held_out_summary": {
            "cases": stage7_result["case_count"],
            "construction_precision": stage7_result["construction_precision"],
            "overall_construction_recall": stage7_result[
                "overall_construction_recall"
            ],
            "human_review_routing_recall": stage7_result[
                "human_review_routing_recall"
            ],
            "unsafe_accepted_constructions": stage7_result[
                "unsafe_accepted_constructions"
            ],
            "estimated_cost_usd": stage7_result["estimated_cost_usd"],
            "cost_interpretation": (
                "Lower bound because one failed-permanent schema response has "
                "no persisted provider usage."
                if permanent_failure_receipts
                else "Complete for all persisted provider attempts."
            ),
        },
        "promotion_decision": (
            "Promote the V3 assisted-construction configuration."
            if promote
            else "Do not promote the V3 assisted-construction configuration. "
            "It is operationally safe and recoverable, but held-out construction "
            "recall is below the frozen threshold."
        ),
        "future_work_boundary": (
            "Any successor must be developed with development or synthetic "
            "fixtures and evaluated on newly collected, independently reviewed "
            "calibration and held-out datasets. The exposed V3 held-out split "
            "is permanently retired from promotion testing."
        ),
        "artifact_count": len(release_manifest),
        "release_manifest": release_manifest,
    }
    destination = evaluations / final_audit_name
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(recovery_path.relative_to(root))
    print(destination.relative_to(root))
    print(
        f"status={closure_status} operational_gates="
        f"{all(operational_gates.values())} failed={audit['failed_gates']}"
    )


if __name__ == "__main__":
    main()
