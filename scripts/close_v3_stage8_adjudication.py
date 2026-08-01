"""Record distinct approval and close the V3.8 adjudication gate."""

import hashlib
import json
from pathlib import Path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    workbook_path = (
        root
        / "benchmarks/"
        "verification_construction_v3_stage8_adjudication_workbook_v1.json"
    )
    result_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage7-held-out-v1.json"
    )
    eligibility_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage8-eligibility-analysis-v1.json"
    )
    ablation_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage8-ablation-v1.json"
    )
    workbook = json.loads(workbook_path.read_text(encoding="utf-8"))
    if workbook.get("annotation_status") != "complete":
        raise ValueError("V3.8 annotation is incomplete")
    if len(workbook["cases"]) != 7:
        raise ValueError("V3.8 requires exactly seven adjudication records")

    for case in workbook["cases"]:
        review = case["prefilled_adjudication"]
        approval = case["distinct_approval"]
        if review["annotator_identity"] != "Md Moshiur Rahman":
            raise ValueError("unexpected annotator identity")
        if approval["approver_identity"] != "Md Rashedul Islam":
            raise ValueError("unexpected distinct approver identity")
        if review["annotator_identity"].casefold() == approval[
            "approver_identity"
        ].casefold():
            raise ValueError("annotator and approver must be distinct")
        approval.update(
            {
                "approved_on": "2026-07-31",
                "decision": "approve",
                "checked_adjudication": True,
                "checked_rationale": True,
                "checked_safety_effect": True,
            }
        )
    workbook["distinct_approval_status"] = "complete"
    workbook["stage_status"] = "human_adjudication_complete"
    workbook_path.write_text(
        json.dumps(workbook, indent=2) + "\n", encoding="utf-8"
    )

    for case in workbook["cases"]:
        review = case["prefilled_adjudication"]
        approval = case["distinct_approval"]
        if review.get("review_status") != "reviewed_and_accepted":
            raise ValueError(f"{case['case_id']}: annotation was not accepted")
        if not all(
            review[key]
            for key in (
                "checked_claim_span",
                "checked_evidence_bindings",
                "checked_material_operands",
                "checked_expected_state_compatibility",
                "checked_fail_closed_behavior",
            )
        ):
            raise ValueError(f"{case['case_id']}: annotation checks incomplete")
        if approval["decision"] != "approve" or not all(
            approval[key]
            for key in (
                "checked_adjudication",
                "checked_rationale",
                "checked_safety_effect",
            )
        ):
            raise ValueError(f"{case['case_id']}: approval checks incomplete")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    audit = {
        "audit_id": "verification-construction-v3-stage8-closure-audit-v1",
        "status": "complete_not_promoted",
        "adjudicated_attempts": 7,
        "annotator_identity": "Md Moshiur Rahman",
        "distinct_approver_identity": "Md Rashedul Islam",
        "annotation_date": "2026-07-31",
        "approval_date": "2026-07-31",
        "reviewer_separation_valid": True,
        "annotation_checklists_complete": True,
        "approval_checklists_complete": True,
        "model_calls": 0,
        "held_out_reruns": 0,
        "held_out_result_unchanged": True,
        "adjudication_decisions": {
            decision: sum(
                case["prefilled_adjudication"]["decision"] == decision
                for case in workbook["cases"]
            )
            for decision in (
                "accept",
                "revise",
                "reject_unsafe",
                "confirm_safe_failure",
            )
        },
        "held_out_metrics": {
            "construction_precision": result["construction_precision"],
            "overall_construction_recall": result["overall_construction_recall"],
            "human_review_routing_recall": result[
                "human_review_routing_recall"
            ],
            "unsafe_accepted_constructions": result[
                "unsafe_accepted_constructions"
            ],
            "failed_promotion_gates": [
                name
                for name, passed in result["promotion_gates"].items()
                if not passed
            ],
        },
        "decision": (
            "V3.8 human adjudication is complete. The evaluated configuration "
            "remains not promoted because held-out overall construction recall "
            "did not meet the frozen threshold. Preserve the result and proceed "
            "to recovery and final experiment audit without held-out retuning."
        ),
        "artifacts": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _hash(path),
            }
            for path in (
                workbook_path,
                result_path,
                eligibility_path,
                ablation_path,
            )
        ],
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage8-closure-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(workbook_path.relative_to(root))
    print(destination.relative_to(root))
    print("status=complete_not_promoted approvals=7 held_out_reruns=0")


if __name__ == "__main__":
    main()
