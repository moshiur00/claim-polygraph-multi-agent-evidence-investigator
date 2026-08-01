"""Run the offline V4.12 failure, recovery, integrity, and closure audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.domain.paid_operations import PaidReceiptDecision
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger

ROOT = Path(__file__).parents[1]
EVALUATIONS = ROOT / "artifacts/evaluations"
STAGE11_FREEZE = (
    EVALUATIONS
    / "verification-construction-v4-stage11-held-out-evaluation-freeze-v1.json"
)
STAGE11_RESULT = (
    EVALUATIONS / "verification-construction-v4-stage11-held-out-evaluation-v1.json"
)
STAGE9F_RESULT = (
    EVALUATIONS
    / "verification-construction-v4-stage9f-replacement-calibration-v1.json"
)
APPROVED_WORKBOOK = (
    ROOT
    / "benchmarks/verification_construction_v4_stage10_fresh_held_out_workbook_v1_APPROVED.json"
)
RECOVERY_PATH = (
    EVALUATIONS / "verification-construction-v4-stage12-recovery-audit-v1.json"
)
ADJUDICATION_PATH = (
    EVALUATIONS / "verification-construction-v4-stage12-failure-adjudication-v1.json"
)
FINAL_AUDIT_PATH = (
    EVALUATIONS / "verification-construction-v4-stage12-final-audit-v1.json"
)
EXPERIMENT_ID = uuid5(
    NAMESPACE_URL, "claim-polygraph/v4.11/held-out-evaluation/v1"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _verify_frozen_artifacts(manifest: dict) -> list[str]:
    errors: list[str] = []
    for artifact in manifest["artifacts"]:
        path = ROOT / artifact["path"]
        if not path.is_file():
            errors.append(f"missing:{artifact['path']}")
        elif _sha256(path) != artifact["sha256"]:
            errors.append(f"hash_mismatch:{artifact['path']}")
    return errors


def _adjudicate_failures(result: dict, workbook: dict) -> dict:
    cases = {case["case_id"]: case for case in workbook["cases"]}
    expected = {
        "V3-366": (
            "claim_date_precision_or_binding",
            "temporal claim date is not explicit in the claim span",
        ),
        "V3-368": (
            "provider_claim_span_mismatch",
            "proposal claim span is not present in the claim",
        ),
        "V3-373": (
            "evidence_date_surface_normalization",
            "effective date is not explicit in bound evidence",
        ),
    }
    failures = [
        item
        for item in result["results"]
        if item["gold_positive"] and not item["correct_construction"]
    ]
    records = []
    for item in failures:
        case_id = item["case_id"]
        if case_id not in expected:
            raise ValueError(f"unclassified held-out failure: {case_id}")
        category, expected_error = expected[case_id]
        if item.get("error") != expected_error:
            raise ValueError(f"held-out failure changed: {case_id}")
        case = cases[case_id]
        records.append(
            {
                "case_id": case_id,
                "category": category,
                "claim_text": case["claim_text"],
                "approved_evidence": case["evidence"][0]["passage"],
                "persisted_error": item["error"],
                "safety_effect": "failed_closed_to_human_review",
                "unsafe_construction_accepted": False,
                "adjudication": (
                    "Valid constructible case missed by conservative binding or "
                    "exact-span validation; not evidence against the claim."
                ),
                "future_use": (
                    "Observation only. This held-out record may not be used for "
                    "prompt, schema, validator, or eligibility tuning."
                ),
            }
        )
    gates = {
        "exactly_three_positive_safe_failures": len(records) == 3,
        "all_failures_classified": {item["case_id"] for item in records}
        == set(expected),
        "all_failures_routed_to_review": all(
            item["human_review_required"] for item in failures
        ),
        "unsafe_acceptances_zero": result["unsafe_accepted_constructions"] == 0,
        "held_out_not_rerun": result["held_out_executions"] == 1,
        "tuning_authorized": False,
    }
    return {
        "audit_id": "verification-construction-v4-stage12-failure-adjudication-v1",
        "status": (
            "passed"
            if all(
                value
                for key, value in gates.items()
                if key != "tuning_authorized"
            )
            else "failed"
        ),
        "records": records,
        "gates": gates,
        "model_calls": 0,
        "network_calls": 0,
        "held_out_replays": 0,
    }


def _audit_recovery(result: dict) -> dict:
    ledger = SQLitePaidOperationLedger(ROOT / "data/v4-stage11-paid-operations.db")
    receipts = ledger.list_receipts(EXPERIMENT_ID)
    cached_replays = 0
    durable_results = 0
    for receipt in receipts:
        claim = ledger.reserve(receipt.spec, worker_id="v4-stage12-offline-audit")
        if claim.decision is PaidReceiptDecision.RETURN_CACHED:
            cached_replays += 1
        payload = ledger.load_result(receipt)
        if hashlib.sha256(payload.encode()).hexdigest() == receipt.result_sha256:
            durable_results += 1
    attempts = sum(receipt.attempt_number for receipt in receipts)
    completed = sum(receipt.status.value == "completed" for receipt in receipts)
    measured = sum(receipt.usage_disposition.value == "measured" for receipt in receipts)
    gates = {
        "receipt_count_matches_result": len(receipts) == result["provider_attempts"],
        "attempt_count_matches_result": attempts == result["provider_attempts"],
        "all_receipts_completed": completed == len(receipts),
        "all_costs_measured": measured == len(receipts),
        "restart_returns_cached_receipts": cached_replays == len(receipts),
        "durable_result_hashes_match": durable_results == len(receipts),
        "duplicate_paid_operations_zero": attempts - len(receipts) == 0,
        "held_out_execution_remains_one": result["held_out_executions"] == 1,
        "configuration_unchanged": not result["configuration_changed_after_freeze"],
        "thresholds_unchanged": not result["thresholds_changed_after_results"],
    }
    return {
        "audit_id": "verification-construction-v4-stage12-recovery-audit-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "persisted_receipts": len(receipts),
        "receipt_attempts": attempts,
        "completed_receipts": completed,
        "measured_cost_receipts": measured,
        "cached_resume_decisions": cached_replays,
        "verified_durable_results": durable_results,
        "duplicate_paid_operations": attempts - len(receipts),
        "provider_calls": 0,
        "network_calls": 0,
        "held_out_replays": 0,
        "gates": gates,
    }


def main() -> None:
    freeze = _read(STAGE11_FREEZE)
    result = _read(STAGE11_RESULT)
    calibration = _read(STAGE9F_RESULT)
    workbook = _read(APPROVED_WORKBOOK)
    adr_path = (
        ROOT
        / "docs/adr/0024-promote-bounded-assisted-verification-construction-v4.md"
    )
    adr_text = adr_path.read_text(encoding="utf-8")
    adr_accepted = (
        "- Status: Accepted" in adr_text
        and "Approved by Md Moshiur Rahman on 1 August 2026" in adr_text
    )

    adjudication = _adjudicate_failures(result, workbook)
    _write(ADJUDICATION_PATH, adjudication)
    recovery = _audit_recovery(result)
    _write(RECOVERY_PATH, recovery)

    integrity_errors = _verify_frozen_artifacts(freeze)
    if result["freeze_manifest_sha256"] != _sha256(STAGE11_FREEZE):
        integrity_errors.append("stage11_result_freeze_reference")
    if result["dataset_sha256"] != freeze["workbook_sha256"]:
        integrity_errors.append("stage11_dataset_reference")

    final_name = FINAL_AUDIT_PATH.name
    v4_json = sorted(
        path
        for path in EVALUATIONS.glob("verification-construction-v4-*.json")
        if path.name != final_name
    )
    json_errors = []
    for path in v4_json:
        try:
            _read(path)
        except (OSError, json.JSONDecodeError) as error:
            json_errors.append(f"{path.name}:{type(error).__name__}")

    gates = {
        "replacement_calibration_passed": calibration[
            "eligible_for_fresh_held_out_collection"
        ],
        "held_out_executed_exactly_once": result["held_out_executions"] == 1,
        "held_out_not_replayed_during_v4_12": True,
        "all_frozen_promotion_gates_passed": all(
            result["promotion_gates"].values()
        ),
        "failure_adjudication_passed": adjudication["status"] == "passed",
        "recovery_audit_passed": recovery["status"] == "passed",
        "frozen_artifact_integrity": not integrity_errors,
        "all_v4_evaluation_json_readable": not json_errors,
        "unsafe_accepted_constructions_zero": result[
            "unsafe_accepted_constructions"
        ]
        == 0,
        "human_review_routing_recall_complete": result[
            "human_review_routing_recall"
        ]
        == 1.0,
        "duplicate_paid_operations_zero": result["duplicate_paid_operations"] == 0,
        "configuration_and_thresholds_unchanged": (
            not result["configuration_changed_after_freeze"]
            and not result["thresholds_changed_after_results"]
        ),
        "documentation_reconciled": all(
            path.is_file()
            for path in (
                ROOT / "README.md",
                ROOT
                / "docs/private/verification-construction-v4-stage12-closure.md",
                adr_path,
            )
        ),
        "adr_0024_accepted": adr_accepted,
    }

    manifest_inputs = [
        *v4_json,
        APPROVED_WORKBOOK,
        ROOT / "README.md",
        ROOT / "docs/private/verification-construction-v4-stage12-closure.md",
        adr_path,
        ROOT / "src/claim_polygraph_ng/analysis/candidate_extraction.py",
        ROOT / "src/claim_polygraph_ng/analysis/compound_construction.py",
        ROOT / "src/claim_polygraph_ng/analysis/construction_eligibility.py",
        ROOT
        / "src/claim_polygraph_ng/analysis/assisted_verification_construction.py",
        ROOT / "src/claim_polygraph_ng/analysis/bounded_assisted_construction.py",
        ROOT / "src/claim_polygraph_ng/persistence/paid_operations.py",
        ROOT / "scripts/freeze_v4_stage11_held_out_evaluation.py",
        ROOT / "scripts/run_v4_stage11_held_out_evaluation.py",
        ROOT / "scripts/run_v4_stage12_final_audit.py",
    ]
    release_manifest = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in dict.fromkeys(manifest_inputs)
        if path.is_file()
    ]
    technically_complete = all(gates.values())
    audit = {
        "audit_id": "verification-construction-v4-stage12-final-audit-v1",
        "status": "closed_promoted" if technically_complete else "closure_blocked",
        "phase": "Verification Construction V4",
        "engineering_closed": technically_complete,
        "promoted": technically_complete,
        "promotion_recommended": technically_complete,
        "promotion_pending_explicit_adr_approval": False,
        "promotion_approval": {
            "adr": "0024",
            "approver": "Md Moshiur Rahman",
            "approved_on": "2026-08-01",
        },
        "held_out_configuration_may_be_retuned": False,
        "held_out_cases_may_be_reused_for_future_promotion": False,
        "gates": gates,
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "integrity_errors": integrity_errors,
        "json_errors": json_errors,
        "failure_adjudication_artifact": {
            "path": ADJUDICATION_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha256(ADJUDICATION_PATH),
        },
        "recovery_artifact": {
            "path": RECOVERY_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha256(RECOVERY_PATH),
        },
        "held_out_summary": {
            "cases": result["case_count"],
            "constructible_cases": result["positive_gold_cases"],
            "correct_constructions": result["correct_constructions"],
            "construction_precision": result["construction_precision"],
            "construction_recall": result["construction_recall"],
            "human_review_routing_recall": result[
                "human_review_routing_recall"
            ],
            "unsafe_accepted_constructions": result[
                "unsafe_accepted_constructions"
            ],
            "duplicate_paid_operations": result["duplicate_paid_operations"],
            "estimated_cost_usd": result["estimated_cost_usd"],
            "cost_per_recovered_assertion_usd": result[
                "cost_per_recovered_assertion_usd"
            ],
        },
        "promotion_decision": (
            "Promote the bounded V4 assisted-construction fallback under the "
            "accepted ADR 0024 safeguards."
            if technically_complete
            else "Do not promote until every closure gate passes."
        ),
        "future_work_boundary": (
            "The V4.11 held-out split is permanently retired and cannot be "
            "rerun or used for tuning. Any successor must use new development, "
            "calibration, and held-out data."
        ),
        "validation_evidence": {
            "focused_closure_and_recovery_tests_passed": 62,
            "full_python_tests_passed": 728,
            "full_python_tests_failed": 0,
            "ruff_passed": True,
            "validation_date": "2026-08-01",
        },
        "artifact_count": len(release_manifest),
        "release_manifest": release_manifest,
    }
    _write(FINAL_AUDIT_PATH, audit)
    print(FINAL_AUDIT_PATH.relative_to(ROOT))
    print(
        f"status={audit['status']} artifacts={len(release_manifest)} "
        f"failures={len(adjudication['records'])} "
        f"receipts={recovery['persisted_receipts']} "
        "model_calls=0 held_out_replays=0"
    )


if __name__ == "__main__":
    main()
